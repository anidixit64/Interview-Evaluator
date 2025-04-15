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
import math # Import math for ceiling function

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

    # Define Visual Percentage Limits for the Arc
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
            self._maximum = max(value, self._minimum) # Prevent max < min
            self.update()

    @pyqtProperty(int)
    def value(self):
        return self._value

    def setValue(self, value):
        # Clamp value within the defined min/max range
        clamped_value = max(self._minimum, min(value, self._maximum))
        if self._value != clamped_value:
            self._value = clamped_value
            self.update() # Trigger repaint

    @pyqtProperty(bool)
    def showText(self):
        return self._show_text

    def setShowText(self, show: bool):
        """Sets whether the percentage text is displayed."""
        if self._show_text != show:
            self._show_text = show
            self.update()

    # --- Appearance Customization Methods ---
    def setBackgroundColor(self, color: QColor):
         """Sets the color of the background track."""
         if self._background_color != color:
            self._background_color = color
            self.update()

    def setTextColor(self, color: QColor):
        """Sets the color of the text (if shown)."""
        if self._text_color != color:
            self._text_color = color
            if self._show_text: # Only update if text is visible
                self.update()

    def setRingThickness(self, thickness: float):
         """Sets the thickness of the progress ring."""
         if self._ring_thickness != thickness:
            self._ring_thickness = max(1.0, thickness) # Ensure minimum thickness
            self.update()

    # --- Range Setting ---
    def setRange(self, minimum: int, maximum: int):
        """Sets the minimum and maximum values for the progress ring."""
        if maximum < minimum:
            maximum = minimum # Ensure max is not less than min
        if minimum != self._minimum or maximum != self._maximum:
            self._minimum = minimum
            self._maximum = maximum
            # Re-clamp current value to new range and update
            self.setValue(self._value)

    # --- Size Hints ---
    def minimumSizeHint(self):
        """Suggests a minimum reasonable size."""
        # Base size on thickness, add padding for text/appearance
        min_dim = int(self._ring_thickness * 4) + 20
        return QSize(min_dim, min_dim)

    def sizeHint(self):
        """Suggests a default size."""
        return QSize(100, 100)

    # --- Painting ---
    def paintEvent(self, event):
        """Handles the painting of the circular progress ring."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Enable anti-aliasing

        # Calculate drawing rectangle, inset by half pen width
        rect = QRectF(self.rect())
        inset = self._ring_thickness / 2.0
        rect.adjust(inset, inset, -inset, -inset)

        # --- Calculate RAW Percentage (for Color and Text) ---
        range_value = self._maximum - self._minimum
        raw_percentage = 0.0
        if range_value > 0:
            # Calculate the actual percentage based on value relative to range
            raw_percentage = (self._value - self._minimum) * 100.0 / range_value
        elif self._value >= self._maximum: # Handle edge case where min == max
             raw_percentage = 100.0

        # Clamp raw_percentage just in case of floating point issues
        raw_percentage = max(0.0, min(raw_percentage, 100.0))

        # --- Determine Progress Color (Based on RAW Percentage) ---
        target_progress_color = self.COLOR_RED # Default to red for <= 40%
        if raw_percentage > 90:
            target_progress_color = self.COLOR_BRIGHT_GREEN
        elif raw_percentage > 80:
            target_progress_color = self.COLOR_LIME_GREEN
        elif raw_percentage > 60:
            target_progress_color = self.COLOR_YELLOW
        elif raw_percentage > 40:
            target_progress_color = self.COLOR_ORANGE
        # else: remains COLOR_RED (already set)

        # --- Calculate VISUAL Angle Span (Mapping Value Range to Visual 1%-97%) ---
        # Start with 0 visual percentage, only calculate if value is above minimum
        visual_percentage = 0.0
        if range_value > 0:
            if self._value > self._minimum: # Map only if value is strictly above minimum
                visual_percentage_range = self.VISUAL_MAX_PERCENT - self.VISUAL_MIN_PERCENT # e.g., 96.0
                # Calculate how far the value is within the range (0.0 to 1.0)
                value_fraction = (self._value - self._minimum) / range_value
                # Linearly map the fraction to the visual range (e.g., 1% to 97%)
                visual_percentage = self.VISUAL_MIN_PERCENT + (value_fraction * visual_percentage_range)
        elif self._value >= self._maximum: # Handle min == max edge case
             visual_percentage = self.VISUAL_MAX_PERCENT # Show full visual range

        # Ensure visual percentage doesn't exceed the defined maximum visual limit
        visual_percentage = min(visual_percentage, self.VISUAL_MAX_PERCENT)
        # Ensure visual percentage doesn't fall below the minimum if value > min
        if self._value > self._minimum:
             visual_percentage = max(visual_percentage, self.VISUAL_MIN_PERCENT)


        # Calculate angle span in degrees based on the VISUAL percentage
        visual_angle_degrees = visual_percentage * 360.0 / 100.0
        # Convert to 1/16th degrees for QPainter. Use ceiling for minimal visibility if > 0.
        span_angle_16th = math.ceil(visual_angle_degrees * 16) if visual_percentage > 0 else 1

        # Define the start angle (top of the circle)
        start_angle_16th = 90 * 16 # 12 o'clock position

        # --- Draw Background Ring ---
        bg_pen = QPen(self._background_color)
        bg_pen.setWidthF(self._ring_thickness)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap) # Rounded ends
        painter.setPen(bg_pen)
        # Draw the full 360-degree background arc
        painter.drawArc(rect, 0, 360 * 16)

        # --- Draw Progress Arc (Based on VISUAL Angle) ---
        # Draw only if the calculated visual angle span is greater than zero
        if span_angle_16th > 0:
            prog_pen = QPen(target_progress_color) # Color determined by raw percentage
            prog_pen.setWidthF(self._ring_thickness)
            prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap) # Rounded ends
            painter.setPen(prog_pen)
            # Draw the progress arc clockwise (-span_angle) from the start angle
            painter.drawArc(rect, start_angle_16th, -span_angle_16th)

        # --- Draw Text (Based on RAW Value/Percentage) ---
        if self._show_text:
            # Display the raw percentage value, rounded to integer
            text = f"{int(round(raw_percentage))}%"

            font = self.font()
            # Adjust font size based on widget height
            font_pixel_size = int(self.height() * self._font_size_factor)
            font.setPixelSize(max(8, font_pixel_size)) # Set minimum font size
            painter.setFont(font)

            # Set text color and draw centered text
            text_pen = QPen(self._text_color)
            painter.setPen(text_pen)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        painter.end() # Finish painting