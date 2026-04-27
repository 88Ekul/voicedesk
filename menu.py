"""Settings & tools palette for VoiceDesk.

Opened by a Ctrl+Win tap.  Replaces the old three-option mode-selection menu.

Zones (top to bottom):
  1. Header   — mic icon + "VoiceDesk" wordmark
  2. Grid     — 2×2 floating tile cards
  3. Style    — output-style segmented control
  4. Cancel   — barely-visible exit row

Public API:
    show_mode_menu(config: dict | None = None) -> None
"""

import logging
import math

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import config_loader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

_BG_TOP        = QColor(0x33, 0x55, 0x55)   # brushed slate gradient top
_BG_BOT        = QColor(0x26, 0x40, 0x40)   # brushed slate gradient bottom
_ROSE          = QColor(0xB7, 0x6E, 0x79)   # Rose Gold
_OFFWHITE      = QColor(0xF5, 0xF5, 0xF5)   # Off-White
_WELL_BG       = QColor(0x1A, 0x2E, 0x2E)   # icon well / segmented control dark fill
_TILE_BG       = QColor(0x22, 0x3A, 0x3A)   # tile resting background
_TILE_BG_HOVER = QColor(0x2D, 0x4C, 0x4C)   # tile hover background
_FONT          = "Segoe UI"

_FADE_IN_MS  = 200
_FADE_OUT_MS = 150


def _rose_alpha(a: int) -> QColor:
    c = QColor(_ROSE)
    c.setAlpha(a)
    return c


def _offwhite_alpha(a: int) -> QColor:
    c = QColor(_OFFWHITE)
    c.setAlpha(a)
    return c


# ---------------------------------------------------------------------------
# Glyph painters  (p: QPainter, r: QRectF) -> None
# ---------------------------------------------------------------------------

def _glyph_snippets(p: QPainter, r: QRectF) -> None:
    """Three horizontal bars — list / snippet icon."""
    pen = QPen(_ROSE, 1.5, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(3):
        y = r.top() + r.height() * (i * 0.33 + 0.17)
        p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))


def _glyph_dictionary(p: QPainter, r: QRectF) -> None:
    """Open book — two pages with a centre spine."""
    pen = QPen(_ROSE, 1.2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx = r.center().x()
    p.drawRoundedRect(
        QRectF(r.left(), r.top(), cx - r.left() - 1.5, r.height()), 1.5, 1.5
    )
    p.drawRoundedRect(
        QRectF(cx + 1.5, r.top(), r.right() - cx - 1.5, r.height()), 1.5, 1.5
    )


def _glyph_recent(p: QPainter, r: QRectF) -> None:
    """Clock face — circle with hour and minute hands."""
    pen = QPen(_ROSE, 1.5, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = r.center().x(), r.center().y()
    rad = min(r.width(), r.height()) / 2 - 0.5
    p.drawEllipse(QPointF(cx, cy), rad, rad)
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - rad * 0.6))
    p.drawLine(QPointF(cx, cy), QPointF(cx + rad * 0.45, cy))


