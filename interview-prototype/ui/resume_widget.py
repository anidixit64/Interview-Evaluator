# ui/resume_widget.py
"""
Defines the ResumeWidget, a clickable widget for displaying
and selecting a recently used resume.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor, QPalette # Added QPalette
from PyQt6.QtCore import Qt, QSize, pyqtSignal # Added Qt, QSize, pyqtSignal

class ResumeWidget(QFrame):
    """
    A clickable frame representing a single resume entry in the list.
    Emits a signal with its data when clicked.
    """
    # Signal emitting the data dictionary {'name': str, 'path': str}
    resume_selected = pyqtSignal(dict)

    def __init__(self, resume_data: dict, parent_widget: QWidget, parent=None):
        """
        Args:
            resume_data: Dictionary {"name": str, "path": str}.
            parent_widget: The main SetupPage instance (for accessing fonts/parent window).
            parent: The parent QWidget.
        """
        super().__init__(parent)
        self.resume_data = resume_data
        self.parent_widget = parent_widget # Usually the SetupPage
        self._is_selected = False

        # --- Appearance ---
        self.setObjectName("resumeEntryWidget") # For QSS styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised) # Default shadow
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Set minimum height to ensure visibility
        self.setMinimumHeight(35)

        # --- Layout & Content ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) # Padding
        layout.setSpacing(10)

        # TODO: Add an icon? e.g., a document icon
        # icon_label = QLabel()
        # icon_label.setPixmap(...)
        # layout.addWidget(icon_label)

        name = self.resume_data.get("name", "Unknown Resume")
        path = self.resume_data.get("path", "No path")

        name_label = QLabel(name)
        # Access font via parent_widget -> parent_window
        name_label.setFont(self.parent_widget.parent_window.font_default)
        name_label.setToolTip(f"Path: {path}") # Show path on hover
        name_label.setObjectName("resumeNameLabel")

        layout.addWidget(name_label, stretch=1) # Allow name to take space

    def mousePressEvent(self, event):
        """Emit the signal when the widget is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.resume_selected.emit(self.resume_data)
        super().mousePressEvent(event) # Call base class implementation

    def set_selected(self, selected: bool):
        """Visually indicate if this widget is the currently selected resume."""
        self._is_selected = selected
        # Update style based on selection state using dynamic properties for QSS
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        # Or change shadow:
        # self.setFrameShadow(QFrame.Shadow.Sunken if selected else QFrame.Shadow.Raised)