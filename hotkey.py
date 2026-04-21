"""Tap-or-hold hotkey listener.

Behaviour
---------
* **Hold** — if the combo is held for >= *hold_threshold* seconds, ``on_hold_cb``
  fires at the threshold moment (start recording).  Releasing afterwards fires
  ``on_stop_cb`` (stop recording / transcribe).
* **Tap** — if the combo is released *before* the threshold, ``on_tap_cb`` fires
  (show mode-selection menu).

The previous push-to-talk ``min_duration`` / ``on_cancel_cb`` contract has been
replaced by this cleaner tap-vs-hold model.
"""

import logging
import threading
import time
from typing import Callable

import keyboard

logger = logging.getLogger(__name__)

_CANONICAL: dict[str, str] = {
    "left ctrl": "ctrl",    "right ctrl": "ctrl",
    "left alt": "alt",      "right alt": "alt",
    "left shift": "shift",  "right shift": "shift",
    "left windows": "win",  "right windows": "win",
    "windows": "win",
}


def _canon(name: str) -> str:
    return _CANONICAL.get(name.lower(), name.lower())


class HotkeyListener:
    """Tap-or-hold listener for a multi-key combo."""

    def __init__(self) -> None:
        self._hook = None
        self._suppressor = None
        self._combo_ctrl_held: bool = False
        self._win_down_suppressed: bool = False
        self._parts: list[str] = []
        self._held: set[str] = set()

        self._active: bool = False      # combo currently pressed
        self._hold_mode: bool = False   # threshold crossed → recording active
        self._press_time: float = 0.0
        self._hold_threshold: float = 0.8

        self._hold_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._ignore_until: float = 0.0
        self._last_press_times: dict[str, float] = {}

        self._on_hold: Callable | None = None
        self._on_stop: Callable | None = None
        self._on_tap: Callable | None = None

    # ------------------------------------------------------------------

    def start(
        self,
        hotkey: str,
        on_hold_cb: Callable[[], None],
        on_stop_cb: Callable[[], None],
        on_tap_cb: Callable[[], None],
        hold_threshold: float = 0.8,
    ) -> None:
        """Register the hotkey.

        Args:
            hotkey: e.g. ``'ctrl+win'``.
            on_hold_cb: Called once the combo has been held for *hold_threshold*
                seconds.  This is where recording should start.
            on_stop_cb: Called when the combo is released after recording began.
            on_tap_cb: Called when the combo is released before the threshold.
            hold_threshold: Seconds to distinguish hold from tap.
        """
        # Guard: unhook any existing hook to prevent double registration.
        if self._hook is not None:
            keyboard.unhook(self._hook)
            logger.warning("Removed stale keyboard hook before re-registration")
            self._hook = None
        if self._suppressor is not None:
            keyboard.unhook(self._suppressor)
            self._suppressor = None

        self._parts = [_canon(p.strip()) for p in hotkey.split("+")]
        self._on_hold = on_hold_cb
        self._on_stop = on_stop_cb
        self._on_tap = on_tap_cb
        self._hold_threshold = hold_threshold
        self._held.clear()
        self._active = False
        self._hold_mode = False

        self._hook = keyboard.hook(self._handle_event, suppress=False)
        # Suppress only the Win key when pressed as part of the combo.
        self._win_down_suppressed = False
        self._combo_ctrl_held = False
        self._suppressor = keyboard.hook(self._suppress_combo, suppress=True)
        logger.info(
            "Hotkey '%s' registered (hold_threshold=%.2fs)", hotkey, hold_threshold
        )

    # ------------------------------------------------------------------

    def _handle_event(self, event: keyboard.KeyboardEvent) -> None:
        if time.monotonic() < self._ignore_until:
            return
        logger.debug("KEY EVENT: type=%s name=%s listener=%x", event.event_type, event.name, id(self))
        key = _canon(event.name)

        # Filter: only process events for keys in our combo.
        if key not in self._parts:
            return

        now = time.monotonic()

        if event.event_type == keyboard.KEY_DOWN:
            with self._lock:
                self._held.add(key)
                self._last_press_times[key] = now

                if self._active or self._hold_timer is not None:
                    return

                # All combo parts must be held AND pressed within the last 500ms.
                # This prevents stuck keys in _held from triggering partial combos.
                if not all(p in self._held for p in self._parts):
                    return
                if any(now - self._last_press_times.get(p, 0.0) > 0.5 for p in self._parts):
                    logger.debug("Combo parts present but stale — ignoring (stuck key?)")
                    return

                self._active = True
                self._hold_mode = False
                self._press_time = now
                self._hold_timer = threading.Timer(
                    self._hold_threshold, self._threshold_reached
                )
                self._hold_timer.daemon = True
                self._hold_timer.start()
                logger.debug("Hotkey down — waiting %.2fs for hold", self._hold_threshold)

        elif event.event_type == keyboard.KEY_UP:
            with self._lock:
                self._held.discard(key)
                if not self._active:
                    return

                self._active = False
                if self._hold_timer is not None:
                    self._hold_timer.cancel()
                    self._hold_timer = None

                elapsed = now - self._press_time

                if self._hold_mode:
                    self._hold_mode = False
                    logger.info("Hold released after %.2fs — stopping recording", elapsed)
                    if self._on_stop:
                        self._on_stop()
                    self._ignore_until = now + 5.0
                else:
                    logger.info("Tap detected (%.2fs) — showing menu", elapsed)
                    if self._on_tap:
                        self._on_tap()

    def _threshold_reached(self) -> None:
        with self._lock:
            if not self._active or self._hold_mode:
                return
            self._hold_mode = True
        logger.info("Hold threshold reached — starting recording (listener=%x)", id(self))
        if self._on_hold:
            self._on_hold()

    def _suppress_combo(self, event: keyboard.KeyboardEvent) -> bool:
        """Selectively suppress Win key events while Ctrl is held.

        Returns False (suppress) only when Win goes down/up as part of a
        Ctrl+Win combination, leaving Win-alone free to open Start Menu.
        True means 'allow the event through'.
        """
        key = _canon(event.name)
        if key == "ctrl":
            self._combo_ctrl_held = (event.event_type == keyboard.KEY_DOWN)
            return True  # always allow Ctrl through
        if key == "win":
            if event.event_type == keyboard.KEY_DOWN and self._combo_ctrl_held:
                self._win_down_suppressed = True
                threading.Thread(
                    target=self._handle_event, args=(event,), daemon=True
                ).start()
                return False  # suppress Win while Ctrl held
            if event.event_type == keyboard.KEY_UP and self._win_down_suppressed:
                self._win_down_suppressed = False
                threading.Thread(
                    target=self._handle_event, args=(event,), daemon=True
                ).start()
                return False  # suppress matching Win release
        return True  # allow everything else

    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Unregister the hotkey hook."""
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None
        if self._suppressor is not None:
            keyboard.unhook(self._suppressor)
            self._suppressor = None
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
            logger.info("Hotkey hook removed")
