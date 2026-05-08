"""VoiceDesk entry point — loads config, starts tray icon, registers hotkey.

Event-loop architecture
-----------------------
* **Main thread** — PyQt6 ``QApplication.exec()`` owns the main thread so the
  overlay and menu widgets work correctly.
* **Tray thread** — pystray runs in its own daemon thread (unchanged).
* **Keyboard thread** — the ``keyboard`` library hooks run in their own thread.
  Hotkey callbacks are fired from that thread; Qt operations are dispatched
  thread-safely via signals or ``QTimer.singleShot``.
* **Audio thread** — recording runs in a dedicated daemon thread.
* **Transcription executor** — a single-worker ``ThreadPoolExecutor`` serialises
  transcription + paste/save jobs.
"""

import concurrent.futures
import logging
import logging.handlers
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time
import winsound

import keyboard
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

import audio
import config_loader
import hotkey as hotkey_module
import menu as menu_module
import overlay as overlay_module
import paste
import transcribe
import tray as tray_module

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "voicedesk.log")


def _setup_logging() -> None:
    if logging.getLogger().handlers:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_audio_thread: threading.Thread | None = None
_audio_path: str | None = None
_config: dict = {}
_tray: tray_module.TrayIcon | None = None
_recording_mode: str = "dictate"   # 'dictate' | 'inbox' | 'inbox_and_paste' | 'inbox_fallback'
_target_hwnd: int | None = None    # foreground HWND captured at dictate record-start

_process_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="transcribe-paste"
)
_pending_future: concurrent.futures.Future | None = None

# Termination state — reset at the start of every recording session.
# One and only one termination path (hotkey release, button click, max-duration)
# may claim the recording; the rest see _terminating=True and return silently.
_termination_lock = threading.Lock()
_terminating: bool = False
_cancel_flag = threading.Event()   # set → discard audio, skip transcription


class _Dispatcher(QObject):
    """QObject that lives on the Qt main thread.

    Emitting ``tap_signal`` from *any* thread delivers the connected slot on
    the main thread because Qt queued-connection dispatch is used automatically
    when the emitter and receiver live in different threads.  This is more
    reliable than ``QTimer.singleShot`` which requires the *calling* thread to
    have a running Qt event loop.
    """

    tap_signal = pyqtSignal()


_dispatcher: _Dispatcher | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_foreground_hwnd() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def _beep(frequency: int, duration_ms: int) -> None:
    threading.Thread(
        target=winsound.Beep, args=(frequency, duration_ms), daemon=True
    ).start()


def _triple_beep() -> None:
    def _do() -> None:
        winsound.Beep(660, 80)
        winsound.Beep(880, 80)
        winsound.Beep(1100, 80)
    threading.Thread(target=_do, daemon=True).start()


# ---------------------------------------------------------------------------
# Recording pipeline
# ---------------------------------------------------------------------------

def _abort_active_recording() -> None:
    """Stop any in-flight recording and discard its output.

    Called at the top of _start_recording so a new activation always supersedes
    a previous one instead of spawning an orphan thread.
    """
    global _audio_thread, _audio_path, _target_hwnd
    if _audio_thread is None or not _audio_thread.is_alive():
        _audio_thread = None
        return
    logger.info("Aborting in-flight recording — superseded by new activation")
    audio.stop_recording()
    _audio_thread.join(timeout=3)
    if _audio_thread.is_alive():
        logger.warning("Audio thread did not exit within 3s after stop signal")
    _audio_thread = None
    if _audio_path:
        try:
            os.remove(_audio_path)
            logger.debug("Discarded orphan audio file: %s", _audio_path)
        except OSError:
            pass
        _audio_path = None
    _target_hwnd = None


