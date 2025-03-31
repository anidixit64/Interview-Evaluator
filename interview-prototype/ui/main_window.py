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
# MODIFIED: Import specific modules instead of the old handler
from core import tts
from core import recording
# MODIFIED: Import the constant from the correct new module
from core.recording import RECORDINGS_DIR

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
        # --- ORIGINAL APPEARANCE CODE ---
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
        # --- END ORIGINAL APPEARANCE CODE ---

    def _load_assets(self): # Load only common/needed icons here
        # --- ORIGINAL ASSET LOADING CODE ---
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
        # --- END ORIGINAL ASSET LOADING CODE ---

    def _init_state(self): # (Add new widget refs)
        # --- ORIGINAL INIT STATE CODE ---
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
        # --- END ORIGINAL INIT STATE CODE ---

    def _setup_ui(self): # Setup Stack + Status/Progress
        # --- ORIGINAL SETUP UI CODE ---
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
        # --- END ORIGINAL SETUP UI CODE ---

    def _update_ui_from_state(self): # Update setup page state
        # --- ORIGINAL UPDATE UI FROM STATE CODE ---
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
        # --- END ORIGINAL UPDATE UI FROM STATE CODE ---

    # --- Navigation/Progress ---
    def _update_progress_indicator(self):
        # --- ORIGINAL PROGRESS INDICATOR CODE ---
        if not hasattr(self, 'progress_indicator_label') or not self.progress_indicator_label:
             return
        current_index = self.stacked_widget.currentIndex()
        steps = ["Step 1: Setup", "Step 2: Interview", "Step 3: Results"]
        progress_parts = []
        for i, step in enumerate(steps):
            if i == current_index:
                # --- MODIFICATION --- From original, keep orange highlight
                # Wrap the bold tag with a font tag for color
                progress_parts.append(f'<font color="orange"><b>{step}</b></font>')
                # --- END MODIFICATION ---
            else:
                progress_parts.append(step)
        # Join with HTML arrow entity
        progress_text = " → ".join(progress_parts)
        self.progress_indicator_label.setText(progress_text)
        # --- END ORIGINAL PROGRESS INDICATOR CODE ---


    def _go_to_setup_page(self):
        # --- ORIGINAL GO TO SETUP CODE ---
        print("Navigating to Setup Page and Resetting...")
        self.reset_interview_state(clear_config=True) # Full reset
        self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self._update_progress_indicator()
        # --- END ORIGINAL GO TO SETUP CODE ---

    def _go_to_interview_page(self):
        # --- ORIGINAL GO TO INTERVIEW CODE ---
        print("Navigating to Interview Page...")
        if hasattr(self, 'current_q_text'): self.current_q_text.clear()
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        if hasattr(self, 'history_text'): self.history_text.clear()
        self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview started. Waiting for question...")
        # --- END ORIGINAL GO TO INTERVIEW CODE ---

    def _go_to_results_page(self, summary, assessment):
        # --- ORIGINAL GO TO RESULTS CODE ---
        print("Navigating to Results Page...")
        if hasattr(self, 'summary_text_results') and self.summary_text_results:
            self.summary_text_results.setMarkdown(summary or "*Summary generation failed or N/A*")
        if hasattr(self, 'assessment_text_results') and self.assessment_text_results:
            self.assessment_text_results.setMarkdown(assessment or "*Assessment generation failed or N/A*")
        self.stacked_widget.setCurrentIndex(self.RESULTS_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview complete. Results displayed.")
        # --- END ORIGINAL GO TO RESULTS CODE ---

    # --- Helpers & State Updates ---
    def _load_icon_internal(self, filename, size=None):
        # --- ORIGINAL ICON LOADING CODE ---
        try:
            path = os.path.join(self.icon_path, filename)
            return QIcon(path) if os.path.exists(path) else None
        except Exception as e:
            print(f"Icon error {filename}: {e}")
            return None
        # --- END ORIGINAL ICON LOADING CODE ---

    def show_message_box(self, level, title, message):
        # --- ORIGINAL MESSAGE BOX CODE ---
        box = QMessageBox(self)
        icon_map = {"info": QMessageBox.Icon.Information, "warning": QMessageBox.Icon.Warning, "error": QMessageBox.Icon.Critical}
        box.setIcon(icon_map.get(level, QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        # --- END ORIGINAL MESSAGE BOX CODE ---

    def _adjust_value(self, value_type, amount):
        # --- ORIGINAL ADJUST VALUE CODE ---
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
        # --- END ORIGINAL ADJUST VALUE CODE ---

    def update_status(self, message, busy=False): # Update Status Bar
        # --- ORIGINAL UPDATE STATUS CODE ---
        if self.status_bar_label:
            self.status_bar_label.setText(message)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()
        # --- END ORIGINAL UPDATE STATUS CODE ---

    def display_question(self, question_text): # Sets last_question_asked
        # --- ORIGINAL DISPLAY QUESTION CODE (MODIFIED TTS CALL) ---
        self.last_question_asked = question_text
        if hasattr(self, 'current_q_text') and self.current_q_text:
            self.current_q_text.setPlainText(question_text)
        else:
            self.update_status(f"Asking: {question_text[:30]}...")
        try:
            # MODIFIED: Call tts module's function
            tts.speak_text(question_text)
        except Exception as e:
            print(f"TTS Error: {e}")
        self.enable_interview_controls()
        if hasattr(self, 'answer_input') and self.answer_input and not self.use_speech_input:
            self.answer_input.setFocus()
        # --- END ORIGINAL DISPLAY QUESTION CODE (MODIFIED TTS CALL) ---

    def add_to_history(self, text, tag=None): # Add to Transcript view
        # --- ORIGINAL ADD TO HISTORY CODE ---
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
        # --- END ORIGINAL ADD TO HISTORY CODE ---

    def set_setup_controls_state(self, enabled): # Enable/Disable Setup Page Controls
        # --- ORIGINAL SET SETUP CONTROLS STATE CODE ---
        pdf_needed_controls = [
            self.job_desc_input, self.topic_minus_btn, self.topic_plus_btn, self.num_topics_label,
            self.followup_minus_btn, self.followup_plus_btn, self.max_follow_ups_label,
            self.speech_checkbox, self.start_interview_btn
        ]
        for widget in pdf_needed_controls:
            if widget: # Check if widget object exists
                widget.setEnabled(enabled)
        # --- END ORIGINAL SET SETUP CONTROLS STATE CODE ---

    def enable_interview_controls(self): # Enable Interview Page Controls
        # --- ORIGINAL ENABLE INTERVIEW CONTROLS CODE ---
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.set_recording_button_state('idle')
        # --- END ORIGINAL ENABLE INTERVIEW CONTROLS CODE ---

    def disable_interview_controls(self, is_recording_stt=False): # Disable Interview Page Controls
        # --- ORIGINAL DISABLE INTERVIEW CONTROLS CODE ---
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt
        # Button state set via set_recording_button_state or update_status_stt
        # --- END ORIGINAL DISABLE INTERVIEW CONTROLS CODE ---

    def reset_interview_state(self, clear_config=True): # Reset state and UI
        # --- ORIGINAL RESET INTERVIEW STATE CODE ---
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
        # --- END ORIGINAL RESET INTERVIEW STATE CODE ---

    def _clean_question_text(self, raw_q_text):
        # --- ORIGINAL CLEAN QUESTION TEXT CODE ---
        cleaned = raw_q_text.strip()
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split('.', 1)
            if len(parts)>1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(' ', 1)
            if len(parts)>1 and parts[0].isdigit(): return parts[1].strip()
        return cleaned
        # --- END ORIGINAL CLEAN QUESTION TEXT CODE ---

    def save_transcript_to_file(self):
        # --- ORIGINAL SAVE TRANSCRIPT CODE (USES IMPORTED RECORDINGS_DIR) ---
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
                        # Find the original raw question to get its index
                        raw_q_match = next(rq for rq in self.initial_questions if self._clean_question_text(rq) == q)
                        topic_index = self.initial_questions.index(raw_q_match)
                    except StopIteration:
                        print(f"Warn: Q mismatch during transcript save for '{q}'")
                    # Check if this is a genuinely new topic based on index progression
                    if topic_index != -1 and topic_index + 1 > current_topic_num:
                        current_topic_num = topic_index + 1
                        current_follow_up_num = 0 # Reset follow-up count
                        if current_topic_num > 1: transcript_lines.append("-------------------------")
                        transcript_lines.append(f"Question {current_topic_num}: {q}\nAnswer: {a}")
                    else: # Should ideally not happen for initial Q if logic is right, treat as follow-up
                        current_follow_up_num += 1
                        transcript_lines.append("") # Blank line before follow-up
                        ctx = f"Topic {current_topic_num}" if current_topic_num > 0 else "Uncertain"
                        transcript_lines.append(f"Follow Up {current_follow_up_num} (re {ctx}): {q}\nAnswer: {a}")
                else: # This is a follow-up question
                    current_follow_up_num += 1
                    transcript_lines.append("") # Blank line before follow-up
                    # Determine context based on last known topic number
                    ctx = f"Topic {current_topic_num}" if current_topic_num > 0 else "Uncertain"
                    transcript_lines.append(f"Follow Up {current_follow_up_num} (re {ctx}): {q}\nAnswer: {a}")
                transcript_lines.append("") # Blank line after Q/A pair

            # Use the imported RECORDINGS_DIR constant
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving transcript to {filepath}...")
            # Ensure final newline for cleaner diffs
            with open(filepath, "w", encoding="utf-8") as f: f.write("\n".join(transcript_lines).strip() + "\n")
            print("Transcript saved.")
        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript: {e}")
        # --- END ORIGINAL SAVE TRANSCRIPT CODE ---

    # --- Button State Helper ---
    def set_recording_button_state(self, state): # Update record/submit button
        # --- ORIGINAL SET RECORDING BUTTON STATE CODE ---
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
            self.submit_button.setEnabled(True) # Enable when idle
            if self.use_speech_input:
                 target_text = "Record Answer"
                 target_icon = self.record_icon
            else:
                 target_text = "Submit Answer"
                 target_icon = self.submit_icon
        else: # Fallback
            if self.use_speech_input: target_text, target_icon = "Record Answer", self.record_icon
            else: target_text, target_icon = "Submit Answer", self.submit_icon
            self.submit_button.setEnabled(True) # Assume enabled in fallback?

        self.submit_button.setText(target_text)
        if target_icon:
            self.submit_button.setIcon(target_icon)
            self.submit_button.setIconSize(self.icon_size) # Ensure size
        else: self.submit_button.setIcon(QIcon()) # Clear icon if none specified
        # --- END ORIGINAL SET RECORDING BUTTON STATE CODE ---

    # --- GUI Logic/Event Handlers ---

    def update_submit_button_text(self, check_state_value=None): # Simplified, uses set_recording_button_state
        # --- ORIGINAL UPDATE SUBMIT BUTTON TEXT CODE ---
        # Handle state change from checkbox signal if provided
        if check_state_value is not None:
            # Qt.CheckState.Checked.value is typically 2
            self.use_speech_input = (check_state_value == Qt.CheckState.Checked.value)
            print(f"Use Speech: {self.use_speech_input}")

        # Update button appearance only if not currently recording
        if not self.is_recording:
            self.set_recording_button_state('idle') # Update idle appearance based on new mode

        # Enable/disable text input based on mode
        if hasattr(self, 'answer_input'):
            is_text_mode = not self.use_speech_input
            # Only allow editing text input if in text mode AND controls are generally enabled
            controls_enabled = hasattr(self, 'submit_button') and self.submit_button.isEnabled()

            self.answer_input.setReadOnly(not is_text_mode)
            self.answer_input.setEnabled(is_text_mode and controls_enabled)

            if is_text_mode and controls_enabled:
                self.answer_input.setFocus() # Focus text input when switching to text mode
                self.answer_input.setPlaceholderText("Type your answer here...")
            elif not is_text_mode:
                self.answer_input.clear() # Clear text if switching to speech
                self.answer_input.setPlaceholderText("Click 'Record Answer'...")
        # --- END ORIGINAL UPDATE SUBMIT BUTTON TEXT CODE ---

    def select_resume_file(self): # Update status bar
        # --- ORIGINAL SELECT RESUME FILE CODE ---
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

        # --- Extract text immediately --- Changed slightly to handle extraction here
        self.update_status(f"Extracting text from '{filename}'...", True)
        QApplication.processEvents()
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        self.update_status("", False) # Clear busy

        if self.resume_content is None:
             self.update_status("[Error extracting PDF]", False)
             self.show_message_box("error", "PDF Error", f"Failed to extract text from {filename}. It might be image-based or protected.")
             self.pdf_filepath = None # Reset path
             if hasattr(self, 'file_label'): self.file_label.setText("Extraction Failed. Select again.")
             self.set_setup_controls_state(False) # Disable dependent controls
             return

        # --- Extraction Success ---
        self.update_status("Resume selected. Configure interview or paste job description.")
        self.set_setup_controls_state(True) # Enable other setup controls
        if hasattr(self, 'job_desc_input'):
            self.job_desc_input.setFocus()
        # --- END ORIGINAL SELECT RESUME FILE CODE (with extraction integrated) ---

    def start_interview_process(self): # Navigate on success
        # --- ORIGINAL START INTERVIEW PROCESS CODE ---
        if not self.pdf_filepath or not self.resume_content: # Check content too
            self.show_message_box("warning", "Input Missing", "Select resume PDF and ensure text was extracted.")
            return
        if hasattr(self, 'job_desc_input'):
            self.job_description_text = self.job_desc_input.toPlainText().strip()
        print(f"Preparing: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, Speech={self.use_speech_input}")
        # Reset interview progress state, keep config
        self.reset_interview_state(clear_config=False)

        self.update_status(f"Generating {self.num_topics} questions...", True)
        self.set_setup_controls_state(False) # Disable setup controls
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False)
        QApplication.processEvents()

        # Generate questions - consider threading
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )

        # Restore UI state after generation attempt
        self.update_status("", False) # Clear busy
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True) # Re-enable select

        if not self.initial_questions:
            self.update_status("Error generating questions", False)
            self.show_message_box("error", "Generation Error", "Failed to generate initial questions. Check API key and console logs.")
            self.set_setup_controls_state(True) # Re-enable setup controls if PDF was ok
            return

        # --- Success ---
        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        if len(self.initial_questions) < self.num_topics:
             print(f"Warning: Model generated {len(self.initial_questions)} questions (requested {self.num_topics}).")
             # Optionally inform user briefly via status bar
             self.update_status(f"Generated {len(self.initial_questions)} questions. Starting interview...")
             QTimer.singleShot(3000, lambda: self.update_status("Interview started.")) # Clear status after delay


        self._go_to_interview_page()
        self.current_initial_q_index = 0
        self.start_next_topic()
        # --- END ORIGINAL START INTERVIEW PROCESS CODE ---

    def start_next_topic(self): # Navigate on finish
        # --- ORIGINAL START NEXT TOPIC CODE ---
        if not self.initial_questions:
            print("Err: No initial questions generated.")
            self._go_to_setup_page() # Go back to setup if failed
            return

        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            # Start new topic
            self.follow_up_count = 0
            self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text) # Store cleaned context
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker") # Display marker in UI
            print(f"Asking Q {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(raw_q_text) # Ask the raw question
        else: # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Generating results...", True)
            self.disable_interview_controls()
            self.save_transcript_to_file() # Save transcript

            # Generate results - consider threading
            print("Generating summary...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating assessment...")
            assessment = logic.generate_qualification_assessment(
                self.resume_content,
                self.job_description_text,
                self.current_full_interview_history
            )

            self.update_status("Results ready.", False) # Clear busy state

            # Handle potential generation errors before navigating
            if summary is None or summary.startswith(logic.ERROR_PREFIX):
                self.show_message_box("warning", "Summary Error", f"Could not generate summary review.\n{summary}")
                summary = "*Summary generation failed.*" # Placeholder
            if assessment is None or assessment.startswith(logic.ERROR_PREFIX):
                 # Only warn if JD was provided, otherwise assessment failure is expected
                 if self.job_description_text:
                     self.show_message_box("warning", "Assessment Error", f"Could not generate qualification assessment.\n{assessment}")
                 assessment = "*Assessment generation failed or N/A (No Job Description provided).*" # Placeholder

            self._go_to_results_page(summary, assessment) # Navigate to Results
        # --- END ORIGINAL START NEXT TOPIC CODE ---

    def handle_answer_submission(self): # Uses set_recording_button_state
        # --- ORIGINAL HANDLE ANSWER SUBMISSION CODE (MODIFIED RECORDING CALL) ---
        if self.is_recording: print("Already recording..."); return
        if self.use_speech_input:
            # Start STT
            print("Record button clicked...")
            self.disable_interview_controls(is_recording_stt=True)
            self.update_status_stt("STT_Status: Starting Mic...")
            if hasattr(self, 'answer_input'): self.answer_input.clear()
            # Determine indices for saving files
            topic_idx = self.current_initial_q_index + 1 # Use 1-based index for topic
            followup_idx = self.follow_up_count # Use 0-based index for follow-up within topic
            # MODIFIED: Call recording module's function
            recording.start_speech_recognition(topic_idx, followup_idx)
        else: # Text submission
            print("Submit button clicked.")
            if not hasattr(self, 'answer_input'): print("Error: answer_input missing."); return
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer: self.show_message_box("warning", "Input Required", "Please enter answer."); return
            # Process text answer directly
            self.process_answer(user_answer)
        # --- END ORIGINAL HANDLE ANSWER SUBMISSION CODE (MODIFIED RECORDING CALL) ---

    def update_status_stt(self, message): # Update Status Bar, trigger button state change
        # --- ORIGINAL UPDATE STATUS STT CODE ---
        if not self.status_bar_label: return
        display_message = message
        button_state = 'idle' # Default state

        # Map internal status messages to user display text and button appearance
        if message == "STT_Status: Adjusting Mic...": # Added handling for adjustment message
             display_message = "[Calibrating microphone...]"
             button_state = 'processing' # Show processing during adjustment
        elif message == "STT_Status: Listening...":
             display_message = "[Listening... Speak Now]"
             button_state = 'listening'
        elif message == "STT_Status: Processing...":
             display_message = "[Processing Speech...]"
             button_state = 'processing'
        elif message.startswith("STT_Warning:"): # Handle warnings
             warning_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Warning: {warning_detail}]"
             button_state = 'idle' # Return to idle after warning
        elif message.startswith("STT_Error:"):
             error_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Error: {error_detail}]"
             button_state = 'idle' # Return to idle after error (controls enabled separately)
        elif message.startswith("STT_Success:"):
             display_message = "[Speech Recognized]"
             button_state = 'idle' # Return to idle, process_answer handles next state

        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state) # Update button appearance/state
        QApplication.processEvents() # Ensure UI updates
        # --- END ORIGINAL UPDATE STATUS STT CODE ---

    def check_stt_queue(self): # Uses set_recording_button_state
        # --- ORIGINAL CHECK STT QUEUE CODE (MODIFIED QUEUE ACCESS) ---
        try:
            # MODIFIED: Access queue from recording module
            result = recording.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")

            # Process based on message prefix
            if result.startswith("STT_Status:") or result.startswith("STT_Warning:"): # Handle warnings too
                self.update_status_stt(result)
            elif result.startswith("STT_Success:"):
                self.is_recording = False # Recording done
                self.update_status_stt(result) # Show success briefly
                transcript = result.split(":", 1)[1].strip() # Extract text

                # Display transcript in answer box (read-only)
                if hasattr(self, 'answer_input'):
                    self.answer_input.setEnabled(True) # Enable to set text
                    self.answer_input.setReadOnly(False)
                    self.answer_input.setText(transcript)
                    self.answer_input.setReadOnly(True) # Make read-only again
                    self.answer_input.setEnabled(False) # Disable until next question

                # Process the recognized text
                self.process_answer(transcript)
            elif result.startswith("STT_Error:"):
                self.is_recording = False # Recording stopped
                error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result) # Show error status
                self.show_message_box("error", "STT Error", error_message)
                self.enable_interview_controls() # Re-enable controls after error
        except queue.Empty:
            pass # No message, nothing to do
        except Exception as e:
            print(f"STT Queue Check Error: {e}")
            # Safety reset if error happens during recording check
            if self.is_recording:
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()
        # --- END ORIGINAL CHECK STT QUEUE CODE (MODIFIED QUEUE ACCESS) ---

    def process_answer(self, user_answer):
        # --- ORIGINAL PROCESS ANSWER CODE ---
        last_q = self.last_question_asked if hasattr(self, 'last_question_asked') and self.last_question_asked else "[Unknown Q]"
        print(f"Processing answer for Q: '{last_q[:50]}...' -> A: '{user_answer[:50]}...'")

        # Record Q&A
        q_data = {"q": last_q, "a": user_answer}
        if hasattr(self, 'current_topic_history'): self.current_topic_history.append(q_data)
        if hasattr(self, 'current_full_interview_history'): self.current_full_interview_history.append(q_data)

        # Add to transcript view
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        # Prepare for next step
        if hasattr(self, 'answer_input'): self.answer_input.clear()
        self.disable_interview_controls()
        self.update_status("Generating response...", True)
        QApplication.processEvents()

        # Follow-up logic
        proceed_to_next = False
        if hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups') and self.follow_up_count < self.max_follow_ups:
            # Generate follow-up
            follow_up_q = logic.generate_follow_up_question(
                context_question=self.current_topic_question, # Original topic question
                user_answer=user_answer,
                conversation_history=self.current_topic_history # History for this topic
            )
            self.update_status("", False) # Clear busy state after LLM call

            if follow_up_q and follow_up_q != "[END TOPIC]":
                # Ask follow-up
                self.follow_up_count += 1
                print(f"Asking Follow-up: {follow_up_q}")
                self.display_question(follow_up_q)
            elif follow_up_q == "[END TOPIC]":
                print("End topic signal received from model.")
                proceed_to_next = True # Move to next topic
            else: # Handle generation error (None returned)
                print("Follow-up generation failed.")
                self.show_message_box("error", "Generation Error", "Error generating follow-up question. Moving to next topic.")
                proceed_to_next = True
        else: # Max follow-ups reached or feature disabled
             print("Max follow-ups reached or follow-ups disabled.")
             self.update_status("", False) # Clear busy state
             proceed_to_next = True

        # Move to next topic if necessary
        if proceed_to_next:
             if hasattr(self, 'current_initial_q_index'):
                 self.current_initial_q_index += 1 # Go to next index
                 self.start_next_topic() # Start next or finish interview
             else:
                  # Should not happen if state is managed correctly
                  print("Error: current_initial_q_index missing!")
                  self._go_to_setup_page() # Fallback: go to setup

        # Ensure cursor is restored if still busy for some reason
        if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        # --- END ORIGINAL PROCESS ANSWER CODE ---

    # --- Results Page Actions ---
    def _save_report(self):
        # --- ORIGINAL SAVE REPORT CODE (USES IMPORTED RECORDINGS_DIR) ---
        if not (hasattr(self, 'summary_text_results') and hasattr(self, 'assessment_text_results')):
             self.show_message_box("warning", "No Data", "Results widgets not found.")
             return
        summary = self.summary_text_results.toPlainText().strip()
        assessment = self.assessment_text_results.toPlainText().strip()
        if not summary and not assessment:
            self.show_message_box("warning", "No Data", "Results are empty.")
            return # Changed from pass to return

        # Prepare report content
        report_content = f"Interview Report\n{'='*16}\n\nPerformance Summary\n{'-'*19}\n{summary}\n\nQualification Assessment\n{'-'*24}\n{assessment}\n"

        # Determine default filename and path
        default_filename = "interview_report.txt"
        if self.pdf_filepath:
            base = os.path.splitext(os.path.basename(self.pdf_filepath))[0]
            default_filename = f"{base}_interview_report.txt"
        # Use imported RECORDINGS_DIR, fallback to home directory
        save_dir = RECORDINGS_DIR if os.path.exists(RECORDINGS_DIR) else os.path.expanduser("~")
        default_path = os.path.join(save_dir, default_filename)

        # Open save dialog
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", default_path, "Text Files (*.txt);;All Files (*)")

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                self.update_status(f"Report saved.")
                self.show_message_box("info", "Report Saved", f"Report saved to:\n{filepath}")
            except Exception as e:
                print(f"Error saving report: {e}")
                self.show_message_box("error", "Save Error", f"Could not save report:\n{e}")
        else:
            self.update_status("Report save cancelled.") # Update status if cancelled
        # --- END ORIGINAL SAVE REPORT CODE ---

    def _open_recordings_folder(self):
        # --- ORIGINAL OPEN RECORDINGS FOLDER CODE (USES IMPORTED RECORDINGS_DIR) ---
        # Use imported RECORDINGS_DIR constant
        folder_path = os.path.abspath(RECORDINGS_DIR)
        print(f"Opening folder: {folder_path}")

        # Create directory if it doesn't exist
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path)
                print(f"Created recordings directory: {folder_path}")
                # Optionally inform the user it was created
                # self.show_message_box("info", "Folder Created", f"Recordings folder created at:\n{folder_path}")
            except OSError as e:
                 print(f"Error creating directory: {e}")
                 self.show_message_box("error", "Folder Error", f"Could not create recordings folder:\n{folder_path}\nError: {e}")
                 self.update_status("Failed to create folder.")
                 return # Don't try to open if creation failed

        # Attempt to open using QDesktopServices
        url = QUrl.fromLocalFile(folder_path)
        if not QDesktopServices.openUrl(url):
            print(f"QDesktopServices failed. Trying fallback...")
            self.update_status("Opening folder (fallback)...")
            # Fallback for different OS
            try:
                system = platform.system()
                if system == "Windows":
                    os.startfile(folder_path)
                elif system == "Darwin": # macOS
                    subprocess.Popen(["open", folder_path])
                else: # Linux/Other
                    subprocess.Popen(["xdg-open", folder_path])
                self.update_status("Opened recordings folder (fallback).")
            except FileNotFoundError: # Command not found
                 cmd = "startfile" if system == "Windows" else ("open" if system == "Darwin" else "xdg-open")
                 print(f"Error: Command '{cmd}' not found.")
                 self.show_message_box("error", "Open Error", f"Could not find command ('{cmd}') to open the folder.\nPlease open manually:\n{folder_path}")
                 self.update_status("Failed to open folder (command missing).")
            except Exception as e:
                print(f"Fallback open error: {e}")
                self.show_message_box("error", "Open Error", f"Could not open folder:\n{folder_path}\nError: {e}")
                self.update_status("Failed to open folder.")
        else:
            self.update_status("Opened recordings folder.")
        # --- END ORIGINAL OPEN RECORDINGS FOLDER CODE ---

    # --- Window Close ---
    def closeEvent(self, event):
        # --- ORIGINAL CLOSE EVENT CODE ---
        print("Closing application window...")
        if hasattr(self, 'stt_timer'):
            self.stt_timer.stop()
            print("STT timer stopped.")
        # Add any other essential cleanup if needed (e.g., stopping threads forcefully?)
        print("Cleanup complete.")
        event.accept()
        # --- END ORIGINAL CLOSE EVENT CODE ---