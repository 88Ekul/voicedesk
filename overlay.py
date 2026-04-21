"""Floating waveform pill overlay for VoiceDesk.

PyQt6-based, always-on-top, borderless, click-through window.  The widget
lives entirely on the Qt main thread; all public methods are thread-safe
because they emit signals rather than touching Qt objects directly.
"""

import logging

from PyQt6.QtCore import QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

PILL_W = 200
PILL_H = 50
NUM_BARS = 8
BAR_W = 8
BAR_GAP = 6
MARGIN_ABOVE_TASKBAR = 20

_BAR_MIN_H = 4
_BAR_MAX_H = 36
_BAR_RANGE = _BAR_MAX_H - _BAR_MIN_H   # 32 px

_GLOW_MAX_RADIUS = 18.0                 # px at smoothed == 1.0
_RMS_GAIN = 50.0                         # amplify raw mic RMS for waveform display
_GLOW_COLOUR = QColor(0xB7, 0x6E, 0x79)


class WaveformOverlay(QWidget):
    """Animated waveform pill.  Always on top, click-through, no taskbar entry."""

    # Signals for thread-safe dispatch onto the Qt main thread.
    _sig_show_recording = pyqtSignal()
    _sig_update_volume = pyqtSignal(float)
    _sig_show_transcribing = pyqtSignal()
    _sig_hide = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        # --- volume state ---
        self._smoothed: float = 0.0          # EMA of amplified RMS, 0.0–1.0
        self._glow_radius: float = 0.0       # current drop-shadow radius in px
        self._last_glow_smoothed: float = -1.0  # sentinel → force first update

        # --- display state ---
        self._transcribing: bool = False
        self._bar_heights: list[float] = [float(_BAR_MIN_H)] * NUM_BARS

        # --- opacity animation ---
        self._anim: QPropertyAnimation | None = None

        self._setup_window()

        self._sig_show_recording.connect(self._do_show_recording)
        self._sig_update_volume.connect(self._do_update_volume)
        self._sig_show_transcribing.connect(self._do_show_transcribing)
        self._sig_hide.connect(self._do_hide)

        self._timer = QTimer(self)
        self._timer.setInterval(16)   # ~60 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(PILL_W, PILL_H)
        self._reposition()
        # Start invisible but alive so the first reveal has no creation cost.
        self.setWindowOpacity(0.0)
        self.show()

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()   # excludes taskbar
        x = g.left() + (g.width() - PILL_W) // 2
        y = g.bottom() - PILL_H - MARGIN_ABOVE_TASKBAR
        self.move(x, y)

    # ------------------------------------------------------------------
    # Public thread-safe API
    # ------------------------------------------------------------------

    def show_recording(self) -> None:
        """Expand the pill and start bar animation.  Thread-safe."""
        self._sig_show_recording.emit()

    def update_volume(self, rms: float) -> None:
        """Drive bar heights from live mic RMS.  Thread-safe, called per block."""
        self._sig_update_volume.emit(rms)

    def show_transcribing(self) -> None:
        """Freeze bars at low height and shift colour to white.  Thread-safe."""
        self._sig_show_transcribing.emit()

    def hide_overlay(self) -> None:
        """Fade out and hide.  Thread-safe."""
        self._sig_hide.emit()

    # ------------------------------------------------------------------
    # Slots — always executed on the Qt main thread via queued signals
    # ------------------------------------------------------------------

    def _do_show_recording(self) -> None:
        self._transcribing = False
        # Entry animation: 0 → 1.0 over 150 ms using QPropertyAnimation.
        self._stop_anim()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(150)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _do_update_volume(self, rms: float) -> None:
        # Noise gate: treat near-silence as zero to avoid idle bar flutter.
        amplified = 0.0 if rms < 0.001 else min(1.0, rms * _RMS_GAIN)
        logger.debug("RMS raw=%.4f  amplified=%.4f  smoothed=%.4f",
                     rms, amplified, self._smoothed)
        # Asymmetric EMA: fast attack (0.6) so bars snap up quickly,
        # slow decay (0.15) so they fall back smoothly.
        alpha = 0.6 if amplified > self._smoothed else 0.15
        self._smoothed = alpha * amplified + (1.0 - alpha) * self._smoothed

        # Update glow radius only when the smoothed value has moved by > 0.02
        # to avoid redundant property updates every single frame.
        if abs(self._smoothed - self._last_glow_smoothed) > 0.02:
            self._glow_radius = self._smoothed * _GLOW_MAX_RADIUS
            self._last_glow_smoothed = self._smoothed

    def _do_show_transcribing(self) -> None:
        self._transcribing = True
        self._smoothed = 0.0
        self._glow_radius = 0.0
        self._last_glow_smoothed = 0.0

    def _do_hide(self) -> None:
        # Exit animation: current opacity → 0 over 300 ms.
        self._stop_anim()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(300)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.start()
        self._glow_radius = 0.0
        self._last_glow_smoothed = 0.0

    def _stop_anim(self) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

    # ------------------------------------------------------------------
    # Animation tick (~60 fps)
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        centre = (NUM_BARS - 1) / 2.0

        if not self._transcribing:
            # Map self._smoothed (0–1) to bar height in px: [_BAR_MIN_H, _BAR_MAX_H].
            # Centre bars are tallest; outer bars taper by up to 45 %.
            for i in range(NUM_BARS):
                dist = abs(i - centre) / centre   # 0 = innermost, 1 = outermost
                target = _BAR_MIN_H + self._smoothed * (1.0 - dist * 0.45) * _BAR_RANGE
                # Smooth bar movement so there are no hard jumps.
                self._bar_heights[i] += (target - self._bar_heights[i]) * 0.18
        else:
            # Freeze at a calm low uniform height while transcribing.
            frozen = _BAR_MIN_H + 0.14 * _BAR_RANGE   # ≈ 8.5 px
            for i in range(NUM_BARS):
                self._bar_heights[i] += (frozen - self._bar_heights[i]) * 0.15

        if self.windowOpacity() > 0.01:
            self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self.windowOpacity() < 0.01:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2.0

        # Volume-driven glow ring — painted first so it sits behind the pill.
        # Colour: #B76E79 (rose gold).  Radius and alpha scale with _glow_radius.
        if self._glow_radius > 0.5:
            spread = self._glow_radius * 0.6
            alpha = int(min(110, self._glow_radius * 6.0))
            glow_path = QPainterPath()
            glow_path.addRoundedRect(
                -spread, -spread,
                w + spread * 2, h + spread * 2,
                radius + spread, radius + spread,
            )
            p.fillPath(glow_path, QBrush(QColor(_GLOW_COLOUR.red(),
                                                 _GLOW_COLOUR.green(),
                                                 _GLOW_COLOUR.blue(),
                                                 alpha)))
        else:
            # Subtle static glow when glow is inactive — 1px, nearly invisible.
            static_glow = QPainterPath()
            static_glow.addRoundedRect(-1, -1, w + 2, h + 2, radius + 1, radius + 1)
            p.fillPath(static_glow, QBrush(QColor(160, 0, 220, 20)))

        # Pill background — pure black at 85 % opacity.
        pill = QPainterPath()
        pill.addRoundedRect(0, 0, w, h, radius, radius)
        p.fillPath(pill, QBrush(QColor(0, 0, 0, 216)))

        # Clip bar drawing to the pill shape.
        p.setClipPath(pill)

        # Bars.
        total_w = NUM_BARS * BAR_W + (NUM_BARS - 1) * BAR_GAP
        sx = (w - total_w) // 2
        centre = (NUM_BARS - 1) / 2.0

        for i, bar_h_f in enumerate(self._bar_heights):
            bar_h = max(_BAR_MIN_H, min(_BAR_MAX_H, int(bar_h_f)))
            bx = sx + i * (BAR_W + BAR_GAP)
            by = (h - bar_h) // 2

            if self._transcribing:
                colour = QColor(255, 255, 255)
            else:
                # Gradient: outermost (t→1) = magenta #FF00FF,
                #            innermost (t→0) = cyan   #00FFFF.
                t = abs(i - centre) / centre
                colour = QColor(int(255 * t), int(255 * (1.0 - t)), 255)

            p.setBrush(QBrush(colour))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bx, by, BAR_W, bar_h, BAR_W / 2, BAR_W / 2)

        p.end()


# ---------------------------------------------------------------------------
# Module-level singleton + convenience functions
# ---------------------------------------------------------------------------

_overlay: WaveformOverlay | None = None


def create_overlay() -> WaveformOverlay:
    """Instantiate the overlay.  Must be called after QApplication exists."""
    global _overlay
    _overlay = WaveformOverlay()
    return _overlay


def show_recording() -> None:
    if _overlay:
        _overlay.show_recording()


def update_volume(rms: float) -> None:
    if _overlay:
        _overlay.update_volume(rms)


def show_transcribing() -> None:
    if _overlay:
        _overlay.show_transcribing()


def hide_overlay() -> None:
    if _overlay:
        _overlay.hide_overlay()