def _start_recording() -> None:
    """Begin audio capture.  Safe to call from any thread."""
    global _audio_thread, _audio_path, _pending_future, _target_hwnd

    _abort_active_recording()

    global _terminating
    _terminating = False
    _cancel_flag.clear()

    _audio_path = None

    if _recording_mode == "dictate":
        _target_hwnd = _get_foreground_hwnd() or None
        logger.info("Dictate start — captured target HWND=%s", _target_hwnd)
    else:
        _target_hwnd = None

    if _pending_future is not None and not _pending_future.done():
        if _pending_future.cancel():
            logger.info("Cancelled stale pending transcription job")

    if _tray:
        _tray.set_recording()

    overlay_module.show_recording()
    _beep(880, 120)

    def _record() -> None:
        global _audio_path, _pending_future
        try:
            _audio_path = audio.record_audio(
                max_duration=_config.get("max_duration_seconds", 120),
                device=_config.get("audio_device"),
                volume_cb=overlay_module.update_volume,
            )
            # Max duration reached without an explicit stop.
            if not audio._stop_event.is_set():
                with _termination_lock:
                    if _terminating:
                        return   # button/hotkey already claimed termination
                    _terminating = True
                logger.info("Max duration reached — auto-triggering transcription")
                _beep(440, 120)
                overlay_module.show_transcribing()
                if _tray:
                    _tray.set_idle()
                if _audio_path:
                    path = _audio_path
                    _audio_path = None
                    _pending_future = _process_executor.submit(
                        _process, path, _resolve_effective_mode()
                    )
        except Exception as exc:
            logger.error("Audio recording failed: %s", exc)
            overlay_module.hide_overlay()

    _audio_thread = threading.Thread(target=_record, daemon=True, name="audio-record")
    _audio_thread.start()


def _process(audio_file: str, mode: str, paste_hwnd: int | None = None) -> None:
    """Transcribe and either paste or save to inbox.  Runs in serial executor."""
    try:
        text = transcribe.transcribe(audio_file, _config)
        logger.info("Transcription (%s): %r", mode, text[:80])

        if not text:
            logger.info("Empty transcription — skipping paste")
            _beep(220, 200)  # low single beep = nothing heard
            return

        if mode in ("inbox_and_paste", "inbox_fallback"):
            inbox_path = _config.get(
                "inbox_path",
                os.path.expanduser("~/Documents/inbox"),
            )
            paste.save_to_inbox(text, inbox_path)
            _triple_beep()
            if mode == "inbox_fallback":
                logger.info("Focus-loss fallback: saved to inbox (no paste)")
        elif mode == "inbox":
            inbox_path = _config.get(
                "inbox_path",
                os.path.expanduser("~/Documents/inbox"),
            )
            paste.save_to_inbox(text, inbox_path)
            _beep(660, 80)
            _beep(880, 80)
        else:
            if paste_hwnd:
                # Restore focus to the original target window — the Stop button
                # click shifted foreground away from it.
                ctypes.windll.user32.SetForegroundWindow(paste_hwnd)
            paste.paste_text(text, auto_paste=_config.get("auto_paste", True))
            _beep(660, 80)
            _beep(880, 80)
    except Exception as exc:
        logger.error("Transcription/paste failed: %s", exc)
    finally:
        overlay_module.hide_overlay()
        try:
            os.remove(audio_file)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Hotkey callbacks
# ---------------------------------------------------------------------------

def _on_hold() -> None:
    """Hold threshold reached — start recording immediately in dictate mode."""
    global _recording_mode
    _recording_mode = "dictate"
    _start_recording()


def _on_hold_inbox() -> None:
    """Hold threshold reached on inbox hotkey — transcribe and save to inbox."""
    global _recording_mode
    _recording_mode = "inbox_and_paste"
    _start_recording()


def _resolve_effective_mode() -> str:
    """Return inbox_fallback if dictate's target window has lost foreground."""
    if _recording_mode == "dictate" and _target_hwnd:
        current = _get_foreground_hwnd()
        if current != _target_hwnd:
            logger.info(
                "Target HWND %s lost foreground (now %s) — falling back to inbox save",
                _target_hwnd, current,
            )
            return "inbox_fallback"
    return _recording_mode


