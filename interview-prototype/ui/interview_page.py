# ui/interview_page.py
"""
Defines the Interview Page QWidget for the Interview App.
Displays question details, and switches between a webcam view (for STT)
or a text input box (for typing).
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QGroupBox, QSizePolicy, QFrame, QSpacerItem, QStackedLayout 
)
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QSize

try:
    from .components import _load_icon
except ImportError:
    from ui.components import _load_icon


class InterviewPage(QWidget):
    """
    The main interview page showing question details and either webcam feed or text input.
    """
    def __init__(self, parent_window, *args, **kwargs):
        """Initializes the InterviewPage."""
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._load_dynamic_icons()
        self._init_ui()
        self.set_input_mode(use_speech=False)

    def _load_dynamic_icons(self):
        """Load icons used for the submit/record button states."""
        pw = self.parent_window
        icon_path = getattr(pw, 'icon_path', 'icons')

        self.submit_icon = _load_icon(icon_path, "send.png")
        self.record_icon = _load_icon(icon_path, "mic_black_36dp.png")
        self.listening_icon = _load_icon(icon_path, "record_wave.png")
        self.processing_icon = _load_icon(icon_path, "spinner.png")

    def _init_ui(self):
        """Initialize the UI elements for the interview page."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(20, 20, 20, 20)
        page_layout.setSpacing(15) 

        pw = self.parent_window

        # --- Fonts ---
        font_large_bold = getattr(pw, 'font_large_bold', QFont("Arial", 12, QFont.Weight.Bold))
        font_bold = getattr(pw, 'font_bold', QFont("Arial", 10, QFont.Weight.Bold))
        font_default = getattr(pw, 'font_default', QFont("Arial", 10))
        base_size = font_default.pointSize()
        font_question_display = QFont(font_default.family(), base_size + 14)
        font_question_number = font_large_bold
        icon_size = getattr(pw, 'icon_size', QSize(20, 20))

        # --- Top Section (Question Number & Text) ---
        self.question_number_label = QLabel("Question -/-")
        self.question_number_label.setFont(font_question_number)
        self.question_number_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.question_number_label.setObjectName("questionNumberLabel")
        page_layout.addWidget(self.question_number_label)

        self.question_text_label = QLabel("Waiting for question...")
        self.question_text_label.setFont(font_question_display)
        self.question_text_label.setWordWrap(True)
        self.question_text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.question_text_label.setObjectName("questionTextLabel")
        self.question_text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        page_layout.addWidget(self.question_text_label)

        # --- Separator ---
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        page_layout.addSpacerItem(
            QSpacerItem(20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        page_layout.addWidget(line1)
        page_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        answer_label = QLabel("Your Answer:")
        answer_label.setFont(font_bold)
        answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        page_layout.addWidget(answer_label)

        # Container for the stacked layout
        self.input_area_container = QWidget()
        self.input_area_stack = QStackedLayout(self.input_area_container)
        self.input_area_stack.setContentsMargins(0,0,0,0)

        # -- Webcam View --
        self.webcam_view_label = QLabel("Webcam feed inactive")
        self.webcam_view_label.setObjectName("webcamViewLabel")
        self.webcam_view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.webcam_view_label.setMinimumSize(320, 240)
        placeholder_pixmap = QPixmap(self.webcam_view_label.minimumSize())
        placeholder_pixmap.fill(QColor("black"))
        painter = QPainter(placeholder_pixmap)
        painter.setPen(QColor("grey"))
        painter.setFont(font_default)
        painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Webcam View (STT Mode)")
        painter.end()
        self.webcam_view_label.setPixmap(placeholder_pixmap)
        self.webcam_view_label.setSizePolicy(
             QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.input_area_stack.addWidget(self.webcam_view_label)

        # -- Text Input --
        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Type answer here...")
        self.answer_input.setFont(font_default)
        self.answer_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.answer_input.setMinimumHeight(150) 
        self.input_area_stack.addWidget(self.answer_input)

       
        page_layout.addWidget(self.input_area_container, stretch=8)


        bottom_area_layout = QVBoxLayout()
        bottom_area_layout.setContentsMargins(0, 15, 0, 0)
        bottom_area_layout.setSpacing(0)

        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.setObjectName("recordSubmitButton")
        self.submit_button.setIconSize(icon_size)
        self.submit_button.setFont(font_bold)
        self.submit_button.clicked.connect(pw.handle_answer_submission)
        self.submit_button.setFixedHeight(45)
        self.submit_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        button_centering_layout = QHBoxLayout()
        button_centering_layout.addStretch(1)
        button_centering_layout.addWidget(self.submit_button)
        button_centering_layout.addStretch(1)

        bottom_area_layout.addLayout(button_centering_layout)
        bottom_area_layout.addStretch(1)

        page_layout.addLayout(bottom_area_layout, stretch=2) 

        self.setLayout(page_layout)

    def set_input_mode(self, use_speech: bool):
        """Switches the input area between webcam view and text edit."""
        if not hasattr(self, 'input_area_stack'):
            return 

        if use_speech:
            self.input_area_stack.setCurrentIndex(0)
            print("InterviewPage: Switched to Webcam View")
        else:
            self.input_area_stack.setCurrentIndex(1)
            print("InterviewPage: Switched to Text Input")

    def clear_fields(self):
        """Clears dynamic fields on this page."""
        if hasattr(self, 'question_number_label'):
            self.question_number_label.setText("Question -/-")
        if hasattr(self, 'question_text_label'):
            self.question_text_label.setText("Waiting for question...")
        if hasattr(self, 'answer_input'):
            self.answer_input.clear()
        # Reset webcam view to placeholder
        if hasattr(self, 'webcam_view_label'):
            placeholder_pixmap = QPixmap(self.webcam_view_label.minimumSize())
            placeholder_pixmap.fill(QColor("black"))
            painter = QPainter(placeholder_pixmap)
            painter.setPen(QColor("grey"))
            painter.setFont(getattr(self.parent_window, 'font_default', QFont()))
            painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Webcam View (STT Mode)")
            painter.end()
            self.webcam_view_label.setPixmap(placeholder_pixmap)


    def set_controls_enabled(self, enabled: bool, is_recording_stt: bool = False):
        """Enable or disable interview input controls."""
        is_text_mode = not self.parent_window.use_speech_input
        if hasattr(self, 'answer_input'):
            self.answer_input.setEnabled(enabled and is_text_mode)
            self.answer_input.setReadOnly(not (enabled and is_text_mode))

        if hasattr(self, 'submit_button'):
            self.submit_button.setEnabled(enabled)


    def update_widgets_from_state(self):
        """Updates widgets based on parent_window's state."""
        pw = self.parent_window
        if hasattr(self, 'question_text_label'):
            if self.question_text_label.text() != pw.last_question_asked:
                if pw.last_question_asked:
                    self.question_text_label.setText(pw.last_question_asked)
                else:
                    self.question_text_label.setText("Waiting for question...")

    def display_question_ui(self, number_text: str, question_text: str):
        """Updates the UI labels with the new question details."""
        if hasattr(self, 'question_number_label'):
            self.question_number_label.setText(number_text)
        if hasattr(self, 'question_text_label'):
            self.question_text_label.setText(question_text)
            self.question_text_label.updateGeometry()

    def set_webcam_frame(self, pixmap: QPixmap | None):
        """Sets the pixmap on the webcam view label."""
        if hasattr(self, 'webcam_view_label'):
            if pixmap and not pixmap.isNull():
                self.webcam_view_label.setPixmap(pixmap.scaled(
                    self.webcam_view_label.size(), 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                 placeholder_pixmap = QPixmap(self.webcam_view_label.minimumSize())
                 placeholder_pixmap.fill(QColor("black"))
                 painter = QPainter(placeholder_pixmap)
                 painter.setPen(QColor("grey"))
                 painter.setFont(getattr(self.parent_window, 'font_default', QFont()))
                 painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Signal / Stopped")
                 painter.end()
                 self.webcam_view_label.setPixmap(placeholder_pixmap)