# ui/jd_widget.py
"""
Defines the JDWidget, a clickable widget for displaying
and selecting a recently used Job Description. Uses larger font.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor
from PyQt6.QtCore import Qt, QSize, pyqtSignal

class JDWidget(QFrame):
    """
    A clickable frame representing a single JD entry in the list.
    Emits a signal with its data when clicked. Uses larger font size.
    """
    jd_selected = pyqtSignal(dict)

    def __init__(self, jd_data: dict, parent_widget: QWidget, parent=None):
        """
        Args:
            jd_data: Dictionary {"name": str, "text": str}.
            parent_widget: The main SetupPage instance (for accessing fonts/parent window).
            parent: The parent QWidget.
        """
        super().__init__(parent)
        self.jd_data = jd_data
        # parent_widget is SetupPage, parent_widget.parent_window is MainWindow
        self.parent_window = parent_widget.parent_window
        self._is_selected = False

        # --- Appearance ---
        self.setObjectName("jdEntryWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Increase minimum height significantly for larger font
        self.setMinimumHeight(55) # Increased height

        # --- Layout & Content ---
        layout = QHBoxLayout(self)
         # Increased padding for larger text
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(15) # Increased spacing

        name = self.jd_data.get("name", "Unnamed Job Description")
        text_preview = self.jd_data.get("text", "")[:80] + "..."

        name_label = QLabel(name)
        # *** Use the XXL font from MainWindow ***
        font_to_use = self.parent_window.font_default # Fallback
        if hasattr(self.parent_window, 'font_default_xxl'):
            font_to_use = self.parent_window.font_default_xxl
        name_label.setFont(font_to_use) # Apply the large font

        name_label.setToolTip(f"Preview: {text_preview}")
        name_label.setObjectName("jdNameLabel")
        name_label.setWordWrap(True) # Allow wrapping

        layout.addWidget(name_label, stretch=1)

    def mousePressEvent(self, event):
        """Emit the signal when the widget is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.jd_selected.emit(self.jd_data)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        """Visually indicate if this widget is the currently selected JD."""
        self._is_selected = selected
        self.setProperty("selected", selected)
        # Re-polish to apply QSS changes based on the 'selected' property
        self.style().unpolish(self)
        self.style().polish(self)
