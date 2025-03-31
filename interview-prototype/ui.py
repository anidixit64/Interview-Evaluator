# ui.py (PyQt6 Version)
# Handles the user interface using PyQt6. Calls logic from logic.py & audio_handler.py

import os
import sys
import queue  # Import queue for STT results

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QCheckBox, QSpinBox,
    QFileDialog, QMessageBox, QDialog, QSizePolicy, QGroupBox, QFrame
)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QTextCursor, QColor, QPalette, QCursor
from PyQt6.QtCore import Qt, QTimer, QSize

# --- Our Existing Modules ---
import core.logic as logic  # Import the logic module
import core.audio_handler as audio_handler  # Import the audio handler
from core.audio_handler import RECORDINGS_DIR  # Import the constant

# --- UI Constants ---
ICON_PATH = "icons"

# Helper function to create separators (optional aesthetic)
def create_separator():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line

class ReviewDialog(QDialog):
    """Dialog to display the final review and assessment."""
    def __init__(self, summary, assessment, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review & Assessment")
        self.setMinimumSize(800, 750)
        self.setModal(True) # Make it block the main window

        layout = QVBoxLayout(self)

        # Performance Summary Section
        summary_group = QGroupBox("Performance Summary")
        summary_layout = QVBoxLayout()
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Sans Serif", 10))
        self.summary_text.setText(summary or "N/A")
        summary_layout.addWidget(self.summary_text)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Qualification Assessment Section
        assessment_group = QGroupBox("Qualification Assessment")
        assessment_layout = QVBoxLayout()
        self.assessment_text = QTextEdit()
        self.assessment_text.setReadOnly(True)
        self.assessment_text.setFont(QFont("Sans Serif", 10))
        self.assessment_text.setText(assessment or "N/A")
        assessment_layout.addWidget(self.assessment_text)
        assessment_group.setLayout(assessment_layout)
        layout.addWidget(assessment_group)

        # Close Button
        self.close_button = QPushButton("Close & Reset")
        self.close_button.setFont(QFont("Sans Serif", 10, QFont.Weight.Bold))
        self.close_button.setFixedHeight(35)
        # Connect the button click to the dialog's accept slot (which closes it)
        # The actual reset logic will be triggered by the dialog's finished signal in the main app
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout() # Center the button
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)


