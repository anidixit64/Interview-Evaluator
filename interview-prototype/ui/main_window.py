# ui/main_window.py
import os
import sys
import queue
import platform # For opening folder
import subprocess # For opening folder fallback
import html # For escaping history text

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QApplication, QStackedWidget,
    QLabel, QSizePolicy, QFrame # Added QFrame
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QUrl

# --- Project Imports ---
import core.logic as logic
from core import tts # NEW TTS facade
from core import recording
# RECORDINGS_DIR is now the absolute user path from core.recording
from core.recording import RECORDINGS_DIR

# Import UI component creation functions
from .components import create_setup_page, create_interview_page, create_results_page


class InterviewApp(QWidget):

    # Define constants for page indices (optional but good practice)
    SETUP_PAGE_INDEX = 0
    INTERVIEW_PAGE_INDEX = 1
    RESULTS_PAGE_INDEX = 2

    # Use the icon_path passed during initialization
    def __init__(self, icon_path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.icon_path = icon_path # Store the resolved path
        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000)

        self._setup_appearance()
        self._load_assets() # Assets now mostly loaded in components
        self._init_state()
        self._setup_ui()
        self._update_ui_from_state()
        self._update_progress_indicator()
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
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(50,50,50)) # Darker tooltip text
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


    def _load_assets(self):
        # Most icons loaded in components using self.icon_path
        # Keep sizes and fonts here
        self.icon_size = QSize(20, 20)
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
        self.use_openai_tts = False  # State for OpenAI TTS checkbox
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
        self.openai_tts_checkbox=None # Widget ref for OpenAI TTS checkbox
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

        # Create Pages (passes self, which includes resolved icon_path)
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
        if hasattr(self, 'num_topics_label') and self.num_topics_label:
            self.num_topics_label.setText(str(self.num_topics))
        if hasattr(self, 'max_follow_ups_label') and self.max_follow_ups_label:
            self.max_follow_ups_label.setText(str(self.max_follow_ups))
        if hasattr(self, 'speech_checkbox') and self.speech_checkbox:
            self.speech_checkbox.setChecked(self.use_speech_input)

        # --- Update OpenAI TTS checkbox ---
        if hasattr(self, 'openai_tts_checkbox') and self.openai_tts_checkbox:
             self.openai_tts_checkbox.blockSignals(True)
             self.openai_tts_checkbox.setChecked(self.use_openai_tts)
             # Ensure enabled state matches dependencies & PDF loaded state
             openai_deps_met = "openai" in tts.get_potentially_available_providers()
             self.openai_tts_checkbox.setEnabled(pdf_loaded and openai_deps_met)
             self.openai_tts_checkbox.blockSignals(False)
        # --- END ADDED ---

        # Update enabled state of setup controls (relies on set_setup_controls_state)
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
                progress_parts.append(f'<font color="orange"><b>{step}</b></font>')
            else:
                progress_parts.append(step)
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
        # This method is now less used, components.py handles most loading
        # It uses self.icon_path which should be resolved
        try:
            path = os.path.join(self.icon_path, filename) # Use resolved base path
            if not os.path.exists(path):
                 print(f"Icon Load Warning (Internal): Icon not found at {path}")
                 return None
            return QIcon(path)
        except Exception as e:
            print(f"Icon Load Error (Internal) {filename}: {e}")
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
            tts.speak_text(question_text) # Facade handles current provider
        except Exception as e:
            print(f"TTS Error during speak_text call: {e}")
        self.enable_interview_controls()
        if hasattr(self, 'answer_input') and self.answer_input and not self.use_speech_input:
            self.answer_input.setFocus()


    def add_to_history(self, text, tag=None): # Add to Transcript view
        # --- MODIFIED to use palette colors and escape text ---
        if not hasattr(self, 'history_text') or not self.history_text:
            return
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_text.setTextCursor(cursor)

        text_color_name = self.palette().color(QPalette.ColorRole.Text).name()
        # Escape HTML special characters and replace newlines with <br> for display
        escaped_text = html.escape(text).replace("\n", "<br>")

        html_content = ""
        if tag == "question_style":
            # Question style uses a specific blue color
            html_content = f'<font color="#569CD6">{escaped_text}</font>'
        elif tag == "answer_style":
            # Answer style uses the standard text color
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>'
        elif tag == "topic_marker":
            # Topic marker uses grey and bold
            html_content = f'<font color="grey"><b>{escaped_text}</b></font>'
        else:
            # Default plain text uses the standard text color
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>'

        self.history_text.insertHtml(html_content)
        self.history_text.ensureCursorVisible()
        # --- END MODIFICATION ---


    def set_setup_controls_state(self, pdf_loaded): # Enable/Disable Setup Page Controls
        # --- MODIFIED: Correctly handle openai_tts_checkbox enabling ---
        controls_to_manage = [
            (self.job_desc_input, True),
            (self.topic_minus_btn, True), (self.topic_plus_btn, True), (self.num_topics_label, True),
            (self.followup_minus_btn, True), (self.followup_plus_btn, True), (self.max_follow_ups_label, True),
            (self.speech_checkbox, True),
            (self.start_interview_btn, True),
            (self.openai_tts_checkbox, False) # Special handling below
        ]

        openai_deps_met = "openai" in tts.get_potentially_available_providers()

        for widget, is_always_pdf_dependent in controls_to_manage:
            if widget: # Check if widget object exists
                should_enable = pdf_loaded

                # Special case for openai checkbox: requires deps AND PDF loaded
                if widget == self.openai_tts_checkbox:
                    should_enable = pdf_loaded and openai_deps_met
                # For others, just depends on pdf_loaded status
                elif not is_always_pdf_dependent:
                     pass # Widgets not solely dependent on PDF (like select_btn) are handled elsewhere

                widget.setEnabled(should_enable)
        # --- END MODIFICATION ---


    def enable_interview_controls(self): # Enable Interview Page Controls
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        text_input_enabled = not self.use_speech_input
        self.answer_input.setReadOnly(not text_input_enabled)
        self.answer_input.setEnabled(True) # Always enable the widget itself
        self.submit_button.setEnabled(True)
        self.is_recording = False
        self.set_recording_button_state('idle')


    def disable_interview_controls(self, is_recording_stt=False): # Disable Interview Page Controls
        if not hasattr(self, 'answer_input') or not hasattr(self, 'submit_button'):
            return
        self.answer_input.setReadOnly(True)
        self.answer_input.setEnabled(False) # Disable interaction
        self.submit_button.setEnabled(False)
        self.is_recording = is_recording_stt


    def reset_interview_state(self, clear_config=True): # Reset state and UI
        print(f"Resetting interview state (clear_config={clear_config})...")
        if clear_config:
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False
            self.use_openai_tts = False # Reset OpenAI flag
            # Set default TTS provider on full reset
            current_provider = tts.get_current_provider()
            default_provider = tts.DEFAULT_PROVIDER
            print(f"Resetting TTS. Current: {current_provider}, Default: {default_provider}")
            if current_provider != default_provider:
                if not tts.set_provider(default_provider):
                    potential = tts.get_potentially_available_providers()
                    if potential and tts.set_provider(potential[0]):
                        print(f"Reset TTS: Set to first available '{potential[0]}'.")
                    else:
                         print("Reset TTS: ERROR - Could not set default or fallback.")
                else:
                     print(f"Reset TTS: Set to default '{default_provider}'.")

        # Reset dynamic state
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""

        # Update UI based on reset values (this will update checkbox states)
        self._update_ui_from_state()
        # Ensure interview controls are disabled after reset
        self.disable_interview_controls()
        QApplication.restoreOverrideCursor()
        print("Interview state reset complete.")


    def _clean_question_text(self, raw_q_text):
        cleaned = raw_q_text.strip()
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(')', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(' ', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
        return cleaned


    def save_transcript_to_file(self):
        # Use the absolute RECORDINGS_DIR path
        if not self.current_full_interview_history:
            print("No history to save.")
            return
        if not self.initial_questions: # Check if initial questions exist for mapping
            print("Warning: Initial questions missing, cannot accurately map topics in transcript.")
            # Proceed without topic mapping? Or return? Let's proceed but it will be less structured.
            topic_index_map = {}
        else:
            topic_index_map = {self._clean_question_text(q): i for i, q in enumerate(self.initial_questions)}

        transcript_lines = []
        last_topic_num = -1

        try:
            for qa_pair in self.current_full_interview_history:
                 q_raw = qa_pair.get('q', 'N/A')
                 a = qa_pair.get('a', 'N/A')
                 q_clean = self._clean_question_text(q_raw)
                 topic_index = topic_index_map.get(q_clean, -1)

                 if topic_index != -1: # Found an initial question
                    current_topic_num = topic_index + 1
                    if current_topic_num != last_topic_num and last_topic_num != -1:
                        transcript_lines.append("\n-------------------------") # Separator between topics
                    transcript_lines.append(f"\nQuestion {current_topic_num}: {q_raw}\nAnswer: {a}")
                    last_topic_num = current_topic_num
                 else: # This is a follow-up question
                    # Determine context based on last known topic number
                    ctx = f"Topic {last_topic_num}" if last_topic_num > 0 else "General"
                    # Find the previous question index to number follow-ups correctly
                    follow_up_num = sum(1 for item in self.current_full_interview_history[:self.current_full_interview_history.index(qa_pair)+1]
                                        if topic_index_map.get(self._clean_question_text(item['q']), -1) == -1) # Count follow-ups up to this point

                    transcript_lines.append(f"\nFollow Up (re {ctx}): {q_raw}\nAnswer: {a}")


            # Ensure user-specific directory exists
            os.makedirs(RECORDINGS_DIR, exist_ok=True) # Use absolute path

            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt") # Use absolute path
            print(f"Saving transcript to {filepath}...")
            # Join lines, ensuring they are stripped and filter empty ones
            final_transcript = "\n".join(line.strip() for line in transcript_lines if line.strip())
            with open(filepath, "w", encoding="utf-8") as f:
                 f.write(final_transcript.strip() + "\n") # Add final newline
            print("Transcript saved.")
        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript: {e}")


    # --- Button State Helper ---
    def set_recording_button_state(self, state): # Update record/submit button
        if not hasattr(self, 'submit_button'): return
        target_icon = None
        target_text = "Submit Answer" # Default

        # Get icons dynamically using the helper (safer if assets changed)
        submit_icon = self._load_icon_internal("send.png", self.icon_size)
        record_icon = self._load_icon_internal("mic_black_36dp.png", self.icon_size)
        listening_icon = self._load_icon_internal("record_wave.png", self.icon_size)
        processing_icon = self._load_icon_internal("spinner.png", self.icon_size)


        if state == 'listening':
            target_text = "Listening..."
            target_icon = listening_icon
            self.submit_button.setEnabled(False) # Cannot click while listening
        elif state == 'processing':
            target_text = "Processing..."
            target_icon = processing_icon
            self.submit_button.setEnabled(False) # Cannot click while processing
        elif state == 'idle':
            self.submit_button.setEnabled(True) # Enable when idle
            if self.use_speech_input:
                 target_text = "Record Answer"
                 target_icon = record_icon
            else:
                 target_text = "Submit Answer"
                 target_icon = submit_icon
        else: # Fallback (treat as idle)
            self.submit_button.setEnabled(True) # Assume enabled in fallback
            if self.use_speech_input: target_text, target_icon = "Record Answer", record_icon
            else: target_text, target_icon = "Submit Answer", submit_icon

        self.submit_button.setText(target_text)
        if target_icon and not target_icon.isNull():
            self.submit_button.setIcon(target_icon)
            self.submit_button.setIconSize(self.icon_size) # Ensure size
        else:
            self.submit_button.setIcon(QIcon()) # Clear icon if none specified or loading failed


    # --- GUI Logic/Event Handlers ---

    # --- Handler for OpenAI TTS Checkbox ---
    def _handle_openai_tts_change(self, check_state_value):
        """Handles the state change of the OpenAI TTS checkbox."""
        is_checked = (check_state_value == Qt.CheckState.Checked.value)
        target_provider = "openai" if is_checked else tts.DEFAULT_PROVIDER # Fallback to gTTS if unchecked
        print(f"OpenAI TTS checkbox {'checked' if is_checked else 'unchecked'}. Attempting to set provider to: '{target_provider}'")

        # Block signals temporarily on the checkbox to prevent loops if we uncheck it programmatically
        if hasattr(self, 'openai_tts_checkbox') and self.openai_tts_checkbox:
            self.openai_tts_checkbox.blockSignals(True)

        success = tts.set_provider(target_provider)

        if success:
            self.use_openai_tts = is_checked
            current_provider = tts.get_current_provider()
            self.update_status(f"TTS Provider set to: {current_provider}")
            print(f"Successfully set TTS provider to: {current_provider}")
        else:
            self.use_openai_tts = False # Revert state if setting failed
            # Uncheck the box visually if setting OpenAI failed
            if is_checked and hasattr(self, 'openai_tts_checkbox') and self.openai_tts_checkbox:
                 self.openai_tts_checkbox.setChecked(False)
            # Try setting default provider as fallback
            print(f"Failed to set provider '{target_provider}'. Attempting fallback to default '{tts.DEFAULT_PROVIDER}'...")
            if not tts.set_provider(tts.DEFAULT_PROVIDER):
                 # Final fallback if default also fails
                 potential = tts.get_potentially_available_providers()
                 final_fallback = potential[0] if potential else None
                 if final_fallback and tts.set_provider(final_fallback):
                      print(f"Fallback to '{final_fallback}' succeeded.")
                 else:
                      print("ERROR: Failed to set any TTS provider.")
                      self.show_message_box("error", "TTS Error", f"Failed to set TTS provider '{target_provider}' and could not fall back. Check console and keyring/dependencies.")
                      # Disable the checkbox?
                      if hasattr(self, 'openai_tts_checkbox') and self.openai_tts_checkbox:
                          self.openai_tts_checkbox.setEnabled(False)
                          self.openai_tts_checkbox.setToolTip("TTS provider error. Check console.")
            else:
                 print(f"Fallback to default provider '{tts.DEFAULT_PROVIDER}' succeeded.")

            current_provider = tts.get_current_provider()
            status_msg = f"Failed to set OpenAI TTS. Using: {current_provider or 'None'}"
            self.update_status(status_msg)
            # Show a more specific error if trying to enable OpenAI failed
            if is_checked:
                 # Construct Keyring info string safely
                 openai_keyring_info = ""
                 try:
                     openai_keyring_info = f"(Service: '{tts.tts_providers['openai'].KEYRING_SERVICE_NAME_OPENAI}')"
                 except (KeyError, AttributeError):
                     openai_keyring_info = "(Keyring details unavailable)" # Fallback

                 self.show_message_box("warning", "OpenAI TTS Failed",
                                      f"Could not enable OpenAI TTS.\nPlease ensure:\n"
                                      f"- Dependencies are installed (openai, sounddevice, pydub, nltk, numpy).\n"
                                      f"- API key is stored in keyring {openai_keyring_info}.\n"
                                      f"- FFmpeg is installed and in PATH.\nCheck console for details. Using: {current_provider or 'None'}")


        # Re-enable signals
        if hasattr(self, 'openai_tts_checkbox') and self.openai_tts_checkbox:
            self.openai_tts_checkbox.blockSignals(False)


    def update_submit_button_text(self, check_state_value=None): # Simplified, uses set_recording_button_state
        # Handle state change from checkbox signal if provided
        if check_state_value is not None:
            # Qt.CheckState.Checked.value is typically 2
            self.use_speech_input = (check_state_value == Qt.CheckState.Checked.value)
            print(f"Use Speech Input (STT): {self.use_speech_input}")

        # Update button appearance only if not currently recording/processing
        if not self.is_recording:
            self.set_recording_button_state('idle') # Update idle appearance based on new mode

        # Enable/disable text input based on mode
        if hasattr(self, 'answer_input'):
            is_text_mode = not self.use_speech_input
            # Check if interview controls are generally enabled (submit button is a good proxy)
            # Controls are enabled if the submit button is enabled AND we are not recording
            controls_enabled = hasattr(self, 'submit_button') and self.submit_button.isEnabled() and not self.is_recording

            # Set read-only based on mode
            self.answer_input.setReadOnly(not is_text_mode)
            # Set enabled based on mode AND general control state
            self.answer_input.setEnabled(is_text_mode and controls_enabled)

            if is_text_mode and controls_enabled:
                self.answer_input.setFocus() # Focus text input when switching to text mode
                self.answer_input.setPlaceholderText("Type your answer here...")
            elif not is_text_mode:
                self.answer_input.clear() # Clear text if switching to speech
                self.answer_input.setPlaceholderText("Click 'Record Answer'...")
            else: # Text mode but controls disabled (e.g., waiting for question or recording active)
                 self.answer_input.setPlaceholderText("Waiting...")


    def select_resume_file(self): # Update status bar
        start_dir = os.path.expanduser("~") # Start in home directory
        start_dir_native = start_dir.replace('/', os.path.sep)
        filepath, _ = QFileDialog.getOpenFileName(self, "Select PDF", start_dir_native, "PDF Files (*.pdf)")
        if not filepath:
            if hasattr(self, 'file_label') and not self.pdf_filepath: # Only update if no file was previously selected
                self.file_label.setText("Selection cancelled.")
            self.update_status("Resume selection cancelled.")
            return

        # --- File successfully selected ---
        self.pdf_filepath = filepath
        filename = os.path.basename(filepath)

        if hasattr(self, 'file_label'):
            self.file_label.setText(filename)

        # --- Extract text immediately ---
        self.update_status(f"Extracting text from '{filename}'...", True)
        QApplication.processEvents() # Ensure UI updates
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        self.update_status("", False) # Clear busy status AFTER extraction attempt

        if self.resume_content is None:
             self.show_message_box("error", "PDF Error", f"Failed to extract text from {filename}. It might be image-based, empty, or protected.")
             self.pdf_filepath = None # Reset path
             if hasattr(self, 'file_label'): self.file_label.setText("Extraction Failed. Select again.")
             self.set_setup_controls_state(False) # Disable dependent controls
             self.update_status("PDF extraction failed.") # Update status
             return

        # --- Extraction Success ---
        self.update_status("Resume loaded. Configure interview or paste job description.")
        self.set_setup_controls_state(True) # Enable other setup controls
        if hasattr(self, 'job_desc_input'):
            self.job_desc_input.setFocus()


    def start_interview_process(self): # Navigate on success
        if not self.pdf_filepath or not self.resume_content: # Check content too
            self.show_message_box("warning", "Input Missing", "Select resume PDF and ensure text was extracted.")
            return
        if hasattr(self, 'job_desc_input'):
            self.job_description_text = self.job_desc_input.toPlainText().strip()

        # --- Check if OpenAI TTS is selected but failed init ---
        if self.use_openai_tts and "openai" not in tts.get_runtime_available_providers():
             self.show_message_box("error", "TTS Provider Error",
                                   "OpenAI TTS is selected, but failed to initialize.\n"
                                   "Please check API key in keyring and dependencies, or uncheck the OpenAI TTS box.\n"
                                   "Cannot start interview.")
             return
        # --- END ADDED ---

        print(f"Preparing: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, SpeechInput={self.use_speech_input}, OpenAITTS={self.use_openai_tts}")
        # Reset interview progress state, keep config (including TTS choice)
        self.reset_interview_state(clear_config=False)

        self.update_status(f"Generating {self.num_topics} questions...", True)
        self.set_setup_controls_state(False) # Disable setup controls while generating
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(False)
        QApplication.processEvents()

        # Generate questions - consider threading for long generations
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )

        # Restore UI state after generation attempt
        self.update_status("", False) # Clear busy
        # Re-enable setup controls *if PDF is still valid* (which it is here)
        pdf_loaded = bool(self.pdf_filepath) # Re-check just in case
        self.set_setup_controls_state(pdf_loaded)
        if hasattr(self, 'select_btn'): self.select_btn.setEnabled(True) # Select always re-enabled if not generating

        if not self.initial_questions:
            self.update_status("Error generating questions", False)
            self.show_message_box("error", "Generation Error", "Failed to generate initial questions. Check API key/keyring and console logs.")
            return

        # --- Success ---
        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        if len(self.initial_questions) < self.num_topics:
             print(f"Warning: Model generated {len(self.initial_questions)} questions (requested {self.num_topics}).")
             self.update_status(f"Generated {len(self.initial_questions)} questions. Starting interview...")
             QTimer.singleShot(3000, lambda: self.update_status("Interview started.")) # Clear status after delay

        self._go_to_interview_page()
        self.current_initial_q_index = 0
        self.start_next_topic()


    def start_next_topic(self): # Navigate on finish
        if not self.initial_questions:
            print("Err: No initial questions available.")
            self.show_message_box("error", "Internal Error", "No initial questions found. Returning to setup.")
            self._go_to_setup_page()
            return

        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            # Start new topic
            self.follow_up_count = 0
            self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text)
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker") # Display marker
            print(f"Asking Q {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(raw_q_text) # Ask the raw question (TTS happens here)
        else: # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Generating results...", True)
            self.disable_interview_controls()
            QApplication.processEvents()

            self.save_transcript_to_file() # Save transcript

            print("Generating summary...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating assessment...")
            assessment = logic.generate_qualification_assessment(
                self.resume_content,
                self.job_description_text,
                self.current_full_interview_history
            )

            self.update_status("Results ready.", False) # Clear busy state

            if summary is None or summary.startswith(logic.ERROR_PREFIX):
                self.show_message_box("warning", "Summary Error", f"Could not generate summary review.\n{summary or ''}")
                summary = "*Summary generation failed.*"
            if assessment is None or assessment.startswith(logic.ERROR_PREFIX):
                 if self.job_description_text:
                     self.show_message_box("warning", "Assessment Error", f"Could not generate qualification assessment.\n{assessment or ''}")
                 assessment = "*Assessment generation failed or N/A (No Job Description provided).*"

            self._go_to_results_page(summary, assessment) # Navigate


    def handle_answer_submission(self): # Uses set_recording_button_state
        if self.is_recording:
            print("Already recording...")
            return

        if self.use_speech_input:
            print("Record button clicked...")
            self.disable_interview_controls(is_recording_stt=True)
            self.update_status_stt("STT_Status: Starting Mic...")
            if hasattr(self, 'answer_input'): self.answer_input.clear()
            topic_idx = self.current_initial_q_index + 1
            followup_idx = self.follow_up_count
            recording.start_speech_recognition(topic_idx, followup_idx)
        else: # Text submission
            print("Submit button clicked.")
            if not hasattr(self, 'answer_input'):
                print("Error: answer_input missing.")
                return
            user_answer = self.answer_input.toPlainText().strip()
            if not user_answer:
                self.show_message_box("warning", "Input Required", "Please enter your answer.")
                return
            self.process_answer(user_answer)


    def update_status_stt(self, message): # Update Status Bar, trigger button state change
        if not self.status_bar_label: return
        display_message = message
        button_state = 'idle' # Default state unless overridden

        if message == "STT_Status: Starting Mic...":
             display_message = "[Starting Mic...]"
             button_state = 'processing'
        elif message == "STT_Status: Adjusting Mic...":
             display_message = "[Calibrating microphone...]"
             button_state = 'processing'
        elif message == "STT_Status: Listening...":
             display_message = "[Listening... Speak Now]"
             button_state = 'listening'
        elif message == "STT_Status: Processing...":
             display_message = "[Processing Speech...]"
             button_state = 'processing'
        elif message.startswith("STT_Warning:"):
             warning_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Warning: {warning_detail}]"
             button_state = 'idle'
             self.is_recording = False # Reset recording state
        elif message.startswith("STT_Error:"):
             error_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Error: {error_detail}]"
             button_state = 'idle'
             self.is_recording = False # Reset recording state
        elif message.startswith("STT_Success:"):
             display_message = "[Speech Recognized]"
             button_state = 'idle'
             # self.is_recording = False # Done in check_stt_queue

        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state) # Update button appearance/state
        QApplication.processEvents() # Ensure UI updates


    def check_stt_queue(self): # Uses set_recording_button_state
        try:
            result = recording.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")

            if result.startswith("STT_Status:") or result.startswith("STT_Warning:"):
                self.update_status_stt(result)
                # If warning/error status resets state, re-enable controls
                if result.startswith("STT_Warning:") or result.startswith("STT_Error:"):
                     if not self.is_recording: # Double check state just in case
                          self.enable_interview_controls()
            elif result.startswith("STT_Success:"):
                self.is_recording = False # Recording definitely done
                self.update_status_stt(result) # Show success briefly
                transcript = result.split(":", 1)[1].strip()

                if hasattr(self, 'answer_input'):
                    # Make briefly editable to display text, then disable again
                    self.answer_input.setEnabled(True)
                    self.answer_input.setReadOnly(False)
                    self.answer_input.setText(transcript)
                    self.answer_input.setReadOnly(True)
                    self.answer_input.setEnabled(False) # Will be disabled in process_answer too

                self.process_answer(transcript) # Handles next step

            elif result.startswith("STT_Error:"):
                self.is_recording = False # Recording stopped
                error_message = result.split(":", 1)[1].strip()
                self.update_status_stt(result) # Show error status
                self.show_message_box("error", "STT Error", error_message)
                self.enable_interview_controls() # Re-enable controls

        except queue.Empty:
            pass # No message
        except Exception as e:
            print(f"STT Queue Check Error: {e}")
            if self.is_recording: # Safety reset
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()


    def process_answer(self, user_answer):
        last_q = self.last_question_asked if hasattr(self, 'last_question_asked') and self.last_question_asked else "[Unknown Q]"
        print(f"Processing answer for Q: '{last_q[:50]}...' -> A: '{user_answer[:50]}...'")

        q_data = {"q": last_q, "a": user_answer}
        if hasattr(self, 'current_topic_history'): self.current_topic_history.append(q_data)
        if hasattr(self, 'current_full_interview_history'): self.current_full_interview_history.append(q_data)

        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        if hasattr(self, 'answer_input'): self.answer_input.clear()
        self.disable_interview_controls() # Disable while generating response
        self.update_status("Generating response...", True)
        QApplication.processEvents()

        proceed_to_next = False
        if hasattr(self, 'follow_up_count') and hasattr(self, 'max_follow_ups') and self.follow_up_count < self.max_follow_ups:
            follow_up_q = logic.generate_follow_up_question(
                context_question=self.current_topic_question,
                user_answer=user_answer,
                conversation_history=self.current_topic_history
            )
            self.update_status("", False) # Clear busy

            if follow_up_q and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1
                print(f"Asking Follow-up: {follow_up_q}")
                self.display_question(follow_up_q) # Re-enables controls
            elif follow_up_q == "[END TOPIC]":
                print("End topic signal received from model.")
                proceed_to_next = True
            else: # Handle generation error (None returned)
                print("Follow-up generation failed.")
                self.show_message_box("warning", "Generation Error", "Error generating follow-up question. Moving to next topic.")
                proceed_to_next = True
        else: # Max follow-ups reached or disabled
             print("Max follow-ups reached or follow-ups disabled.")
             self.update_status("", False)
             proceed_to_next = True

        if proceed_to_next:
             if hasattr(self, 'current_initial_q_index'):
                 self.current_initial_q_index += 1
                 self.start_next_topic() # Starts next or finishes
             else:
                  print("Error: current_initial_q_index missing!")
                  self._go_to_setup_page()

        if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()


    # --- Results Page Actions ---
    def _save_report(self):
        # Use the absolute RECORDINGS_DIR path
        if not (hasattr(self, 'summary_text_results') and hasattr(self, 'assessment_text_results')):
             self.show_message_box("warning", "No Data", "Results widgets not found.")
             return
        summary = self.summary_text_results.toPlainText().strip()
        assessment = self.assessment_text_results.toPlainText().strip()
        if not summary and not assessment:
            self.show_message_box("warning", "No Data", "Results are empty.")
            return

        report_content = f"Interview Report\n{'='*16}\n\nPerformance Summary\n{'-'*19}\n{summary}\n\nQualification Assessment\n{'-'*24}\n{assessment}\n"

        default_filename = "interview_report.txt"
        if self.pdf_filepath:
            base = os.path.splitext(os.path.basename(self.pdf_filepath))[0]
            default_filename = f"{base}_interview_report.txt"

        # --- Use user-specific directory (absolute path) ---
        save_dir = RECORDINGS_DIR # Already absolute path to user dir
        try:
            os.makedirs(save_dir, exist_ok=True) # Ensure it exists
        except OSError as e:
             print(f"Warning: Could not create directory for saving report: {e}")
             # Fallback to home directory if creation fails
             save_dir = os.path.expanduser("~")

        default_path = os.path.join(save_dir, default_filename) # default_path is absolute
        # --- END MODIFICATION ---

        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", default_path, "Text Files (*.txt);;All Files (*)")

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f: f.write(report_content)
                self.update_status(f"Report saved.")
                self.show_message_box("info", "Report Saved", f"Report saved to:\n{filepath}")
            except Exception as e:
                print(f"Error saving report: {e}")
                self.show_message_box("error", "Save Error", f"Could not save report:\n{e}")
        else:
            self.update_status("Report save cancelled.")


    def _open_recordings_folder(self):
        # Use the absolute RECORDINGS_DIR path
        folder_path = RECORDINGS_DIR
        print(f"Opening user recordings folder: {folder_path}")

        # Create directory if it doesn't exist (safe check)
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"Created recordings directory before opening: {folder_path}")
            except OSError as e:
                 print(f"Error creating directory before opening: {e}")
                 self.show_message_box("error", "Folder Error", f"Could not create recordings folder:\n{folder_path}\nError: {e}")
                 self.update_status("Failed to create folder.")
                 return

        # Attempt to open using QDesktopServices
        url = QUrl.fromLocalFile(folder_path)
        if not QDesktopServices.openUrl(url):
            print(f"QDesktopServices failed. Trying fallback...")
            self.update_status("Opening folder (fallback)...")
            # Fallback for different OS
            try:
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(['explorer', os.path.normpath(folder_path)])
                elif system == "Darwin": # macOS
                    subprocess.Popen(["open", folder_path])
                else: # Linux/Other
                    subprocess.Popen(["xdg-open", folder_path])
                self.update_status("Opened recordings folder (fallback).")
            except FileNotFoundError: # Command not found
                 cmd = "explorer" if system == "Windows" else ("open" if system == "Darwin" else "xdg-open")
                 print(f"Error: Command '{cmd}' not found.")
                 self.show_message_box("error", "Open Error", f"Could not find command ('{cmd}') to open the folder.\nPlease open manually:\n{folder_path}")
                 self.update_status("Failed to open folder (command missing).")
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

        # Stop any ongoing TTS playback
        print("Stopping any active TTS...")
        current_provider_name = tts.get_current_provider()
        if current_provider_name and current_provider_name in tts.tts_providers:
             provider_module = tts.tts_providers[current_provider_name]
             if hasattr(provider_module, 'stop_playback'):
                 try: provider_module.stop_playback()
                 except Exception as tts_stop_err: print(f"Error stopping TTS: {tts_stop_err}")
        else: print("No active TTS provider to stop.")

        # TODO: Add explicit stop signal for recording thread if necessary

        print("Cleanup attempts complete.")
        event.accept()