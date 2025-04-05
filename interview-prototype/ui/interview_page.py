# ui/interview_page.py
"""
Defines the Interview Page QWidget for the Interview App.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QGroupBox, QSizePolicy, QFrame
)
from PyQt6.QtGui import QFont, QIcon # Added QIcon
from PyQt6.QtCore import Qt, QSize

# Import shared components
from .components import _load_icon

class InterviewPage(QWidget):
    """
    The main interview page showing question, answer input, and history.
    """
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        # Load icons needed for dynamic button state changes
        self._load_dynamic_icons()
        self._init_ui()

    def _load_dynamic_icons(self):
        """Load icons used for the submit/record button states."""
        pw = self.parent_window
        # Load and store icons on this page instance
        self.submit_icon = _load_icon(pw.icon_path, "send.png")
        self.record_icon = _load_icon(pw.icon_path, "mic_black_36dp.png")
        self.listening_icon = _load_icon(pw.icon_path, "record_wave.png")
        self.processing_icon = _load_icon(pw.icon_path, "spinner.png")

    def _init_ui(self):
        """Initialize the UI elements for the interview page."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(15)

        pw = self.parent_window # Shortcut

        # --- Interview Area ---
        interview_group = QGroupBox("Interview")
        interview_group.setFont(pw.font_large_bold)
        interview_layout = QVBoxLayout(interview_group)
        interview_layout.setSpacing(10)

        current_q_label = QLabel("Interviewer Question:")
        current_q_label.setFont(pw.font_bold)
        # Assign widgets to self
        self.current_q_text = QTextEdit()
        self.current_q_text.setReadOnly(True)
        self.current_q_text.setFont(pw.font_default)
        self.current_q_text.setObjectName("interviewerQuestion")
        self.current_q_text.setMinimumHeight(80)
        self.current_q_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)

        answer_label = QLabel("Your Answer:")
        answer_label.setFont(pw.font_bold)
        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Type answer or use record...")
        self.answer_input.setFont(pw.font_default)
        self.answer_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Submit/Record Button
        self.submit_button = QPushButton("Submit Answer") # Initial text
        self.submit_button.setObjectName("recordSubmitButton")
        # Initial icon set by parent_window logic (update_submit_button_text/set_recording_button_state)
        self.submit_button.setIconSize(pw.icon_size)
        self.submit_button.setFont(pw.font_bold)
        self.submit_button.clicked.connect(pw.handle_answer_submission) # Connect to parent's slot
        self.submit_button.setFixedHeight(35)
        submit_button_layout = QHBoxLayout()
        submit_button_layout.addStretch()
        submit_button_layout.addWidget(self.submit_button)
        submit_button_layout.addStretch()

        interview_layout.addWidget(current_q_label)
        interview_layout.addWidget(self.current_q_text)
        interview_layout.addWidget(line1)
        interview_layout.addWidget(answer_label)
        interview_layout.addWidget(self.answer_input)
        interview_layout.addLayout(submit_button_layout)

        page_layout.addWidget(interview_group, stretch=3)

        # --- Separator ---
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        page_layout.addWidget(line2)

        # --- History/Transcript Area ---
        history_group = QGroupBox("Transcript")
        history_group.setFont(pw.font_large_bold)
        history_layout = QVBoxLayout(history_group)
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setFont(pw.font_history)
        self.history_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        history_layout.addWidget(self.history_text)
        page_layout.addWidget(history_group, stretch=2)

        self.setLayout(page_layout)

    def clear_fields(self):
        """Clears dynamic fields on this page."""
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()

    def set_controls_enabled(self, enabled, is_recording_stt=False):
        """Enable or disable interview input controls."""
        if hasattr(self, 'answer_input'):
            text_input_enabled = not self.parent_window.use_speech_input
            # Enable widget, but set read-only based on mode if enabled=True
            self.answer_input.setEnabled(enabled)
            if enabled:
                self.answer_input.setReadOnly(not text_input_enabled)
            else:
                 self.answer_input.setReadOnly(True) # Always read-only when disabled

        if hasattr(self, 'submit_button'):
            self.submit_button.setEnabled(enabled)

        # Update button state/icon if enabling/disabling (unless disabled for recording)
        if not is_recording_stt:
             # Let parent window handle button state update via set_recording_button_state
             # which will access the icons stored here.
             pass

    def update_widgets_from_state(self):
        """Updates widgets based on parent_window's state (e.g., display question)."""
        pw = self.parent_window
        if hasattr(self, 'current_q_text'):
            # Only update if different to avoid resetting cursor/selection?
            if self.current_q_text.toPlainText() != pw.last_question_asked:
                 self.current_q_text.setPlainText(pw.last_question_asked)

        # History is updated via parent_window.add_to_history which accesses self.history_text
        # Answer input placeholder/focus is handled by parent_window methods like display_question
        # Button state/text/icon is handled by parent_window.set_recording_button_state