class InterviewApp(QWidget): # Inherit from QWidget
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000) # x, y, width, height

        # --- Appearance (Optional: Set palette for dark mode hint) ---
        # PyQt inherits system theme by default. Explicit dark mode needs more styling.
        # Let's set a dark background for the main window for a similar feel.
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        # Disabled text color hint
        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)

        self.setPalette(palette)
        QApplication.setStyle("Fusion") # Often looks better across platforms

        # --- Load Icons ---
        self.icon_size = QSize(20, 20)
        self.select_icon = self._load_icon("folder.png", self.icon_size)
        self.start_icon = self._load_icon("play.png", self.icon_size)
        self.submit_icon = self._load_icon("send.png", self.icon_size)
        self.record_icon = self._load_icon("mic_black_36dp.png", self.icon_size) # Assuming a mic icon exists

        # --- Fonts ---
        self.font_default = QFont("Sans Serif", 10)
        self.font_bold = QFont("Sans Serif", 10, QFont.Weight.Bold)
        self.font_small = QFont("Sans Serif", 9)
        self.font_large_bold = QFont("Sans Serif", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9) # Monospace often good for history/code

        # --- State Variables ---
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        # self.num_topics_var (use spinbox directly)
        # self.max_follow_ups_var (use spinbox directly)
        self.num_topics = logic.DEFAULT_NUM_TOPICS
        self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.review_dialog = None # Use QDialog instead of Toplevel
        self.use_speech_input = False # Store the boolean state directly
        self.is_recording = False
        self.stt_timer = QTimer(self) # Timer for checking STT queue

        # --- Main Layout (Vertical) ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Section 1: Setup ---
        setup_group = QGroupBox("Setup")
        setup_group.setFont(self.font_large_bold)
        setup_layout = QGridLayout() # Use Grid for this section
        setup_layout.setSpacing(10)

        # Row 0: Resume
        self.select_btn = QPushButton("Select Resume PDF")
        if self.select_icon: self.select_btn.setIcon(self.select_icon)
        self.select_btn.setIconSize(self.icon_size)
        self.select_btn.setFont(self.font_default)
        self.select_btn.clicked.connect(self.select_resume_file)
        self.file_label = QLineEdit("No resume selected.")
        self.file_label.setFont(self.font_small)
        self.file_label.setReadOnly(True) # Make it non-editable

        setup_layout.addWidget(self.select_btn, 0, 0) # row, col
        setup_layout.addWidget(self.file_label, 0, 1, 1, 3) # row, col, rowspan, colspan

        # Row 1: Job Description
        jd_label = QLabel("Job Description (Optional):")
        jd_label.setFont(self.font_default)
        self.job_desc_input = QTextEdit()
        self.job_desc_input.setPlaceholderText("Paste job description here...")
        self.job_desc_input.setFont(self.font_small)
        self.job_desc_input.setFixedHeight(100) # Set initial height
        self.job_desc_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        setup_layout.addWidget(jd_label, 1, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft) # Align label nicely
        setup_layout.addWidget(self.job_desc_input, 1, 1, 1, 3)

        # Row 2: Configuration (Topics, Followups) in a QHBoxLayout
        config_layout = QHBoxLayout()
        config_layout.setSpacing(10)

        topics_label = QLabel("Topics:")
        topics_label.setFont(self.font_default)
        self.num_topics_spinbox = QSpinBox()
        self.num_topics_spinbox.setRange(logic.MIN_TOPICS, logic.MAX_TOPICS)
        self.num_topics_spinbox.setValue(logic.DEFAULT_NUM_TOPICS)
        self.num_topics_spinbox.setFixedWidth(50)
        self.num_topics_spinbox.setFont(self.font_default)
        self.num_topics_spinbox.valueChanged.connect(self.update_topic_count)

        followups_label = QLabel("Max Follow-ups:")
        followups_label.setFont(self.font_default)
        self.max_follow_ups_spinbox = QSpinBox()
        self.max_follow_ups_spinbox.setRange(logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT)
        self.max_follow_ups_spinbox.setValue(logic.DEFAULT_MAX_FOLLOW_UPS)
        self.max_follow_ups_spinbox.setFixedWidth(50)
        self.max_follow_ups_spinbox.setFont(self.font_default)
        self.max_follow_ups_spinbox.valueChanged.connect(self.update_followup_count)

        config_layout.addWidget(topics_label)
        config_layout.addWidget(self.num_topics_spinbox)
        config_layout.addSpacing(20) # Add space between controls
        config_layout.addWidget(followups_label)
        config_layout.addWidget(self.max_follow_ups_spinbox)
        config_layout.addStretch() # Push controls to the left

        setup_layout.addLayout(config_layout, 2, 0, 1, 4) # Span across columns

        # Row 3: Input Mode Checkbox and Start Button in a QHBoxLayout
        start_layout = QHBoxLayout()
        start_layout.setSpacing(15)
        self.speech_checkbox = QCheckBox("Use Speech Input")
        self.speech_checkbox.setFont(self.font_default)
        self.speech_checkbox.stateChanged.connect(self.update_submit_button_text)

        self.start_interview_btn = QPushButton("Start Interview")
        if self.start_icon: self.start_interview_btn.setIcon(self.start_icon)
        self.start_interview_btn.setIconSize(self.icon_size)
        self.start_interview_btn.setFont(self.font_bold)
        self.start_interview_btn.clicked.connect(self.start_interview_process)

        start_layout.addWidget(self.speech_checkbox)
        start_layout.addStretch() # Add space
        start_layout.addWidget(self.start_interview_btn)

        setup_layout.addLayout(start_layout, 3, 0, 1, 4)

        setup_group.setLayout(setup_layout)
        main_layout.addWidget(setup_group)

        # --- Section 2: Interview Interaction ---
        interview_group = QGroupBox("Interview")
        interview_group.setFont(self.font_large_bold)
        interview_layout = QVBoxLayout() # Vertical layout for this section

        current_q_label = QLabel("Interviewer:")
        current_q_label.setFont(self.font_bold)
        self.current_q_text = QTextEdit()
        self.current_q_text.setReadOnly(True)
        self.current_q_text.setFont(self.font_default)
        self.current_q_text.setFixedHeight(80) # Set initial height
        self.current_q_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        answer_label = QLabel("Your Answer:")
        answer_label.setFont(self.font_bold)
        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Type your answer here, or use the record button...")
        self.answer_input.setFont(self.font_default)
        # Adjust vertical size policy to allow expansion
        self.answer_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.submit_button = QPushButton("Submit Answer")
        if self.submit_icon: self.submit_button.setIcon(self.submit_icon)
        self.submit_button.setIconSize(self.icon_size)
        self.submit_button.setFont(self.font_bold)
        self.submit_button.clicked.connect(self.handle_answer_submission)
        self.submit_button.setFixedHeight(35)

        # Layout for submit button (centered)
        submit_button_layout = QHBoxLayout()
        submit_button_layout.addStretch()
        submit_button_layout.addWidget(self.submit_button)
        submit_button_layout.addStretch()

        interview_layout.addWidget(current_q_label)
        interview_layout.addWidget(self.current_q_text)
        interview_layout.addWidget(answer_label)
        interview_layout.addWidget(self.answer_input) # Takes expanding space
        interview_layout.addLayout(submit_button_layout) # Add the centered button layout

        interview_group.setLayout(interview_layout)
        # Set interview group to expand vertically more than setup/history
        interview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(interview_group, stretch=3) # Give it more stretch factor

        # --- Section 3: History ---
        history_group = QGroupBox("History")
        history_group.setFont(self.font_large_bold)
        history_layout = QVBoxLayout()
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setFont(self.font_history)
        # Set a fixed or minimum height, or let it expand
        self.history_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        history_layout.addWidget(self.history_text)
        history_group.setLayout(history_layout)
        main_layout.addWidget(history_group, stretch=2) # Less stretch than interview

        self.setLayout(main_layout)

        # --- Initial Setup ---
        self.reset_interview_state(clear_config=True)
        # Start the timer to check the STT queue
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100) # Check every 100ms

    # --- PyQt Helper Methods ---

    def _load_icon(self, filename, size=None):
        try:
            path = os.path.join(ICON_PATH, filename)
            if not os.path.exists(path):
                print(f"Warning: Icon not found at {path}")
                return None
            pixmap = QPixmap(path)
            #if size and not pixmap.isNull():
            #    pixmap = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            return QIcon(pixmap)
        except Exception as e:
            print(f"Error loading icon {filename}: {e}")
            return None

    def show_message_box(self, level, title, message):
        """Helper to show QMessageBox."""
        box = QMessageBox(self)
        if level == "info":
             box.setIcon(QMessageBox.Icon.Information)
        elif level == "warning":
             box.setIcon(QMessageBox.Icon.Warning)
        elif level == "error":
             box.setIcon(QMessageBox.Icon.Critical)
        else:
             box.setIcon(QMessageBox.Icon.NoIcon)

        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    # --- Core Logic Ported Methods ---

    def adjust_value(self, spinbox, amount):
        """Helper for potential future +/- buttons, currently using SpinBox directly."""
        # This function is less needed with QSpinBox, but kept for conceptual parity
        current_val = spinbox.value()
        new_val = current_val + amount
        spinbox.setValue(new_val) # Spinbox handles clamping to range

    def update_topic_count(self, value):
        """Called when the num_topics_spinbox value changes."""
        self.num_topics = value
        print(f"Num Topics set to: {self.num_topics}")

    def update_followup_count(self, value):
        """Called when the max_follow_ups_spinbox value changes."""
        self.max_follow_ups = value
        print(f"Max Follow-ups set to: {self.max_follow_ups}")

    def update_status(self, message, busy=False):
        """Updates the current question text area as a status display."""
        if not self.is_recording:
            self.current_q_text.setText(message)
            self.current_q_text.ensureCursorVisible() # Scroll if needed

        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents() # Force UI update

    def display_question(self, question_text):
        """Displays the question and enables controls."""
        self.update_status(question_text, busy=False)
        try:
            audio_handler.speak_text(question_text)
        except Exception as e:
            print(f"UI Error: Failed to initiate TTS: {e}")

        self.enable_interview_controls()
        if not self.use_speech_input:
            self.answer_input.setFocus()

    def add_to_history(self, text, tag=None):
        """Adds text to the history QTextEdit, applying simple HTML styling."""
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_text.setTextCursor(cursor)

        # Use simple HTML for styling
        if tag == "question_style":
            # Example: Blue color for questions (adjust color code)
            self.history_text.insertHtml(f'<font color="#569CD6">{text}</font>')
        elif tag == "answer_style":
            # Example: Default text color for answers (usually light in dark theme)
            self.history_text.insertHtml(f'<font color="{self.palette().color(QPalette.ColorRole.Text).name()}">{text}</font>')
        elif tag == "topic_marker":
             # Example: Gray and bold for topic markers
            self.history_text.insertHtml(f'<font color="grey"><b>{text}</b></font>')
        else:
            self.history_text.insertPlainText(text)

        self.history_text.ensureCursorVisible() # Scroll to the end

    def set_setup_controls_state(self, enabled):
        """Enables or disables setup controls."""
        self.job_desc_input.setEnabled(enabled)
        self.num_topics_spinbox.setEnabled(enabled)
        self.max_follow_ups_spinbox.setEnabled(enabled)
        self.start_interview_btn.setEnabled(enabled)
        self.speech_checkbox.setEnabled(enabled)
        # Keep select button separate, disable after selection during interview setup
        # self.select_btn.setEnabled(enabled) # Handled separately

    def enable_interview_controls(self):
        """Enables answer input and submit button."""
        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True) # Keep widget enabled, control read-only state
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.update_submit_button_text() # Update button text/icon

    def disable_interview_controls(self, is_recording_stt=False):
        """Disables answer input and submit button."""
        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False) # Visually disable too
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt
        if is_recording_stt:
             self.submit_button.setText("Recording...")
             if self.record_icon: self.submit_button.setIcon(self.record_icon)
        # update_submit_button_text will fix text if not recording

    def reset_interview_state(self, clear_config=True):
        """Resets the UI and state variables."""
        print(f"Resetting interview state (clear_config={clear_config})...")
        # Reset state variables
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False

        # Reset UI elements
        self.disable_interview_controls()
        self.answer_input.clear()
        self.history_text.clear()

        if clear_config:
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.file_label.setText("No resume selected.")
            self.select_btn.setEnabled(True) # Enable select button
            self.job_desc_input.clear()
            self.job_desc_input.setEnabled(False) # Disable until PDF is selected
            self.num_topics_spinbox.setValue(logic.DEFAULT_NUM_TOPICS)
            self.max_follow_ups_spinbox.setValue(logic.DEFAULT_MAX_FOLLOW_UPS)
            self.set_setup_controls_state(False) # Disable most setup controls initially
            self.update_status("[Select Resume PDF above to enable setup]", busy=False)
            self.speech_checkbox.setChecked(False) # Reset checkbox
            self.use_speech_input = False
            self.update_submit_button_text()
        else:
            # Interview is starting or restarting without clearing config
            self.set_setup_controls_state(False) # Disable setup during interview
            self.select_btn.setEnabled(False) # Disable select during interview
            self.update_status("[Ready to Start Interview]", busy=False)

        # Close review dialog if open
        if self.review_dialog and self.review_dialog.isVisible():
            self.review_dialog.reject() # Close it without triggering reset again
        self.review_dialog = None

        QApplication.restoreOverrideCursor() # Ensure cursor is reset
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text):
        """Removes number prefixes like '1. ' or '1 ' from question text."""
        # This function remains the same
        cleaned_q = raw_q_text.strip()
        if cleaned_q and cleaned_q[0].isdigit():
            parts = cleaned_q.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit():
                return parts[1].strip()
            else:
                # Handle cases like "1 Question text" without a dot
                parts = cleaned_q.split(' ', 1)
                if len(parts) > 1 and parts[0].isdigit():
                    return parts[1].strip()
                else:
                    # If it starts with a digit but isn't clearly numbered, return as is
                    return cleaned_q
        else:
            # Doesn't start with a digit
            return cleaned_q

    def save_transcript_to_file(self):
        """Saves the full interview history to transcript.txt, grouping by topic."""
        # This function remains the same logic, just uses print/messagebox
        if not self.current_full_interview_history:
            print("No interview history to save.")
            return

        if not self.cleaned_initial_questions:
             print("Warning: Cleaned initial questions set is empty. Cannot structure transcript correctly.")
             # Fallback: Save flat list if structure info is missing
             try:
                filepath = os.path.join(RECORDINGS_DIR, "transcript_flat.txt")
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    for i, qa in enumerate(self.current_full_interview_history):
                        f.write(f"{i+1}. Q: {qa.get('q', 'N/A')}\n   A: {qa.get('a', 'N/A')}\n\n")
                print(f"Saved flat transcript to {filepath}")
             except Exception as e:
                 print(f"Error saving flat transcript: {e}")
                 self.show_message_box("error", "File Save Error", f"Could not save flat transcript:\n{e}")
             return

        transcript_lines = []
        current_topic_num = 0
        current_follow_up_num = 0

        try:
            # Sort history temporarily if needed, or rely on order of addition
            # Assuming current_full_interview_history is in chronological order
            cleaned_q_list = list(self.cleaned_initial_questions) # For potential index lookup if needed

            for qa_pair in self.current_full_interview_history:
                q = qa_pair.get('q', 'MISSING QUESTION')
                a = qa_pair.get('a', 'MISSING ANSWER')

                # Check if this question matches one of the *cleaned* initial questions
                # This assumes the 'q' stored in history is the *cleaned* version
                is_initial = q in self.cleaned_initial_questions

                if is_initial:
                    # Find which initial question it was (robustness check)
                    try:
                        # This relies on initial_questions being the *raw* list
                        raw_q_match = next(raw_q for raw_q in self.initial_questions if self._clean_question_text(raw_q) == q)
                        topic_index = self.initial_questions.index(raw_q_match)
                        # Only advance topic number if it's a *new* topic index
                        if topic_index + 1 > current_topic_num:
                             current_topic_num = topic_index + 1
                             current_follow_up_num = 0 # Reset follow-up count for new topic
                             if current_topic_num > 1:
                                 transcript_lines.append("-------------------------") # Separator
                             transcript_lines.append(f"Question {current_topic_num}: {q}") # Use cleaned q
                             transcript_lines.append(f"Answer: {a}")
                        else: # Re-asking or issue? Treat as follow-up for safety
                             current_follow_up_num += 1
                             transcript_lines.append("")
                             transcript_lines.append(f"Follow Up {current_follow_up_num} (appears related to Topic {current_topic_num}): {q}")
                             transcript_lines.append(f"Answer: {a}")

                    except StopIteration:
                        # Cleaned question not found in raw list - indicates a state mismatch
                        print(f"Warning: Could not match history question '{q}' to initial questions list during transcript save. Treating as follow-up.")
                        # Treat as a follow-up to the *last known* topic
                        if current_topic_num == 0: current_topic_num = 1 # Start at 1 if no topic yet
                        current_follow_up_num += 1
                        transcript_lines.append("")
                        transcript_lines.append(f"Follow Up {current_follow_up_num} (Topic Uncertain): {q}")
                        transcript_lines.append(f"Answer: {a}")

                else: # It's a follow-up
                    current_follow_up_num += 1
                    transcript_lines.append("") # Add extra newline before follow-up for spacing
                    transcript_lines.append(f"Follow Up {current_follow_up_num}: {q}")
                    transcript_lines.append(f"Answer: {a}")

                transcript_lines.append("") # Add blank line after each Answer

            # Ensure the recordings directory exists
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving grouped transcript to {filepath}...")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(transcript_lines).strip()) # Write joined lines, remove trailing newline
            print("Grouped transcript saved successfully.")

        except Exception as e:
            print(f"Error saving grouped transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript to {filepath}:\n{e}")

    # --- GUI Logic Methods ---

    def update_submit_button_text(self, state=None):
        """Updates submit button text/icon based on speech input checkbox."""
        # 'state' is passed by QCheckBox stateChanged signal (0=unchecked, 2=checked)
        if state is not None:
            self.use_speech_input = (state == Qt.CheckState.Checked.value) # Update internal state
            print(f"Use Speech Input: {self.use_speech_input}")

        if not hasattr(self, 'submit_button'): return # Check if widget exists

        # Only change if interview controls are supposed to be active
        # Check if the button is currently enabled (meaning interview is active)
        if self.submit_button.isEnabled() or self.is_recording:
            if self.use_speech_input:
                self.submit_button.setText("Record Answer")
                if self.record_icon: self.submit_button.setIcon(self.record_icon)
                self.answer_input.setReadOnly(True) # Disable text input
                self.answer_input.clear()
                self.answer_input.setPlaceholderText("Click 'Record Answer' to speak")
                self.answer_input.setEnabled(False) # Visually disable
            else:
                self.submit_button.setText("Submit Answer")
                if self.submit_icon: self.submit_button.setIcon(self.submit_icon)
                self.answer_input.setReadOnly(False) # Enable text input
                self.answer_input.setPlaceholderText("Type your answer here...")
                self.answer_input.setEnabled(True) # Ensure enabled
                self.answer_input.setFocus()
        else:
             # If controls are disabled (e.g., pre-interview or processing),
             # ensure text reflects that state regardless of checkbox
             if not self.is_recording: # Don't override "Recording..."
                 if self.use_speech_input:
                     self.submit_button.setText("Record Answer")
                     if self.record_icon: self.submit_button.setIcon(self.record_icon)
                 else:
                     self.submit_button.setText("Submit Answer")
                     if self.submit_icon: self.submit_button.setIcon(self.submit_icon)


    def select_resume_file(self):
        """Opens file dialog to select a PDF."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume PDF",
            "", # Start directory (empty for default)
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not filepath:
            if not self.pdf_filepath:
                self.file_label.setText("Selection cancelled.")
            return

        self.pdf_filepath = filepath
        filename = os.path.basename(filepath)
        self.file_label.setText(filename)

        # Enable setup controls now that a file is selected
        self.set_setup_controls_state(True)
        self.select_btn.setEnabled(False) # Disable select button after selection
        self.update_status("[Optional: Paste JD, adjust settings, then Start]", busy=False)
        self.job_desc_input.setFocus()

    def start_interview_process(self):
        """Starts the interview after setup."""
        if not self.pdf_filepath:
            self.show_message_box("warning", "Input Missing", "Please select a resume PDF file first.")
            return

        self.job_description_text = self.job_desc_input.toPlainText().strip()
        # Num topics/followups already stored in self.num_topics / self.max_follow_ups via spinbox signals

        # Validate settings (though SpinBox ranges should prevent invalid values)
        if not (logic.MIN_TOPICS <= self.num_topics <= logic.MAX_TOPICS):
            self.show_message_box("error", "Invalid Settings", f"Number of topics must be between {logic.MIN_TOPICS} and {logic.MAX_TOPICS}.")
            return
        if not (logic.MIN_FOLLOW_UPS <= self.max_follow_ups <= logic.MAX_FOLLOW_UPS_LIMIT):
            self.show_message_box("error", "Invalid Settings", f"Maximum follow-ups must be between {logic.MIN_FOLLOW_UPS} and {logic.MAX_FOLLOW_UPS_LIMIT}.")
            return

        print(f"Starting Interview: Topics={self.num_topics}, Max FollowUps={self.max_follow_ups}, Speech Input={self.use_speech_input}")

        # Disable setup UI, reset state (keeping config)
        self.set_setup_controls_state(False)
        self.select_btn.setEnabled(False)
        self.reset_interview_state(clear_config=False)

        # --- Start Background Tasks ---
        self.update_status("Extracting text from PDF...", busy=True)

        # Run PDF extraction (could be moved to a thread for large PDFs later)
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        if not self.resume_content:
            self.update_status("[Error extracting PDF text. Check file.]", busy=False)
            # Re-enable setup to allow trying again or selecting a different file
            self.select_btn.setEnabled(True)
            self.set_setup_controls_state(True) # Re-enable all setup
            return # Stop processing

        self.update_status(f"Generating {self.num_topics} initial questions...", busy=True)

        # Run question generation (this involves network I/O, ideally threaded)
        # For now, keep it blocking for simplicity, but UI will freeze.
        # TODO: Move logic calls to QThreads for responsiveness
        self.initial_questions = logic.generate_initial_questions(
            self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )

        QApplication.restoreOverrideCursor() # Restore cursor after blocking call

        if not self.initial_questions:
            self.update_status("[Error generating questions. Check API key/network.]", busy=False)
            # Re-enable setup
            self.select_btn.setEnabled(True)
            self.set_setup_controls_state(True)
            return # Stop processing

        # --- Questions Generated Successfully ---
        print(f"Generated {len(self.initial_questions)} questions.")
        # Prepare cleaned initial questions set for transcript structuring
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        print(f"Cleaned questions set: {self.cleaned_initial_questions}")


        self.current_initial_q_index = 0
        self.start_next_topic()

    def start_next_topic(self):
        """Asks the next initial question or ends the interview."""
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0
            self.current_topic_history = [] # Reset history for this topic

            raw_q_text = self.initial_questions[self.current_initial_q_index]
            # Clean the question text *before* storing and displaying
            self.current_topic_question = self._clean_question_text(raw_q_text)

            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker")

            print(f"Asking Initial Question {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(self.current_topic_question) # Display cleaned question

        else:
            # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Interview complete. Saving transcript & generating review...", busy=True)
            self.disable_interview_controls()

            self.save_transcript_to_file() # Save transcript first

            # Generate summary and assessment (blocking, consider QThread)
            # TODO: Move logic calls to QThreads
            summary = logic.generate_summary_review(self.current_full_interview_history)
            assessment = logic.generate_qualification_assessment(
                self.resume_content,
                self.job_description_text,
                self.current_full_interview_history
            )

            QApplication.restoreOverrideCursor() # Restore cursor

            self.show_final_review_dialog(summary, assessment) # Use QDialog
            self.update_status("[Interview Complete. Review dialog open. Close dialog to reset.]", busy=False)


    def handle_answer_submission(self):
        """Handles click on Submit/Record button."""
        if self.is_recording:
            print("Already recording, ignoring click.")
            return # Avoid double actions

        if self.use_speech_input:
            # Start Speech Recognition
            print("Record button clicked. Starting STT...")
            self.disable_interview_controls(is_recording_stt=True) # Disable controls, set recording flag
            self.update_status_stt("STT_Status: Starting Mic...") # Update status display

            # Clear the (disabled) answer input visually
            self.answer_input.clear()

            # Determine indices for saving audio
            topic_idx = self.current_initial_q_index + 1 # 1-based index for topic
            followup_idx = self.follow_up_count # 0 for initial, 1+ for follow-ups

            # Call the audio handler to start listening in a thread
            audio_handler.start_speech_recognition(
                topic_idx=topic_idx,
                follow_up_idx=followup_idx
            )
        else:
            # Submit Text Answer
            print("Submit button clicked.")
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer:
                self.show_message_box("warning", "Input Required", "Please enter your answer before submitting.")
                return

            # Process the text answer
            self.process_answer(user_answer)

    def update_status_stt(self, message):
        """Updates the status display specifically for STT messages."""
        display_message = message # Default
        if message == "STT_Status: Adjusting...":
            display_message = "[Calibrating microphone noise level...]"
        elif message == "STT_Status: Listening...":
            display_message = "[Listening... Please speak clearly]"
            # Optionally change button text again here if needed
            self.submit_button.setText("Listening...")
        elif message == "STT_Status: Processing...":
            display_message = "[Processing captured speech...]"
            self.submit_button.setText("Processing...")
        elif message.startswith("STT_Error:"):
            error_detail = message.split(':', 1)[1].strip()
            display_message = f"[STT Error: {error_detail}]"
        elif message.startswith("STT_Success:"):
            display_message = "[Speech Recognized Successfully]"

        # Update the interviewer question area as the status bar
        self.current_q_text.setText(display_message)
        QApplication.processEvents() # Force UI update


    def check_stt_queue(self):
        """Periodically checks the queue for results from the STT thread."""
        try:
            result = audio_handler.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}") # Debugging

            if result.startswith("STT_Status:"):
                self.update_status_stt(result) # Update status display

            elif result.startswith("STT_Success:"):
                self.is_recording = False # Recording finished
                self.update_status_stt(result) # Show success message briefly
                transcript = result.split(":", 1)[1].strip()

                # Put transcript in the (disabled) answer box for visibility
                self.answer_input.setReadOnly(False) # Temporarily allow writing
                self.answer_input.setText(transcript)
                self.answer_input.setReadOnly(True)  # Set back to read-only

                # Now process the recognized answer
                self.process_answer(transcript)

            elif result.startswith("STT_Error:"):
                self.is_recording = False # Recording/processing failed
                error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result) # Show error in status area
                self.show_message_box("error", "Speech Recognition Error", error_message)
                # Re-enable controls so the user can try again or type
                self.enable_interview_controls()

        except queue.Empty:
            pass # No message in the queue, just continue
        except Exception as e:
            print(f"Error processing STT queue: {e}")
            # Ensure controls are re-enabled in case of unexpected error
            if self.is_recording:
                self.is_recording = False
                self.enable_interview_controls()

        # Reschedule the check (handled by QTimer instance) - no need to call after()

    def process_answer(self, user_answer):
        """Processes the user's answer (text or recognized speech)."""

        # Determine the question this answer corresponds to.
        # It's the question currently displayed or the last one asked in this topic.
        # `self.current_topic_question` holds the initial question for the *topic*.
        # `self.current_topic_history` holds the actual Q&A pairs for the topic.
        last_q = ""
        if not self.current_topic_history: # This answer is for the initial topic question
            last_q = self.current_topic_question
        elif self.current_topic_history: # This answer is for the last follow-up in the history
            last_q = self.current_topic_history[-1]['q']
        else: # Fallback, should ideally not happen if logic is correct
            last_q = self.current_q_text.toPlainText().strip() # Use what's displayed
            if last_q.startswith("["): # If status message is displayed, use topic question
                 last_q = self.current_topic_question

        if not last_q:
             print("Error: Could not determine the question for the current answer.")
             last_q = "[Unknown Question]"


        print(f"Processing answer for Q: '{last_q}' -> A: '{user_answer[:50]}...'")

        # Store in history structures
        q_data = {"q": last_q, "a": user_answer}
        self.current_topic_history.append(q_data)
        self.current_full_interview_history.append(q_data)

        # Add to displayed history log
        # Use the determined 'last_q' for accuracy
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        # Clear input area and disable controls while thinking
        self.answer_input.clear()
        self.disable_interview_controls() # Disables submit/record and answer input
        self.update_status("Generating response or next question...", busy=True)

        # --- Call Logic for Follow-up ---
        # Check if follow-ups are allowed for this topic
        if self.follow_up_count < self.max_follow_ups:
            # Generate follow-up (blocking, consider QThread)
            # TODO: Move logic calls to QThreads
            print(f"Generating follow-up (count {self.follow_up_count + 1}/{self.max_follow_ups})")
            follow_up_q = logic.generate_follow_up_question(
                context_question=self.current_topic_question, # Provide initial topic Q as context
                user_answer=user_answer,
                conversation_history=self.current_topic_history # Provide history *for this topic*
            )

            QApplication.restoreOverrideCursor() # Restore cursor after blocking call

            if follow_up_q and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1
                print(f"Asking Follow-up {self.follow_up_count}: {follow_up_q}")
                # Store this follow-up question in the topic history *before* displaying
                # The answer will be added when process_answer runs next time
                # We need a placeholder or structure to know the question being asked
                # Let's refine: Store Q/A pair *after* answer is received.
                # The `display_question` will show it, and `process_answer` will pair it.
                self.display_question(follow_up_q) # This enables controls again
            else:
                # No follow-up generated or [END TOPIC] received
                print("No more follow-ups for this topic.")
                self.current_initial_q_index += 1 # Move to the next initial question index
                self.start_next_topic() # Start the next topic (or end interview)
        else:
            # Max follow-ups reached for this topic
            print(f"Max follow-ups ({self.max_follow_ups}) reached for this topic.")
            QApplication.restoreOverrideCursor() # Restore cursor if busy was set
            self.current_initial_q_index += 1 # Move to the next initial question index
            self.start_next_topic() # Start the next topic (or end interview)

        # Ensure cursor is reset if it was busy
        if QApplication.overrideCursor() is not None:
             QApplication.restoreOverrideCursor()


    # --- Review Window Methods ---
    def _handle_review_close(self, result):
        """Called when the review dialog is closed."""
        print(f"Review dialog closed with result: {result}") # result=1 for Accept (Close button)
        # Reset the main application state regardless of how the dialog was closed
        self.reset_interview_state(clear_config=True)

    def show_final_review_dialog(self, summary, assessment):
        """Creates and shows the QDialog for review."""
        if self.review_dialog is None:
            self.review_dialog = ReviewDialog(summary, assessment, self)
            # Connect the finished signal to our handler
            self.review_dialog.finished.connect(self._handle_review_close)

        # Ensure it's shown and brought to front
        self.review_dialog.show()
        self.review_dialog.raise_()
        self.review_dialog.activateWindow()

    # --- Override closeEvent ---
    def closeEvent(self, event):
        """Ensure timer stops when main window closes."""
        print("Closing application...")
        self.stt_timer.stop()
        # Clean up other resources if necessary (e.g., close audio streams)
        event.accept() # Proceed with closing