def _glyph_settings(p: QPainter, r: QRectF) -> None:
    """Three horizontal sliders — equaliser / settings icon."""
    pen = QPen(_ROSE, 1.2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    hr = 2.5
    for i, fx in enumerate((0.25, 0.65, 0.45)):
        y  = r.top() + r.height() * (i * 0.33 + 0.17)
        hx = r.left() + r.width() * fx
        p.drawLine(QPointF(r.left(), y), QPointF(hx - hr, y))
        p.drawLine(QPointF(hx + hr, y), QPointF(r.right(), y))
        p.setBrush(QBrush(_WELL_BG))
        p.drawEllipse(QPointF(hx, y), hr, hr)
        p.setBrush(Qt.BrushStyle.NoBrush)


# ---------------------------------------------------------------------------
# MicIcon
# ---------------------------------------------------------------------------

class _MicIcon(QWidget):
    """52×52 vintage desk microphone drawn with QPainter."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(_ROSE, 1.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Capsule head: 12w × 22h pill, centred at x=26
        p.drawRoundedRect(20, 4, 12, 22, 6, 6)

        # Two horizontal grille lines
        for gy in (11, 18):
            p.drawLine(22, gy, 30, gy)

        # Yoke arms: left and right arcs cradling the capsule, meeting at stand top
        left_arm = QPainterPath()
        left_arm.moveTo(20, 16)
        left_arm.cubicTo(12, 20, 14, 32, 26, 32)
        p.drawPath(left_arm)

        right_arm = QPainterPath()
        right_arm.moveTo(32, 16)
        right_arm.cubicTo(40, 20, 38, 32, 26, 32)
        p.drawPath(right_arm)

        # Stand: from yoke junction to base
        p.drawLine(26, 32, 26, 44)

        # Base
        p.drawRoundedRect(15, 44, 22, 4, 1, 1)

        p.end()


# ---------------------------------------------------------------------------
# GradientDivider
# ---------------------------------------------------------------------------

class _GradientDivider(QWidget):
    """1 px horizontal line: transparent → Rose Gold → transparent."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(sp)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        grad = QLinearGradient(QPointF(0, 0), QPointF(self.width(), 0))
        grad.setColorAt(0.0, _rose_alpha(0))
        grad.setColorAt(0.5, _rose_alpha(140))
        grad.setColorAt(1.0, _rose_alpha(0))
        p.fillRect(0, 0, self.width(), 1, QBrush(grad))
        p.end()


# ---------------------------------------------------------------------------
# IconWell
# ---------------------------------------------------------------------------

class _IconWell(QWidget):
    """36×36 circular icon well: dark inset with Rose Gold ring."""

    def __init__(self, glyph_fn, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self._glyph = glyph_fn
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = 18.0, 18.0, 12.5
        outer = QRectF(cx - r, cy - r, r * 2, r * 2)

        # Translucent dark inset with visible Rose Gold ring.
        inner = outer.adjusted(1.5, 1.5, -1.5, -1.5)
        p.setBrush(QBrush(QColor(0x14, 0x24, 0x24, 90)))
        p.setPen(QPen(_rose_alpha(110), 1.0))
        p.drawEllipse(inner)

        # Subtle upper-left highlight to reinforce the recessed feel.
        hi_pen = QPen(_offwhite_alpha(20), 1.0)
        hi_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(hi_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        hi_rect = inner.adjusted(0.5, 0.5, -0.5, -0.5)
        p.drawArc(hi_rect, 135 * 16, 90 * 16)

        # Glyph
        self._glyph(p, inner.adjusted(3.5, 3.5, -3.5, -3.5))

        p.end()


# ---------------------------------------------------------------------------
# Tile
# ---------------------------------------------------------------------------

class _Tile(QWidget):
    """Floating card tile with icon well, label, and subtitle."""

    clicked = pyqtSignal(str)

    def __init__(self, tile_id: str, label: str, subtitle: str,
                 glyph_fn, primary: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._tile_id = tile_id
        self._primary = primary
        self._hovered = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        well = _IconWell(glyph_fn)
        layout.addWidget(well, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        lbl_font = QFont(_FONT, 12)
        lbl_font.setWeight(QFont.Weight.Medium)

        lbl = QLabel(label)
        lbl.setFont(lbl_font)
        lbl.setStyleSheet(f"color: {_OFFWHITE.name()}; background: transparent;")
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        sub = QLabel(subtitle)
        sub.setFont(QFont(_FONT, 9))
        sub.setStyleSheet(
            f"color: rgba({_ROSE.red()},{_ROSE.green()},{_ROSE.blue()},140);"
            "background: transparent;"
        )
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_col.addWidget(lbl)
        text_col.addWidget(sub)
        layout.addLayout(text_col, 1)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._tile_id)
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        if self._primary:
            p.fillPath(path, QBrush(_TILE_BG))
            p.fillPath(path, QBrush(_rose_alpha(33)))   # ~13% Rose Gold tint
        elif self._hovered:
            p.fillPath(path, QBrush(_TILE_BG_HOVER))
        else:
            p.fillPath(path, QBrush(_TILE_BG))

        border_alpha = 102 if self._hovered else 46    # ~40% vs ~18%
        p.setPen(QPen(_rose_alpha(border_alpha), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.end()


# ---------------------------------------------------------------------------
# SegmentedControl
# ---------------------------------------------------------------------------

class _SegmentButton(QWidget):
    """One pill option inside the segmented control."""

    clicked_val = pyqtSignal(str)

    def __init__(self, val: str, label: str, active: bool, parent=None) -> None:
        super().__init__(parent)
        self._val = val
        self._label = label
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(90, 34)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_val.emit(self._val)
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._active:
            pill = QPainterPath()
            pill.addRoundedRect(
                QRectF(2, 3, self.width() - 4, self.height() - 6), 14, 14
            )
            p.fillPath(pill, QBrush(_ROSE))
            p.setPen(QPen(_OFFWHITE))
        else:
            p.setPen(QPen(_offwhite_alpha(89)))   # ~35 % opacity

        p.setFont(QFont(_FONT, 10))
        p.drawText(
            QRectF(0, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )
        p.end()


class _SegmentedControl(QWidget):
    """Three-option segmented control for output style."""

    styleChanged = pyqtSignal(str)

    _OPTIONS = [
        ("formal",      "Formal"),
        ("casual",      "Casual"),
        ("very_casual", "Very casual"),
    ]

    def __init__(self, current: str, parent=None) -> None:
        super().__init__(parent)
        self._current = current
        self._btns: dict[str, _SegmentButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        for val, label in self._OPTIONS:
            btn = _SegmentButton(val, label, val == current)
            btn.clicked_val.connect(self._on_click)
            layout.addWidget(btn)
            self._btns[val] = btn

        self.setMinimumHeight(42)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 18, 18)
        p.fillPath(path, QBrush(_WELL_BG))
        p.end()

    def _on_click(self, val: str) -> None:
        if val == self._current:
            return
        self._current = val
        for v, btn in self._btns.items():
            btn.set_active(v == val)
        self.styleChanged.emit(val)


# ---------------------------------------------------------------------------
# BrushedBackground
# ---------------------------------------------------------------------------

class _BrushedBackground(QWidget):
    """Palette card: brushed slate gradient + Rose Gold border."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(360)

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(40)
        glow.setOffset(0, 0)
        glow.setColor(QColor(_ROSE.red(), _ROSE.green(), _ROSE.blue(), 60))
        self.setGraphicsEffect(glow)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)

        grad = QLinearGradient(QPointF(0, 0), QPointF(0, self.height()))
        grad.setColorAt(0.0, _BG_TOP)
        grad.setColorAt(1.0, _BG_BOT)
        p.fillPath(path, QBrush(grad))

        border = QPainterPath()
        border.addRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), 19.5, 19.5)
        p.setPen(QPen(_rose_alpha(140), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(border)

        p.end()


# ---------------------------------------------------------------------------
# ClickLabel helper
# ---------------------------------------------------------------------------

class _ClickLabel(QLabel):
    """QLabel that fires a callback on mouse press."""

    def __init__(self, html: str, callback) -> None:
        super().__init__()
        self.setText(html)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cb = callback

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self._cb()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class _PaletteDialog(QDialog):
    """Frameless settings & tools palette."""

    def __init__(self, config: dict) -> None:
        super().__init__()
        self._config = config
        self._dismissed = False
        self._entry_group: QParallelAnimationGroup | None = None

        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Window + UI
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 44)

        bg = _BrushedBackground()
        outer.addWidget(bg)

        inner = QVBoxLayout(bg)
        inner.setContentsMargins(20, 16, 20, 14)
        inner.setSpacing(10)

        # --- Zone 1: Header ---
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addStretch()
        header.addWidget(_MicIcon())

        wordmark = QLabel()
        wordmark.setTextFormat(Qt.TextFormat.RichText)
        wordmark.setText(
            f"<span style='font-family:{_FONT};font-size:19pt;font-weight:500;"
            f"color:{_OFFWHITE.name()};'>Voice</span>"
            f"<span style='font-family:{_FONT};font-size:19pt;font-weight:500;"
            f"color:{_ROSE.name()};'>Desk</span>"
        )
        wordmark.setStyleSheet("background: transparent;")
        header.addWidget(wordmark)
        header.addStretch()

        inner.addLayout(header)
        inner.addWidget(_GradientDivider())

        # --- Zone 2: 2×2 tile grid ---
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        _TILES = [
            ("snippets",   "Snippets",   "Voice shortcuts",       _glyph_snippets,   True),
            ("dictionary", "Dictionary", "Custom vocabulary",     _glyph_dictionary, False),
            ("recent",     "Recent",     "Last 5 transcriptions", _glyph_recent,     False),
            ("settings",   "Settings",   "Hotkeys & model",       _glyph_settings,   False),
        ]
        for idx, (tid, lbl, sub, glyph, primary) in enumerate(_TILES):
            row, col = divmod(idx, 2)
            tile = _Tile(tid, lbl, sub, glyph, primary)
            tile.clicked.connect(self._on_tile)
            grid.addWidget(tile, row, col)

        inner.addLayout(grid)

        # --- Zone 3: Output style ---
        inner.addWidget(_GradientDivider())

        cap_font = QFont(_FONT, 9)
        cap_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.3)

        style_cap = QLabel("OUTPUT STYLE")
        style_cap.setFont(cap_font)
        style_cap.setStyleSheet(
            f"color: rgba({_ROSE.red()},{_ROSE.green()},{_ROSE.blue()},140);"
            "background: transparent;"
        )
        style_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(style_cap)

        seg = _SegmentedControl(self._config.get("output_style", "formal"))
        seg.styleChanged.connect(self._on_style_change)
        inner.addWidget(seg)

        # --- Zone 4: Cancel ---
        subtle = QWidget()
        subtle.setFixedHeight(1)
        subtle.setStyleSheet(
            f"background: rgba({_ROSE.red()},{_ROSE.green()},{_ROSE.blue()},30);"
        )
        inner.addWidget(subtle)

        cancel = _ClickLabel(
            f"<span style='font-family:{_FONT};font-size:11pt;"
            f"color:rgba(245,245,245,51);'>✕ Cancel</span>",
            self._cancel,
        )
        inner.addWidget(cancel)

    # ------------------------------------------------------------------
    # Positioning + entry animation
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
    # Dismissal
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(_FADE_OUT_MS)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self.reject)
        anim.start()
        logger.debug("Palette dismissed")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        gp = event.globalPosition().toPoint()
        if not self.geometry().contains(gp):
            self._cancel()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_tile(self, tile_id: str) -> None:
        logger.info("Palette: opened %s", tile_id)
        self._cancel()

    def _on_style_change(self, val: str) -> None:
        logger.info("Output style changed: %s", val)
        try:
            config_loader.save_output_style(val)
            self._config["output_style"] = val
        except Exception as exc:
            logger.warning("Could not persist output style: %s", exc)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        target = self._centre_pos()
        self._start_entry_animation(target)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_open_palette: "_PaletteDialog | None" = None


def _clear_palette_ref() -> None:
    global _open_palette
    _open_palette = None


def show_mode_menu(config: dict | None = None) -> None:
    """Show the settings/tools palette.  Must be called on the Qt main thread."""
    global _open_palette
    if _open_palette is not None:
        return  # already open — ignore re-trigger
    if config is None:
        try:
            config = config_loader.load_config()
        except Exception as exc:
            logger.warning("Could not load config for palette: %s", exc)
            config = {}
    dlg = _PaletteDialog(config)
    dlg.finished.connect(_clear_palette_ref)
    _open_palette = dlg
    dlg.run()
