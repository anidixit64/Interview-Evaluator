# ui/main_window.py
import os
import sys
import queue
import platform # For opening folder
import subprocess # For opening folder fallback

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QApplication, QStackedWidget,
    QLabel, QSizePolicy, QFrame # Added QFrame
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QUrl

# --- Project Imports ---
import core.logic as logic
import core.audio_handler as audio_handler
from core.audio_handler import RECORDINGS_DIR

# Import UI component creation functions
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
        self.setGeometry(100, 100, 850, 1000)

        self._setup_appearance()
        self._load_assets() # Load only icons needed directly here
        self._init_state()
        self._setup_ui()   # Now sets up QStackedWidget
        self._update_ui_from_state() # Set initial UI state based on variables
        self._update_progress_indicator() # Set initial progress text
        self.stt_timer = QTimer(self)
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100)


    def _setup_appearance(self):
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
        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)
        self.setPalette(palette)
        QApplication.setStyle("Fusion")

    def _load_assets(self): # Load only common/needed icons here
        self.icon_size = QSize(20, 20)
        self.submit_icon = self._load_icon_internal("send.png", self.icon_size)
        self.record_icon = self._load_icon_internal("mic_black_36dp.png", self.icon_size)
        self.listening_icon = self._load_icon_internal("record_wave.png", self.icon_size)
        self.processing_icon = self._load_icon_internal("spinner.png", self.icon_size)
        # Fonts
        self.font_default = QFont("Arial", 10)
        self.font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 9)
        self.font_large_bold = QFont("Arial", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9)

    def _init_state(self): # (Add new widget refs)
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
        self.use_speech_input = False
        self.is_recording = False
        self.last_question_asked = ""
        # Widget refs - set by components.py
        self.select_btn=None
        self.file_label=None
        self.job_desc_input=None
        self.topic_minus_btn=None
        self.topic_plus_btn=None
        self.num_topics_label=None
        self.followup_minus_btn=None
        self.followup_plus_btn=None
        self.max_follow_ups_label=None
        self.speech_checkbox=None
        self.start_interview_btn=None
        self.current_q_text=None
        self.answer_input=None
        self.submit_button=None
        self.history_text=None
        self.summary_text_results=None
        self.assessment_text_results=None
        self.new_interview_button=None
        self.save_report_button=None
        self.open_folder_button=None
        # New UI elements
        self.progress_indicator_label = None
        self.status_bar_label = None

    def _setup_ui(self): # Setup Stack + Status/Progress
        main_window_layout = QVBoxLayout(self)
        main_window_layout.setContentsMargins(0,0,0,0)
        main_window_layout.setSpacing(0)

        # --- Progress Indicator ---
        self.progress_indicator_label = QLabel("...")
        self.progress_indicator_label.setObjectName("progressIndicator")
        self.progress_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_indicator_label.setTextFormat(Qt.TextFormat.RichText) # Allow HTML/Rich Text
        main_window_layout.addWidget(self.progress_indicator_label)

        # --- Separator Line ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_window_layout.addWidget(line)

        # --- Stacked Widget ---
        self.stacked_widget = QStackedWidget()
        main_window_layout.addWidget(self.stacked_widget, stretch=1)

        # --- Create Pages ---
        self.setup_page = create_setup_page(self)
        self.interview_page = create_interview_page(self)
        self.results_page = create_results_page(self)

        # --- Add Pages to Stack ---
        self.stacked_widget.addWidget(self.setup_page)
        self.stacked_widget.addWidget(self.interview_page)
        self.stacked_widget.addWidget(self.results_page)

        # --- Status Bar ---
        self.status_bar_label = QLabel("Ready.")
        self.status_bar_label.setObjectName("statusBar")
        main_window_layout.addWidget(self.status_bar_label)

        self.setLayout(main_window_layout)

    def _update_ui_from_state(self): # Update setup page state
        print("Updating UI from state...")
        pdf_loaded = bool(self.pdf_filepath)

        # Setup page updates
        if hasattr(self, 'file_label') and self.file_label:
            self.file_label.setText(os.path.basename(self.pdf_filepath) if pdf_loaded else "No resume selected.")
        if hasattr(self, 'job_desc_input') and self.job_desc_input:
            self.job_desc_input.setPlainText(self.job_description_text)
            self.job_desc_input.setEnabled(pdf_loaded)
        if hasattr(self, 'num_topics_label') and self.num_topics_label:
            self.num_topics_label.setText(str(self.num_topics))
        if hasattr(self, 'max_follow_ups_label') and self.max_follow_ups_label:
            self.max_follow_ups_label.setText(str(self.max_follow_ups))
        if hasattr(self, 'speech_checkbox') and self.speech_checkbox:
            self.speech_checkbox.setChecked(self.use_speech_input)

        # Update enabled state of setup controls
        self.set_setup_controls_state(pdf_loaded)
        if hasattr(self, 'select_btn') and self.select_btn:
             self.select_btn.setEnabled(True) # Select always enabled initially

        # Clear Interview/Results pages (relevant after reset)
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()
        if hasattr(self, 'summary_text_results'): self.summary_text_results.clear()
        if hasattr(self, 'assessment_text_results'): self.assessment_text_results.clear()

        # Reset status bar
        self.update_status("Ready.")
        # Set initial page (usually setup after reset)
        self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)

    # --- Navigation/Progress ---
    def _update_progress_indicator(self):
        if not hasattr(self, 'progress_indicator_label') or not self.progress_indicator_label:
             return
        current_index = self.stacked_widget.currentIndex()
        steps = ["Step 1: Setup", "Step 2: Interview", "Step 3: Results"]
        progress_parts = []
        for i, step in enumerate(steps):
            if i == current_index:
                # --- MODIFICATION ---
                # Wrap the bold tag with a font tag for color
                progress_parts.append(f'<font color="orange"><b>{step}</b></font>')
                # --- END MODIFICATION ---
            else:
                progress_parts.append(step)
        # Join with HTML arrow entity
        progress_text = " → ".join(progress_parts)
        self.progress_indicator_label.setText(progress_text)


    def _go_to_setup_page(self):
        print("Navigating to Setup Page and Resetting...")
        self.reset_interview_state(clear_config=True) # Full reset
        self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self._update_progress_indicator()

    def _go_to_interview_page(self):
        print("Navigating to Interview Page...")
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()
        self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview started. Waiting for question...")

    def _go_to_results_page(self, summary, assessment):
        print("Navigating to Results Page...")
        if hasattr(self, 'summary_text_results') and self.summary_text_results:
            self.summary_text_results.setMarkdown(summary or "*Summary generation failed or N/A*")
        if hasattr(self, 'assessment_text_results') and self.assessment_text_results:
            self.assessment_text_results.setMarkdown(assessment or "*Assessment generation failed or N/A*")
        self.stacked_widget.setCurrentIndex(self.RESULTS_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview complete. Results displayed.")

    # --- Helpers & State Updates ---
    def _load_icon_internal(self, filename, size=None):
        try:
            path = os.path.join(self.icon_path, filename)
            return QIcon(path) if os.path.exists(path) else None
        except Exception as e:
            print(f"Icon error {filename}: {e}")
            return None

    def show_message_box(self, level, title, message):
        box = QMessageBox(self)
        icon_map = {"info": QMessageBox.Icon.Information, "warning": QMessageBox.Icon.Warning, "error": QMessageBox.Icon.Critical}
        box.setIcon(icon_map.get(level, QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _adjust_value(self, value_type, amount):
        current_val, min_val, max_val, target_label, target_var_name = 0, 0, 0, None, ""
        if value_type == 'topics':
            current_val, min_val, max_val, target_label, target_var_name = self.num_topics, logic.MIN_TOPICS, logic.MAX_TOPICS, self.num_topics_label, 'num_topics'
        elif value_type == 'followups':
            current_val, min_val, max_val, target_label, target_var_name = self.max_follow_ups, logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT, self.max_follow_ups_label, 'max_follow_ups'
        else:
            return
        new_value = current_val + amount
        if min_val <= new_value <= max_val:
            setattr(self, target_var_name, new_value)
            if target_label: target_label.setText(str(new_value))
            print(f"{target_var_name.replace('_',' ').title()} set to: {new_value}")
        else:
            print(f"Value {new_value} out of bounds ({min_val}-{max_val})")

    def update_status(self, message, busy=False): # Update Status Bar
        if self.status_bar_label:
            self.status_bar_label.setText(message)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def display_question(self, question_text): # Sets last_question_asked
        self.last_question_asked = question_text
        if hasattr(self, 'current_q_text') and self.current_q_text:
            self.current_q_text.setPlainText(question_text)
        else:
            self.update_status(f"Asking: {question_text[:30]}...")
        try:
            audio_handler.speak_text(question_text)
        except Exception as e:
            print(f"TTS Error: {e}")
        self.enable_interview_controls()
        if hasattr(self, 'answer_input') and self.answer_input and not self.use_speech_input:
            self.answer_input.setFocus()

    def add_to_history(self, text, tag=None): # Add to Transcript view
        if not hasattr(self, 'history_text') or not self.history_text:
            return
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_text.setTextCursor(cursor)
        if tag == "question_style":
            self.history_text.insertHtml(f'<font color="#569CD6">{text}</font>')
        elif tag == "answer_style":
            self.history_text.insertHtml(f'<font color="{self.palette().color(QPalette.ColorRole.Text).name()}">{text}</font>')
        elif tag == "topic_marker":
            self.history_text.insertHtml(f'<font color="grey"><b>{text}</b></font>')
        else:
            self.history_text.insertPlainText(text)
        self.history_text.ensureCursorVisible()

    def set_setup_controls_state(self, enabled): # Enable/Disable Setup Page Controls
        pdf_needed_controls = [
            self.job_desc_input, self.topic_minus_btn, self.topic_plus_btn, self.num_topics_label,
            self.followup_minus_btn, self.followup_plus_btn, self.max_follow_ups_label,
            self.speech_checkbox, self.start_interview_btn
        ]
        for widget in pdf_needed_controls:
            if widget: # Check if widget object exists
                widget.setEnabled(enabled)

    def enable_interview_controls(self): # Enable Interview Page Controls
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.set_recording_button_state('idle')

    def disable_interview_controls(self, is_recording_stt=False): # Disable Interview Page Controls
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt
        # Button state set via set_recording_button_state or update_status_stt

    def reset_interview_state(self, clear_config=True): # Reset state and UI
        print(f"Resetting interview state (clear_config={clear_config})...")
        if clear_config:
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""
        self._update_ui_from_state() # Update UI based on reset values
        self.disable_interview_controls()
        QApplication.restoreOverrideCursor()
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text):
        cleaned = raw_q_text.strip()
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split('.', 1)
            if len(parts)>1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(' ', 1)
            if len(parts)>1 and parts[0].isdigit(): return parts[1].strip()
        return cleaned

    def save_transcript_to_file(self):
        if not self.current_full_interview_history: print("No history to save."); return
        if not self.cleaned_initial_questions: print("Warning: Cleaned Qs missing..."); return
        transcript_lines = []
        current_topic_num = 0
        current_follow_up_num = 0
        try:
            for qa_pair in self.current_full_interview_history:
                q, a = qa_pair.get('q', 'N/A'), qa_pair.get('a', 'N/A')
                is_initial = q in self.cleaned_initial_questions
                if is_initial:
                    topic_index = -1
                    try:
                        raw_q_match = next(rq for rq in self.initial_questions if self._clean_question_text(rq) == q)
                        topic_index = self.initial_questions.index(raw_q_match)
                    except StopIteration:
                        print(f"Warn: Q mismatch '{q}'")
                    if topic_index != -1 and topic_index + 1 > current_topic_num:
                        current_topic_num = topic_index + 1
                        current_follow_up_num = 0
                        if current_topic_num > 1: transcript_lines.append("-------------------------")
                        transcript_lines.append(f"Question {current_topic_num}: {q}\nAnswer: {a}")
                    else:
                        current_follow_up_num += 1
                        transcript_lines.append("")
                        ctx = f"Topic {current_topic_num}" if current_topic_num > 0 else "Uncertain"
                        transcript_lines.append(f"Follow Up {current_follow_up_num} (re {ctx}): {q}\nAnswer: {a}")
                else:
                    current_follow_up_num += 1
                    transcript_lines.append("")
                    transcript_lines.append(f"Follow Up {current_follow_up_num}: {q}\nAnswer: {a}")
                transcript_lines.append("")

            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving transcript to {filepath}...")
            with open(filepath, "w", encoding="utf-8") as f: f.write("\n".join(transcript_lines).strip())
            print("Transcript saved.")
        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript: {e}")

    # --- Button State Helper ---
    def set_recording_button_state(self, state): # Update record/submit button
        if not hasattr(self, 'submit_button'): return
        current_icon = self.submit_button.icon()
        target_icon = None
        target_text = "Submit Answer" # Default

        if state == 'listening':
            target_text = "Listening..."
            target_icon = self.listening_icon
            self.submit_button.setEnabled(False)
        elif state == 'processing':
            target_text = "Processing..."
            target_icon = self.processing_icon
            self.submit_button.setEnabled(False)
        elif state == 'idle':
            self.submit_button.setEnabled(not self.is_recording) # Re-enable if not recording
            if self.use_speech_input:
                 target_text = "Record Answer"
                 target_icon = self.record_icon
            else:
                 target_text = "Submit Answer"
                 target_icon = self.submit_icon
        else: # Fallback
            if self.use_speech_input: target_text, target_icon = "Record Answer", self.record_icon
            else: target_text, target_icon = "Submit Answer", self.submit_icon

        self.submit_button.setText(target_text)
        if target_icon:
            self.submit_button.setIcon(target_icon)
        # else: self.submit_button.setIcon(QIcon()) # Option to clear icon

    # --- GUI Logic/Event Handlers ---

    def update_submit_button_text(self, state=None): # Simplified, uses set_recording_button_state
        if state is not None:
            self.use_speech_input = (state == Qt.CheckState.Checked.value)
            print(f"Use Speech: {self.use_speech_input}")
        if not self.is_recording:
            self.set_recording_button_state('idle') # Update idle appearance
        if hasattr(self, 'answer_input'): # Enable/disable text input
            is_text_mode = not self.use_speech_input
            controls_enabled = hasattr(self, 'submit_button') and self.submit_button.isEnabled()
            self.answer_input.setReadOnly(not is_text_mode)
            self.answer_input.setEnabled(is_text_mode and controls_enabled)
            if is_text_mode and controls_enabled:
                self.answer_input.setFocus()
            elif not is_text_mode:
                self.answer_input.clear()
                self.answer_input.setPlaceholderText("Click 'Record Answer'...")

    def select_resume_file(self): # Update status bar
        start_dir = os.path.expanduser("~")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select PDF", start_dir, "*.pdf;;*")
        if not filepath:
            if hasattr(self, 'file_label') and not self.pdf_filepath:
                self.file_label.setText("Selection cancelled.")
            self.update_status("Resume selection cancelled.")
            return

        # --- File successfully selected ---
        self.pdf_filepath = filepath
        filename = os.path.basename(filepath)

        if hasattr(self, 'file_label'):
            self.file_label.setText(filename)

        # Enable other setup controls now that a resume is loaded
        self.set_setup_controls_state(True)

    
        self.update_status("Resume selected. Configure interview or paste job description.")

        if hasattr(self, 'job_desc_input'):
            self.job_desc_input.setFocus()

    def start_interview_process(self): # Navigate on success
        if not self.pdf_filepath:
            self.show_message_box("warning", "Input Missing", "Select resume PDF.")
            return
        if hasattr(self, 'job_desc_input'):
            self.job_description_text = self.job_desc_input.toPlainText().strip()
        print(f"Preparing: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, Speech={self.use_speech_input}")
        self.reset_interview_state(clear_config=False)
        self.update_status("Extracting PDF...", True)
        # TODO: Threading
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        QApplication.processEvents()
        if self.resume_content is None:
            self.update_status("[Error extracting PDF]", False)
            self.show_message_box("error", "PDF Error", "Failed to extract text...")
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True) # Re-enable select
            self.set_setup_controls_state(False) # Disable others
            return
        self.update_status(f"Generating {self.num_topics} questions...", True)
        # TODO: Threading
        self.initial_questions = logic.generate_initial_questions(resume_text=self.resume_content, job_desc_text=self.job_description_text, num_questions=self.num_topics)
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()
        if not self.initial_questions:
            self.update_status("[Error generating questions]", False)
            self.show_message_box("error", "Gen Error", "Failed to generate questions...")
            if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True) # Re-enable select
            self.set_setup_controls_state(True) # Re-enable config if PDF was ok
            return
        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        self._go_to_interview_page()
        self.current_initial_q_index = 0
        self.start_next_topic()

    def start_next_topic(self): # Navigate on finish
        if not self.initial_questions:
            print("Err: No initial questions.")
            self._go_to_setup_page()
            return
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0
            self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text)
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker")
            print(f"Asking Q {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(self.current_topic_question) # Sets last_question_asked
        else: # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Generating results...", True)
            self.disable_interview_controls()
            self.save_transcript_to_file()
            # TODO: Threading
            print("Gen summary...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Gen assessment...")
            assessment = logic.generate_qualification_assessment(self.resume_content, self.job_description_text, self.current_full_interview_history)
            QApplication.restoreOverrideCursor()
            if summary.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Summary Error", "Could not generate summary...")
            if assessment.startswith(logic.ERROR_PREFIX): self.show_message_box("warning", "Assessment Error", "Could not generate assessment...")
            self._go_to_results_page(summary, assessment) # Navigate to Results

    def handle_answer_submission(self): # Uses set_recording_button_state
        if self.is_recording: print("Already recording..."); return
        if self.use_speech_input:
            print("Record button clicked...")
            self.disable_interview_controls(is_recording_stt=True)
            self.update_status_stt("STT_Status: Starting Mic...")
            if hasattr(self, 'answer_input'): self.answer_input.clear()
            topic_idx, followup_idx = self.current_initial_q_index + 1, self.follow_up_count
            audio_handler.start_speech_recognition(topic_idx, followup_idx)
        else: # Text submission
            print("Submit button clicked.")
            if not hasattr(self, 'answer_input'): print("Error: answer_input missing."); return
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer: self.show_message_box("warning", "Input Required", "Please enter answer."); return
            self.process_answer(user_answer)

    def update_status_stt(self, message): # Update Status Bar, trigger button state change
        if not self.status_bar_label: return
        display_message = message
        button_state = 'idle'
        if message == "STT_Status: Adjusting...": display_message = "[Calibrating microphone...]"
        elif message == "STT_Status: Listening...": display_message = "[Listening...]"; button_state = 'listening'
        elif message == "STT_Status: Processing...": display_message = "[Processing...]"; button_state = 'processing'
        elif message.startswith("STT_Error:"): display_message = f"[STT Error: {message.split(':', 1)[1].strip()}]"; button_state = 'idle'
        elif message.startswith("STT_Success:"): display_message = "[Speech Recognized]"; button_state = 'idle'
        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state)
        QApplication.processEvents()

    def check_stt_queue(self): # Uses set_recording_button_state
        try:
            result = audio_handler.stt_result_queue.get_nowait()
            print(f"STT Queue: {result}")
            if result.startswith("STT_Status:"): self.update_status_stt(result)
            elif result.startswith("STT_Success:"):
                self.is_recording = False
                self.update_status_stt(result)
                transcript = result.split(":", 1)[1].strip()
                if hasattr(self, 'answer_input'):
                    self.answer_input.setEnabled(True)
                    self.answer_input.setReadOnly(False)
                    self.answer_input.setText(transcript)
                    self.answer_input.setReadOnly(True)
                    self.answer_input.setEnabled(False)
                self.process_answer(transcript)
            elif result.startswith("STT_Error:"):
                self.is_recording = False
                error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result)
                self.show_message_box("error", "STT Error", error_message)
                self.enable_interview_controls()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"STT Queue Error: {e}")
            if self.is_recording:
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()

    def process_answer(self, user_answer):
        last_q = self.last_question_asked if hasattr(self, 'last_question_asked') and self.last_question_asked else "[Unknown Q]"
        print(f"Processing answer for Q: '{last_q}' -> A: '{user_answer[:50]}...'")
        q_data = {"q": last_q, "a": user_answer}
        if hasattr(self, 'current_topic_history'): self.current_topic_history.append(q_data)
        if hasattr(self, 'current_full_interview_history'): self.current_full_interview_history.append(q_data)
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        self.disable_interview_controls()
        self.update_status("Generating response...", True)
        # Follow-up logic...
        if hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups') and self.follow_up_count < self.max_follow_ups:
            follow_up_q = logic.generate_follow_up_question(self.current_topic_question, user_answer, self.current_topic_history)
            QApplication.restoreOverrideCursor()
            if follow_up_q and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1
                print(f"Asking Follow-up: {follow_up_q}")
                self.display_question(follow_up_q)
            elif follow_up_q == "[END TOPIC]":
                print("End topic signal.")
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
            else:
                print("Follow-up error.")
                self.show_message_box("error", "Gen Error", "Error generating follow-up...")
                if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
                self.start_next_topic()
        else: # Max follow-ups or missing state
             print("Max follow-ups reached or state error.")
             QApplication.restoreOverrideCursor()
             if hasattr(self, 'current_initial_q_index'): self.current_initial_q_index += 1
             self.start_next_topic()
        if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()

    # --- Results Page Actions ---
    def _save_report(self):
        if not (hasattr(self, 'summary_text_results') and hasattr(self, 'assessment_text_results')):
             self.show_message_box("warning", "No Data", "Results widgets not found.")
             return
        summary = self.summary_text_results.toPlainText()
        assessment = self.assessment_text_results.toPlainText()
        if not summary and not assessment: self.show_message_box("warning", "No Data", "Results are empty.")
        return
        report_content = f"Interview Report\n{'='*16}\n\nPerformance Summary\n{'-'*19}\n{summary}\n\nQualification Assessment\n{'-'*24}\n{assessment}\n"
        default_filename = "interview_report.txt"
        if self.pdf_filepath: base = os.path.splitext(os.path.basename(self.pdf_filepath))[0]; default_filename = f"{base}_interview_report.txt"
        save_dir = RECORDINGS_DIR if os.path.exists(RECORDINGS_DIR) else os.path.expanduser("~")
        default_path = os.path.join(save_dir, default_filename)
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", default_path, "Text Files (*.txt);;All Files (*)")
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f: f.write(report_content)
                self.update_status(f"Report saved.")
                self.show_message_box("info", "Report Saved", f"Report saved to:\n{filepath}")
            except Exception as e:
                print(f"Err save report: {e}")
                self.show_message_box("error", "Save Error", f"Could not save report:\n{e}")

    def _open_recordings_folder(self):
        folder_path = os.path.abspath(RECORDINGS_DIR)
        print(f"Opening folder: {folder_path}")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Created dir: {folder_path}")
        url = QUrl.fromLocalFile(folder_path)
        if not QDesktopServices.openUrl(url):
            print(f"QDesktopServices failed. Trying fallback...")
            self.update_status("Opening folder (fallback)...")
            try:
                if platform.system() == "Windows": os.startfile(folder_path)
                elif platform.system() == "Darwin": subprocess.Popen(["open", folder_path])
                else: subprocess.Popen(["xdg-open", folder_path])
                self.update_status("Opened recordings folder (fallback).")
            except Exception as e:
                print(f"Fallback open error: {e}")
                self.show_message_box("error", "Open Error", f"Could not open folder:\n{folder_path}\nError: {e}")
                self.update_status("Failed to open folder.")
        else:
            self.update_status("Opened recordings folder.")

    # --- Window Close ---
    def closeEvent(self, event):
        print("Closing application window...")
        if hasattr(self, 'stt_timer'):
            self.stt_timer.stop()
            print("STT timer stopped.")
        print("Cleanup complete.")
        event.accept()