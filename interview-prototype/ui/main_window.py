# ui/main_window.py
import os
import sys
import queue

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox, QFileDialog, QApplication, QDialog, QLabel
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal

# --- Project Imports ---
import core.logic as logic
import core.audio_handler as audio_handler
from core.audio_handler import RECORDINGS_DIR

from .components import create_setup_group, create_interview_group, create_history_group
from .dialogs import ReviewDialog


class InterviewApp(QWidget):
    def __init__(self, icon_path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.icon_path = icon_path # Store base path for icons

        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000)

        self._setup_appearance()
        self._load_assets() # Load icons, fonts
        self._init_state() # Initialize application state variables
        self._setup_ui()   # Setup the main UI layout and components
        self._connect_signals() # Connect signals if not done in components

        # --- Initial UI State ---
        self.reset_interview_state(clear_config=True)

        # --- STT Queue Timer ---
        self.stt_timer = QTimer(self)
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100) # Check every 100ms


    def _setup_appearance(self):
        """Sets the visual appearance (theme, style)."""
        # Dark theme palette setup
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220)) # Keep text light for dark button override
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        # Disabled text color hint
        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text_color) # For LineEdit/TextEdit placeholders
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)
        self.setPalette(palette)
        QApplication.setStyle("Fusion")


    def _load_assets(self):
        """Loads icons and defines fonts."""
        self.icon_size = QSize(20, 20)
        # Load common icons needed directly by this class
        self.submit_icon = self._load_icon_internal("send.png", self.icon_size)
        # plus/minus/record icons loaded in components.py and stored on self

        # Fonts
        self.font_default = QFont("Arial", 10)
        self.font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 9)
        self.font_large_bold = QFont("Arial", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9)


    def _init_state(self):
        """Initializes application state variables."""
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        self.num_topics = logic.DEFAULT_NUM_TOPICS
        self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.review_dialog = None
        self.use_speech_input = False
        self.is_recording = False
        self.last_question_asked = ""
        # Ensure icon attributes exist even if loading fails
        self.record_icon = None
        self.select_btn = None # Will be set by component creation
        # Add placeholders for new widgets created in components.py
        self.topic_minus_btn = None
        self.topic_plus_btn = None
        self.num_topics_label = None
        self.followup_minus_btn = None
        self.followup_plus_btn = None
        self.max_follow_ups_label = None


    def _setup_ui(self):
        """Creates the main layout and adds UI component groups."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create UI sections by calling functions from components.py
        # These functions set widget attributes on `self` (e.g., self.select_btn)
        setup_group = create_setup_group(self)
        interview_group = create_interview_group(self)
        history_group = create_history_group(self)

        # Add groups to the main layout
        main_layout.addWidget(setup_group)
        main_layout.addWidget(interview_group, stretch=3) # Give interview section more stretch
        main_layout.addWidget(history_group, stretch=2)   # History less stretch

        self.setLayout(main_layout)


    def _connect_signals(self):
        """Connect signals here if not handled within component creation."""
        # Connections are now done in components.py using lambda
        pass


    # --- PyQt Helper Methods ---
    def _load_icon_internal(self, filename, size=None):
        # Internal helper for loading icons needed by this class directly
        try:
            path = os.path.join(self.icon_path, filename)
            if not os.path.exists(path):
                print(f"Warning: Icon not found at {path}")
                return None
            # Return QIcon directly for use with buttons etc.
            return QIcon(path)
        except Exception as e:
            print(f"Error loading icon {filename}: {e}")
            return None


    def show_message_box(self, level, title, message):
        """Helper to show QMessageBox."""
        box = QMessageBox(self)
        icon = QMessageBox.Icon.NoIcon
        if level == "info":
             icon = QMessageBox.Icon.Information
        elif level == "warning":
             icon = QMessageBox.Icon.Warning
        elif level == "error":
             icon = QMessageBox.Icon.Critical

        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()


    # --- NEW: Handler for +/- Buttons ---
    def _adjust_value(self, value_type, amount):
        """Handles clicks for topic and follow-up +/- buttons."""
        current_val = 0
        min_val = 0
        max_val = 0
        target_label = None
        target_var_name = ""

        if value_type == 'topics':
            current_val = self.num_topics
            min_val = logic.MIN_TOPICS
            max_val = logic.MAX_TOPICS
            target_label = self.num_topics_label # Get ref to the QLabel
            target_var_name = 'num_topics'
        elif value_type == 'followups':
            current_val = self.max_follow_ups
            min_val = logic.MIN_FOLLOW_UPS
            max_val = logic.MAX_FOLLOW_UPS_LIMIT
            target_label = self.max_follow_ups_label # Get ref to the QLabel
            target_var_name = 'max_follow_ups'
        else:
            print(f"Error: Unknown value_type '{value_type}' in _adjust_value")
            return # Should not happen

        new_value = current_val + amount

        # Check bounds
        if min_val <= new_value <= max_val:
            # Update state variable
            setattr(self, target_var_name, new_value)
            # Update label text if the label widget exists
            if target_label:
                target_label.setText(str(new_value))
            print(f"{target_var_name.replace('_', ' ').title()} set to: {new_value}")
        else:
             print(f"Value {new_value} out of bounds ({min_val}-{max_val}) for {value_type}")


    # --- Core Logic/State Management Methods ---

    def update_status(self, message, busy=False):
        # Ensure widget exists before accessing
        if hasattr(self, 'current_q_text') and self.current_q_text:
             if not self.is_recording:
                self.current_q_text.setText(message)
                self.current_q_text.ensureCursorVisible()
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def display_question(self, question_text):
        self.last_question_asked = question_text # Store the question being displayed
        self.update_status(question_text, busy=False)
        try:
            audio_handler.speak_text(question_text)
        except Exception as e:
            print(f"UI Error: Failed to initiate TTS: {e}")
        self.enable_interview_controls()
        # Ensure answer_input exists before focusing
        if hasattr(self, 'answer_input') and self.answer_input:
            if not self.use_speech_input:
                self.answer_input.setFocus()

    def add_to_history(self, text, tag=None):
        # Ensure widget exists
        if not hasattr(self, 'history_text') or not self.history_text: return

        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_text.setTextCursor(cursor)
        # Use simple HTML for styling
        if tag == "question_style":
            self.history_text.insertHtml(f'<font color="#569CD6">{text}</font>') # Blueish
        elif tag == "answer_style":
            text_color = self.palette().color(QPalette.ColorRole.Text).name()
            self.history_text.insertHtml(f'<font color="{text_color}">{text}</font>')
        elif tag == "topic_marker":
            self.history_text.insertHtml(f'<font color="grey"><b>{text}</b></font>')
        else:
            self.history_text.insertPlainText(text)
        self.history_text.ensureCursorVisible()

    def set_setup_controls_state(self, enabled):
        """Enables or disables setup controls AFTER PDF selection."""
        # Check if widgets exist before configuring them
        if hasattr(self, 'job_desc_input'): self.job_desc_input.setEnabled(enabled)

        # Enable/disable the new +/- buttons and potentially labels
        if hasattr(self, 'topic_minus_btn'): self.topic_minus_btn.setEnabled(enabled)
        if hasattr(self, 'topic_plus_btn'): self.topic_plus_btn.setEnabled(enabled)
        if hasattr(self, 'num_topics_label'): self.num_topics_label.setEnabled(enabled) # Can disable label too
        if hasattr(self, 'followup_minus_btn'): self.followup_minus_btn.setEnabled(enabled)
        if hasattr(self, 'followup_plus_btn'): self.followup_plus_btn.setEnabled(enabled)
        if hasattr(self, 'max_follow_ups_label'): self.max_follow_ups_label.setEnabled(enabled) # Can disable label too

        if hasattr(self, 'start_interview_btn'): self.start_interview_btn.setEnabled(enabled)
        if hasattr(self, 'speech_checkbox'): self.speech_checkbox.setEnabled(enabled)
        # select_btn is handled separately (usually disabled after selection)

    def enable_interview_controls(self):
        # Check if widgets exist
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'): return

        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True) # Enable widget itself
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.update_submit_button_text() # Update button text/icon based on state

    def disable_interview_controls(self, is_recording_stt=False):
        # Check if widgets exist
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'): return

        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False) # Visually disable too
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt
        if is_recording_stt:
            self.submit_button.setText("Recording...")
            # Ensure record_icon attribute exists and was loaded
            if hasattr(self, 'record_icon') and self.record_icon:
                 self.submit_button.setIcon(self.record_icon)
            else:
                 print("Warning: Record icon not loaded/available when disabling controls.")
                 self.submit_button.setIcon(QIcon()) # Clear icon if missing

    def reset_interview_state(self, clear_config=True):
        print(f"Resetting interview state (clear_config={clear_config})...")
        # Reset python state variables first
        self.pdf_filepath = None if clear_config else self.pdf_filepath
        self.resume_content = "" if clear_config else self.resume_content
        self.job_description_text = "" if clear_config else self.job_description_text
        # --- MOVED logic was here, now handled inside clear_config block ---
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        # Only reset use_speech_input if clear_config is True
        self.use_speech_input = False if clear_config else self.use_speech_input
        self.is_recording = False
        self.last_question_asked = "" # Reset last question asked state


        # Reset UI elements to initial state, check existence first
        self.disable_interview_controls()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()

        if clear_config:
            # --- NOW RESET COUNTS AND UI ONLY ON FULL CLEAR ---
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS

            if hasattr(self, 'file_label'): self.file_label.setText("No resume selected.")
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True)
            if hasattr(self, 'job_desc_input'): self.job_desc_input.clear()

            # Disable setup controls until PDF selected
            self.set_setup_controls_state(False)
            if hasattr(self, 'job_desc_input'): self.job_desc_input.setEnabled(False)

            # Reset labels to default values using the just-reset state variables
            if hasattr(self, 'num_topics_label'): self.num_topics_label.setText(str(self.num_topics))
            if hasattr(self, 'max_follow_ups_label'): self.max_follow_ups_label.setText(str(self.max_follow_ups))

            self.update_status("[Select Resume PDF above to enable setup]", busy=False)
            if hasattr(self, 'speech_checkbox'):
                 self.speech_checkbox.setChecked(False)
        else:
            # Interview is starting or restarting without clearing config
            # DO NOT reset num_topics/max_follow_ups here
            # Ensure labels reflect current state (they should already from _adjust_value)
            if hasattr(self, 'num_topics_label'): self.num_topics_label.setText(str(self.num_topics))
            if hasattr(self, 'max_follow_ups_label'): self.max_follow_ups_label.setText(str(self.max_follow_ups))

            self.set_setup_controls_state(False) # Disable setup during interview
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False)
            self.update_status("[Ready to Start Interview]", busy=False)

        # Close review dialog if open
        if self.review_dialog and self.review_dialog.isVisible():
            try: self.review_dialog.finished.disconnect(self._handle_review_close)
            except TypeError: pass
            self.review_dialog.reject()
        self.review_dialog = None

        # Ensure button text/icon reflects final state (important after clear_config=True)
        self.update_submit_button_text()

        QApplication.restoreOverrideCursor()
        print("Interview state reset complete.")


    def _clean_question_text(self, raw_q_text):
        # (Keep as before)
        cleaned_q = raw_q_text.strip()
        if cleaned_q and cleaned_q[0].isdigit():
            parts = cleaned_q.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit():
                return parts[1].strip()
            else:
                parts = cleaned_q.split(' ', 1)
                if len(parts) > 1 and parts[0].isdigit():
                    return parts[1].strip()
                else:
                    return cleaned_q
        else:
            return cleaned_q


    def save_transcript_to_file(self):
        # (Keep as before)
        if not self.current_full_interview_history:
            print("No interview history to save.")
            return

        if not self.cleaned_initial_questions:
            print("Warning: Cleaned initial questions set is empty...")
            # ... (fallback saving logic) ...
            return

        transcript_lines = []
        current_topic_num = 0
        current_follow_up_num = 0
        try:
            # ... (structured transcript generation logic) ...
            for qa_pair in self.current_full_interview_history:
                q = qa_pair.get('q', 'MISSING QUESTION')
                a = qa_pair.get('a', 'MISSING ANSWER')
                is_initial = q in self.cleaned_initial_questions
                if is_initial:
                    topic_index = -1
                    try:
                        raw_q_match = next(raw_q for raw_q in self.initial_questions if self._clean_question_text(raw_q) == q)
                        topic_index = self.initial_questions.index(raw_q_match)
                    except StopIteration: print(f"Warning: Could not match history Q '{q}' to initial list.")
                    if topic_index != -1 and topic_index + 1 > current_topic_num:
                        current_topic_num = topic_index + 1
                        current_follow_up_num = 0
                        if current_topic_num > 1: transcript_lines.append("-------------------------")
                        transcript_lines.append(f"Question {current_topic_num}: {q}")
                        transcript_lines.append(f"Answer: {a}")
                    else: # Follow-up handling for re-ask/mismatch
                        current_follow_up_num += 1; transcript_lines.append("")
                        topic_context = f"Topic {current_topic_num}" if current_topic_num > 0 else "Topic Uncertain"
                        transcript_lines.append(f"Follow Up {current_follow_up_num} (appears related to {topic_context}): {q}")
                        transcript_lines.append(f"Answer: {a}")
                else: # Normal Follow-up
                    current_follow_up_num += 1; transcript_lines.append("")
                    transcript_lines.append(f"Follow Up {current_follow_up_num}: {q}")
                    transcript_lines.append(f"Answer: {a}")
                transcript_lines.append("")

            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving grouped transcript to {filepath}...")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(transcript_lines).strip())
            print("Grouped transcript saved successfully.")
        except Exception as e:
            print(f"Error saving grouped transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript to {filepath}:\n{e}")


    # --- GUI Logic/Event Handlers ---

    def update_submit_button_text(self, state=None):
        # (Keep as before)
        if state is not None:
            self.use_speech_input = (state == Qt.CheckState.Checked.value)
            print(f"Use Speech Input: {self.use_speech_input}")

        if not hasattr(self, 'submit_button'): return

        if self.submit_button.isEnabled() or self.is_recording:
            if self.use_speech_input:
                self.submit_button.setText("Record Answer")
                if hasattr(self, 'record_icon') and self.record_icon:
                    self.submit_button.setIcon(self.record_icon)
                else: self.submit_button.setIcon(QIcon())
                if hasattr(self, 'answer_input'):
                    self.answer_input.setReadOnly(True); self.answer_input.clear()
                    self.answer_input.setPlaceholderText("Click 'Record Answer' to speak")
                    self.answer_input.setEnabled(False)
            else:
                self.submit_button.setText("Submit Answer")
                if hasattr(self, 'submit_icon') and self.submit_icon:
                    self.submit_button.setIcon(self.submit_icon)
                else: self.submit_button.setIcon(QIcon())
                if hasattr(self, 'answer_input'):
                    self.answer_input.setReadOnly(False)
                    self.answer_input.setPlaceholderText("Type your answer here...")
                    self.answer_input.setEnabled(True)
                    if self.submit_button.isEnabled(): self.answer_input.setFocus()
        else:
            if not self.is_recording:
                default_text = "Record Answer" if self.use_speech_input else "Submit Answer"
                default_icon = self.record_icon if self.use_speech_input else self.submit_icon
                self.submit_button.setText(default_text)
                if default_icon: self.submit_button.setIcon(default_icon)
                else: self.submit_button.setIcon(QIcon())


    def select_resume_file(self):
        # (Keep as before)
        start_dir = os.path.expanduser("~")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Resume PDF", start_dir, "PDF Files (*.pdf);;All Files (*)")
        if not filepath:
            if hasattr(self, 'file_label') and not self.pdf_filepath:
                 self.file_label.setText("Selection cancelled.")
            return
        self.pdf_filepath = filepath
        filename = os.path.basename(filepath)
        if hasattr(self, 'file_label'): self.file_label.setText(filename)
        self.set_setup_controls_state(True)
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False)
        self.update_status("[Optional: Paste JD, adjust settings, then Start]", busy=False)
        if hasattr(self, 'job_desc_input'): self.job_desc_input.setFocus()


    def start_interview_process(self):
        # (Keep as before, including the corrected call to generate_initial_questions)
        if not self.pdf_filepath:
            self.show_message_box("warning", "Input Missing", "Please select a resume PDF file first.")
            return
        if hasattr(self, 'job_desc_input'):
            self.job_description_text = self.job_desc_input.toPlainText().strip()
        else: self.job_description_text = ""

        print(f"Starting Interview: Topics={self.num_topics}, Max FollowUps={self.max_follow_ups}, Speech={self.use_speech_input}")
        self.set_setup_controls_state(False)
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False)
        self.reset_interview_state(clear_config=False)

        self.update_status("Extracting text from PDF...", busy=True)
        # TODO: Threading
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        QApplication.processEvents()
        if self.resume_content is None:
            self.update_status("[Error extracting PDF text. Check file.]", busy=False)
            self.show_message_box("error", "PDF Error", "Failed to extract text...")
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True)
            self.set_setup_controls_state(True); return

        self.update_status(f"Generating {self.num_topics} initial questions...", busy=True)
        # TODO: Threading
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()
        if not self.initial_questions:
            self.update_status("[Error generating questions...]", busy=False)
            self.show_message_box("error", "Generation Error", "Failed to generate questions...")
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True)
            self.set_setup_controls_state(True); return

        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        print(f"Cleaned questions set: {self.cleaned_initial_questions}")
        self.current_initial_q_index = 0
        self.start_next_topic()


    def start_next_topic(self):
        # (Keep as before)
        if not self.initial_questions:
             print("Error: Cannot start next topic, initial questions list is empty.")
             self.update_status("[Error: No initial questions loaded]", busy=False)
             self.reset_interview_state(clear_config=True); return

        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0; self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text)
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker")
            print(f"Asking Initial Q {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(self.current_topic_question)
        else:
            print("\n--- Interview Finished ---")
            self.update_status("Interview complete. Saving transcript & generating review...", busy=True)
            self.disable_interview_controls()
            self.save_transcript_to_file()
            # TODO: Threading
            print("Generating performance summary...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating qualification assessment...")
            assessment = logic.generate_qualification_assessment(self.resume_content, self.job_description_text, self.current_full_interview_history)
            QApplication.restoreOverrideCursor()
            if summary.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Summary Error", "Could not generate summary...")
            if assessment.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Assessment Error", "Could not generate assessment...")
            self.show_final_review_dialog(summary, assessment)


    def handle_answer_submission(self):
        # (Keep as before)
        if self.is_recording: print("Already recording..."); return
        if self.use_speech_input:
            print("Record button clicked. Starting STT...")
            self.disable_interview_controls(is_recording_stt=True)
            self.update_status_stt("STT_Status: Starting Mic...")
            if hasattr(self, 'answer_input'): self.answer_input.clear()
            topic_idx = self.current_initial_q_index + 1
            followup_idx = self.follow_up_count
            audio_handler.start_speech_recognition(topic_idx, followup_idx)
        else:
            print("Submit button clicked.")
            if not hasattr(self, 'answer_input'): print("Error: answer_input missing."); return
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer: self.show_message_box("warning", "Input Required", "Please enter answer."); return
            self.process_answer(user_answer)


    def update_status_stt(self, message):
        # (Keep as before)
        if not hasattr(self, 'current_q_text') or not self.current_q_text: return
        display_message = message; button_text_update = None
        if message == "STT_Status: Adjusting...": display_message = "[Calibrating microphone...]"
        elif message == "STT_Status: Listening...": display_message = "[Listening...]"; button_text_update = "Listening..."
        elif message == "STT_Status: Processing...": display_message = "[Processing...]"; button_text_update = "Processing..."
        elif message.startswith("STT_Error:"): display_message = f"[STT Error: {message.split(':', 1)[1].strip()}]"
        elif message.startswith("STT_Success:"): display_message = "[Speech Recognized]"
        self.current_q_text.setText(display_message)
        if button_text_update and self.is_recording and hasattr(self, 'submit_button'):
             self.submit_button.setText(button_text_update)
        QApplication.processEvents()


    def check_stt_queue(self):
        # (Keep as before)
        try:
            result = audio_handler.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")
            if result.startswith("STT_Status:"): self.update_status_stt(result)
            elif result.startswith("STT_Success:"):
                self.is_recording = False; self.update_status_stt(result)
                transcript = result.split(":", 1)[1].strip()
                if hasattr(self, 'answer_input'):
                    self.answer_input.setEnabled(True); self.answer_input.setReadOnly(False)
                    self.answer_input.setText(transcript)
                    self.answer_input.setReadOnly(True); self.answer_input.setEnabled(False)
                else: print("Warning: answer_input missing.")
                self.process_answer(transcript)
            elif result.startswith("STT_Error:"):
                self.is_recording = False
                error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result)
                self.show_message_box("error", "Speech Recognition Error", error_message)
                self.enable_interview_controls()
        except queue.Empty: pass
        except Exception as e:
            print(f"Error processing STT queue: {e}")
            if self.is_recording: self.is_recording = False; self.enable_interview_controls()


    def process_answer(self, user_answer):
        # (Keep as before, using self.last_question_asked)
        if not hasattr(self, 'last_question_asked') or not self.last_question_asked:
             print("Warning: Last question asked state not found..."); last_q = "[Unknown Question]"
        else: last_q = self.last_question_asked

        print(f"Processing answer for last asked Q: '{last_q}' -> A: '{user_answer[:50]}...'")
        q_data = {"q": last_q, "a": user_answer}
        if hasattr(self, 'current_topic_history'): self.current_topic_history.append(q_data)
        if hasattr(self, 'current_full_interview_history'): self.current_full_interview_history.append(q_data)
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        if hasattr(self, 'answer_input'): self.answer_input.clear()
        self.disable_interview_controls()
        self.update_status("Generating response or next question...", busy=True)

        if hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups') and \
           self.follow_up_count < self.max_follow_ups:
            # TODO: Threading
            print(f"Generating follow-up (count {self.follow_up_count + 1}/{self.max_follow_ups})")
            follow_up_q = logic.generate_follow_up_question(self.current_topic_question, user_answer, self.current_topic_history)
            QApplication.restoreOverrideCursor()
            if follow_up_q and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1; print(f"Asking Follow-up {self.follow_up_count}: {follow_up_q}")
                self.display_question(follow_up_q)
            elif follow_up_q == "[END TOPIC]":
                print("No more follow-ups ([END TOPIC] received).")
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
            else: # None == Error
                print("Error generating follow-up. Ending topic.")
                self.show_message_box("error", "Generation Error", "Error generating follow-up...")
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
        else:
            if not hasattr(self, 'follow_up_count') or not hasattr(self, 'max_follow_ups'): print("Warning: follow-up state missing.")
            else: print(f"Max follow-ups ({self.max_follow_ups}) reached.")
            QApplication.restoreOverrideCursor()
            if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
            self.start_next_topic()
        if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()


    # --- Review Window Methods ---
    def _handle_review_close(self, result):
        # (Keep as before)
        print(f"Review dialog closed with result: {result}")
        if result == QDialog.DialogCode.Accepted: print("Review accepted, resetting.")
        else: print("Review rejected/closed, resetting.")
        self.reset_interview_state(clear_config=True)
        self.review_dialog = None


    def show_final_review_dialog(self, summary, assessment):
        # (Keep as before)
        if self.review_dialog and self.review_dialog.isVisible():
            self.review_dialog.raise_(); self.review_dialog.activateWindow(); return
        print("Creating and opening review dialog...")
        self.review_dialog = ReviewDialog(summary, assessment, self)
        self.review_dialog.finished.connect(self._handle_review_close)
        self.review_dialog.open() # Modal
        print("Review dialog finished.")


    # --- Override closeEvent ---
    def closeEvent(self, event):
        # (Keep as before)
        print("Closing application window...")
        if hasattr(self, 'stt_timer'): self.stt_timer.stop(); print("STT timer stopped.")
        if self.review_dialog and self.review_dialog.isVisible():
             print("Closing open review dialog...")
             try: self.review_dialog.finished.disconnect(self._handle_review_close)
             except TypeError: pass
             self.review_dialog.reject()
        print("Cleanup complete. Accepting close event.")
        event.accept()