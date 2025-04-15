# ui/loading_page.py
"""
Defines the Loading Page QWidget for the Interview App.
Displayed while results are being generated.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QFrame
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# Optional: Import spinner/progress widget if desired later
# from .circular_progress_ring import CircularProgressBarRing

class LoadingPage(QWidget):
    """
    A simple page displaying a 'Generating Results...' message.
    """
    def __init__(self, parent_window, *args, **kwargs):
        """Initializes the LoadingPage."""
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI elements."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(50, 50, 50, 50) # Add some padding
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center content

        pw = self.parent_window

        # Use a large font, consistent with setup page titles or similar
        font_loading = getattr(pw, 'font_group_title_xxl', QFont("Arial", 18, QFont.Weight.Bold))

        loading_label = QLabel("Generating Results...")
        loading_label.setFont(font_loading)
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.setWordWrap(True)
        loading_label.setObjectName("loadingLabel")

        # Optional: Add a visual indicator like a spinner later
        # self.spinner = CircularProgressBarRing() # Example
        # self.spinner.setFixedSize(150, 150)
        # self.spinner.setRange(0, 0) # Indeterminate mode

        page_layout.addStretch(1) # Push content down
        page_layout.addWidget(loading_label)
        # if hasattr(self, 'spinner'):
        #     page_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        page_layout.addStretch(2) # More stretch below to center vertically

        self.setLayout(page_layout)

    def clear_fields(self):
        """Placeholder - nothing to clear on this static page."""
        pass

    def update_widgets_from_state(self):
        """Placeholder - nothing state-dependent to update."""
        pass