def _terminate_recording(cancel: bool, pinned_hwnd: int | None = None) -> None:
    """Single shared termination path for Stop and Cancel.

    Args:
        cancel: True → discard audio, no transcription.
                False → transcribe and paste/save as configured.
        pinned_hwnd: When set (Stop button path), the target HWND captured at
            record-start.  Bypasses the foreground-loss check in
            _resolve_effective_mode and restores focus before pasting.
    Safe to call from any thread; idempotent via _termination_lock.
    """
    global _audio_thread, _audio_path, _target_hwnd, _terminating

    with _termination_lock:
        if _terminating:
            return   # another path (button, hotkey, max-duration) already won
        _terminating = True
        if cancel:
            _cancel_flag.set()

    audio.stop_recording()
    if cancel:
        _beep(220, 200)              # low single beep = audio discarded
        overlay_module.hide_overlay()
    else:
        _beep(440, 120)
        overlay_module.show_transcribing()

    if _audio_thread is not None:
        _audio_thread.join(timeout=10)
        _audio_thread = None

    if _tray:
        _tray.set_idle()

    if cancel:
        if _audio_path:
            try:
                os.remove(_audio_path)
                logger.debug("Cancel: discarded audio file %s", _audio_path)
            except OSError:
                pass
            _audio_path = None
        _target_hwnd = None
        return

    # --- Stop path: transcribe and paste/save ---
    if not _audio_path:
        logger.warning("No audio file produced — skipping transcription")
        overlay_module.hide_overlay()
        return

    path = _audio_path
    _audio_path = None

    global _pending_future
    # When the Stop button triggered termination, pinned_hwnd holds the
    # original target HWND.  Skip the foreground-loss check — the button
    # click itself caused the focus shift, not genuine user navigation.
    if pinned_hwnd is not None and _recording_mode == "dictate":
        effective_mode = _recording_mode
    else:
        effective_mode = _resolve_effective_mode()
    _target_hwnd = None
    _pending_future = _process_executor.submit(_process, path, effective_mode, pinned_hwnd)


def _on_stop() -> None:
    """Key released while recording — stop and transcribe."""
    _terminate_recording(cancel=False)


def _on_tap() -> None:
    """Short press — stop an in-flight recording, else show the mode menu."""
    if _audio_thread is not None and _audio_thread.is_alive():
        # Recording active (typically menu-initiated — no key to release).
        # Treat the tap as an explicit stop.  Dispatch to a worker thread so
        # the keyboard hook returns immediately (_on_stop joins the audio thread).
        logger.info("Tap during recording — stopping")
        threading.Thread(target=_on_stop, daemon=True, name="tap-stop").start()
        return
    if _dispatcher is not None:
        _dispatcher.tap_signal.emit()
    else:
        logger.error("_dispatcher not initialised — tap ignored")


def _on_stop_button() -> None:
    """Stop button clicked — stop recording and transcribe.  Qt main thread."""
    if _audio_thread is None or not _audio_thread.is_alive():
        return
    # Capture the target HWND now, before this click shifts foreground focus
    # away from the user's original window.
    saved_hwnd = _target_hwnd
    threading.Thread(
        target=_terminate_recording, args=(False, saved_hwnd), daemon=True, name="btn-stop"
    ).start()


def _on_cancel_button() -> None:
    """Cancel button clicked — stop recording and discard audio.  Qt main thread."""
    if _audio_thread is None or not _audio_thread.is_alive():
        return
    threading.Thread(
        target=_terminate_recording, args=(True,), daemon=True, name="btn-cancel"
    ).start()


