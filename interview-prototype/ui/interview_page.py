# ui/interview_page.py
"""
Defines the Interview Page QWidget for the Interview App.
Displays the question number/status, the large left-justified question text,
an answer input area that expands, and a submit button centered in
a reserved space at the bottom.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QGroupBox, QSizePolicy, QFrame, QSpacerItem
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt, QSize

# Import shared components
try:
    from .components import _load_icon
except ImportError:
    from ui.components import _load_icon


class InterviewPage(QWidget):
    """
    The main interview page showing question details, expanding answer input,
    and a submit button in a bottom reserved area.
    """
    def __init__(self, parent_window, *args, **kwargs):
        """Initializes the InterviewPage."""
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._load_dynamic_icons()
        self._init_ui()

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
        # --- Main Vertical Layout for the Page ---
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(20, 20, 20, 20) # Overall padding
        page_layout.setSpacing(15) # Spacing between main sections

        pw = self.parent_window

        # --- Fonts ---
        font_large_bold = getattr(pw, 'font_large_bold', QFont("Arial", 12, QFont.Weight.Bold))
        font_bold = getattr(pw, 'font_bold', QFont("Arial", 10, QFont.Weight.Bold))
        font_default = getattr(pw, 'font_default', QFont("Arial", 10))
        base_size = font_default.pointSize()
        font_question_display = QFont(font_default.family(), base_size + 14)
        font_question_number = font_large_bold
        icon_size = getattr(pw, 'icon_size', QSize(20, 20))

        # --- Question Number/Status Label ---
        self.question_number_label = QLabel("Question -/-")
        self.question_number_label.setFont(font_question_number)
        self.question_number_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.question_number_label.setObjectName("questionNumberLabel")
        page_layout.addWidget(self.question_number_label) # Add to top

        # --- Large Question Text Display Label ---
        self.question_text_label = QLabel("Waiting for question...")
        self.question_text_label.setFont(font_question_display)
        self.question_text_label.setWordWrap(True)
        self.question_text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.question_text_label.setObjectName("questionTextLabel")
        # Allow horizontal expansion, minimum vertical expansion
        self.question_text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        page_layout.addWidget(self.question_text_label) # Add below number

        # --- Separator ---
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        # Add separator with some spacing
        page_layout.addSpacerItem(
            QSpacerItem(20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        page_layout.addWidget(line1)
        page_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        # --- Answer Section ---
        answer_label = QLabel("Your Answer:")
        answer_label.setFont(font_bold)
        # Left-align the "Your Answer:" label
        answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        page_layout.addWidget(answer_label) # Add below separator

        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Type answer or use record...")
        self.answer_input.setFont(font_default)
        # Allow answer input to expand vertically and horizontally
        self.answer_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Assign stretch factor here to take up most space before bottom area
        page_layout.addWidget(self.answer_input, stretch=8) # e.g., 80% of stretch

        # --- Bottom Area (Submit Button Centered in Empty Space) ---
        bottom_area_layout = QVBoxLayout()
        bottom_area_layout.setContentsMargins(0, 15, 0, 0) # Add some top margin
        bottom_area_layout.setSpacing(0)

        # -- Submit Button Layout (Centered Horizontally) --
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.setObjectName("recordSubmitButton")
        self.submit_button.setIconSize(icon_size)
        self.submit_button.setFont(font_bold)
        self.submit_button.clicked.connect(pw.handle_answer_submission)
        self.submit_button.setFixedHeight(45)
        # Don't let button expand horizontally
        self.submit_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        button_centering_layout = QHBoxLayout()
        button_centering_layout.addStretch(1)
        button_centering_layout.addWidget(self.submit_button)
        button_centering_layout.addStretch(1)

        # Add button layout to the bottom area layout
        bottom_area_layout.addLayout(button_centering_layout)
        # Add stretch below the button to create the empty space
        bottom_area_layout.addStretch(1) # This stretch defines the empty space height visually

        # Add the bottom area layout to the main page layout
        # The stretch factor here determines its proportion relative to answer_input
        page_layout.addLayout(bottom_area_layout, stretch=2) # e.g., 20% of stretch

        self.setLayout(page_layout)

    def clear_fields(self):
        """Clears dynamic fields on this page."""
        if hasattr(self, 'question_number_label'):
            self.question_number_label.setText("Question -/-")
        if hasattr(self, 'question_text_label'):
            self.question_text_label.setText("Waiting for question...")
        if hasattr(self, 'answer_input'):
            self.answer_input.clear()

    def set_controls_enabled(self, enabled: bool, is_recording_stt: bool = False):
        """Enable or disable interview input controls."""
        if hasattr(self, 'answer_input'):
            text_input_editable = not self.parent_window.use_speech_input
            self.answer_input.setEnabled(enabled)
            if enabled:
                self.answer_input.setReadOnly(not text_input_editable)
            else:
                self.answer_input.setReadOnly(True)

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
            self.question_text_label.updateGeometry() # Hint geometry change