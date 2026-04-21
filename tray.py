"""System tray icon with idle (grey) and recording (red) states."""

import logging
import threading

from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)

_ICON_SIZE = 64
_CIRCLE_MARGIN = 4


def _make_icon(color: str) -> Image.Image:
    """Create a 64×64 RGBA image with a filled circle of the given colour."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [_CIRCLE_MARGIN, _CIRCLE_MARGIN, _ICON_SIZE - _CIRCLE_MARGIN, _ICON_SIZE - _CIRCLE_MARGIN],
        fill=color,
    )
    return img


_ICON_IDLE = _make_icon("#808080")       # grey
_ICON_RECORDING = _make_icon("#cc0000")  # red


class TrayIcon:
    """Wraps a pystray.Icon with idle/recording state switching."""

    def __init__(self, quit_cb=None) -> None:
        self._quit_cb = quit_cb
        menu = pystray.Menu(
            pystray.MenuItem("VoiceDesk", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )
        self._icon = pystray.Icon(
            name="VoiceDesk",
            icon=_ICON_IDLE,
            title="VoiceDesk — idle",
            menu=menu,
        )
        self._thread: threading.Thread | None = None

    def run_detached(self) -> None:
        """Start the tray icon in a background daemon thread."""
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="tray")
        self._thread.start()
        logger.info("Tray icon started")

    def set_idle(self) -> None:
        """Switch the icon to the grey idle state."""
        self._icon.icon = _ICON_IDLE
        self._icon.title = "VoiceDesk — idle"
        logger.debug("Tray icon: idle")

    def set_recording(self) -> None:
        """Switch the icon to the red recording state."""
        self._icon.icon = _ICON_RECORDING
        self._icon.title = "VoiceDesk — recording"
        logger.debug("Tray icon: recording")

    def _on_quit(self) -> None:
        logger.info("Quit requested via tray menu")
        self._icon.stop()
        if self._quit_cb is not None:
            self._quit_cb()