def _show_mode_menu() -> None:
    """Show the settings/tools palette (Qt main thread only)."""
    menu_module.show_mode_menu(_config)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    # --- Single-instance lock (must be first) ---
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\VoiceDesk_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        logging.warning("VoiceDesk already running — exiting.")
        sys.exit(1)

    _setup_logging()
    logger.info("VoiceDesk starting")

    global _config, _tray

    try:
        _config = config_loader.load_config()
        logger.info("Config loaded: %s", _config)
    except Exception as exc:
        logger.critical("Failed to load config: %s", exc)
        raise SystemExit(1) from exc

    # Create the Qt application first — must exist before any QWidget.
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # overlay hiding must not quit the app

    # Allow Ctrl+C in the terminal to exit cleanly.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # Pulse the Python event loop every 250 ms so SIGINT is processed.
    _sigint_timer = QTimer()
    _sigint_timer.setInterval(250)
    _sigint_timer.timeout.connect(lambda: None)
    _sigint_timer.start()

    # Dispatcher bridge — must be created on the main thread so its signals
    # are delivered here.  Connect before the hotkey is registered.
    global _dispatcher
    _dispatcher = _Dispatcher()
    _dispatcher.tap_signal.connect(_show_mode_menu)

    # Overlay and menu widgets (must be created after QApplication).
    overlay_module.create_overlay()
    overlay_module.stop_signal().connect(_on_stop_button)
    overlay_module.cancel_signal().connect(_on_cancel_button)

    # Tray icon (background daemon thread).
    _tray = tray_module.TrayIcon(quit_cb=app.quit)
    _tray.run_detached()

    # Warm up the transcription model in the background.
    threading.Thread(
        target=transcribe.warmup, args=(_config,), daemon=True, name="model-warmup"
    ).start()

    # Register the primary dictate hotkey.
    listener = hotkey_module.HotkeyListener()
    listener.start(
        hotkey=_config["hotkey"],
        on_hold_cb=_on_hold,
        on_stop_cb=_on_stop,
        on_tap_cb=_on_tap,
        hold_threshold=_config.get("hold_threshold_seconds", 0.8),
    )

    # Register the inbox hotkey (paste + save to Second Brain inbox).
    listener_inbox = hotkey_module.HotkeyListener()
    listener_inbox.start(
        hotkey=_config.get("inbox_hotkey", "alt+win"),
        on_hold_cb=_on_hold_inbox,
        on_stop_cb=_on_stop,
        on_tap_cb=lambda: None,  # hold-only; tap intentionally ignored
        hold_threshold=_config.get("hold_threshold_seconds", 0.8),
    )

    logger.info(
        "Ready. Hold %r (%.1fs) to dictate; tap to select mode. Hold %r to inbox+paste.",
        _config["hotkey"],
        _config.get("hold_threshold_seconds", 0.8),
        _config.get("inbox_hotkey", "alt+win"),
    )

    # Run the Qt event loop — this blocks until app.quit() is called.
    exit_code = app.exec()

    listener.stop()
    listener_inbox.stop()
    _process_executor.shutdown(wait=False)
    logger.info("VoiceDesk shut down (exit code %d)", exit_code)


# ---------------------------------------------------------------------------
# Watchdog supervisor
# ---------------------------------------------------------------------------

def _run_watchdog() -> None:
    """Spawn --worker subprocesses and restart on crash."""
    _setup_logging()
    MAX_RESTARTS = 3
    restarts = 0
    pythonw = sys.executable
    script = os.path.abspath(__file__)

    while True:
        logger.info("Watchdog: starting VoiceDesk (attempt %d)", restarts + 1)
        try:
            proc = subprocess.Popen([pythonw, script, "--worker"])
            proc.wait()
            returncode = proc.returncode
        except Exception as exc:
            logger.error("Watchdog: failed to launch worker: %s", exc)
            returncode = -1

        if returncode == 0:
            logger.info("Watchdog: worker exited cleanly — shutting down")
            break

        restarts += 1
        logger.warning(
            "Watchdog: worker exited with code %d (restart %d/%d)",
            returncode,
            restarts,
            MAX_RESTARTS,
        )
        if restarts >= MAX_RESTARTS:
            logger.error(
                "Watchdog: giving up after %d restarts — check logs/voicedesk.log",
                MAX_RESTARTS,
            )
            break

        logger.info("Watchdog: waiting 5s before restart")
        time.sleep(5)

    logger.info("Watchdog: exiting")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        main()
    else:
        _run_watchdog()
