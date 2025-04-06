# ui/circular_progress_ring.py
"""
Custom QWidget for displaying a circular ring progress indicator.
"""
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QRectF, pyqtProperty, QSize # <--- IMPORT ADDED

class CircularProgressBarRing(QWidget):
    """A widget that draws a circular progress ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0

        # Customizable properties
        self._progress_color = QColor(66, 130, 218) # Default blue progress
        self._background_color = QColor(53, 53, 53) # Dark background for the ring track
        self._text_color = QColor(220, 220, 220)    # Text color matching theme
        self._ring_thickness = 12.0 # Thickness of the ring
        self._font_size_factor = 0.3 # Factor to determine font size based on widget height

        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    # --- Properties ---
    @pyqtProperty(int)
    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        if self._minimum != value:
            self._minimum = value
            self.update() # Trigger repaint

    @pyqtProperty(int)
    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        if self._maximum != value:
            self._maximum = value
            self.update()

    @pyqtProperty(int)
    def value(self):
        return self._value

    def setValue(self, value):
        # Clamp value within range
        clamped_value = max(self._minimum, min(value, self._maximum))
        if self._value != clamped_value:
            self._value = clamped_value
            self.update()

    # --- Appearance Customization Methods ---
    def setProgressColor(self, color: QColor):
        if self._progress_color != color:
            self._progress_color = color
            self.update()

    def setBackgroundColor(self, color: QColor):
         if self._background_color != color:
            self._background_color = color
            self.update()

    def setTextColor(self, color: QColor):
        if self._text_color != color:
            self._text_color = color
            self.update()

    def setRingThickness(self, thickness: float):
         if self._ring_thickness != thickness:
            self._ring_thickness = max(1.0, thickness) # Ensure minimum thickness
            self.update()

    # --- Range Setting ---
    def setRange(self, minimum: int, maximum: int):
        if minimum != self._minimum or maximum != self._maximum:
            self._minimum = minimum
            self._maximum = maximum
            # Re-clamp current value if necessary
            self.setValue(self._value) # This calls update()

    # --- Size Hints ---
    def minimumSizeHint(self):
        # Suggest a minimum reasonable size
        return QSize(int(self._ring_thickness * 4), int(self._ring_thickness * 4)) # Uses QSize

    def sizeHint(self):
         # Default size hint
        return QSize(100, 100) # Uses QSize

    # --- Painting ---
    def paintEvent(self, event):
        """Handles the painting of the circular progress ring."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Smooth edges

        rect = QRectF(self.rect()) # Get widget's rectangle as float
        # Inset the rectangle for drawing by half the pen width to avoid clipping
        inset = self._ring_thickness / 2.0
        rect.adjust(inset, inset, -inset, -inset)

        # Calculate angles (angles in 1/16th of a degree for QPainter.drawArc)
        # Ensure maximum isn't equal to minimum to avoid division by zero
        range_value = (self._maximum - self._minimum)
        if range_value == 0:
            range_value = 1 # Avoid division by zero

        # Map value to angle (0-360 degrees)
        progress_angle = (self._value - self._minimum) * 360.0 / range_value
        span_angle = int(progress_angle * 16) # Convert to 1/16th degrees

        start_angle = 90 * 16 # Start at the top (12 o'clock)

        # --- Draw Background Ring ---
        bg_pen = QPen(self._background_color)
        bg_pen.setWidthF(self._ring_thickness)
        bg_pen.setCapStyle(Qt.PenCapStyle.FlatCap) # Or RoundCap for rounded ends
        painter.setPen(bg_pen)
        # Draw the full circle background arc
        painter.drawArc(rect, 0, 360 * 16) # Full circle

        # --- Draw Progress Arc ---
        prog_pen = QPen(self._progress_color)
        prog_pen.setWidthF(self._ring_thickness)
        prog_pen.setCapStyle(Qt.PenCapStyle.FlatCap) # Match background cap style
        painter.setPen(prog_pen)
        # Draw the progress arc over the background
        painter.drawArc(rect, start_angle, -span_angle) # Negative span draws clockwise

        # --- Draw Text ---
        text = f"{self.value}%"
        font = self.font()
        # Adjust font size based on widget height for responsiveness
        font_pixel_size = int(self.height() * self._font_size_factor)
        font.setPixelSize(max(8, font_pixel_size)) # Minimum font size of 8
        painter.setFont(font)

        fm = QFontMetrics(font)
        # text_rect = fm.boundingRect(text) # Not strictly needed if using drawText with alignment
        text_pen = QPen(self._text_color)
        painter.setPen(text_pen)

        # Center the text in the original widget rectangle (self.rect())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        painter.end()