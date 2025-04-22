# ui/circular_progress_ring.py
"""
Custom QWidget for displaying a circular ring progress indicator.
Color changes dynamically based on value percentage.
Arc ends are rounded.
Visual arc length is limited to 1% - 97% range.
"""
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QRectF, pyqtProperty, QSize
import math 

class CircularProgressBarRing(QWidget):
    """
    A widget that draws a circular progress ring with rounded ends.
    The progress color dynamically changes based on the value.
    The visual arc length maps the value range to a visual 1% to 97% range.
    """
    # Define Colors
    COLOR_BRIGHT_GREEN = QColor(60, 220, 60)    # > 90%
    COLOR_LIME_GREEN = QColor(150, 230, 50)   # > 80%
    COLOR_YELLOW = QColor(255, 210, 0)      # > 60%
    COLOR_ORANGE = QColor(255, 140, 0)      # > 40%
    COLOR_RED = QColor(220, 50, 50)         # <= 40%

    VISUAL_MIN_PERCENT = 1.0
    VISUAL_MAX_PERCENT = 97.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0

        # Customizable properties
        self._background_color = QColor(53, 53, 53)
        self._text_color = QColor(220, 220, 220)
        self._ring_thickness = 12.0
        self._font_size_factor = 0.3
        self._show_text = True

        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    # --- Properties ---
    @pyqtProperty(int)
    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        if self._minimum != value:
            self._minimum = value
            self.update()

    @pyqtProperty(int)
    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        if self._maximum != value:
            self._maximum = max(value, self._minimum) 
            self.update()

    @pyqtProperty(int)
    def value(self):
        return self._value

    def setValue(self, value):
        clamped_value = max(self._minimum, min(value, self._maximum))
        if self._value != clamped_value:
            self._value = clamped_value
            self.update() 

    @pyqtProperty(bool)
    def showText(self):
        return self._show_text

    def setShowText(self, show: bool):
        """Sets whether the percentage text is displayed."""
        if self._show_text != show:
            self._show_text = show
            self.update()

    def setBackgroundColor(self, color: QColor):
         """Sets the color of the background track."""
         if self._background_color != color:
            self._background_color = color
            self.update()

    def setTextColor(self, color: QColor):
        """Sets the color of the text (if shown)."""
        if self._text_color != color:
            self._text_color = color
            if self._show_text: 
                self.update()

    def setRingThickness(self, thickness: float):
         """Sets the thickness of the progress ring."""
         if self._ring_thickness != thickness:
            self._ring_thickness = max(1.0, thickness)
            self.update()

    def setRange(self, minimum: int, maximum: int):
        """Sets the minimum and maximum values for the progress ring."""
        if maximum < minimum:
            maximum = minimum
        if minimum != self._minimum or maximum != self._maximum:
            self._minimum = minimum
            self._maximum = maximum
            self.setValue(self._value)

    def minimumSizeHint(self):
        """Suggests a minimum reasonable size."""
        min_dim = int(self._ring_thickness * 4) + 20
        return QSize(min_dim, min_dim)

    def sizeHint(self):
        """Suggests a default size."""
        return QSize(100, 100)

    def paintEvent(self, event):
        """Handles the painting of the circular progress ring."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) 

        rect = QRectF(self.rect())
        inset = self._ring_thickness / 2.0
        rect.adjust(inset, inset, -inset, -inset)

        range_value = self._maximum - self._minimum
        raw_percentage = 0.0
        if range_value > 0:
            raw_percentage = (self._value - self._minimum) * 100.0 / range_value
        elif self._value >= self._maximum:
             raw_percentage = 100.0

        raw_percentage = max(0.0, min(raw_percentage, 100.0))

        target_progress_color = self.COLOR_RED 
        if raw_percentage > 90:
            target_progress_color = self.COLOR_BRIGHT_GREEN
        elif raw_percentage > 80:
            target_progress_color = self.COLOR_LIME_GREEN
        elif raw_percentage > 60:
            target_progress_color = self.COLOR_YELLOW
        elif raw_percentage > 40:
            target_progress_color = self.COLOR_ORANGE
       
        visual_percentage = 0.0
        if range_value > 0:
            if self._value > self._minimum:
                visual_percentage_range = self.VISUAL_MAX_PERCENT - self.VISUAL_MIN_PERCENT 
                value_fraction = (self._value - self._minimum) / range_value
                visual_percentage = self.VISUAL_MIN_PERCENT + (value_fraction * visual_percentage_range)
        elif self._value >= self._maximum:
             visual_percentage = self.VISUAL_MAX_PERCENT

        visual_percentage = min(visual_percentage, self.VISUAL_MAX_PERCENT)
        if self._value > self._minimum:
             visual_percentage = max(visual_percentage, self.VISUAL_MIN_PERCENT)


        visual_angle_degrees = visual_percentage * 360.0 / 100.0
        span_angle_16th = math.ceil(visual_angle_degrees * 16) if visual_percentage > 0 else 1

        start_angle_16th = 90 * 16 

        bg_pen = QPen(self._background_color)
        bg_pen.setWidthF(self._ring_thickness)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap) 
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if span_angle_16th > 0:
            prog_pen = QPen(target_progress_color) 
            prog_pen.setWidthF(self._ring_thickness)
            prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap) 
            painter.setPen(prog_pen)
            painter.drawArc(rect, start_angle_16th, -span_angle_16th)

        if self._show_text:
            text = f"{int(round(raw_percentage))}%"

            font = self.font()
            font_pixel_size = int(self.height() * self._font_size_factor)
            font.setPixelSize(max(8, font_pixel_size))
            painter.setFont(font)

            text_pen = QPen(self._text_color)
            painter.setPen(text_pen)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        painter.end()