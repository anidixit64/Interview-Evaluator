# ui/jd_widget.py
"""
Defines the JDWidget, a clickable widget for displaying
and selecting a recently used Job Description.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor
from PyQt6.QtCore import Qt, QSize, pyqtSignal

class JDWidget(QFrame):
    """
    A clickable frame representing a single JD entry in the list.
    Emits a signal with its data when clicked.
    """
    # Signal emitting the data dictionary {'name': str, 'text': str}
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
        self.parent_widget = parent_widget # Usually the SetupPage
        self._is_selected = False

        # --- Appearance ---
        self.setObjectName("jdEntryWidget") # For QSS styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised) # Default shadow
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(30) # Adjust height as needed

        # --- Layout & Content ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) # Padding
        layout.setSpacing(10)

        # TODO: Maybe a briefcase or document icon?
        # icon_label = QLabel()
        # icon_label.setPixmap(...)
        # layout.addWidget(icon_label)

        name = self.jd_data.get("name", "Unnamed Job Description")
        text_preview = self.jd_data.get("text", "")[:80] + "..." # Show preview in tooltip

        name_label = QLabel(name)
        # Access font via parent_widget -> parent_window
        name_label.setFont(self.parent_widget.parent_window.font_default)
        name_label.setToolTip(f"Preview: {text_preview}") # Show preview on hover
        name_label.setObjectName("jdNameLabel")

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
        self.style().unpolish(self)
        self.style().polish(self)