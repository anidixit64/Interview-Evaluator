# ui/loading_page.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QFrame
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

class LoadingPage(QWidget):
    
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._init_ui()

    def _init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(50, 50, 50, 50)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pw = self.parent_window

        font_loading = getattr(pw, 'font_group_title_xxl', QFont("Arial", 18, QFont.Weight.Bold))

        loading_label = QLabel("Generating Results...")
        loading_label.setFont(font_loading)
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.setWordWrap(True)
        loading_label.setObjectName("loadingLabel")

        page_layout.addStretch(1)
        page_layout.addWidget(loading_label)
         
        page_layout.addStretch(2)

        self.setLayout(page_layout)

    def clear_fields(self):
        pass

    def update_widgets_from_state(self):
        pass