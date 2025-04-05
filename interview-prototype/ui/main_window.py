# ui/main_window.py
import os
import sys
import queue
import platform
import subprocess
import html

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QApplication, QStackedWidget,
    QLabel, QSizePolicy, QFrame
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QUrl # Keep pyqtSignal import if defining *new* signals

# --- Project Imports ---
try:
    # Assume core is a sibling directory when running normally
    import core.logic as logic
    from core import tts
    from core import recording
    from core.recording import RECORDINGS_DIR
except ImportError:
    # Fallback for running script directly from ui directory or issues
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import core.logic as logic
    from core import tts
    from core import recording
    from core.recording import RECORDINGS_DIR

# --- Import Page Classes ---
from .setup_page import SetupPage
from .interview_page import InterviewPage
from .results_page import ResultsPage
# Import constants from results_page for use in save_report
from .results_page import FIXED_SPEECH_DESCRIPTION, FIXED_SPEECH_SCORE, FIXED_CONTENT_SCORE


class InterviewApp(QWidget):
    """
    Main application window for the Interview Bot Pro.
    Manages the UI pages, application state, and core logic interactions.
    """
    # Constants for page indices
    SETUP_PAGE_INDEX = 0
    INTERVIEW_PAGE_INDEX = 1
    RESULTS_PAGE_INDEX = 2

    # --- IF YOU NEED TO DEFINE *NEW* SIGNALS FOR THIS WINDOW, DO IT HERE ---
    # Example:
    # interview_started_signal = pyqtSignal(str) # Emits resume filename when started

    def __init__(self, icon_path, *args, **kwargs):
        """
        Initializes the InterviewApp.

        Args:
            icon_path (str): The absolute path to the icons directory.
            *args: Variable length argument list for QWidget.
            **kwargs: Arbitrary keyword arguments for QWidget.
        """
        super().__init__(*args, **kwargs)
        self.icon_path = icon_path # Store resolved path for pages to use
        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000) # Initial position and size

        self._setup_appearance()      # Apply custom styling/palette
        self._load_assets()           # Load shared resources like fonts/sizes
        self._init_state()            # Initialize application state variables
        self._setup_ui()              # Create UI layout and page instances
        self._update_ui_from_state()  # Set initial UI based on state
        self._update_progress_indicator() # Set initial progress display
        # Timer for checking Speech-to-Text results queue
        self.stt_timer = QTimer(self)
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100) # Check every 100ms

    def _setup_appearance(self):
        """Sets the dark theme palette for the application."""
        palette = self.palette()
        # Define colors for various UI roles
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))        # Background for text inputs
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53)) # Used by some views
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(50,50,50))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))     # Default text color
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))      # Button background
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))      # Color for links
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218)) # Selection background
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black) # Selection text
        # Disabled state colors
        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)
        # Apply the palette and style
        self.setPalette(palette)
        QApplication.setStyle("Fusion") # Fusion style works well with custom palettes

    def _load_assets(self):
        """Loads shared resources like fonts and icon sizes needed by pages."""
        # Define shared sizes and fonts that pages can access via self.parent_window
        self.icon_size = QSize(20, 20)
        self.font_default = QFont("Arial", 10)
        self.font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 9)
        self.font_large_bold = QFont("Arial", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9) # For transcript view

    def _init_state(self):
        """Initializes the application's state variables."""
        # Configuration state
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        self.num_topics = logic.DEFAULT_NUM_TOPICS
        self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
        self.use_speech_input = False
        self.use_openai_tts = False

        # Interview progress state
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = [] # History for the *current* topic (for follow-ups)
        self.follow_up_count = 0
        self.current_full_interview_history = [] # History of all Q&A pairs
        self.is_recording = False # Flag for STT recording active
        self.last_question_asked = "" # Store the text of the last question asked

        # Page instances - will be created in _setup_ui
        self.setup_page_instance = None
        self.interview_page_instance = None
        self.results_page_instance = None

        # Keep references to widgets directly part of the main window layout
        self.progress_indicator_label = None
        self.status_bar_label = None
        self.stacked_widget = None

    def _setup_ui(self):
        """Sets up the main window layout, stack widget, and page instances."""
        main_window_layout = QVBoxLayout(self)
        main_window_layout.setContentsMargins(0, 0, 0, 0) # No margins for main layout
        main_window_layout.setSpacing(0)                  # No spacing

        # --- Progress Indicator (Top Bar) ---
        self.progress_indicator_label = QLabel("...")
        self.progress_indicator_label.setObjectName("progressIndicator") # For QSS styling
        self.progress_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_indicator_label.setTextFormat(Qt.TextFormat.RichText) # Allow HTML for styling active step
        main_window_layout.addWidget(self.progress_indicator_label)

        # --- Separator Line ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_window_layout.addWidget(line)

        # --- Stacked Widget (Main Content Area) ---
        self.stacked_widget = QStackedWidget()
        main_window_layout.addWidget(self.stacked_widget, stretch=1) # Allow stack to grow

        # --- Instantiate Page Widgets ---
        # Pass 'self' (the InterviewApp instance) to each page constructor.
        # Pages can then access shared state, resources (fonts, icon_path), and methods.
        self.setup_page_instance = SetupPage(self)
        self.interview_page_instance = InterviewPage(self)
        self.results_page_instance = ResultsPage(self)

        # --- Add Page Instances to the Stacked Widget ---
        self.stacked_widget.addWidget(self.setup_page_instance)
        self.stacked_widget.addWidget(self.interview_page_instance)
        self.stacked_widget.addWidget(self.results_page_instance)

        # --- Status Bar (Bottom Bar) ---
        self.status_bar_label = QLabel("Ready.")
        self.status_bar_label.setObjectName("statusBar") # For QSS styling
        main_window_layout.addWidget(self.status_bar_label)

        self.setLayout(main_window_layout) # Apply the main layout to the window

    def _update_ui_from_state(self):
        """
        Updates all UI elements across pages to reflect the current application state.
        Typically called after state changes (e.g., reset, loading).
        """
        print("Updating UI from state...")
        pdf_loaded = bool(self.pdf_filepath) # Check if a resume PDF is loaded

        # Delegate state updates to each page instance
        if self.setup_page_instance:
            self.setup_page_instance.update_widgets_from_state()
            # Explicitly ensure the select button is enabled after state update
            # (unless it should be disabled for other reasons, like generation in progress)
            select_btn = getattr(self.setup_page_instance, 'select_btn', None)
            if select_btn:
                # Consider if start_interview_process is running? Assume not during this general update.
                 select_btn.setEnabled(True)

        if self.interview_page_instance:
            # Clear dynamic fields like question/answer/history on reset
            self.interview_page_instance.clear_fields()

        if self.results_page_instance:
            # Clear results text areas on reset
            self.results_page_instance.clear_fields()

        # Reset status bar message
        self.update_status("Ready.")
        # Ensure the first page (Setup) is shown
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        # Update the submit button state based on current settings (e.g., STT enabled/disabled)
        self.update_submit_button_text()

    # --- Navigation and Progress Indication ---

    def _update_progress_indicator(self):
        """Updates the top progress bar label to highlight the current step."""
        if not self.progress_indicator_label or not self.stacked_widget:
             return # Widgets not ready yet
        current_index = self.stacked_widget.currentIndex()
        steps = ["Step 1: Setup", "Step 2: Interview", "Step 3: Results"]
        progress_parts = []
        for i, step in enumerate(steps):
            if i == current_index:
                # Use HTML/Rich Text for styling the active step
                progress_parts.append(f'<font color="orange"><b>{step}</b></font>')
            else:
                progress_parts.append(step)
        progress_text = " → ".join(progress_parts)
        self.progress_indicator_label.setText(progress_text)

    def _go_to_setup_page(self):
        """Navigates to the Setup page and performs a full reset."""
        print("Navigating to Setup Page and Resetting...")
        self.reset_interview_state(clear_config=True) # Full reset including config
        if self.stacked_widget: self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self._update_progress_indicator() # Update progress display

    def _go_to_interview_page(self):
        """Navigates to the Interview page, clearing relevant fields."""
        print("Navigating to Interview Page...")
        # Clear dynamic fields on the interview page before showing it
        if self.interview_page_instance:
            self.interview_page_instance.clear_fields()
        if self.stacked_widget: self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview started. Waiting for question...")

    def _go_to_results_page(self, summary, assessment):
        """Navigates to the Results page and displays the generated results."""
        print("Navigating to Results Page...")
        # Display results using the results page's method
        if self.results_page_instance:
            # The display_results method now handles both summary and assessment
            self.results_page_instance.display_results(summary, assessment)
        if self.stacked_widget: self.stacked_widget.setCurrentIndex(self.RESULTS_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview complete. Results displayed.")

    # --- Helper Methods & State Management ---

    def show_message_box(self, level, title, message):
        """Displays a modal message box."""
        box = QMessageBox(self) # Parent to the main window
        icon_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical
        }
        box.setIcon(icon_map.get(level, QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec() # Show modally

    def _adjust_value(self, value_type, amount):
        """
        Adjusts configuration values (topics, follow-ups) based on button clicks.
        Updates both the internal state and the corresponding label on the setup page.
        """
        current_val, min_val, max_val, target_label_widget, target_var_name = 0, 0, 0, None, ""

        # Determine which value to adjust and get the corresponding label widget
        if value_type == 'topics' and self.setup_page_instance:
            target_label_widget = getattr(self.setup_page_instance, 'num_topics_label', None)
            current_val, min_val, max_val, target_var_name = self.num_topics, logic.MIN_TOPICS, logic.MAX_TOPICS, 'num_topics'
        elif value_type == 'followups' and self.setup_page_instance:
            target_label_widget = getattr(self.setup_page_instance, 'max_follow_ups_label', None)
            current_val, min_val, max_val, target_var_name = self.max_follow_ups, logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT, 'max_follow_ups'
        else:
            print(f"Warning: Cannot adjust value. Type '{value_type}' or setup page instance not found.")
            return # Cannot proceed if setup page or label isn't found

        new_value = current_val + amount

        # Apply change if within limits
        if min_val <= new_value <= max_val:
            setattr(self, target_var_name, new_value) # Update the state variable (e.g., self.num_topics)
            if target_label_widget:
                target_label_widget.setText(str(new_value)) # Update the visual label
            print(f"{target_var_name.replace('_',' ').title()} set to: {new_value}")
        else:
            print(f"Value {new_value} for {value_type} out of bounds ({min_val}-{max_val})")

    def update_status(self, message, busy=False):
        """Updates the bottom status bar text and optionally shows a busy cursor."""
        if self.status_bar_label:
            self.status_bar_label.setText(message)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents() # Ensure UI updates immediately

    def display_question(self, question_text):
        """
        Displays the interviewer's question on the interview page and triggers TTS.
        """
        self.last_question_asked = question_text # Store for context
        # Update the question text edit widget via the interview page instance
        if self.interview_page_instance and hasattr(self.interview_page_instance, 'current_q_text'):
            self.interview_page_instance.current_q_text.setPlainText(question_text)
        else:
            # Fallback if widget isn't ready - show in status bar
            self.update_status(f"Asking: {question_text[:30]}...")

        # Speak the question using the configured TTS provider
        try:
            tts.speak_text(question_text)
        except Exception as e:
            print(f"TTS Error during speak_text call: {e}")
            self.show_message_box("warning", "TTS Error", f"Could not speak question: {e}")

        # Enable controls for user to answer
        self.enable_interview_controls()

        # Focus the answer input if not using speech input
        answer_input = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input and not self.use_speech_input:
            answer_input.setFocus()

    def add_to_history(self, text, tag=None):
        """Adds text (question or answer) to the transcript view on the interview page."""
        if not self.interview_page_instance or not hasattr(self.interview_page_instance, 'history_text'):
            print("Warning: History text widget not found.")
            return # Cannot add history if widget doesn't exist

        history_widget = self.interview_page_instance.history_text
        cursor = history_widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End) # Go to the end
        history_widget.setTextCursor(cursor)

        # Determine text color based on application palette and tag
        text_color_name = self.palette().color(QPalette.ColorRole.Text).name() # Default text color
        # Escape HTML special characters and handle newlines for display
        escaped_text = html.escape(text).replace("\n", "<br>")

        # Apply styling using simple HTML tags
        html_content = ""
        if tag == "question_style":
            html_content = f'<font color="#569CD6">{escaped_text}</font>' # Blue for questions
        elif tag == "answer_style":
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>' # Default text color for answers
        elif tag == "topic_marker":
            html_content = f'<font color="grey"><b>{escaped_text}</b></font>' # Grey and bold for separators
        else:
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>' # Default

        history_widget.insertHtml(html_content) # Insert the styled HTML
        history_widget.ensureCursorVisible()      # Scroll to the bottom

    def set_setup_controls_state(self, pdf_loaded):
        """Delegates enabling/disabling controls on the setup page based on PDF load state."""
        if self.setup_page_instance:
            self.setup_page_instance.set_controls_enabled_state(pdf_loaded)
        # Note: Disabling the 'Select Resume' button during question generation
        # is handled directly in `start_interview_process`.

    def enable_interview_controls(self):
        """Delegates enabling controls on the interview page."""
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(True)
            self.is_recording = False # Ensure recording flag is off
            # Update button state to 'idle' (record or submit based on mode)
            self.set_recording_button_state('idle')

    def disable_interview_controls(self, is_recording_stt=False):
        """
        Delegates disabling controls on the interview page.

        Args:
            is_recording_stt (bool): True if disabling is due to STT recording starting.
        """
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(False, is_recording_stt)
            self.is_recording = is_recording_stt # Update recording flag

    def reset_interview_state(self, clear_config=True):
        """
        Resets the application state, optionally clearing configuration.
        Updates the UI to reflect the reset state.
        """
        print(f"Resetting interview state (clear_config={clear_config})...")
        if clear_config:
            # Reset configuration state
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = "" # Clear state variable
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False
            self.use_openai_tts = False
            # Reset TTS provider to default
            current_provider = tts.get_current_provider()
            default_provider = tts.DEFAULT_PROVIDER
            print(f"Resetting TTS. Current: {current_provider}, Default: {default_provider}")
            if current_provider != default_provider:
                if not tts.set_provider(default_provider):
                    # Try first available if default fails
                    potential = tts.get_potentially_available_providers()
                    fallback = potential[0] if potential else None
                    if fallback and tts.set_provider(fallback):
                        print(f"Reset TTS: Set to first available '{fallback}'.")
                    else: print("Reset TTS: ERROR - Could not set default or fallback TTS provider.")
                else: print(f"Reset TTS: Set to default '{default_provider}'.")

        # Always reset dynamic interview progress state
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""

        # Update UI based on the reset state
        self._update_ui_from_state() # This calls update methods on page instances
        # Ensure interview controls are disabled after reset
        self.disable_interview_controls()
        QApplication.restoreOverrideCursor() # Ensure normal cursor
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text):
        """Removes leading numbers/punctuation from generated questions for cleaner matching."""
        cleaned = raw_q_text.strip()
        # Try removing "1.", "1)", "1 " etc.
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split('.', 1);
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(')', 1);
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            parts = cleaned.split(' ', 1);
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
        return cleaned # Return original cleaned text if no pattern matched

    def save_transcript_to_file(self):
        """Saves the full interview transcript (Q&A) to a text file in the recordings directory."""
        if not self.current_full_interview_history:
            print("No history to save.")
            return
        # Create a mapping from cleaned initial question text to its index for topic grouping
        if not self.initial_questions:
            print("Warning: Initial questions missing, cannot accurately map topics in transcript.")
            topic_index_map = {} # Proceed without mapping
        else:
            topic_index_map = {self._clean_question_text(q): i for i, q in enumerate(self.initial_questions)}

        transcript_lines = []
        last_topic_num = -1 # Track the last initial question number

        try:
            for qa_pair in self.current_full_interview_history:
                 q_raw = qa_pair.get('q', 'N/A')
                 a = qa_pair.get('a', 'N/A')
                 q_clean = self._clean_question_text(q_raw)
                 # Find if the question matches one of the initial questions
                 topic_index = topic_index_map.get(q_clean, -1)

                 if topic_index != -1: # It's an initial question
                    current_topic_num = topic_index + 1
                    # Add a separator if starting a new topic (and not the very first one)
                    if current_topic_num != last_topic_num and last_topic_num != -1:
                        transcript_lines.append("\n-------------------------") # Separator
                    transcript_lines.append(f"\nQuestion {current_topic_num}: {q_raw}\nAnswer: {a}")
                    last_topic_num = current_topic_num
                 else: # It's a follow-up question
                    ctx = f"Topic {last_topic_num}" if last_topic_num > 0 else "General"
                    transcript_lines.append(f"\nFollow Up (re {ctx}): {q_raw}\nAnswer: {a}")

            # Ensure user-specific directory exists (using absolute path from core.recording)
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
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

    def set_recording_button_state(self, state):
        """
        Updates the text and icon of the Submit/Record button based on the current state.
        Retrieves necessary icons from the interview page instance.
        """
        # Get the button widget from the interview page instance
        if not self.interview_page_instance: return
        target_button = getattr(self.interview_page_instance, 'submit_button', None)
        if not target_button:
            # This might happen briefly during startup or shutdown
            # print("Warning: Submit button not found on interview page during set_recording_button_state.")
            return

        target_icon = None
        target_text = "Submit Answer" # Default

        # Access icons stored on the interview page instance
        # Use getattr for safety in case icons didn't load
        submit_icon = getattr(self.interview_page_instance, 'submit_icon', None)
        record_icon = getattr(self.interview_page_instance, 'record_icon', None)
        listening_icon = getattr(self.interview_page_instance, 'listening_icon', None)
        processing_icon = getattr(self.interview_page_instance, 'processing_icon', None)

        # Determine text, icon, and enabled state based on the requested state
        if state == 'listening':
            target_text, target_icon = "Listening...", listening_icon
            target_button.setEnabled(False) # Cannot click while listening
        elif state == 'processing':
            target_text, target_icon = "Processing...", processing_icon
            target_button.setEnabled(False) # Cannot click while processing
        elif state == 'idle':
            target_button.setEnabled(True) # Enable button in idle state
            if self.use_speech_input:
                target_text, target_icon = "Record Answer", record_icon
            else:
                target_text, target_icon = "Submit Answer", submit_icon
        else: # Fallback (treat as idle)
            target_button.setEnabled(True)
            if self.use_speech_input: target_text, target_icon = "Record Answer", record_icon
            else: target_text, target_icon = "Submit Answer", submit_icon

        # Apply the changes to the button
        target_button.setText(target_text)
        if target_icon and not target_icon.isNull():
            target_button.setIcon(target_icon)
            target_button.setIconSize(self.icon_size) # Ensure size is set
        else:
            target_button.setIcon(QIcon()) # Clear icon if none provided or load failed

    # --- GUI Logic/Event Handlers (Slots) ---

    def _handle_openai_tts_change(self, check_state_value):
        """
        Slot triggered when the 'Use OpenAI TTS' checkbox state changes.
        Attempts to set the TTS provider and updates the UI accordingly.
        """
        checkbox = getattr(self.setup_page_instance, 'openai_tts_checkbox', None)
        is_checked = (check_state_value == Qt.CheckState.Checked.value)
        target_provider = "openai" if is_checked else tts.DEFAULT_PROVIDER # Fallback to default if unchecked
        print(f"OpenAI TTS change detected. Target provider: '{target_provider}'")

        # Block signals on the checkbox to prevent loops if we change its state programmatically
        if checkbox: checkbox.blockSignals(True)

        # Attempt to set the TTS provider via the core TTS facade
        success = tts.set_provider(target_provider)

        if success:
            self.use_openai_tts = is_checked # Update the main application state
            current_provider = tts.get_current_provider()
            self.update_status(f"TTS Provider set to: {current_provider}")
            print(f"Successfully set TTS provider to: {current_provider}")
        else:
            # Setting the provider failed, revert state and UI
            self.use_openai_tts = False # Revert state variable
            if is_checked and checkbox: checkbox.setChecked(False) # Uncheck the box visually

            print(f"Failed to set provider '{target_provider}'. Attempting fallback...")
            # Try setting default provider as fallback
            if not tts.set_provider(tts.DEFAULT_PROVIDER):
                 # Final fallback if default also fails
                 potential = tts.get_potentially_available_providers()
                 final_fallback = potential[0] if potential else None
                 if final_fallback and tts.set_provider(final_fallback):
                      print(f"Fallback to first available '{final_fallback}' succeeded.")
                 else:
                      # Critical failure - no TTS available
                      print("ERROR: Failed to set any TTS provider.")
                      self.show_message_box("error", "TTS Error", f"Failed to set TTS provider '{target_provider}' and could not fall back. Check console and dependencies/keyring.")
                      # Optionally disable the checkbox entirely if it's unusable
                      if checkbox:
                          checkbox.setEnabled(False)
                          checkbox.setToolTip("TTS provider error. Check console.")
            else:
                 print(f"Fallback to default provider '{tts.DEFAULT_PROVIDER}' succeeded.")

            current_provider = tts.get_current_provider()
            status_msg = f"Failed to set OpenAI TTS. Using: {current_provider or 'None'}"
            self.update_status(status_msg)

            # Show a more specific error message if enabling OpenAI was the action that failed
            if is_checked:
                 openai_keyring_info = ""
                 try: # Safely construct keyring info string
                     openai_keyring_info = f"(Service: '{tts.tts_providers['openai'].KEYRING_SERVICE_NAME_OPENAI}')"
                 except (KeyError, AttributeError): openai_keyring_info = "(Keyring details unavailable)"

                 self.show_message_box("warning", "OpenAI TTS Failed",
                                      f"Could not enable OpenAI TTS.\nPlease ensure:\n"
                                      f"- Dependencies are installed (openai, sounddevice, pydub, etc.).\n"
                                      f"- API key is stored correctly in keyring {openai_keyring_info}.\n"
                                      f"- FFmpeg is installed and accessible in PATH.\nCheck console logs for details. Currently using: {current_provider or 'None'}")

        # Re-enable signals on the checkbox
        if checkbox: checkbox.blockSignals(False)

    def update_submit_button_text(self, check_state_value=None):
        """
        Slot triggered by the 'Use Speech Input' checkbox. Updates the STT state
        and the appearance/behavior of the submit/record button and answer input field.
        Can also be called directly to refresh button state.
        """
        # Update state if called directly from the checkbox signal
        if check_state_value is not None:
            self.use_speech_input = (check_state_value == Qt.CheckState.Checked.value)
            print(f"Use Speech Input (STT) state changed to: {self.use_speech_input}")

        # Update button appearance (text/icon) based on the STT mode,
        # but only if not currently in a recording/processing state.
        if not self.is_recording:
            self.set_recording_button_state('idle') # Update to 'Record Answer' or 'Submit Answer'

        # Adjust the answer input field's behavior
        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input_widget:
            is_text_mode = not self.use_speech_input

            # Determine if interview controls should generally be enabled
            # (i.e., not waiting for question, not currently processing answer)
            submit_btn = getattr(self.interview_page_instance, 'submit_button', None)
            # Controls enabled if submit button *is currently* enabled AND not currently recording
            # Note: button might be disabled by processing state, check that too.
            controls_generally_active = submit_btn and submit_btn.isEnabled() and not self.is_recording

            # Set read-only based on input mode
            answer_input_widget.setReadOnly(not is_text_mode)
            # Set enabled state based on mode AND whether controls are generally active
            # Input field should be disabled if not in text mode OR if controls are generally inactive
            answer_input_widget.setEnabled(is_text_mode and controls_generally_active)

            # Update placeholder text and focus
            if is_text_mode and controls_generally_active:
                answer_input_widget.setFocus()
                answer_input_widget.setPlaceholderText("Type your answer here...")
            elif not is_text_mode: # Speech input mode
                answer_input_widget.clear() # Clear any typed text when switching to speech
                answer_input_widget.setPlaceholderText("Click 'Record Answer' to speak...")
            else: # Text mode, but controls are disabled (e.g., waiting for question/processing)
                 answer_input_widget.setPlaceholderText("Waiting for question or processing...")

    def select_resume_file(self):
        """Slot triggered by the 'Select Resume PDF' button."""
        # Default to user's home directory
        start_dir = os.path.expanduser("~")
        # Convert to platform-specific path separators if needed (though Qt often handles it)
        start_dir_native = os.path.normpath(start_dir)

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume PDF",
            start_dir_native,
            "PDF Files (*.pdf)"
        )

        file_label_widget = getattr(self.setup_page_instance, 'file_label', None)

        if not filepath:
            # User cancelled - only update label if no file was previously selected
            if file_label_widget and not self.pdf_filepath:
                file_label_widget.setText("Selection cancelled.")
            self.update_status("Resume selection cancelled.")
            return

        # --- File successfully selected ---
        self.pdf_filepath = filepath # Store the path
        filename = os.path.basename(filepath)
        if file_label_widget: file_label_widget.setText(filename) # Update label

        # --- Extract text immediately ---
        self.update_status(f"Extracting text from '{filename}'...", True) # Show busy state
        QApplication.processEvents() # Ensure UI updates before potentially long operation
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        self.update_status("", False) # Clear busy state AFTER extraction attempt

        if self.resume_content is None:
             # Extraction failed
             self.show_message_box("error", "PDF Error", f"Failed to extract text from {filename}. It might be image-based, empty, or protected.")
             self.pdf_filepath = None # Reset path state
             if file_label_widget: file_label_widget.setText("Extraction Failed. Select again.")
             self.set_setup_controls_state(False) # Disable dependent controls via page method
             self.update_status("PDF extraction failed.")
             return

        # --- Extraction Success ---
        self.update_status("Resume loaded. Configure interview or paste job description.")
        self.set_setup_controls_state(True) # Enable other setup controls via page method
        job_desc_widget = getattr(self.setup_page_instance, 'job_desc_input', None)
        if job_desc_widget: job_desc_widget.setFocus() # Focus JD input

    def start_interview_process(self):
        """Slot triggered by the 'Start Interview' button."""
        # --- Validation ---
        if not self.pdf_filepath or not self.resume_content: # Check content too
            self.show_message_box("warning", "Input Missing", "Please select a valid resume PDF first.")
            return

        # Get job description text from the setup page widget
        job_desc_widget = getattr(self.setup_page_instance, 'job_desc_input', None)
        if job_desc_widget:
            self.job_description_text = job_desc_widget.toPlainText().strip()
        else:
            self.job_description_text = "" # Ensure it's reset if widget not found

        # Check if OpenAI TTS is selected but failed initialization (e.g., missing key)
        if self.use_openai_tts and "openai" not in tts.get_runtime_available_providers():
             self.show_message_box("error", "TTS Provider Error",
                                   "OpenAI TTS is selected, but failed to initialize.\n"
                                   "Please check API key in keyring and dependencies, or uncheck the OpenAI TTS box.\n"
                                   "Cannot start interview.")
             return

        # --- Preparation ---
        print(f"Preparing Interview: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, STT={self.use_speech_input}, OpenAITTS={self.use_openai_tts}")
        # Reset interview progress state, but keep configuration (PDF, JD, topics, TTS choice etc.)
        self.reset_interview_state(clear_config=False)

        self.update_status(f"Generating {self.num_topics} interview questions...", True)
        # Disable setup controls while generating questions
        self.set_setup_controls_state(False) # Disables most controls via page method
        select_btn_widget = getattr(self.setup_page_instance, 'select_btn', None)
        if select_btn_widget: select_btn_widget.setEnabled(False) # Specifically disable select button
        QApplication.processEvents()

        # --- Generate Initial Questions (Potentially long operation) ---
        # Consider running this in a separate thread for complex scenarios
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )

        # --- Post-Generation ---
        self.update_status("", False) # Clear busy status
        pdf_loaded = bool(self.pdf_filepath) # Re-check just in case
        self.set_setup_controls_state(pdf_loaded) # Re-enable controls via page method
        if select_btn_widget: select_btn_widget.setEnabled(True) # Re-enable select button

        if not self.initial_questions:
            self.update_status("Error generating questions", False)
            self.show_message_box("error", "Generation Error", "Failed to generate initial questions. Check API key/connection and console logs.")
            return

        # --- Success ---
        print(f"Generated {len(self.initial_questions)} initial questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        # Handle if fewer questions generated than requested
        if len(self.initial_questions) < self.num_topics:
             print(f"Warning: Model generated {len(self.initial_questions)} questions (requested {self.num_topics}). Proceeding with available questions.")
             self.update_status(f"Generated {len(self.initial_questions)} questions. Starting interview...")
             # Optional: Short delay before clearing status
             QTimer.singleShot(3000, lambda: self.update_status("Interview started."))

        # Navigate to the interview page and start the first topic
        self._go_to_interview_page()
        self.current_initial_q_index = 0 # Start with the first question
        self.start_next_topic()

    def start_next_topic(self):
        """Initiates the next topic or ends the interview if all topics are covered."""
        if not self.initial_questions:
            print("Error: start_next_topic called with no initial questions.")
            self.show_message_box("error", "Internal Error", "No initial questions found. Returning to setup.")
            self._go_to_setup_page()
            return

        # Check if there are more initial questions left
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            # Start the next topic
            self.follow_up_count = 0 # Reset follow-up counter for the new topic
            self.current_topic_history = [] # Clear history for the new topic
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text) # Store cleaned question for context

            # Add a visual separator in the transcript
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1} of {len(self.initial_questions)} ---\n"
            print(topic_marker.strip()) # Log separator
            self.add_to_history(topic_marker, tag="topic_marker") # Add styled separator to UI

            print(f"Asking Initial Question {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(raw_q_text) # Display and speak the raw question
        else:
            # --- End of Interview ---
            print("\n--- All Initial Questions Asked: Interview Finished ---")
            self.update_status("Generating final results...", True)
            self.disable_interview_controls() # Disable input on interview page
            QApplication.processEvents()

            # Save the transcript before generating summary/assessment
            self.save_transcript_to_file()

            # Generate summary review and qualification assessment
            print("Generating summary review...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating qualification assessment...")
            assessment = logic.generate_qualification_assessment(
                self.resume_content,
                self.job_description_text,
                self.current_full_interview_history
            )

            self.update_status("Results ready.", False) # Clear busy state

            # Handle potential generation errors/empty results
            if summary is None or summary.startswith(logic.ERROR_PREFIX):
                self.show_message_box("warning", "Summary Error", f"Could not generate summary review.\nDetails: {summary or 'No details'}")
                summary = "*Summary generation failed or an error occurred.*"
            if assessment is None or assessment.startswith(logic.ERROR_PREFIX):
                 # Only show assessment error if JD was provided
                 if self.job_description_text:
                     self.show_message_box("warning", "Assessment Error", f"Could not generate qualification assessment.\nDetails: {assessment or 'No details'}")
                 assessment = "*Assessment generation failed, an error occurred, or no Job Description was provided.*"

            # Navigate to the results page and display the content
            self._go_to_results_page(summary, assessment)

    def handle_answer_submission(self):
        """
        Slot triggered by the Submit/Record button. Handles either text submission
        or initiates speech recognition.
        """
        if self.is_recording:
            print("Already recording, ignoring button press.")
            return

        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)

        if self.use_speech_input:
            # --- Start Speech Recognition ---
            print("Record button clicked, starting STT...")
            self.disable_interview_controls(is_recording_stt=True) # Disable controls, set recording flag
            self.update_status_stt("STT_Status: Starting Mic...") # Update status/button
            if answer_input_widget: answer_input_widget.clear() # Clear text area
            # Prepare context for filename/logging
            topic_idx = self.current_initial_q_index + 1
            followup_idx = self.follow_up_count # Use current count (0 for initial Q)
            # Call the core recording function (runs in a separate thread)
            recording.start_speech_recognition(topic_idx, followup_idx)
        else:
            # --- Process Text Submission ---
            print("Submit button clicked, processing text answer.")
            if not answer_input_widget:
                print("Error: Answer input widget not found.")
                self.show_message_box("error", "Internal Error", "Cannot find answer input field.")
                return
            user_answer = answer_input_widget.toPlainText().strip()
            if not user_answer:
                self.show_message_box("warning", "Input Required", "Please type your answer before submitting.")
                return
            # Process the typed answer
            self.process_answer(user_answer)

    def update_status_stt(self, message):
        """Updates the status bar and submit/record button state based on STT messages."""
        if not self.status_bar_label: return # Status bar not ready
        display_message = message
        button_state = 'idle' # Default state unless overridden by status

        # Map internal STT status messages to user-friendly text and button states
        if message == "STT_Status: Starting Mic...":
             display_message = "[Starting Microphone...]"
             button_state = 'processing'
        elif message == "STT_Status: Adjusting Mic...":
             display_message = "[Calibrating microphone threshold...]"
             button_state = 'processing'
        elif message == "STT_Status: Listening...":
             display_message = "[Listening... Speak Now]"
             button_state = 'listening'
        elif message == "STT_Status: Processing...":
             display_message = "[Processing Speech... Please Wait]"
             button_state = 'processing'
        elif message.startswith("STT_Warning:"):
             warning_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Warning: {warning_detail}]"
             button_state = 'idle' # Return to idle state on warning
             self.is_recording = False # Ensure recording flag is reset
        elif message.startswith("STT_Error:"):
             error_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Error: {error_detail}]"
             button_state = 'idle' # Return to idle state on error
             self.is_recording = False # Ensure recording flag is reset
        elif message.startswith("STT_Success:"):
             # Status shows success briefly, then process_answer takes over status
             display_message = "[Speech Recognized Successfully]"
             button_state = 'idle' # Return button to idle after success
             # self.is_recording flag is reset in check_stt_queue after processing result

        # Update the UI elements
        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state) # Update button appearance/state
        QApplication.processEvents() # Force UI update

    def check_stt_queue(self):
        """Periodically checks the STT result queue for messages from the recording thread."""
        try:
            # Non-blocking check of the queue
            result = recording.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")

            # Handle different types of messages from the queue
            if result.startswith("STT_Status:") or result.startswith("STT_Warning:") or result.startswith("STT_Error:"):
                # Update status bar and button state for status/warning/error messages
                self.update_status_stt(result)
                # If warning/error resets state, re-enable controls if needed
                if result.startswith("STT_Warning:") or result.startswith("STT_Error:"):
                     if not self.is_recording: # Check if state was reset
                          self.enable_interview_controls()
            elif result.startswith("STT_Success:"):
                # Successful recognition
                self.is_recording = False # Mark recording as finished
                self.update_status_stt(result) # Show success message briefly
                transcript = result.split(":", 1)[1].strip() # Extract the transcript text

                # Display the transcript in the answer box (temporarily enable/disable)
                answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
                if answer_input_widget:
                    answer_input_widget.setEnabled(True); answer_input_widget.setReadOnly(False)
                    answer_input_widget.setText(transcript)
                    answer_input_widget.setReadOnly(True); answer_input_widget.setEnabled(False) # Lock it again

                # Process the recognized answer
                self.process_answer(transcript)

            # Note: STT_Error was handled above by update_status_stt, which resets state
            # and re-enables controls. No specific action needed here for STT_Error message itself.

        except queue.Empty:
            pass # No message in the queue, do nothing
        except Exception as e:
            print(f"Error checking STT Queue: {e}")
            # Safety reset in case of unexpected errors
            if self.is_recording:
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()
            self.update_status(f"Error checking speech recognition: {e}")


    def process_answer(self, user_answer):
        """
        Processes the user's answer (text or STT result), adds it to history,
        generates a follow-up question or moves to the next topic.
        """
        last_q = self.last_question_asked or "[Unknown Question]" # Get context
        print(f"Processing answer for Q: '{last_q[:50]}...' -> A: '{user_answer[:50]}...'")

        # Add Q&A pair to history lists
        q_data = {"q": last_q, "a": user_answer}
        self.current_topic_history.append(q_data)       # For follow-up generation context
        self.current_full_interview_history.append(q_data) # For final transcript/review

        # Add styled Q&A to the transcript view on the interview page
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style") # Updates widget via page instance

        # Clear the answer input field
        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input_widget: answer_input_widget.clear()

        # Disable controls while generating the next response
        self.disable_interview_controls() # Disables controls via page instance
        self.update_status("Generating response from interviewer...", True)
        QApplication.processEvents()

        proceed_to_next_topic = False # Flag to determine if we move on

        # Check if follow-ups are allowed for this topic
        if self.follow_up_count < self.max_follow_ups:
            # Generate follow-up question based on context
            follow_up_q = logic.generate_follow_up_question(
                context_question=self.current_topic_question, # The original topic question
                user_answer=user_answer,
                conversation_history=self.current_topic_history # Q&A pairs for *this* topic
            )
            self.update_status("", False) # Clear busy status after generation attempt

            if follow_up_q and follow_up_q.strip() and follow_up_q != "[END TOPIC]":
                # Valid follow-up generated
                self.follow_up_count += 1
                print(f"Asking Follow-up Question ({self.follow_up_count}/{self.max_follow_ups}): {follow_up_q}")
                self.display_question(follow_up_q) # Display and speak follow-up
                # display_question re-enables controls
            elif follow_up_q == "[END TOPIC]":
                # Model explicitly signalled to end the topic
                print("Model signalled to end the current topic.")
                proceed_to_next_topic = True
            else:
                # Follow-up generation failed (returned None or empty) or was invalid
                print("Follow-up question generation failed or returned invalid response.")
                self.show_message_box("warning", "Generation Error", "Error generating follow-up question. Moving to the next topic.")
                proceed_to_next_topic = True
        else:
             # Max follow-ups reached for this topic
             print(f"Max follow-ups ({self.max_follow_ups}) reached for this topic.")
             self.update_status("", False) # Clear busy status if needed
             proceed_to_next_topic = True

        # If flagged, move to the next initial question/topic
        if proceed_to_next_topic:
             self.current_initial_q_index += 1 # Increment index
             self.start_next_topic() # Initiate next topic or end interview

        # Ensure cursor returns to normal if it was busy
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    # --- Results Page Actions (Slots) ---

    def _save_report(self):
        """Slot triggered by the 'Save Report' button on the results page."""
        # Get text content from the results page widgets
        if not self.results_page_instance:
            self.show_message_box("warning", "Internal Error", "Results page not found.")
            return

        content_widget = getattr(self.results_page_instance, 'content_score_text_edit', None)
        job_fit_widget = getattr(self.results_page_instance, 'job_fit_text_edit', None)

        # Fetch dynamic content (handling cases where widgets might be missing)
        # Use toMarkdown() to preserve formatting if needed, otherwise toPlainText()
        content_analysis = content_widget.toMarkdown().strip() if content_widget else "N/A"
        job_fit_analysis = job_fit_widget.toMarkdown().strip() if job_fit_widget else "N/A"

        # Remove the prepended title we added in display_results for the report
        # Do this *before* checking if content is "N/A"
        content_prefix = "**Content Analysis (Summary):**\n\n"
        if content_analysis.startswith(content_prefix):
            content_analysis = content_analysis[len(content_prefix):]

        # Check if there's anything substantial *dynamic* to save
        # We always include the fixed speech score/desc now
        if content_analysis == "N/A" and job_fit_analysis == "N/A":
            # Check if the placeholders are still there
             placeholder_summary_check = "*Content analysis will appear here based on the interview summary.*"
             placeholder_assessment_check = "*Job fit assessment will appear here.*"
             is_content_placeholder = content_widget and content_widget.toPlainText().strip() == placeholder_summary_check
             is_jobfit_placeholder = job_fit_widget and job_fit_widget.toPlainText().strip() == placeholder_assessment_check
             if is_content_placeholder and is_jobfit_placeholder:
                 self.show_message_box("warning", "No Data", "Results have not been generated yet, nothing to save.")
                 return


        # --- Format the report content ---
        # Use the imported fixed values and fetched dynamic content
        report_content = (
            f"Interview Report\n{'='*16}\n\n"
            f"Speech Delivery Score: {FIXED_SPEECH_SCORE}%\n"
            f"{'-'*23}\n"
            # Basic markdown removal for plain text report
            f"{FIXED_SPEECH_DESCRIPTION.replace('**', '').replace('*', '')}\n\n"
            f"Response Content Score: {FIXED_CONTENT_SCORE}%\n"
            f"{'-'*24}\n"
            # Clean dynamic content as well
            f"{content_analysis.replace('**', '').replace('*', '')}\n\n"
            f"Job Fit Analysis\n"
            f"{'-'*16}\n"
            f"{job_fit_analysis.replace('**', '').replace('*', '')}\n"
        )

        # Suggest a default filename based on the resume filename
        default_filename = "interview_report.txt"
        if self.pdf_filepath:
            base = os.path.splitext(os.path.basename(self.pdf_filepath))[0]
            default_filename = f"{base}_interview_report.txt"

        # Default save directory (user's recording folder)
        save_dir = RECORDINGS_DIR # Absolute path from core.recording
        try:
            os.makedirs(save_dir, exist_ok=True) # Ensure directory exists
        except OSError as e:
             print(f"Warning: Could not create directory for saving report: {save_dir}. Error: {e}")
             # Fallback to home directory if creation fails
             save_dir = os.path.expanduser("~")

        default_path = os.path.join(save_dir, default_filename) # Absolute default path

        # Open 'Save As' dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Interview Report",
            default_path,
            "Text Files (*.txt);;All Files (*)"
        )

        if filepath: # User selected a file path
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content) # Write the cleaned plain text
                self.update_status(f"Report saved to {os.path.basename(filepath)}.")
                self.show_message_box("info", "Report Saved", f"Interview report saved successfully to:\n{filepath}")
            except Exception as e:
                print(f"Error saving report to {filepath}: {e}")
                self.show_message_box("error", "Save Error", f"Could not save the report:\n{e}")
        else:
            # User cancelled the dialog
            self.update_status("Report save cancelled.")

    def _open_recordings_folder(self):
        """Slot triggered by the 'Open Recordings Folder' button."""
        folder_path = RECORDINGS_DIR # Absolute path from core.recording
        print(f"Attempting to open user recordings folder: {folder_path}")

        # Ensure the directory exists before trying to open it
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"Created recordings directory before opening: {folder_path}")
            except OSError as e:
                 print(f"Error creating recordings directory: {e}")
                 self.show_message_box("error", "Folder Error", f"Could not create the recordings folder:\n{folder_path}\nError: {e}")
                 self.update_status("Failed to create recordings folder.")
                 return

        # Attempt to open using Qt's cross-platform method first
        url = QUrl.fromLocalFile(folder_path) # Create a QUrl from the local path
        if not QDesktopServices.openUrl(url):
            # QDesktopServices failed, try platform-specific fallbacks
            print(f"QDesktopServices failed to open {folder_path}. Trying platform-specific fallback...")
            self.update_status("Opening folder (using fallback)...")
            try:
                system = platform.system()
                if system == "Windows":
                    # Use 'explorer' on Windows
                    subprocess.Popen(['explorer', os.path.normpath(folder_path)])
                elif system == "Darwin": # macOS
                    # Use 'open' on macOS
                    subprocess.Popen(["open", folder_path])
                else: # Linux/Other Unix-like
                    # Use 'xdg-open' as the standard freedesktop utility
                    subprocess.Popen(["xdg-open", folder_path])
                self.update_status("Opened recordings folder (using fallback).")
            except FileNotFoundError:
                 # The required command (explorer, open, xdg-open) wasn't found
                 cmd = "explorer" if system == "Windows" else ("open" if system == "Darwin" else "xdg-open")
                 print(f"Error: Command '{cmd}' not found in system PATH.")
                 self.show_message_box("error", "Open Error", f"Could not find the command ('{cmd}') needed to open the folder.\nPlease open the folder manually:\n{folder_path}")
                 self.update_status("Failed to open folder (command missing).")
            except Exception as e:
                # Other errors during subprocess execution
                print(f"Fallback open error for {folder_path}: {e}")
                self.show_message_box("error", "Open Error", f"Could not open the recordings folder:\n{folder_path}\nError: {e}")
                self.update_status("Failed to open recordings folder.")
        else:
            # QDesktopServices successfully opened the folder
            self.update_status("Opened recordings folder.")

    # --- Window Close Event ---

    def closeEvent(self, event):
        """Handles the window close event."""
        print("Close event triggered. Cleaning up...")
        # Stop the STT check timer
        if hasattr(self, 'stt_timer'):
            self.stt_timer.stop()
            print("STT queue check timer stopped.")

        # Stop any ongoing TTS playback
        print("Attempting to stop any active TTS playback...")
        try:
            tts.stop_playback() # Use the facade's stop method
            print("TTS stop signal sent (if applicable).")
        except Exception as tts_stop_err:
            print(f"Error trying to stop TTS playback: {tts_stop_err}")

        # Attempt to gracefully stop the recording thread if it's active
        # Note: The recording thread should ideally check a flag or respond to a signal.
        # This is a placeholder for potentially more robust cleanup.
        if self.is_recording:
            print("Signalling recording thread to stop (if implemented)...")
            # Example if using an Event flag:
            # if hasattr(recording, 'stop_recording_flag'):
            #     recording.stop_recording_flag.set()

        print("Main window cleanup attempts complete.")
        event.accept() # Allow the window to close