# --- Main Execution ---
if __name__ == "__main__":
    # Initial checks before creating QApplication
    if not os.path.exists(ICON_PATH):
        print(f"Warning: Icon folder '{ICON_PATH}' not found. Icons will be missing.")
    if not os.path.exists(".env"):
        # Show message box *after* QApplication is created
        pass # Will show warning later if needed
    if not logic.configure_gemini():
        # Cannot proceed without API key
        # Need QApplication to show message box
        temp_app = QApplication(sys.argv) # Temporary app just for the error message
        QMessageBox.critical(None, "Fatal Error", "Failed to configure Gemini API.\nPlease ensure GOOGLE_API_KEY is set correctly in a .env file.\nApplication will exit.")
        sys.exit(1)

    # Create the main application instance
    q_app = QApplication(sys.argv)

    # Now show .env warning if needed
    if not os.path.exists(".env"):
         QMessageBox.warning(None, "Configuration Warning", f"'.env' file not found in the current directory ({os.getcwd()}).\nMake sure it exists and contains your GOOGLE_API_KEY for Gemini.")

    # --- Microphone Check (Optional but Recommended) ---
    stt_backend_found = False
    audio_lib = "Not Checked"
    mic_warning_message = ""
    try:
        # Quick check using sounddevice (often available with SpeechRecognition)
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            print("Audio Input Check: Found input devices via sounddevice.")
            stt_backend_found = True
            audio_lib = "sounddevice"
        else:
             mic_warning_message = "No input devices found via sounddevice."
             print(f"Audio Input Check: {mic_warning_message}")
    except Exception as e_sd:
        print(f"Audio Input Check: sounddevice check failed ({e_sd}). Trying PyAudio...")
        try:
            # Fallback check using PyAudio (another common backend)
            import pyaudio
            p = pyaudio.PyAudio()
            input_devices_found = False
            default_input_device_info = None
            try:
                default_input_device_info = p.get_default_input_device_info()
                if default_input_device_info['maxInputChannels'] > 0:
                     input_devices_found = True
                     print(f"Audio Input Check: Found default input device via PyAudio: {default_input_device_info['name']}")
            except IOError:
                 print("Audio Input Check: No default PyAudio input device found. Checking all devices...")
                 # Check all devices if no default is found or fails
                 for i in range(p.get_device_count()):
                     dev_info = p.get_device_info_by_index(i)
                     if dev_info.get('maxInputChannels', 0) > 0:
                         print(f"Audio Input Check: Found potential PyAudio input device: {dev_info.get('name')}")
                         input_devices_found = True
                         break # Found at least one
            p.terminate()
            if input_devices_found:
                stt_backend_found = True
                audio_lib = "PyAudio"
            else:
                mic_warning_message = "No input devices found via PyAudio either."
                print(f"Audio Input Check: {mic_warning_message}")
        except Exception as e_pa:
            mic_warning_message = f"Could not check for audio input devices using sounddevice or PyAudio.\nSounddevice error: {e_sd}\nPyAudio error: {e_pa}"
            print(f"Audio Input Check: Error during PyAudio check: {e_pa}")

    if not stt_backend_found:
        full_warning = f"{mic_warning_message}\n\nSpeech input will likely not function. Please ensure you have a working microphone and the necessary audio libraries (like PyAudio or portaudio) installed and configured for your operating system."
        QMessageBox.warning(None, "Audio Input Warning", full_warning)
    # --- End Microphone Check ---


    # Create and show the main window
    app_window = InterviewApp()
    app_window.show()

    # Start the Qt event loop
    exit_code = q_app.exec()
    print("\n--- Program End ---")
    sys.exit(exit_code)