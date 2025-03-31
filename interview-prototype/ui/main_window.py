# ui/main_window.py
import os
import sys
import queue

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox, QFileDialog, QApplication, QStackedWidget, # Added QStackedWidget
    QLabel # Added QLabel for _adjust_value type hinting
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal

# --- Project Imports ---
import core.logic as logic
import core.audio_handler as audio_handler
from core.audio_handler import RECORDINGS_DIR

# Import UI component creation functions
# Note: Dialogs are no longer imported
from .components import create_setup_page, create_interview_page, create_results_page


class InterviewApp(QWidget):

    # Define constants for page indices (optional but good practice)
    SETUP_PAGE_INDEX = 0
    INTERVIEW_PAGE_INDEX = 1
    RESULTS_PAGE_INDEX = 2

    def __init__(self, icon_path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.icon_path = icon_path
        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000) # Adjusted default size slightly

        self._setup_appearance()
        self._load_assets()
        self._init_state() # Initialize before UI setup needs defaults
        self._setup_ui()   # Now sets up QStackedWidget
        # self._connect_signals() # Signals connected during component creation

        # Set initial state for controls on the setup page
        self._update_ui_from_state() # Ensure UI reflects initial state

        # Start STT Timer
        self.stt_timer = QTimer(self)
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100)


    def _setup_appearance(self):
        # (Keep as before)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        # ... rest of palette settings ...
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)
        self.setPalette(palette)
        QApplication.setStyle("Fusion")

    def _load_assets(self):
        # (Keep as before)
        self.icon_size = QSize(20, 20)
        self.submit_icon = self._load_icon_internal("send.png", self.icon_size)
        # Other icons loaded in components.py

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
        # self.review_dialog = None # No longer needed
        self.use_speech_input = False
        self.is_recording = False
        self.last_question_asked = ""
        # Icon references will be set later if needed by this class
        self.record_icon = None
        # Widget references (set during page creation by components.py)
        self.select_btn = None
        self.file_label = None
        self.job_desc_input = None
        self.topic_minus_btn = None
        self.topic_plus_btn = None
        self.num_topics_label = None
        self.followup_minus_btn = None
        self.followup_plus_btn = None
        self.max_follow_ups_label = None
        self.speech_checkbox = None
        self.start_interview_btn = None
        self.current_q_text = None
        self.answer_input = None
        self.submit_button = None
        self.history_text = None
        self.summary_text_results = None
        self.assessment_text_results = None
        self.new_interview_button = None

    def _setup_ui(self):
        """Creates the QStackedWidget and adds pages."""
        # --- Main Window Layout ---
        main_window_layout = QVBoxLayout(self)
        main_window_layout.setContentsMargins(0,0,0,0) # Stacked widget fills window

        # --- Stacked Widget ---
        self.stacked_widget = QStackedWidget()
        main_window_layout.addWidget(self.stacked_widget)

        # --- Create Pages ---
        # Functions from components.py create the QWidget for each page
        # and set the necessary widget references on `self`
        self.setup_page = create_setup_page(self)
        self.interview_page = create_interview_page(self)
        self.results_page = create_results_page(self)

        # --- Add Pages to Stack ---
        self.stacked_widget.addWidget(self.setup_page)       # Index 0
        self.stacked_widget.addWidget(self.interview_page)    # Index 1
        self.stacked_widget.addWidget(self.results_page)      # Index 2

        # --- Set Initial Page ---
        self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)

        self.setLayout(main_window_layout)

    def _update_ui_from_state(self):
        """Ensures UI controls reflect the current state variables."""
        print("Updating UI from state...")
        # Update Setup Page controls
        if hasattr(self, 'file_label') and self.file_label:
            self.file_label.setText(os.path.basename(self.pdf_filepath) if self.pdf_filepath else "No resume selected.")
        if hasattr(self, 'job_desc_input') and self.job_desc_input:
            self.job_desc_input.setPlainText(self.job_description_text) # Use setPlainText
        if hasattr(self, 'num_topics_label') and self.num_topics_label:
            self.num_topics_label.setText(str(self.num_topics))
        if hasattr(self, 'max_follow_ups_label') and self.max_follow_ups_label:
            self.max_follow_ups_label.setText(str(self.max_follow_ups))
        if hasattr(self, 'speech_checkbox') and self.speech_checkbox:
            self.speech_checkbox.setChecked(self.use_speech_input)

        # Enable/disable setup controls based on whether a PDF is loaded
        pdf_loaded = bool(self.pdf_filepath)
        self.set_setup_controls_state(pdf_loaded) # Enable based on loaded state
        if hasattr(self, 'select_btn') and self.select_btn:
             self.select_btn.setEnabled(True) # Select is always enabled initially

        # Reset Interview Page controls (usually cleared on reset)
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()

        # Reset Results Page controls (usually cleared on reset)
        if hasattr(self, 'summary_text_results'): self.summary_text_results.clear()
        if hasattr(self, 'assessment_text_results'): self.assessment_text_results.clear()

        # Set initial status message on interview page (even though hidden)
        self.update_status("[Interview Not Started]", busy=False)


    # --- Navigation Methods ---
    def _go_to_setup_page(self):
        """Switches to the setup page and resets the application state."""
        print("Navigating to Setup Page and Resetting...")
        # Perform a full reset including configuration
        self.reset_interview_state(clear_config=True) # This now resets state vars and UI elements
        self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX) # Switch view


    def _go_to_interview_page(self):
        """Switches to the interview page."""
        print("Navigating to Interview Page...")
        # Clear potential leftover text from previous interviews
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()
        self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)


    def _go_to_results_page(self, summary, assessment):
        """Populates results widgets and switches to the results page."""
        print("Navigating to Results Page...")
        # Populate the text boxes on the results page
        if hasattr(self, 'summary_text_results') and self.summary_text_results:
            self.summary_text_results.setPlainText(summary or "N/A")
        if hasattr(self, 'assessment_text_results') and self.assessment_text_results:
            self.assessment_text_results.setPlainText(assessment or "N/A")

        self.stacked_widget.setCurrentIndex(self.RESULTS_PAGE_INDEX)

    # --- PyQt Helper Methods --- (Keep _load_icon_internal, show_message_box)
    def _load_icon_internal(self, filename, size=None):
        try:
            path = os.path.join(self.icon_path, filename)
            if not os.path.exists(path):
                print(f"Warning: Icon not found at {path}"); return None
            return QIcon(path)
        except Exception as e:
            print(f"Error loading icon {filename}: {e}"); return None

    def show_message_box(self, level, title, message):
        box = QMessageBox(self)
        icon_map = {"info": QMessageBox.Icon.Information,
                    "warning": QMessageBox.Icon.Warning,
                    "error": QMessageBox.Icon.Critical}
        box.setIcon(icon_map.get(level, QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok); box.exec()

    # --- State Update Handlers --- (Keep _adjust_value)
    def _adjust_value(self, value_type, amount):
        current_val, min_val, max_val, target_label, target_var_name = 0, 0, 0, None, ""
        if value_type == 'topics':
            current_val, min_val, max_val = self.num_topics, logic.MIN_TOPICS, logic.MAX_TOPICS
            target_label, target_var_name = self.num_topics_label, 'num_topics'
        elif value_type == 'followups':
            current_val, min_val, max_val = self.max_follow_ups, logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT
            target_label, target_var_name = self.max_follow_ups_label, 'max_follow_ups'
        else: return

        new_value = current_val + amount
        if min_val <= new_value <= max_val:
            setattr(self, target_var_name, new_value)
            if target_label: target_label.setText(str(new_value))
            print(f"{target_var_name.replace('_', ' ').title()} set to: {new_value}")
        else: print(f"Value {new_value} out of bounds ({min_val}-{max_val})")

    # --- Core Logic/State Management Methods ---
    # (Keep update_status, display_question, add_to_history,
    # set_setup_controls_state, enable_interview_controls, disable_interview_controls,
    # reset_interview_state, _clean_question_text, save_transcript_to_file)

    def update_status(self, message, busy=False):
        # Update status on the *interview page* text widget
        if hasattr(self, 'current_q_text') and self.current_q_text:
            if not self.is_recording:
                self.current_q_text.setText(message)
                self.current_q_text.ensureCursorVisible()
        if busy: QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else: QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def display_question(self, question_text):
        self.last_question_asked = question_text # Store question
        self.update_status(question_text, busy=False) # Display on interview page
        try: audio_handler.speak_text(question_text)
        except Exception as e: print(f"UI Error: Failed to initiate TTS: {e}")
        self.enable_interview_controls()
        if hasattr(self, 'answer_input') and self.answer_input and not self.use_speech_input:
            self.answer_input.setFocus()

    def add_to_history(self, text, tag=None):
        # Add to history text widget on the *interview page*
        if not hasattr(self, 'history_text') or not self.history_text: return
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_text.setTextCursor(cursor)
        if tag == "question_style": self.history_text.insertHtml(f'<font color="#569CD6">{text}</font>')
        elif tag == "answer_style": self.history_text.insertHtml(f'<font color="{self.palette().color(QPalette.ColorRole.Text).name()}">{text}</font>')
        elif tag == "topic_marker": self.history_text.insertHtml(f'<font color="grey"><b>{text}</b></font>')
        else: self.history_text.insertPlainText(text)
        self.history_text.ensureCursorVisible()

    def set_setup_controls_state(self, enabled):
        """Enables/disables controls on the setup page."""
        # Controls specific to Setup Page
        if hasattr(self, 'job_desc_input'): self.job_desc_input.setEnabled(enabled)
        if hasattr(self, 'topic_minus_btn'): self.topic_minus_btn.setEnabled(enabled)
        if hasattr(self, 'topic_plus_btn'): self.topic_plus_btn.setEnabled(enabled)
        if hasattr(self, 'num_topics_label'): self.num_topics_label.setEnabled(enabled)
        if hasattr(self, 'followup_minus_btn'): self.followup_minus_btn.setEnabled(enabled)
        if hasattr(self, 'followup_plus_btn'): self.followup_plus_btn.setEnabled(enabled)
        if hasattr(self, 'max_follow_ups_label'): self.max_follow_ups_label.setEnabled(enabled)
        if hasattr(self, 'speech_checkbox'): self.speech_checkbox.setEnabled(enabled)
        if hasattr(self, 'start_interview_btn'): self.start_interview_btn.setEnabled(enabled)
        # Select button is handled separately in select_resume_file

    def enable_interview_controls(self):
        # Controls specific to Interview Page
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'): return
        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.update_submit_button_text()

    def disable_interview_controls(self, is_recording_stt=False):
        # Controls specific to Interview Page
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'): return
        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt
        if is_recording_stt:
            self.submit_button.setText("Recording...")
            if hasattr(self, 'record_icon') and self.record_icon: self.submit_button.setIcon(self.record_icon)
            else: self.submit_button.setIcon(QIcon())

    def reset_interview_state(self, clear_config=True):
        """Resets application state and relevant UI elements across pages."""
        print(f"Resetting interview state (clear_config={clear_config})...")
        # Reset python state variables
        if clear_config:
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False
        # Always reset interview progress state
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""

        # Update UI elements to reflect the new state
        self._update_ui_from_state()

        # Ensure interview controls are disabled after reset
        self.disable_interview_controls()

        QApplication.restoreOverrideCursor() # Ensure cursor is normal
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text):
        # (Keep as before)
        cleaned_q = raw_q_text.strip()
        if cleaned_q and cleaned_q[0].isdigit():
            parts = cleaned_q.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned_q.split(' ', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            return cleaned_q
        return cleaned_q

    def save_transcript_to_file(self):
        # (Keep as before)
        if not self.current_full_interview_history: print("No history to save."); return
        if not self.cleaned_initial_questions: print("Warning: Cleaned Qs missing..."); return # Add fallback if needed
        transcript_lines, current_topic_num, current_follow_up_num = [], 0, 0
        try:
            # ... (structured transcript logic as before) ...
            for qa_pair in self.current_full_interview_history:
                q, a = qa_pair.get('q', 'N/A'), qa_pair.get('a', 'N/A')
                is_initial = q in self.cleaned_initial_questions
                if is_initial:
                    topic_index = -1
                    try: raw_q_match = next(rq for rq in self.initial_questions if self._clean_question_text(rq) == q); topic_index = self.initial_questions.index(raw_q_match)
                    except StopIteration: print(f"Warn: Q mismatch '{q}'")
                    if topic_index != -1 and topic_index + 1 > current_topic_num:
                        current_topic_num = topic_index + 1; current_follow_up_num = 0
                        if current_topic_num > 1: transcript_lines.append("---")
                        transcript_lines.append(f"Q {current_topic_num}: {q}\nA: {a}")
                    else: # Follow-up (re-ask/mismatch)
                        current_follow_up_num += 1; transcript_lines.append("")
                        ctx = f"Topic {current_topic_num}" if current_topic_num > 0 else "Uncertain"
                        transcript_lines.append(f"Follow Up {current_follow_up_num} (re {ctx}): {q}\nA: {a}")
                else: # Normal Follow-up
                    current_follow_up_num += 1; transcript_lines.append("")
                    transcript_lines.append(f"Follow Up {current_follow_up_num}: {q}\nA: {a}")
                transcript_lines.append("")

            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving transcript to {filepath}...")
            with open(filepath, "w", encoding="utf-8") as f: f.write("\n".join(transcript_lines).strip())
            print("Transcript saved.")
        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript: {e}")

    # --- GUI Logic/Event Handlers ---

    def update_submit_button_text(self, state=None):
        # (Keep as before - updates button on Interview page)
        if state is not None: self.use_speech_input = (state == Qt.CheckState.Checked.value)
        if not hasattr(self, 'submit_button'): return
        if self.submit_button.isEnabled() or self.is_recording:
            if self.use_speech_input:
                self.submit_button.setText("Record Answer")
                if hasattr(self, 'record_icon') and self.record_icon: self.submit_button.setIcon(self.record_icon)
                else: self.submit_button.setIcon(QIcon())
                if hasattr(self, 'answer_input'): self.answer_input.setReadOnly(True); self.answer_input.clear(); self.answer_input.setPlaceholderText("Click 'Record Answer'..."); self.answer_input.setEnabled(False)
            else:
                self.submit_button.setText("Submit Answer")
                if hasattr(self, 'submit_icon') and self.submit_icon: self.submit_button.setIcon(self.submit_icon)
                else: self.submit_button.setIcon(QIcon())
                if hasattr(self, 'answer_input'): self.answer_input.setReadOnly(False); self.answer_input.setPlaceholderText("Type answer..."); self.answer_input.setEnabled(True);
                if self.submit_button.isEnabled(): self.answer_input.setFocus()
        else:
            if not self.is_recording: # Reset appearance if disabled and not recording
                 default_text = "Record Answer" if self.use_speech_input else "Submit Answer"
                 default_icon = self.record_icon if self.use_speech_input else self.submit_icon
                 self.submit_button.setText(default_text)
                 if default_icon: self.submit_button.setIcon(default_icon)
                 else: self.submit_button.setIcon(QIcon())

    def select_resume_file(self):
        # (Keep as before - updates widgets on Setup page)
        start_dir = os.path.expanduser("~")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Resume PDF", start_dir, "PDF Files (*.pdf);;All Files (*)")
        if not filepath:
            if hasattr(self, 'file_label') and not self.pdf_filepath: self.file_label.setText("Selection cancelled.")
            return
        self.pdf_filepath = filepath; filename = os.path.basename(filepath)
        if hasattr(self, 'file_label'): self.file_label.setText(filename)
        self.set_setup_controls_state(True) # Enable config controls
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False) # Disable select itself
        self.update_status("[Ready to configure or start]", busy=False) # Update status on interview page (though hidden)
        if hasattr(self, 'job_desc_input'): self.job_desc_input.setFocus()

    def start_interview_process(self):
        """Validates setup, generates questions, switches to Interview page."""
        if not self.pdf_filepath:
            self.show_message_box("warning", "Input Missing", "Please select a resume PDF first."); return
        if hasattr(self, 'job_desc_input'): self.job_description_text = self.job_desc_input.toPlainText().strip()
        else: self.job_description_text = ""

        print(f"Preparing Interview: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, Speech={self.use_speech_input}")

        # --- Reset Interview State (but keep config) ---
        # This clears history, counters etc. NOT num_topics/max_follow_ups
        self.reset_interview_state(clear_config=False)

        # --- Background Tasks ---
        self.update_status("Extracting text from PDF...", busy=True)
        # TODO: Threading
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        QApplication.processEvents()
        if self.resume_content is None:
            self.update_status("[Error extracting PDF text]", busy=False)
            self.show_message_box("error", "PDF Error", "Failed to extract text..."); return

        self.update_status(f"Generating {self.num_topics} initial questions...", busy=True)
        # TODO: Threading
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content, job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()
        if not self.initial_questions:
            self.update_status("[Error generating questions]", busy=False)
            self.show_message_box("error", "Generation Error", "Failed to generate questions..."); return

        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}

        # --- Switch Page and Start ---
        self._go_to_interview_page()
        self.current_initial_q_index = 0
        self.start_next_topic() # Ask the first question


    def start_next_topic(self):
        """Asks the next initial question or ends the interview."""
        if not self.initial_questions:
            print("Error: Cannot start next topic, initial questions list is empty."); self._go_to_setup_page(); return

        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0; self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text)
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker")
            print(f"Asking Initial Q {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(self.current_topic_question) # Sets last_question_asked
        else:
            # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Interview complete. Generating results...", busy=True)
            self.disable_interview_controls()
            self.save_transcript_to_file()
            # TODO: Threading
            print("Generating summary...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating assessment...")
            assessment = logic.generate_qualification_assessment(self.resume_content, self.job_description_text, self.current_full_interview_history)
            QApplication.restoreOverrideCursor()
            if summary.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Summary Error", "Could not generate summary...")
            if assessment.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Assessment Error", "Could not generate assessment...")
            # --- Switch to Results Page ---
            self._go_to_results_page(summary, assessment)


    def handle_answer_submission(self):
        # (Keep as before - handles button click on Interview page)
        if self.is_recording: print("Already recording..."); return
        if self.use_speech_input:
            print("Record button clicked...")
            self.disable_interview_controls(is_recording_stt=True); self.update_status_stt("STT_Status: Starting Mic...")
            if hasattr(self, 'answer_input'): self.answer_input.clear()
            topic_idx = self.current_initial_q_index + 1; followup_idx = self.follow_up_count
            audio_handler.start_speech_recognition(topic_idx, followup_idx)
        else:
            print("Submit button clicked.")
            if not hasattr(self, 'answer_input'): print("Error: answer_input missing."); return
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer: self.show_message_box("warning", "Input Required", "Please enter answer."); return
            self.process_answer(user_answer)

    def update_status_stt(self, message):
        # (Keep as before - updates status text on Interview page)
        if not hasattr(self, 'current_q_text') or not self.current_q_text: return
        display_message = message; btn_txt = None
        if message == "STT_Status: Adjusting...": display_message = "[Calibrating...]"
        elif message == "STT_Status: Listening...": display_message = "[Listening...]"; btn_txt = "Listening..."
        elif message == "STT_Status: Processing...": display_message = "[Processing...]"; btn_txt = "Processing..."
        elif message.startswith("STT_Error:"): display_message = f"[STT Error: {message.split(':', 1)[1].strip()}]"
        elif message.startswith("STT_Success:"): display_message = "[Speech Recognized]"
        self.current_q_text.setText(display_message)
        if btn_txt and self.is_recording and hasattr(self, 'submit_button'): self.submit_button.setText(btn_txt)
        QApplication.processEvents()

    def check_stt_queue(self):
        # (Keep as before - handles results from audio_handler)
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
                self.process_answer(transcript) # Process the transcript
            elif result.startswith("STT_Error:"):
                self.is_recording = False; error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result); self.show_message_box("error", "STT Error", error_message)
                self.enable_interview_controls()
        except queue.Empty: pass
        except Exception as e:
            print(f"Error processing STT queue: {e}")
            if self.is_recording: self.is_recording = False; self.enable_interview_controls()

    def process_answer(self, user_answer):
        # (Keep as before - processes answer, generates follow-up, calls start_next_topic)
        if not hasattr(self, 'last_question_asked') or not self.last_question_asked:
             print("Warn: last_question_asked missing."); last_q = "[Unknown Q]"
        else: last_q = self.last_question_asked
        print(f"Processing answer for Q: '{last_q}' -> A: '{user_answer[:50]}...'")
        q_data = {"q": last_q, "a": user_answer}
        if hasattr(self, 'current_topic_history'): self.current_topic_history.append(q_data)
        if hasattr(self, 'current_full_interview_history'): self.current_full_interview_history.append(q_data)
        self.add_to_history(f"Q: {last_q}\n", tag="question_style"); self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        if hasattr(self, 'answer_input'): self.answer_input.clear()
        self.disable_interview_controls(); self.update_status("Generating response...", busy=True)

        if hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups') and self.follow_up_count < self.max_follow_ups:
            # TODO: Threading
            print(f"Generating follow-up ({self.follow_up_count + 1}/{self.max_follow_ups})...")
            follow_up_q = logic.generate_follow_up_question(self.current_topic_question, user_answer, self.current_topic_history)
            QApplication.restoreOverrideCursor()
            if follow_up_q and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1; print(f"Asking Follow-up {self.follow_up_count}: {follow_up_q}")
                self.display_question(follow_up_q) # Sets last_question_asked
            elif follow_up_q == "[END TOPIC]":
                print("No more follow-ups ([END TOPIC]).");
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
            else: # Error (None)
                print("Error generating follow-up."); self.show_message_box("error", "Generation Error", "Error generating follow-up...")
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
        else:
            if not (hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups')): print("Warn: follow-up state missing.")
            else: print(f"Max follow-ups ({self.max_follow_ups}) reached.")
            QApplication.restoreOverrideCursor()
            if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
            self.start_next_topic()
        if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()

    # --- Window Close ---
    def closeEvent(self, event):
        # (Keep as before)
        print("Closing application window...")
        if hasattr(self, 'stt_timer'): self.stt_timer.stop(); print("STT timer stopped.")
        # No review dialog to close now
        print("Cleanup complete. Accepting close event.")
        event.accept()