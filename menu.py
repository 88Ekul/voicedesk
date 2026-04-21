"""Mode-selection popup menu.

Appears centre-screen on tap.  Returns 'dictate', 'inbox', or None.

Dismissal methods (all return None):
  - Escape key
  - Key 3
  - 5-second auto-dismiss (150 ms fade-out then reject)
  - Click / activation-loss outside the dialog

Entry animation: slides up 10 px while fading in over 200 ms.
"""

import logging

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_FADE_IN_MS   = 200
_FADE_OUT_MS  = 150
_AUTO_DISMISS_MS = 5_000

_BG     = "#2F4F4F"
_BORDER = "#B76E79"
_TEXT   = "#F5F5F5"
_NUM    = "#B76E79"
_FONT   = "Segoe UI"
_PT     = 13

# Menu options: (display number, display text, return value)
_OPTIONS = [
    ("[1]", "Dictate to Cursor",  "dictate"),
    ("[2]", "Save to Inbox",      "inbox"),
    ("[3]", "Cancel",             None),
]


def _option_html(num: str, text: str) -> str:
    """Build rich-text HTML for one menu row."""
    return (
        f"<span style='color:{_NUM};font-family:{_FONT};font-size:{_PT}pt;'>{num}</span>"
        f"<span style='color:{_TEXT};font-family:{_FONT};font-size:{_PT}pt;'>&nbsp;{text}</span>"
    )


# ---------------------------------------------------------------------------
# Clickable label helper
# ---------------------------------------------------------------------------

class _ClickLabel(QLabel):
    """QLabel that fires a callback on mouse press."""

    def __init__(self, html: str, callback) -> None:
        super().__init__()
        self.setText(html)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._cb = callback

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self._cb()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class _ModeDialog(QDialog):
    """Modal, frameless mode-selection dialog."""

    def __init__(self) -> None:
        super().__init__()
        self._mode: str | None = None
        self._dismissed: bool = False
        self._dismiss_timer: QTimer | None = None
        self._entry_group: QParallelAnimationGroup | None = None

        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Window / layout setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(380)
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(sp)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        bg = QWidget(self)
        bg.setObjectName("bg")
        bg.setStyleSheet(
            f"#bg {{"
            f"  background-color: {_BG};"
            f"  border: 1.5px solid {_BORDER};"
            f"  border-radius: 20px;"
            f"}}"
        )
        sp = bg.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        bg.setSizePolicy(sp)
        outer.addWidget(bg)

        inner = QVBoxLayout(bg)
        inner.setContentsMargins(24, 16, 24, 16)
        inner.setSpacing(10)

        for num, text, mode in _OPTIONS:
            lbl = _ClickLabel(
                _option_html(num, text),
                # capture mode in default arg to avoid late-binding closure
                lambda m=mode: self._select(m),
            )
            inner.addWidget(lbl)

    # ------------------------------------------------------------------
    # Centre-screen positioning
    # ------------------------------------------------------------------

    def _centre_pos(self) -> QPoint:
        screen = QApplication.primaryScreen()
        if screen is None:
            return QPoint(0, 0)
        self.adjustSize()
        g = screen.geometry()
        x = g.left() + (g.width()  - self.width())  // 2
        y = g.top()  + (g.height() - self.height()) // 2
        return QPoint(x, y)

    # ------------------------------------------------------------------
    # Entry animation: slide up 10 px + fade in over 200 ms
    # ------------------------------------------------------------------

    def _start_entry_animation(self, target: QPoint) -> None:
        start = QPoint(target.x(), target.y() + 10)
        self.move(start)
        self.setWindowOpacity(0.0)
        self.show()

        pos_anim = QPropertyAnimation(self, b"pos", self)
        pos_anim.setDuration(_FADE_IN_MS)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(target)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        fade_anim.setDuration(_FADE_IN_MS)
        fade_anim.setStartValue(0.0)
        fade_anim.setEndValue(1.0)

        self._entry_group = QParallelAnimationGroup(self)
        self._entry_group.addAnimation(pos_anim)
        self._entry_group.addAnimation(fade_anim)
        self._entry_group.start()

    # ------------------------------------------------------------------
    # Auto-dismiss timer
    # ------------------------------------------------------------------

    def _start_dismiss_timer(self) -> None:
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.setInterval(_AUTO_DISMISS_MS)
        self._dismiss_timer.timeout.connect(self._cancel)
        self._dismiss_timer.start()

    # ------------------------------------------------------------------
    # Cancellation — fade out 150 ms then reject
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()

        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(_FADE_OUT_MS)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self.reject)
        anim.start()
        logger.debug("Mode menu dismissed")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_1:
            self._select("dictate")
        elif key == Qt.Key.Key_2:
            self._select("inbox")
        elif key in (Qt.Key.Key_3, Qt.Key.Key_Escape):
            self._cancel()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802
        """Dismiss when the dialog loses activation (user clicks outside)."""
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self._cancel()
        super().changeEvent(event)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select(self, mode: str | None) -> None:
        if self._dismissed:
            return
        if mode is None:
            self._cancel()
            return
        self._dismissed = True
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
        logger.info("Mode selected: %s", mode)
        self._mode = mode
        self.accept()

    # ------------------------------------------------------------------
    # Run (called on Qt main thread)
    # ------------------------------------------------------------------

    def run(self) -> str | None:
        """Position, animate in, block until selection/dismiss, return mode or None."""
        target = self._centre_pos()
        self._start_entry_animation(target)
        self._start_dismiss_timer()
        super().exec()
        return self._mode


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def show_mode_menu() -> str | None:
    """Create, show and block on the mode dialog.

    Must be called on the Qt main thread.
    Returns 'dictate', 'inbox', or None.
    """
    dlg = _ModeDialog()
    return dlg.run()
