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

_MODIFIERS: frozenset[str] = frozenset({"ctrl", "shift", "alt", "win"})

# Module-level registry so suppressors can broadcast Win events to all listeners.
_listeners: list["HotkeyListener"] = []
_listeners_lock = threading.Lock()


def _canon(name: str) -> str:
    return _CANONICAL.get(name.lower(), name.lower())


def _broadcast_to_all(event: "keyboard.KeyboardEvent") -> None:
    """Dispatch a (suppressed) Win event to every registered listener's handler."""
    with _listeners_lock:
        targets = list(_listeners)
    for lst in targets:
        threading.Thread(target=lst._handle_event, args=(event,), daemon=True).start()


class HotkeyListener:
    """Tap-or-hold listener for a multi-key combo."""

    def __init__(self) -> None:
        self._hook = None
        self._suppressor = None
        self._win_down_suppressed: bool = False
        self._parts: list[str] = []
        self._held: set[str] = set()
        self._all_held: set[str] = set()        # all currently-held modifier keys
        self._suppressor_held: set[str] = set() # modifier state seen by suppressor

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
        self._all_held.clear()
        self._suppressor_held.clear()
        self._active = False
        self._hold_mode = False

        self._hook = keyboard.hook(self._handle_event, suppress=False)
        # Suppress only the Win key when pressed as part of the combo.
        self._win_down_suppressed = False
        self._suppressor = keyboard.hook(self._suppress_combo, suppress=True)
        with _listeners_lock:
            if self not in _listeners:
                _listeners.append(self)
        logger.info(
            "Hotkey '%s' registered (hold_threshold=%.2fs)", hotkey, hold_threshold
        )

    # ------------------------------------------------------------------

    def _handle_event(self, event: keyboard.KeyboardEvent) -> None:
        key = _canon(event.name)

        # Always track modifier state, even during ignore windows, to keep
        # the extra-modifier guard accurate across key sequences.
        if key in _MODIFIERS:
            if event.event_type == keyboard.KEY_DOWN:
                self._all_held.add(key)
            else:
                self._all_held.discard(key)

        # If we're pre-hold (active, threshold not yet reached) and an extra
        # modifier has just arrived, the user is reaching for a longer combo —
        # cancel so that listener wins cleanly.  _hold_mode means recording is
        # already underway; leave it alone.
        if self._active and not self._hold_mode:
            extra = (_MODIFIERS & self._all_held) - set(self._parts)
            if extra:
                with self._lock:
                    if self._active and not self._hold_mode:
                        if self._hold_timer is not None:
                            self._hold_timer.cancel()
                            self._hold_timer = None
                        self._active = False
                        logger.debug(
                            "Cancelled pre-hold activation — extra modifier %s (listener=%x)",
                            extra, id(self),
                        )

        if time.monotonic() < self._ignore_until:
            return
        logger.debug("KEY EVENT: type=%s name=%s listener=%x", event.event_type, event.name, id(self))

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

                # Don't activate if an extra modifier is held — a longer combo on
                # another listener (e.g. ctrl+shift+win) should handle it instead.
                extra_mods = (_MODIFIERS & self._all_held) - set(self._parts)
                if extra_mods:
                    logger.debug(
                        "Extra modifier(s) %s held — combo ignored (listener=%x)",
                        extra_mods, id(self)
                    )
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
                    logger.info("Tap detected (%.2fs) — firing on_tap callback (listener=%x)", elapsed, id(self))
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
        """Selectively suppress Win key events when all other combo parts are held.

        Generalised: derives the guard keys from self._parts so this works for
        both ctrl+win and ctrl+shift+win without hardcoding key names.
        Returns False (suppress) only when Win goes down/up as part of this
        specific combo, leaving Win-alone free to open Start Menu.
        True means 'allow the event through'.
        """
        key = _canon(event.name)
        # Track modifier state for the guard computation.
        if key in _MODIFIERS:
            if event.event_type == keyboard.KEY_DOWN:
                self._suppressor_held.add(key)
            else:
                self._suppressor_held.discard(key)
        if key == "win" and "win" in self._parts:
            guards = set(self._parts) - {"win"}
            if event.event_type == keyboard.KEY_DOWN and guards.issubset(self._suppressor_held):
                self._win_down_suppressed = True
                _broadcast_to_all(event)
                return False  # suppress Win while guard keys held
            if event.event_type == keyboard.KEY_UP and self._win_down_suppressed:
                self._win_down_suppressed = False
                _broadcast_to_all(event)
                return False  # suppress matching Win release
        return True  # allow everything else

    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Unregister the hotkey hook."""
        with _listeners_lock:
            try:
                _listeners.remove(self)
            except ValueError:
                pass
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
