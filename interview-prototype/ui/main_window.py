# ui/main_window.py
"""
Main application window for the Interview Bot Pro.
Manages pages, state, and core interactions. Adheres to style guidelines.
Ensures webcam feed persists on InterviewPage while STT mode is active.
Clears recordings folder before each interview and generates a new transcript after.
"""
import os
import sys
import queue
import platform
import subprocess
import html
import json
import shutil # Import shutil for folder clearing
from pathlib import Path
import numpy as np
import cv2
import threading

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QApplication,
    QStackedWidget, QLabel, QSizePolicy, QFrame, QListWidgetItem,
    QInputDialog, QLineEdit
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap,
    QDesktopServices, QImage
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, QUrl, QStandardPaths
)

# --- Project Imports ---
try:
    import core.logic as logic
    from core import tts, recording
    # Import the constant directly for clarity
    from core.recording import RECORDINGS_DIR
except ImportError:
    # Add parent directory to sys.path if running script directly
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import core.logic as logic
    from core import tts, recording
    # Import the constant directly for clarity
    from core.recording import RECORDINGS_DIR

# --- Import Page Classes & Constants ---
from .setup_page import SetupPage
from .interview_page import InterviewPage
from .results_page import ResultsContainerPage # Use the container
from .loading_page import LoadingPage

# --- Constants ---
CONFIG_FILE_NAME = "settings.json"
RESUMES_SUBDIR = "resumes"
MAX_RECENT_RESUMES = 10
MAX_RECENT_JDS = 10
WEBCAM_UPDATE_INTERVAL = 40


class InterviewApp(QWidget):
    """Main application window for the Interview Bot Pro."""
    SETUP_PAGE_INDEX = 0
    INTERVIEW_PAGE_INDEX = 1
    LOADING_PAGE_INDEX = 2
    RESULTS_CONTAINER_INDEX = 3 # Use the container index

    # Constants needed by _save_report
    FIXED_SPEECH_SCORE = 75 # Example value
    FIXED_SPEECH_DESCRIPTION = """
**Prosody Analysis:**
*(This is a placeholder analysis for speech delivery.)*

*(Actual speech analysis is not implemented in this version.)*
"""

    def __init__(self, icon_path, *args, **kwargs):
        """Initializes the main application window."""
        super().__init__(*args, **kwargs)
        self.icon_path = icon_path
        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 1050, 1200) # Adjusted default size

        self._setup_appearance()
        self._load_assets()
        self._init_state()
        self._ensure_app_dirs_exist()
        self.config = self._load_config()
        self._setup_ui()
        self._update_ui_from_state()
        self._update_progress_indicator()

        # Timers and threads
        self.stt_timer = QTimer(self)
        self.stt_timer.timeout.connect(self.check_stt_queue)
        self.stt_timer.start(100) # Check STT queue every 100ms

        self.webcam_frame_queue = queue.Queue(maxsize=5)
        self.webcam_timer = QTimer(self)
        self.webcam_timer.timeout.connect(self._update_webcam_view)
        self.webcam_stream_thread = None
        self.webcam_stream_stop_event = None

    def _setup_appearance(self):
        """Sets the application's color palette and style."""
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        disabled_text_color = QColor(128, 128, 128)
        palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text_color)
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color
        )

        self.setPalette(palette)
        QApplication.setStyle("Fusion")

    def _load_assets(self):
        """Loads fonts and defines standard sizes used across the UI."""
        self.icon_size = QSize(24, 24)
        self.font_default = QFont("Arial", 10)
        self.font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 9)
        self.font_large_bold = QFont("Arial", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9)
        base_size = self.font_default.pointSize()
        # Larger fonts for XXL style (adjust multiplier as needed)
        self.font_default_xxl = QFont(self.font_default.family(), base_size + 6)
        self.font_bold_xxl = QFont(
            self.font_bold.family(), base_size + 6, QFont.Weight.Bold
        )
        self.font_small_xxl = QFont(self.font_small.family(), base_size + 5)
        self.font_group_title_xxl = QFont(
            self.font_large_bold.family(), base_size + 8, QFont.Weight.Bold
        )
        # Font for the progress indicator at the top
        self.font_progress_indicator = self.font_default_xxl

    def _init_state(self):
        """Initializes the application's state variables."""
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        self.selected_jd_name = None
        self.num_topics = logic.DEFAULT_NUM_TOPICS
        self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
        self.use_speech_input = False
        self.use_openai_tts = False
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False # Tracks if STT is actively listening/processing
        self.last_question_asked = ""
        self.last_assessment_data = None
        self.last_content_score_data = None
        self.app_data_dir = self._get_app_data_dir()
        self.config_path = self.app_data_dir / CONFIG_FILE_NAME
        self.resumes_dir = self.app_data_dir / RESUMES_SUBDIR
        self.config = {"recent_resumes": [], "recent_job_descriptions": []}
        # UI Page Instances
        self.setup_page_instance = None
        self.interview_page_instance = None
        self.loading_page_instance = None
        self.results_container_instance = None # Use the container instance
        # UI Element References
        self.progress_indicator_label = None
        self.status_bar_label = None
        self.stacked_widget = None

    def _get_app_data_dir(self) -> Path:
        """Determines the application data directory path."""
        app_data_dir_str = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not app_data_dir_str:
            # Fallback if standard location fails (less common)
            app_data_dir_str = os.path.join(
                os.path.expanduser("~"), ".InterviewBotPro"
            )
            print(
                f"Warning: Could not get standard AppDataLocation. "
                f"Using fallback: {app_data_dir_str}"
            )
        # Ensure the app name part is included (AppDataLocation might just give the parent dir)
        # This logic might need adjustment based on OS and Qt version specifics
        base_path = Path(app_data_dir_str)
        if base_path.name.lower() != "interviewbotpro":
             return base_path / "InterviewBotPro"
        else:
             return base_path


    def _ensure_app_dirs_exist(self):
        """Creates application data and resume directories if they don't exist."""
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
            self.resumes_dir.mkdir(parents=True, exist_ok=True)
            # Also ensure recordings dir exists at startup
            Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)
            print(f"Ensured app data directories exist: {self.app_data_dir}")
            print(f"Ensured recordings directory exists: {RECORDINGS_DIR}")
        except OSError as e:
            print(f"CRITICAL ERROR: Could not create app directories: {e}")
            self.show_message_box(
                "error",
                "Directory Error",
                f"Could not create necessary application directories:\n"
                f"{self.app_data_dir}\n{self.resumes_dir}\n{RECORDINGS_DIR}\n\n{e}"
            )

    def _load_config(self) -> dict:
        """Loads application settings from the JSON config file."""
        default_config = {
            "recent_resumes": [],
            "recent_job_descriptions": []
        }
        if not self.config_path.exists():
            print(f"Config file not found at {self.config_path}. Using default.")
            return default_config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            needs_save = False # Flag to save if we prune invalid entries

            # --- Validate Recent Resumes ---
            if not isinstance(config.get("recent_resumes"), list):
                print("Warning: 'recent_resumes' in config is not a list. Resetting.")
                config["recent_resumes"] = []
                needs_save = True
            else:
                valid_resumes = []
                for item in config.get("recent_resumes", []):
                    if isinstance(item, dict) and 'name' in item and 'path' in item:
                        p = Path(item['path'])
                        # Check if it's an absolute path, exists, and is within the managed dir
                        is_valid = False
                        if p.is_absolute() and p.exists():
                             try:
                                 if p.is_relative_to(self.resumes_dir):
                                     is_valid = True
                             except ValueError: # Paths on different drives (Windows)
                                 pass # Not relative, so invalid
                        if is_valid:
                            valid_resumes.append(item)
                        else:
                            needs_save = True
                            print(f"Pruning invalid/external/non-existent resume: {item}")
                    else:
                        needs_save = True
                        print(f"Pruning malformed resume entry: {item}")
                if len(valid_resumes) != len(config.get("recent_resumes", [])):
                     config["recent_resumes"] = valid_resumes

            # --- Validate Recent Job Descriptions ---
            if not isinstance(config.get("recent_job_descriptions"), list):
                print("Warning: 'recent_job_descriptions' in config is not a list. Resetting.")
                config["recent_job_descriptions"] = []
                needs_save = True
            else:
                valid_jds = []
                for item in config.get("recent_job_descriptions", []):
                    if (isinstance(item, dict) and
                            item.get("name") and isinstance(item["name"], str) and
                            item.get("text") is not None and isinstance(item["text"], str)):
                        valid_jds.append(item)
                    else:
                        needs_save = True
                        print(f"Pruning malformed JD entry: {item}")
                if len(valid_jds) != len(config.get("recent_job_descriptions", [])):
                    config["recent_job_descriptions"] = valid_jds

            # Save the cleaned config if changes were made
            if needs_save:
                self._save_config(config)

            return config

        except json.JSONDecodeError as e:
            print(f"Error decoding config file {self.config_path}: {e}. Using default.")
            return default_config
        except IOError as e:
            print(f"Error reading config file {self.config_path}: {e}. Using default.")
            return default_config
        except Exception as e:
             print(f"Unexpected error loading config: {e}. Using default.")
             return default_config

    def _save_config(self, config_data=None):
        """Saves the current application settings to the JSON config file."""
        data_to_save = config_data if config_data is not None else self.config
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Config saved to {self.config_path}")
        except IOError as e:
            print(f"Error saving config file {self.config_path}: {e}")
        except TypeError as e:
            print(f"Error serializing config data to JSON: {e}")

    def _add_recent_resume(self, name: str, path_in_resumes_dir: str):
        """Adds or updates a resume entry in the recent list (must be managed path)."""
        if not name or not path_in_resumes_dir:
            print("Warning: Attempted to add recent resume with missing name or path.")
            return

        p = Path(path_in_resumes_dir)
        # CRITICAL CHECK: Ensure the path is absolute and within the managed resumes directory
        try:
            if not p.is_absolute() or not p.is_relative_to(self.resumes_dir):
                print(f"Error: Attempted to add non-managed path to recent resumes: {path_in_resumes_dir}")
                # Do NOT add invalid paths
                return
        except ValueError: # Paths on different drives
             print(f"Error: Attempted to add path on different drive to recent resumes: {path_in_resumes_dir}")
             return

        new_entry = {"name": name, "path": str(p)}
        recent_list = self.config.get("recent_resumes", [])

        # Remove any existing entries with the same path (should only be one if managed)
        existing_indices = [
            i for i, item in enumerate(recent_list) if item.get("path") == str(p)
        ]
        for i in reversed(existing_indices):
            del recent_list[i]

        # Add the new entry to the beginning and trim the list
        recent_list.insert(0, new_entry)
        self.config["recent_resumes"] = recent_list[:MAX_RECENT_RESUMES]
        self._save_config()
        self._update_ui_from_state() # Update UI to show new list order

    def _add_recent_jd(self, name: str, text: str):
        """Adds or updates a job description entry in the recent list."""
        if not name or text is None: # Ensure text is not None (empty string is allowed)
            print("Warning: Attempted to add recent JD with missing name or text.")
            return

        new_entry = {"name": name, "text": text}
        jd_list = self.config.get("recent_job_descriptions", [])

        # Remove any existing entries with the same name
        existing_indices = [
            i for i, item in enumerate(jd_list) if item.get("name") == name
        ]
        for i in reversed(existing_indices):
            del jd_list[i]

        # Add the new entry to the beginning and trim the list
        jd_list.insert(0, new_entry)
        self.config["recent_job_descriptions"] = jd_list[:MAX_RECENT_JDS]
        self._save_config()
        # UI update handled when JD is selected or Setup page refreshed

    def _setup_ui(self):
        """Builds the main UI structure: progress, pages, status bar."""
        main_window_layout = QVBoxLayout(self)
        main_window_layout.setContentsMargins(0, 0, 0, 0)
        main_window_layout.setSpacing(0)

        # Progress Indicator Label (at the top)
        self.progress_indicator_label = QLabel("...")
        self.progress_indicator_label.setObjectName("progressIndicator")
        self.progress_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_indicator_label.setTextFormat(Qt.TextFormat.RichText)
        if hasattr(self, 'font_progress_indicator'):
            self.progress_indicator_label.setFont(self.font_progress_indicator)
        self.progress_indicator_label.setMinimumHeight(35) # Make sure it's visible
        # Optional: Add background color for better visual separation
        self.progress_indicator_label.setStyleSheet("background-color: #353535; padding: 5px;")
        main_window_layout.addWidget(self.progress_indicator_label)

        # Separator Line (Optional, if progress indicator style doesn't provide enough separation)
        # line = QFrame()
        # line.setFrameShape(QFrame.Shape.HLine)
        # line.setFrameShadow(QFrame.Shadow.Sunken)
        # main_window_layout.addWidget(line)

        # Stacked Widget for Pages
        self.stacked_widget = QStackedWidget()
        main_window_layout.addWidget(self.stacked_widget, stretch=1) # Allow stack to expand

        # Instantiate Pages
        self.setup_page_instance = SetupPage(self)
        self.interview_page_instance = InterviewPage(self)
        self.loading_page_instance = LoadingPage(self)
        self.results_container_instance = ResultsContainerPage(self) # Instantiate the container

        # Add Pages to Stack
        self.stacked_widget.addWidget(self.setup_page_instance)           # Index 0
        self.stacked_widget.addWidget(self.interview_page_instance)       # Index 1
        self.stacked_widget.addWidget(self.loading_page_instance)         # Index 2
        self.stacked_widget.addWidget(self.results_container_instance)    # Index 3

        # Status Bar Label (at the bottom)
        self.status_bar_label = QLabel("Ready.")
        self.status_bar_label.setObjectName("statusBar")
        if hasattr(self, 'font_small_xxl'):
            self.status_bar_label.setFont(self.font_small_xxl)
        # Optional: Add padding and background to status bar
        self.status_bar_label.setStyleSheet("background-color: #2D2D2D; padding: 5px; border-top: 1px solid #555;")
        self.status_bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center status text
        main_window_layout.addWidget(self.status_bar_label)

        self.setLayout(main_window_layout)

    def _update_ui_from_state(self):
        """Updates the UI elements to reflect the current application state."""
        print("Updating UI from state...")
        pdf_loaded = bool(self.pdf_filepath and Path(self.pdf_filepath).exists())
        jd_loaded = bool(self.job_description_text)

        # Update Setup Page specifically
        if self.setup_page_instance:
            recent_resumes_data = self.config.get("recent_resumes", [])
            recent_jd_data = self.config.get("recent_job_descriptions", [])
            self.setup_page_instance.update_widgets_from_state(
                recent_resumes_data=recent_resumes_data,
                current_selection_path=self.pdf_filepath,
                recent_jd_data=recent_jd_data,
                current_jd_name=self.selected_jd_name
            )
            # Enable/disable controls based on loaded state
            self.setup_page_instance.set_controls_enabled_state(pdf_loaded, jd_loaded)

        # Clear other pages if they are not the current page
        current_page_index = self.stacked_widget.currentIndex() if self.stacked_widget else -1

        if self.interview_page_instance and current_page_index != self.INTERVIEW_PAGE_INDEX:
            self.interview_page_instance.clear_fields() # Clear if not on interview page

        if self.results_container_instance and current_page_index != self.RESULTS_CONTAINER_INDEX:
            self.results_container_instance.clear_fields() # Call clear on container

        # Update general UI elements
        self.update_status("Ready.") # Reset status bar
        self.update_submit_button_text() # Reflects STT state on interview page
        self._update_progress_indicator() # Update step indicator

    def _update_progress_indicator(self):
        """Updates the text/styling of the progress indicator label."""
        if not self.progress_indicator_label or not self.stacked_widget:
            return

        current_index = self.stacked_widget.currentIndex()
        current_step_index = -1 # Default to none active

        # Map main stack index to logical step index (0, 1, 2)
        if current_index == self.SETUP_PAGE_INDEX:
            current_step_index = 0
        elif current_index == self.INTERVIEW_PAGE_INDEX:
            current_step_index = 1
        elif current_index == self.LOADING_PAGE_INDEX:
            # Show Interview as active step during loading
            current_step_index = 1
        elif current_index == self.RESULTS_CONTAINER_INDEX:
            # Show Results as active step when on results container
            current_step_index = 2

        # Define the steps text
        steps = ["Step 1: Setup", "Step 2: Interview", "Step 3: Results"]
        progress_parts = []
        active_color = QColor("#FFA500").name() # Orange for active step
        # Get inactive color from current palette
        inactive_color = self.palette().color(QPalette.ColorRole.WindowText).name()

        for i, step in enumerate(steps):
            # Highlight if the logical step index matches
            is_active = (i == current_step_index)
            if is_active:
                # Use bold and active color
                progress_parts.append(
                    f'<font color="{active_color}"><b>  {step}  </b></font>'
                )
            else:
                # Use inactive color (no bold)
                progress_parts.append(
                    f'<font color="{inactive_color}">  {step}  </font>'
                )

        # Use a visually distinct separator
        separator = f'<font color="{inactive_color}"> → </font>'
        self.progress_indicator_label.setText(separator.join(progress_parts))

    def _go_to_setup_page(self):
        """Navigates to the Setup page and resets the interview state."""
        print("Navigating to Setup Page and Resetting...")
        self.stop_webcam_feed() # Ensure webcam is off
        self.reset_interview_state(clear_config=True) # Full reset including selections
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self._update_progress_indicator() # Update progress
        self.update_status("Ready for new interview setup.")

    def _go_to_interview_page(self):
        """Navigates to the Interview page."""
        print("Navigating to Interview Page...")
        if self.interview_page_instance:
            self.interview_page_instance.clear_fields()
            self.interview_page_instance.set_input_mode(self.use_speech_input)
            if self.use_speech_input:
                self.start_webcam_feed() # Start webcam only if STT is on
            else:
                self.stop_webcam_feed() # Ensure webcam is off if text mode

        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview started. Waiting for question...")

    def _go_to_loading_page(self):
        """Navigates to the Loading page."""
        print("Navigating to Loading Page...")
        self.stop_webcam_feed() # Ensure webcam stops before loading/results
        self.update_status("Generating results...")
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.LOADING_PAGE_INDEX)
        self._update_progress_indicator() # Update progress indicator
        QApplication.processEvents() # Allow UI to update before heavy work

    def _go_to_results_page(self, summary: str | None,
                            assessment_data: dict | None,
                            content_score_data: dict | None):
        """Navigates to the Results container page and displays results."""
        print("Navigating to Results Container Page...")
        self.stop_webcam_feed() # Ensure webcam is stopped
        # Store the latest results data in the main window state
        self.last_assessment_data = assessment_data
        self.last_content_score_data = content_score_data

        # Call display_results on the container instance
        if self.results_container_instance:
            self.results_container_instance.display_results(
                summary, assessment_data, content_score_data
            )
        else:
             print("Error: Results container instance not found.")
             self.show_message_box("error", "UI Error", "Results page could not be loaded.")

        # Navigate to the container index
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.RESULTS_CONTAINER_INDEX)
        self._update_progress_indicator() # Update progress indicator
        self.update_status("Interview complete. Results displayed.")

    def show_message_box(self, level: str, title: str, message: str):
        """Displays a modal message box."""
        box = QMessageBox(self)
        icon_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical
        }
        box.setIcon(icon_map.get(level.lower(), QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _adjust_value(self, value_type: str, amount: int):
        """Adjusts topic or follow-up count and updates the UI."""
        current_val = 0
        min_val = 0
        max_val = 0
        target_label_widget = None
        target_var_name = ""
        font_to_apply = None

        if not self.setup_page_instance:
             print(f"Warning: Cannot adjust value. Setup page not available.")
             return

        # Access widgets safely using getattr
        if value_type == 'topics':
            target_label_widget = getattr(self.setup_page_instance, 'num_topics_label', None)
            current_val = self.num_topics
            min_val = logic.MIN_TOPICS
            max_val = logic.MAX_TOPICS
            target_var_name = 'num_topics'
            font_to_apply = getattr(self, 'font_default_xxl', None)
        elif value_type == 'followups':
            target_label_widget = getattr(self.setup_page_instance, 'max_follow_ups_label', None)
            current_val = self.max_follow_ups
            min_val = logic.MIN_FOLLOW_UPS
            max_val = logic.MAX_FOLLOW_UPS_LIMIT
            target_var_name = 'max_follow_ups'
            font_to_apply = getattr(self, 'font_default_xxl', None)
        else:
            print(f"Warning: Cannot adjust value. Type '{value_type}' unknown.")
            return

        new_value = current_val + amount
        # Clamp the value within the allowed range
        clamped_value = max(min_val, min(new_value, max_val))

        if clamped_value != current_val:
            setattr(self, target_var_name, clamped_value)
            if target_label_widget:
                target_label_widget.setText(str(clamped_value))
                if font_to_apply:
                    target_label_widget.setFont(font_to_apply)
            print(f"{target_var_name.replace('_',' ').title()} set to: {clamped_value}")
        else:
             # Optional: Feedback if limit is reached
             limit_type = "minimum" if amount < 0 else "maximum"
             print(f"Value for {value_type} already at {limit_type} limit ({clamped_value}).")

    def update_status(self, message: str, busy: bool = False):
        """Updates the status bar text and optionally shows busy cursor."""
        if self.status_bar_label:
            self.status_bar_label.setText(message)

        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            # Only restore if an override cursor is active
            if QApplication.overrideCursor() is not None:
                 QApplication.restoreOverrideCursor()

        QApplication.processEvents() # Allow UI to update

    def display_question(self, question_text: str):
        """Updates UI with question text/status and speaks it."""
        self.last_question_asked = question_text # Store the question asked

        # --- Format Question Number String ---
        number_str = "Question" # Default
        total_questions = len(self.initial_questions)
        current_q_num = self.current_initial_q_index + 1

        if total_questions > 0 and current_q_num > 0:
            # Initial question or follow-up to an initial question
            number_str = f"Question {current_q_num}/{total_questions}"
            if self.follow_up_count > 0:
                number_str += f", Follow-up {self.follow_up_count}"
        elif self.follow_up_count > 0:
            # Follow-up but no initial questions (shouldn't happen in normal flow)
            number_str = f"Follow-up {self.follow_up_count}"
        else:
            # Very start or error state
            number_str = "Starting Interview..."

        # --- Update Interview Page UI ---
        if self.interview_page_instance:
            self.interview_page_instance.display_question_ui(
                number_text=number_str,
                question_text=question_text
            )
            # Ensure the Interview Page is visible
            if self.stacked_widget and self.stacked_widget.currentIndex() != self.INTERVIEW_PAGE_INDEX:
                 print("Warning: Trying to display question while not on Interview page.")
                 # Optionally force navigation: self._go_to_interview_page()
        else:
            self.update_status(f"Asking: {question_text[:30]}...") # Fallback

        # --- Speak the Question ---
        try:
            tts.speak_text(question_text)
        except Exception as e:
            print(f"TTS Error during speak_text call: {e}")
            self.show_message_box("warning", "TTS Error", f"Could not speak the question: {e}")

        # --- Enable Controls and Set Focus ---
        self.enable_interview_controls()
        answer_input = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input and not self.use_speech_input: # Focus only if in text mode
            answer_input.setFocus()

    def add_to_history(self, text: str, tag: str = None):
        """Logs interview events (question/answer/topic markers) to the console."""
        log_prefix = "HISTORY [I]: " # Default/Info
        if tag == "question_style":
            log_prefix = "HISTORY [Q]: "
        elif tag == "answer_style":
            log_prefix = "HISTORY [A]: "
        elif tag == "topic_marker":
            log_prefix = "HISTORY [T]: "

        cleaned_text = text.strip()
        print(f"{log_prefix}{cleaned_text}")

    def set_setup_controls_state(self, pdf_loaded: bool, jd_loaded: bool = False):
        """Enables/disables controls on the Setup page based on load state."""
        if self.setup_page_instance:
            self.setup_page_instance.set_controls_enabled_state(pdf_loaded, jd_loaded)

    def enable_interview_controls(self):
        """Enables controls on the Interview page for user input."""
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(True)
            self.is_recording = False # Ensure recording state is idle
            # Set button to appropriate state (Record/Submit) based on STT mode
            self.set_recording_button_state('idle')

    def disable_interview_controls(self, is_recording_stt: bool = False):
        """Disables controls on the Interview page, e.g., during processing."""
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(False, is_recording_stt)
            self.is_recording = is_recording_stt # Update recording state
            # Button state will be updated via set_recording_button_state separately

    def reset_interview_state(self, clear_config: bool = True):
        """Resets interview variables and optionally clears config selections."""
        print(f"Resetting interview state (clear_config={clear_config})...")
        if clear_config:
            # Reset user selections and settings
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.selected_jd_name = None
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False # Reset STT state
            self.use_openai_tts = False  # Reset OpenAI TTS state

            # Reset TTS provider to default or first available
            current_provider = tts.get_current_provider()
            default_provider = tts.DEFAULT_PROVIDER
            print(f"Resetting TTS. Current: {current_provider}, Default: {default_provider}")
            if current_provider != default_provider:
                if not tts.set_provider(default_provider):
                    potential = tts.get_potentially_available_providers()
                    fallback = potential[0] if potential else None
                    if fallback and tts.set_provider(fallback):
                        print(f"Reset TTS: Set to first available '{fallback}'.")
                    else:
                        print("Reset TTS: ERROR - Could not set default or fallback provider.")
                else:
                    print(f"Reset TTS: Set to default '{default_provider}'.")
            else:
                 print("Reset TTS: Already using default provider.")

        # Reset interview progress variables
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""
        self.last_assessment_data = None # Clear results data
        self.last_content_score_data = None

        # Update UI to reflect reset state
        self._update_ui_from_state()
        self.disable_interview_controls() # Ensure controls are disabled initially
        # Restore cursor if it was overridden
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text: str) -> str:
        """Removes common leading numbering/markers from question text."""
        cleaned = raw_q_text.strip()
        # Try matching "1.", "1)", "1 " prefixes (up to 2 digits)
        if cleaned and cleaned[0].isdigit():
            # More robust: use regex to remove leading digits and punctuation/space
            import re
            match = re.match(r"^\d{1,2}[\.\)\s]+(.*)", cleaned)
            if match:
                return match.group(1).strip()
        # If no pattern matches, return the original cleaned string
        return cleaned

    # --- NEW METHOD: Clear Recordings Folder ---
    def _clear_recordings_folder(self):
        """Removes all files and subdirectories within the recordings folder."""
        recordings_path = Path(RECORDINGS_DIR)
        print(f"Attempting to clear recordings folder: {recordings_path}")
        if recordings_path.exists() and recordings_path.is_dir():
            try:
                for item_path in recordings_path.iterdir():
                    try:
                        if item_path.is_file():
                            os.remove(item_path)
                            print(f"  Deleted file: {item_path.name}")
                        elif item_path.is_dir():
                            shutil.rmtree(item_path) # Use shutil to remove directories
                            print(f"  Deleted directory: {item_path.name}")
                    except OSError as e:
                        print(f"  Error deleting {item_path}: {e}")
                        # Optionally show a warning if deletion fails during cleanup
                        # self.show_message_box("warning", "Cleanup Warning", f"Could not delete item during cleanup:\n{item_path.name}\n\n{e}")
                print("Recordings folder cleared successfully.")
            except Exception as e:
                print(f"Error iterating or clearing recordings folder {recordings_path}: {e}")
                self.show_message_box("error", "Cleanup Error", f"Could not clear recordings folder:\n{recordings_path}\n\n{e}")
        else:
            print(f"Recordings folder does not exist or is not a directory: {recordings_path}")
            # Ensure it exists for the upcoming interview
            try:
                recordings_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                 print(f"CRITICAL ERROR: Could not create recordings directory: {e}")
                 self.show_message_box(
                    "error",
                    "Directory Error",
                    f"Could not create necessary recordings directory:\n{recordings_path}"
                 )

    # --- REVIEWED METHOD: save_transcript_to_file ---
    # Ensures it overwrites and saves to the correct directory. Handles both input modes.
    def save_transcript_to_file(self):
        """Saves the full interview transcript to a text file."""
        if not self.current_full_interview_history:
            print("No interview history to save.")
            # Optionally inform user: self.show_message_box("info", "No History", "Interview transcript is empty.")
            return

        # Create a map from cleaned initial question text to its index (for topic numbering)
        topic_index_map = {}
        if self.initial_questions:
            topic_index_map = {
                self._clean_question_text(q): i for i, q in enumerate(self.initial_questions)
            }
        else:
            print("Warning: Initial questions missing, cannot map topics accurately for transcript.")

        transcript_lines = []
        last_topic_num = -1 # Track the last main topic number written

        try:
            for qa_pair in self.current_full_interview_history:
                q_raw = qa_pair.get('q', 'N/A')
                a = qa_pair.get('a', 'N/A')
                q_clean = self._clean_question_text(q_raw) # Clean the question for lookup

                # Check if this question matches one of the initial questions
                topic_index = topic_index_map.get(q_clean, -1)

                if topic_index != -1:
                    # This is an initial question
                    current_topic_num = topic_index + 1
                    # Add a separator if moving to a new topic (and not the very first one)
                    if current_topic_num != last_topic_num and last_topic_num != -1:
                        transcript_lines.append("\n-------------------------")
                    transcript_lines.append(f"\nQuestion {current_topic_num}: {q_raw}\nAnswer: {a}")
                    last_topic_num = current_topic_num
                else:
                    # This is likely a follow-up question
                    context = f"Topic {last_topic_num}" if last_topic_num > 0 else "General"
                    transcript_lines.append(f"\nFollow Up (re {context}): {q_raw}\nAnswer: {a}")

            # Prepare file path in recordings directory
            recordings_path = Path(RECORDINGS_DIR)
            # >>> Ensure directory exists before writing <<<
            os.makedirs(recordings_path, exist_ok=True)
            filepath = recordings_path / "transcript.txt" # Standard filename
            print(f"Saving transcript to {filepath}...")

            # Join lines, ensuring only one newline between entries
            final_transcript = "\n".join(line.strip() for line in transcript_lines if line.strip())

            # >>> Write with 'w' mode to overwrite any previous transcript <<<
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(final_transcript.strip() + "\n") # Add trailing newline

            print("Transcript saved.")
            self.update_status(f"Transcript saved to {filepath.name}")

        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript:\n{e}")

    def set_recording_button_state(self, state: str):
        """Updates the submit/record button's text, icon, and enabled state."""
        if not self.interview_page_instance: return
        target_button = getattr(self.interview_page_instance, 'submit_button', None)
        if not target_button: return

        # Get icons (handle potential load failures gracefully)
        submit_icon = getattr(self.interview_page_instance, 'submit_icon', QIcon())
        record_icon = getattr(self.interview_page_instance, 'record_icon', QIcon())
        listening_icon = getattr(self.interview_page_instance, 'listening_icon', QIcon())
        processing_icon = getattr(self.interview_page_instance, 'processing_icon', QIcon())

        target_icon = QIcon() # Default empty icon
        target_text = "Submit Answer" # Default text
        enabled = True # Default enabled

        if state == 'listening':
            target_text = "Listening..."
            target_icon = listening_icon
            enabled = False # Button should be disabled while listening/recording
        elif state == 'processing':
            target_text = "Processing..."
            target_icon = processing_icon
            enabled = False # Button disabled while processing
        elif state == 'idle':
            enabled = True # Enable button in idle state
            if self.use_speech_input:
                target_text = "Record Answer"
                target_icon = record_icon
            else:
                target_text = "Submit Answer"
                target_icon = submit_icon
        else: # Handle unknown state gracefully
            print(f"Warning: Unknown recording button state '{state}'. Defaulting to idle.")
            enabled = True
            if self.use_speech_input:
                target_text = "Record Answer"
                target_icon = record_icon
            else:
                target_text = "Submit Answer"
                target_icon = submit_icon

        # Apply changes to the button
        target_button.setText(target_text)
        target_button.setEnabled(enabled)
        if target_icon and not target_icon.isNull():
            target_button.setIcon(target_icon)
            target_button.setIconSize(getattr(self, 'icon_size', QSize(24, 24)))
        else:
            target_button.setIcon(QIcon()) # Set empty icon if load failed or not applicable


    def _process_selected_resume(self, resume_data: dict):
        """Handles copying, naming, extracting text, and updating state for a resume."""
        original_filepath = resume_data.get("path")
        preferred_name = resume_data.get("name") # Name from recent list / initial selection

        if not original_filepath or not Path(original_filepath).exists():
            self.show_message_box("error", "File Error", f"Selected file not found:\n{original_filepath}")
            self.update_status("Selected resume not found.")
            # Clean up entry from config if it's invalid
            recent_list = self.config.get("recent_resumes", [])
            updated_list = [item for item in recent_list if item.get("path") != original_filepath]
            if len(updated_list) < len(recent_list):
                self.config["recent_resumes"] = updated_list
                self._save_config()
                self._update_ui_from_state() # Refresh list display
            return

        filename = Path(original_filepath).name
        target_filepath = self.resumes_dir / filename # Path within managed directory
        managed_path_str = str(target_filepath)
        custom_name = preferred_name
        needs_copy = True
        needs_name_prompt = not custom_name # Prompt if no name provided yet

        # Check if the file is already in the managed directory and identical
        try:
            if target_filepath.exists() and os.path.samefile(original_filepath, managed_path_str):
                needs_copy = False
                print(f"File '{filename}' is already managed and identical.")
                # If it's managed but we didn't have a name, try finding it in config
                if not custom_name:
                    for item in self.config.get("recent_resumes", []):
                        if item.get("path") == managed_path_str:
                            custom_name = item.get("name")
                            print(f"Found existing name in config: '{custom_name}'")
                            break
                    needs_name_prompt = not custom_name # Prompt only if still no name
                else:
                    needs_name_prompt = False # Already had a name
            elif target_filepath.exists():
                # A file with the same name exists, but it's different.
                print(f"Warning: A different file with the name '{filename}' exists in the managed directory. It will be overwritten.")
                needs_name_prompt = not custom_name # Prompt if no name given yet
        except OSError as e: # Covers samefile errors and other FS issues
            print(f"OS Error checking file status for {filename}: {e}. Assuming copy/overwrite needed.")
            needs_copy = True
            needs_name_prompt = not custom_name

        # Prompt for a name if needed
        if needs_name_prompt:
            # Suggest a name based on filename (cleaned up)
            suggested_name = Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
            name, ok = QInputDialog.getText(
                self, "Name Resume", "Enter a display name for this resume:",
                QLineEdit.EchoMode.Normal, suggested_name
            )
            if ok and name and name.strip():
                custom_name = name.strip()
            else:
                self.update_status("Resume loading cancelled (no name provided).")
                return # User cancelled or provided no name

        # Fallback name if somehow still no name
        if not custom_name:
            custom_name = Path(filename).stem

        # Copy the file if necessary
        if needs_copy:
            try:
                print(f"Copying '{original_filepath}' to '{target_filepath}'...")
                shutil.copy2(original_filepath, target_filepath) # copy2 preserves metadata
                print("Copy successful.")
            except (IOError, OSError, shutil.Error) as e:
                print(f"Error copying resume file: {e}")
                self.show_message_box("error", "File Error", f"Could not copy resume file:\n{e}")
                self.update_status("Failed to copy resume.")
                return # Stop processing if copy fails

        # Extract text from the (now managed) PDF
        self.update_status(f"Loading resume '{custom_name}'...", True) # Show busy cursor
        QApplication.processEvents()
        extracted_content = logic.extract_text_from_pdf(managed_path_str)
        self.update_status("", False) # Restore cursor

        if extracted_content is None:
            self.show_message_box("error", "PDF Error", f"Failed to extract text from '{filename}'.")
            # Reset UI state if extraction failed
            if self.setup_page_instance:
                self.setup_page_instance.show_resume_selection_state(None) # Clear selection visually
            if self.pdf_filepath == managed_path_str: # Clear state if this was the selected file
                self.pdf_filepath = None
                self.resume_content = ""
            jd_loaded = bool(self.job_description_text)
            self.set_setup_controls_state(False, jd_loaded) # Update button enable state
            self.update_status("PDF extraction failed.")
            return # Stop processing

        # Success: Update state and UI
        self.pdf_filepath = managed_path_str
        self.resume_content = extracted_content
        self.update_status(f"Resume '{custom_name}' loaded.")
        jd_loaded = bool(self.job_description_text)
        self.set_setup_controls_state(True, jd_loaded) # Enable 'Start' if JD also loaded
        # Add/update in recent list (using the managed path) - this triggers UI update
        self._add_recent_resume(custom_name, managed_path_str)
        if self.setup_page_instance:
            # Ensure the correct item is visually selected in the list
            self.setup_page_instance.show_resume_selection_state(managed_path_str)


    def _handle_openai_tts_change(self, check_state_value: int):
        """Handles the state change of the OpenAI TTS checkbox."""
        checkbox = getattr(self.setup_page_instance, 'openai_tts_checkbox', None)
        is_checked = (check_state_value == Qt.CheckState.Checked.value)
        target_provider = "openai" if is_checked else tts.DEFAULT_PROVIDER # Target default if unchecked
        print(f"OpenAI TTS change detected. Target provider: '{target_provider}'")

        if checkbox:
            checkbox.blockSignals(True) # Prevent recursion if set_provider fails

        # Attempt to set the desired provider
        success = tts.set_provider(target_provider)

        if success:
            self.use_openai_tts = is_checked
            current_provider = tts.get_current_provider()
            self.update_status(f"TTS Provider set to: {current_provider}")
            print(f"Successfully set TTS provider to: {current_provider}")
        else:
            # Failed to set the target provider (OpenAI or Default)
            self.use_openai_tts = False # Ensure state reflects failure
            if is_checked and checkbox:
                checkbox.setChecked(False) # Uncheck the box visually if OpenAI failed
            print(f"Failed to set provider '{target_provider}'. Attempting fallback...")

            # Try setting the default provider if the target wasn't it
            fallback_success = False
            if target_provider != tts.DEFAULT_PROVIDER:
                if tts.set_provider(tts.DEFAULT_PROVIDER):
                     print(f"Fallback to default provider '{tts.DEFAULT_PROVIDER}' succeeded.")
                     fallback_success = True

            # If fallback to default failed or wasn't needed, try first available
            if not fallback_success:
                 potential = tts.get_potentially_available_providers()
                 final_fallback = potential[0] if potential else None
                 if final_fallback and tts.set_provider(final_fallback):
                     print(f"Fallback to first available '{final_fallback}' succeeded.")
                     fallback_success = True

            current_provider = tts.get_current_provider() # Get the provider actually set
            if not fallback_success:
                 # Total failure - no TTS provider available
                 print("ERROR: Failed to set any TTS provider.")
                 self.show_message_box("error", "TTS Error", "Failed to set any TTS provider.")
                 if checkbox:
                     checkbox.setEnabled(False) # Disable checkbox if totally broken
                     checkbox.setToolTip("TTS provider error. Check console.")
                 status_msg = f"Error setting TTS: No provider available"
            else:
                 status_msg = f"Failed to set '{target_provider}'. Using: {current_provider}"

            self.update_status(status_msg)

            # Show specific warning if OpenAI was requested but failed
            if is_checked and not success: # User wanted OpenAI, but it failed
                keyring_info = "(Check if API key is correctly stored in keyring)"
                # Try to add specific service name if available
                try:
                    openai_provider_info = tts.tts_providers.get('openai')
                    if openai_provider_info and hasattr(openai_provider_info, 'KEYRING_SERVICE_NAME_OPENAI'):
                         keyring_info = f"(Service: '{openai_provider_info.KEYRING_SERVICE_NAME_OPENAI}')"
                except Exception: pass # Ignore errors fetching details
                self.show_message_box(
                    "warning", "OpenAI TTS Failed",
                    f"Could not enable OpenAI TTS.\n{keyring_info}\n\nUsing fallback: {current_provider or 'None'}"
                )

        if checkbox:
            checkbox.blockSignals(False) # Re-enable signals

    def update_submit_button_text(self, check_state_value: int = None):
        """Updates the submit/record button and input mode based on STT checkbox."""
        # Update state if called directly from checkbox signal
        if check_state_value is not None:
            self.use_speech_input = (check_state_value == Qt.CheckState.Checked.value)
            print(f"Use Speech Input (STT) state changed to: {self.use_speech_input}")

            # Update Interview Page UI immediately if it's the current page
            if self.interview_page_instance and self.stacked_widget and \
               self.stacked_widget.currentIndex() == self.INTERVIEW_PAGE_INDEX:
                self.interview_page_instance.set_input_mode(self.use_speech_input)
                # Start/Stop webcam feed based on new mode ONLY IF on Interview Page
                if self.use_speech_input:
                    self.start_webcam_feed()
                else:
                    self.stop_webcam_feed()

        # Update the button appearance (text/icon) based on current STT state
        # Only change if not currently recording/processing
        if not self.is_recording:
            self.set_recording_button_state('idle')

        # --- Update Answer Input ReadOnly/Enabled State ---
        # This needs to consider both STT mode AND general control enabled state
        answer_input = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input:
            is_text_mode = not self.use_speech_input

            # Determine if interview controls should be generally active
            # (i.e., not disabled due to processing or waiting for question)
            submit_btn = getattr(self.interview_page_instance, 'submit_button', None)
            # Check if button exists, is enabled, AND we are not currently in STT recording/processing
            controls_generally_active = submit_btn and submit_btn.isEnabled() and not self.is_recording

            # Input is enabled ONLY if in text mode AND controls are generally active
            answer_input.setEnabled(is_text_mode and controls_generally_active)
            # Input is read-only if NOT in text mode (i.e., STT is ON)
            answer_input.setReadOnly(not is_text_mode)

            # Update placeholder text based on mode and state
            if is_text_mode and controls_generally_active:
                answer_input.setPlaceholderText("Type your answer here...")
                # Set focus only if the interview page is the current page
                if self.stacked_widget and self.stacked_widget.currentIndex() == self.INTERVIEW_PAGE_INDEX:
                    answer_input.setFocus()
            elif not is_text_mode:
                answer_input.setPlaceholderText("Webcam view active (STT Mode)...")
            else: # Text mode but controls disabled (e.g., waiting for question or processing)
                answer_input.setPlaceholderText("Waiting for question or processing...")


    def select_resume_file(self):
        """Opens a file dialog to select a new resume PDF."""
        # Start in user's home directory or last used directory (if tracked)
        start_dir = os.path.expanduser("~")
        start_dir_native = os.path.normpath(start_dir)
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select New Resume PDF", start_dir_native, "PDF Files (*.pdf)"
        )
        if filepath:
            # Process the selected file, pass None for name to trigger prompt if needed
            # Pass the original path for processing (copying/naming will handle managed path)
            self._process_selected_resume({"path": filepath, "name": None})
        else:
            self.update_status("Resume selection cancelled.")

    def _handle_resume_widget_selected(self, resume_data: dict):
        """Handles the selection of a resume from the recent list widget."""
        name = resume_data.get('name', 'Unknown')
        path = resume_data.get('path')
        print(f"ResumeWidget selected: '{name}' Path: {path}")
        if isinstance(resume_data, dict) and path:
            # Pass the full data dict (contains name and path)
            # The path should already be the managed path from the config/widget
            self._process_selected_resume(resume_data)
        else:
            print("Warning: Received invalid data from ResumeWidget click.")
            self.show_message_box("warning", "Internal Error", "Invalid data received from resume list.")

    def _handle_add_new_jd(self):
        """Handles adding a new job description via input dialogs."""
        # Prompt for the JD text first
        jd_text, ok = QInputDialog.getMultiLineText(
            self, "Add Job Description", "Paste the full job description text below:"
        )
        if ok and jd_text and jd_text.strip():
            jd_text = jd_text.strip() # Store the valid text

            # Prompt for a name for this JD
            name, ok_name = QInputDialog.getText(
                self, "Name Job Description",
                "Enter a short, unique name for this job description:"
            )
            if ok_name and name and name.strip():
                name = name.strip() # Store the valid name

                # Check if name already exists and ask to overwrite
                existing_names = [item.get("name") for item in self.config.get("recent_job_descriptions", [])]
                if name in existing_names:
                    reply = QMessageBox.question(
                        self, 'Overwrite JD?',
                        f"A job description named '{name}' already exists. Overwrite it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No # Default to No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        self.update_status(f"Job description '{name}' not overwritten.")
                        return # Cancelled overwrite

                # Add or overwrite the JD
                self._add_recent_jd(name, jd_text)
                # Select the newly added JD
                self.selected_jd_name = name
                self.job_description_text = jd_text
                self._update_ui_from_state() # Update UI to show new selection
                self.update_status(f"Job description '{name}' added and selected.")
            else:
                self.update_status("Job description add cancelled (no name provided).")
        elif ok: # Text was empty
            self.show_message_box("warning", "Input Needed", "Job Description text cannot be empty.")
            self.update_status("Job description add cancelled (empty text).")
        else: # User cancelled the text input dialog
            self.update_status("Job description add cancelled.")

    def _handle_jd_widget_selected(self, jd_data: dict):
        """Handles the selection of a JD from the recent list widget."""
        name = jd_data.get("name")
        text = jd_data.get("text")
        print(f"JDWidget selected: {name}")
        if name and text is not None: # Ensure both name and text are valid
            self.selected_jd_name = name
            self.job_description_text = text
            # Update UI state which includes highlighting selection and enabling start button
            self._update_ui_from_state()
            self.update_status(f"Job description '{name}' selected.")
        else:
            print("Warning: Received invalid data from JDWidget click.")
            self.show_message_box("warning", "Internal Error", "Invalid data received from JD list.")

    # --- MODIFIED METHOD: start_interview_process ---
    # Includes clearing the recordings folder
    def start_interview_process(self):
        """Validates inputs, clears recordings, and starts the interview generation process."""
        # --- Input Validation ---
        if not self.pdf_filepath or not self.resume_content:
            self.show_message_box("warning", "Input Missing", "Please select a resume PDF first.")
            return
        if not self.job_description_text:
            self.show_message_box("warning", "Input Missing", "Please select or add a Job Description first.")
            return

        current_jd_text = self.job_description_text # Use the currently selected/loaded JD

        # Check TTS availability if OpenAI TTS is selected
        if self.use_openai_tts and "openai" not in tts.get_runtime_available_providers():
            self.show_message_box("error", "TTS Error", "OpenAI TTS selected but unavailable. Please check API key or select another TTS option.")
            return

        # --- Log Interview Settings ---
        print("-" * 20)
        print(f"Preparing Interview:")
        print(f"  Resume: {Path(self.pdf_filepath).name if self.pdf_filepath else 'N/A'}")
        print(f"  JD Name: {self.selected_jd_name or 'Pasted/Unnamed'}")
        print(f"  Topics: {self.num_topics}")
        print(f"  Max Follow-ups: {self.max_follow_ups}")
        print(f"  STT Enabled: {self.use_speech_input}")
        print(f"  OpenAI TTS Enabled: {self.use_openai_tts}")
        print("-" * 20)

        # --- Reset State for New Interview (keep selections) ---
        self.reset_interview_state(clear_config=False)

        # --- >>> NEW: Clear Recordings Folder <<< ---
        self._clear_recordings_folder() # Clear out old .wav and .txt files

        # --- Disable Setup Controls & Show Busy State ---
        self.update_status(f"Generating {self.num_topics} initial questions...", True)
        pdf_loaded = bool(self.pdf_filepath) # Store current loaded state before disabling
        jd_loaded = bool(self.job_description_text)
        self.set_setup_controls_state(False, False) # Disable setup controls during generation
        # Disable sidebar toggle too, if setup page instance exists
        toggle_btn = getattr(self.setup_page_instance, 'sidebar_toggle_btn', None)
        if toggle_btn:
            toggle_btn.setEnabled(False)
        QApplication.processEvents() # Update UI

        # --- Generate Initial Questions (Logic Call) ---
        try:
            self.initial_questions = logic.generate_initial_questions(
                resume_text=self.resume_content,
                job_desc_text=current_jd_text, # Use the current JD text
                num_questions=self.num_topics
            )
        except Exception as e:
            print(f"ERROR generating initial questions: {e}")
            self.initial_questions = None # Ensure it's None on error
            self.show_message_box("error", "Generation Error", f"Failed to generate interview questions:\n{e}")
        finally:
            # --- Re-enable Setup Controls & Restore Cursor ---
            self.update_status("", False) # Clear busy state
            self.set_setup_controls_state(pdf_loaded, jd_loaded) # Restore original enabled state
            if toggle_btn:
                toggle_btn.setEnabled(True) # Re-enable toggle button

        # --- Handle Generation Outcome ---
        if not self.initial_questions:
            self.update_status("Error generating interview questions.")
            print("Failed to generate initial interview questions. Returning to setup.")
            # Stay on setup page if generation failed
            return

        print(f"Generated {len(self.initial_questions)} initial questions.")
        # Clean and store unique questions (case-insensitive might be better if needed)
        self.cleaned_initial_questions = {
            self._clean_question_text(q) for q in self.initial_questions
        }
        if len(self.initial_questions) < self.num_topics:
            print(f"Warning: Received {len(self.initial_questions)} questions "
                  f"(requested {self.num_topics}). Continuing with available questions.")
            # Optionally inform user if fewer questions were generated

        # --- Proceed to Interview Page ---
        self._go_to_interview_page()
        # Start the first topic
        self.current_initial_q_index = 0
        self.start_next_topic()


    def start_next_topic(self):
        """Starts the next interview topic or finishes the interview."""
        if not self.initial_questions:
            print("Error: No initial questions available to start topic.")
            self.show_message_box("error", "Interview Error", "No questions were generated. Returning to setup.")
            self._go_to_setup_page() # Go back if questions are missing
            return

        # Check if there are more initial questions left
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            # Start the next topic
            self.follow_up_count = 0 # Reset follow-up counter for the new topic
            self.current_topic_history = [] # Clear history for the new topic
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text) # Store cleaned version for context

            # Log topic start to console/history
            topic_marker = (
                f"\n--- Topic {self.current_initial_q_index + 1}"
                f"/{len(self.initial_questions)} ---"
            )
            print(topic_marker.strip())
            self.add_to_history(topic_marker, tag="topic_marker")

            print(f"Asking Initial Q{self.current_initial_q_index + 1}: "
                  f"'{self.current_topic_question}'") # Log cleaned version for context
            self.display_question(raw_q_text) # Display raw question to user
        else:
            # All initial questions (and their follow-ups) are done
            print("\n--- Interview Finished ---")
            self.disable_interview_controls()
            self._go_to_loading_page() # Show loading screen
            # Use QTimer.singleShot to delay the heavy results generation,
            # allowing the UI to update to the loading page first.
            QTimer.singleShot(100, self._start_results_generation)

    # --- REVIEWED METHOD: _start_results_generation ---
    # Calls save_transcript_to_file first.
    def _start_results_generation(self):
        """Saves transcript, generates results, and navigates to the results page."""
        print("Starting results generation process...")
        self.update_status("Generating results...") # Keep status updated

        # --- >>> Perform transcript saving FIRST <<< ---
        self.save_transcript_to_file()
        QApplication.processEvents() # Allow UI updates if needed

        # --- Continue with other analysis tasks ---
        # 1. Generate summary review (LLM call)
        print("Generating summary review...")
        summary = logic.generate_summary_review(self.current_full_interview_history)
        QApplication.processEvents()

        # 2. Generate content score analysis (LLM call)
        print("Generating content score analysis...")
        content_score_data = logic.generate_content_score_analysis(self.current_full_interview_history)
        QApplication.processEvents()

        # 3. Generate qualification assessment (LLM call)
        print("Generating qualification assessment...")
        assessment_data = logic.generate_qualification_assessment(
            self.resume_content, self.job_description_text, self.current_full_interview_history
        )
        QApplication.processEvents()

        # --- Finalize and Navigate ---
        self.update_status("Results ready.", False) # Clear busy state

        # Handle potential errors during generation (optional: add more specific messages)
        if summary is None or (isinstance(summary, str) and summary.startswith(logic.ERROR_PREFIX)):
            error_detail = summary or "No summary returned."
            self.show_message_box("warning", "Summary Error", f"Could not generate interview summary.\n{error_detail}")
        if assessment_data and assessment_data.get("error") and self.job_description_text:
            # Only show assessment error if JD was provided (as it's job-fit related)
            self.show_message_box("warning", "Assessment Error", f"Could not generate job fit assessment.\n{assessment_data.get('error', '')}")
        if content_score_data and content_score_data.get("error"):
             self.show_message_box("warning", "Content Score Error", f"Could not generate content score analysis.\n{content_score_data.get('error', '')}")

        # Navigate to the final results page (container)
        self._go_to_results_page(summary, assessment_data, content_score_data)

    def handle_answer_submission(self):
        """Handles the submission of an answer, either text or recorded."""
        if self.is_recording:
            print("Already recording/processing, ignoring button press.")
            return # Prevent double submission

        answer_input = getattr(self.interview_page_instance, 'answer_input', None)

        if self.use_speech_input:
            # --- Start Speech Recognition ---
            print("Record button clicked, starting STT...")
            self.disable_interview_controls(is_recording_stt=True) # Disable controls, indicate recording
            self.update_status_stt("STT_Status: Starting Mic...") # Update UI feedback
            # Webcam feed should already be running if STT mode is active

            # Generate indices for saving the recording filename
            topic_idx = self.current_initial_q_index + 1
            followup_idx = self.follow_up_count
            # Start the STT/Saving thread (defined in core.recording)
            # This function handles mic setup, listening, processing, and putting result in queue
            recording.start_speech_recognition(topic_idx, followup_idx)
        else:
            # --- Process Text Input ---
            print("Submit button clicked, processing text answer.")
            if not answer_input:
                print("Error: Answer input widget not found.")
                self.show_message_box("error", "Internal Error", "Cannot find answer input field.")
                return
            user_answer = answer_input.toPlainText().strip()
            if not user_answer:
                self.show_message_box("warning", "Input Required", "Please type your answer before submitting.")
                return # Don't process empty answers
            # Process the text answer directly
            self.process_answer(user_answer)

    def update_status_stt(self, message: str):
        """Updates status bar and record button based on STT status messages."""
        if not self.status_bar_label: return # Skip if status bar isn't ready

        display_message = message # Default display message
        button_state = 'idle' # Default button state

        # Map STT messages to user-friendly status and button states
        if message == "STT_Status: Starting Mic...":
            display_message = "[Starting Microphone...]"
            button_state = 'processing' # Show spinner/processing state
        elif message == "STT_Status: Adjusting Mic...":
            display_message = "[Calibrating microphone threshold...]"
            button_state = 'processing'
        elif message == "STT_Status: Listening...":
            display_message = "[Listening... Speak Now]"
            button_state = 'listening' # Show listening icon/state
        elif message == "STT_Status: Processing...":
            display_message = "[Processing Speech... Please Wait]"
            button_state = 'processing' # Show spinner again
        elif message.startswith("STT_Warning:"):
            detail = message.split(':', 1)[1].strip()
            display_message = f"[STT Warning: {detail}]"
            button_state = 'idle' # Go back to idle state on warning
            self.is_recording = False # Ensure recording state is reset
            # Don't stop webcam on warning, user might retry
        elif message.startswith("STT_Error:"):
            detail = message.split(':', 1)[1].strip()
            display_message = f"[STT Error: {detail}]"
            button_state = 'idle' # Go back to idle state on error
            self.is_recording = False # Ensure recording state is reset
            # Don't stop webcam on error, user might retry or switch mode
        elif message.startswith("STT_Success:"):
            # Success message is usually followed immediately by process_answer
            # We can show a brief success status, but the button will quickly change again
            display_message = "[Speech Recognized Successfully]"
            # Button state remains 'processing' briefly until process_answer takes over
            button_state = 'processing' # Or could be 'idle' depending on desired flow

        # Update UI elements
        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state)
        QApplication.processEvents() # Ensure UI updates are shown

    def check_stt_queue(self):
        """Checks the STT result queue for messages and processes them."""
        try:
            # Check queue without blocking
            result = recording.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")

            if result.startswith(("STT_Status:", "STT_Warning:", "STT_Error:")):
                # Update status bar and button based on the message
                self.update_status_stt(result)
                # Re-enable controls ONLY if an error/warning occurred and we are back to idle state
                if result.startswith(("STT_Warning:", "STT_Error:")) and not self.is_recording:
                     # Check is_recording again, as update_status_stt might have reset it
                     print("STT Warning/Error received, enabling controls.")
                     self.enable_interview_controls()
            elif result.startswith("STT_Success:"):
                # STT was successful, transcript received
                self.is_recording = False # STT part is done, now process answer
                self.update_status_stt(result) # Show brief success status
                transcript = result.split(":", 1)[1].strip()
                # Process the received transcript
                self.process_answer(transcript)
            else:
                 print(f"Warning: Received unknown message from STT queue: {result}")

        except queue.Empty:
            # Queue is empty, nothing to do
            pass
        except Exception as e:
            # Handle unexpected errors reading the queue
            print(f"Error checking STT Queue: {e}")
            if self.is_recording: # If an error happens during recording state
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()
                # Consider stopping webcam on unexpected queue errors
                # self.stop_webcam_feed()
            self.update_status(f"Error checking speech recognition: {e}")

    def process_answer(self, user_answer: str):
        """Processes the user's answer and generates the next question."""
        # Note: Webcam feed is NOT stopped here. It continues if STT mode is active.

        last_q = self.last_question_asked or "[Unknown Question]"
        print(f"Processing answer for Q: '{last_q[:50]}...' -> A: '{user_answer[:50]}...'")

        # --- Store History ---
        q_data = {"q": last_q, "a": user_answer}
        self.current_topic_history.append(q_data) # History for current topic (follow-ups)
        self.current_full_interview_history.append(q_data) # Full history for final report

        # --- Log to Console ---
        self.add_to_history(f"Q: {last_q}", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n", tag="answer_style")

        # --- Clear Input Field ---
        answer_input = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input:
            answer_input.clear()

        # --- Disable Controls & Show Processing State ---
        self.disable_interview_controls()
        self.update_status("Generating response from interviewer...", True)
        # Set button to processing state while waiting for LLM
        self.set_recording_button_state('processing')
        QApplication.processEvents()

        # --- Determine Next Step (Follow-up or Next Topic) ---
        proceed_to_next_topic = False
        if self.follow_up_count < self.max_follow_ups:
            # Try generating a follow-up question
            try:
                follow_up_q = logic.generate_follow_up_question(
                    context_question=self.current_topic_question, # Cleaned initial question
                    user_answer=user_answer,
                    conversation_history=self.current_topic_history # Pass history for this topic
                )
            except Exception as e:
                print(f"ERROR calling generate_follow_up_question: {e}")
                follow_up_q = None # Treat errors as signal to move on
                self.show_message_box("warning", "Follow-up Error", f"Could not generate follow-up:\n{e}")

            self.update_status("", False) # Clear busy state after LLM call

            # Evaluate the generated follow-up
            if follow_up_q and follow_up_q.strip() and follow_up_q.upper() != "[END TOPIC]":
                # Valid follow-up received
                self.follow_up_count += 1
                print(f"Asking Follow-up Q ({self.follow_up_count}/{self.max_follow_ups}): {follow_up_q}")
                self.display_question(follow_up_q) # Display the follow-up
            elif follow_up_q and follow_up_q.upper() == "[END TOPIC]":
                # Model explicitly ended the topic
                print("Model signalled end of topic.")
                proceed_to_next_topic = True
            else:
                # No valid follow-up generated (None, empty, or error)
                print("No valid follow-up generated or generation failed.")
                proceed_to_next_topic = True
        else:
            # Max follow-ups reached for this topic
            print(f"Max follow-ups ({self.max_follow_ups}) reached for this topic.")
            self.update_status("", False) # Clear busy state if we didn't make LLM call
            proceed_to_next_topic = True

        # --- Move to Next Topic if Decided ---
        if proceed_to_next_topic:
            self.current_initial_q_index += 1 # Move to the next initial question index
            # self.follow_up_count = 0 # Reset counter (already done in start_next_topic)
            self.start_next_topic() # Handles finishing interview or starting next topic

        # Restore cursor if it was overridden (e.g., by update_status busy=True)
        # Check redundant, update_status(busy=False) already handles it.
        # if QApplication.overrideCursor() is not None:
        #     QApplication.restoreOverrideCursor()


    def _save_report(self):
        """Gathers results data and saves it to a text report file."""
        # Access results data stored in MainWindow state
        content_score = 0
        analysis = "N/A"
        content_error = None
        if self.last_content_score_data:
            content_score = self.last_content_score_data.get('score', 0)
            analysis = self.last_content_score_data.get('analysis_text', 'N/A')
            content_error = self.last_content_score_data.get('error')

        assess_error = None
        req_list = []
        fit_text = "N/A"
        if self.last_assessment_data:
            assess_error = self.last_assessment_data.get("error")
            req_list = self.last_assessment_data.get("requirements", [])
            fit_text = self.last_assessment_data.get("overall_fit", "N/A")

        # Check if there is any data to save
        if not self.last_content_score_data and not self.last_assessment_data and not self.current_full_interview_history:
            self.show_message_box("warning", "No Data", "No results data available to save.")
            return

        # Build the report content using data and constants from MainWindow
        report_lines = [
            "Interview Report",
            f"{'='*16}\n",
            f"Speech Delivery Score: {self.FIXED_SPEECH_SCORE}%", # Use constant from self
            f"{'-'*23}",
             # Clean markdown/HTML from description
            self.FIXED_SPEECH_DESCRIPTION.replace('**', '').replace('*', '').replace('<i>','').replace('</i>',''),
            "\n",
            f"Response Content Score: {content_score}%",
            f"{'-'*24}"
        ]

        # Add Content Analysis section (handle error)
        if content_error:
            report_lines.append(f"Content Analysis Error: {content_error}")
        else:
            # Clean markdown from analysis text for plain text report
            cleaned_analysis = analysis.replace('**', '').replace('*', '')
            report_lines.append(cleaned_analysis)

        # Add Job Fit Analysis section
        report_lines.append("\n")
        report_lines.extend([f"Job Fit Analysis", f"{'-'*16}"])
        if assess_error:
             report_lines.append(f"Assessment Error: {assess_error}")
        elif req_list: # If requirements list exists
            for i, req in enumerate(req_list):
                # Clean fields before adding
                req_text = req.get('requirement', 'N/A').replace('**','').replace('*','')
                assess_text = req.get('assessment', 'N/A').replace('**','').replace('*','')
                resume_ev = req.get('resume_evidence', 'N/A').replace('**','').replace('*','')
                trans_ev = req.get('transcript_evidence', 'N/A').replace('**','').replace('*','')

                report_lines.append(f"\nRequirement {i+1}: {req_text}")
                report_lines.append(f"  Assessment: {assess_text}")
                report_lines.append(f"  Resume Evidence: {resume_ev}")
                report_lines.append(f"  Interview Evidence: {trans_ev}")

            # Add overall fit text after listing requirements
            cleaned_fit = fit_text.replace('<b>','').replace('</b>','').replace('*','') # Clean HTML/Markdown
            report_lines.append(f"\nOverall Fit Assessment: {cleaned_fit}")
        else: # No requirements list, but maybe overall fit text exists
            report_lines.append("No specific requirements assessment details available.")
            cleaned_fit = fit_text.replace('<b>','').replace('</b>','').replace('*','')
            # Add overall fit if it's meaningful
            if cleaned_fit != "N/A" and not cleaned_fit.startswith("Overall fit assessment not found"):
                 report_lines.append(f"\nOverall Fit Assessment: {cleaned_fit}")

        # --- File Saving Logic ---
        report_content = "\n".join(report_lines)
        default_filename = "interview_report.txt"
        # Suggest filename based on resume if available
        if self.pdf_filepath:
            base = Path(self.pdf_filepath).stem
            # Sanitize filename (remove potentially problematic chars)
            sanitized_base = "".join(c for c in base if c.isalnum() or c in (' ', '_', '-')).rstrip()
            default_filename = f"{sanitized_base}_interview_report.txt"

        # Ensure recordings directory exists (though it should)
        recordings_path = Path(RECORDINGS_DIR)
        try:
            os.makedirs(recordings_path, exist_ok=True)
        except OSError as e:
            print(f"Warning: Cannot ensure save directory {recordings_path} exists: {e}")
            recordings_path = Path.home() # Fallback to home directory

        default_path = str(recordings_path / default_filename)

        # Open file dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Interview Report", default_path, "Text Files (*.txt);;All Files (*)"
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                self.update_status(f"Report saved to {os.path.basename(filepath)}.")
                self.show_message_box("info", "Report Saved", f"Saved report to:\n{filepath}")
            except Exception as e:
                print(f"Error saving report: {e}")
                self.show_message_box("error", "Save Error", f"Could not save report:\n{e}")
        else:
            self.update_status("Report save cancelled.")

    def _open_recordings_folder(self):
        """Opens the folder containing saved transcripts and recordings."""
        recordings_path = Path(RECORDINGS_DIR)
        folder_path_str = str(recordings_path)
        print(f"Attempting to open user recordings folder: {folder_path_str}")

        # Ensure the directory exists, create if not
        if not recordings_path.exists():
            try:
                os.makedirs(recordings_path, exist_ok=True)
                print(f"Created recordings directory: {recordings_path}")
            except OSError as e:
                print(f"Error creating recordings directory: {e}")
                self.show_message_box("error", "Folder Error", f"Could not create recordings folder at:\n{folder_path_str}")
                self.update_status("Failed to create recordings folder.")
                return # Cannot open if creation failed

        # Try opening using QDesktopServices first (preferred)
        url = QUrl.fromLocalFile(folder_path_str)
        if not QDesktopServices.openUrl(url):
            # Fallback using platform-specific commands
            print(f"QDesktopServices failed. Trying platform fallback...")
            self.update_status("Opening folder (using fallback)...")
            QApplication.processEvents() # Update UI before potentially blocking call
            try:
                system = platform.system()
                if system == "Windows":
                    # Use os.startfile for preferred Windows behavior
                    os.startfile(os.path.normpath(folder_path_str))
                elif system == "Darwin": # macOS
                    subprocess.Popen(["open", folder_path_str])
                else: # Linux/Other Unix-like
                    subprocess.Popen(["xdg-open", folder_path_str])
                self.update_status("Opened recordings folder (fallback).")
            except FileNotFoundError:
                cmd = "startfile/explorer" if system=="Windows" else ("open" if system=="Darwin" else "xdg-open")
                print(f"Error: Command '{cmd}' not found.")
                self.show_message_box("error", "Open Error", f"Could not find command '{cmd}' to open the folder.")
                self.update_status("Failed to open folder (command missing).")
            except Exception as e:
                print(f"Fallback open error: {e}")
                self.show_message_box("error", "Open Error", f"Could not open folder using fallback method: {e}")
                self.update_status("Failed to open recordings folder.")
        else:
            # QDesktopServices succeeded
            self.update_status("Opened recordings folder.")


    # --- Webcam Feed Methods ---
    def start_webcam_feed(self):
        """Starts the dedicated webcam streaming thread and UI timer."""
        if self.webcam_stream_thread is not None and self.webcam_stream_thread.is_alive():
            print("Webcam feed already running.")
            return

        # Clear any stale frames from previous runs
        while not self.webcam_frame_queue.empty():
            try: self.webcam_frame_queue.get_nowait()
            except queue.Empty: break

        print("Starting webcam streaming thread...")
        self.webcam_stream_stop_event = threading.Event()
        # Pass queue and stop event to the streaming function (in core.recording)
        self.webcam_stream_thread = threading.Thread(
            target=recording.stream_webcam,
            args=(self.webcam_frame_queue, self.webcam_stream_stop_event),
            daemon=True # Ensure thread exits when main app exits
        )
        self.webcam_stream_thread.start()

        # Start the QTimer to update the UI label with frames from the queue
        if not self.webcam_timer.isActive():
            self.webcam_timer.start(WEBCAM_UPDATE_INTERVAL)
            print(f"Webcam UI update timer started (interval: {WEBCAM_UPDATE_INTERVAL}ms).")

    def stop_webcam_feed(self):
        """Stops the webcam streaming thread and UI timer."""
        # Check if anything related to webcam is actually running
        was_active = (self.webcam_timer.isActive() or
                      (self.webcam_stream_thread is not None and self.webcam_stream_thread.is_alive()))

        if not was_active:
            # print("Webcam feed was not active, no need to stop.") # Optional debug
            return

        print("Stopping webcam feed...")
        # 1. Stop the UI update timer
        if self.webcam_timer.isActive():
            self.webcam_timer.stop()
            print("Webcam UI timer stopped.")

        # 2. Signal the streaming thread to stop
        if self.webcam_stream_stop_event:
            self.webcam_stream_stop_event.set()
            print("Webcam stream stop event set.")

        # 3. Wait for the streaming thread to finish
        if self.webcam_stream_thread is not None:
            thread_to_join = self.webcam_stream_thread # Store ref before clearing
            print("Joining webcam stream thread...")
            thread_to_join.join(timeout=1.0) # Reduce timeout slightly
            if thread_to_join.is_alive():
                print("Warning: Webcam stream thread join timed out.")
                # Thread might be stuck, but we continue cleanup
            else:
                print("Webcam stream thread joined successfully.")
            self.webcam_stream_thread = None # Clear thread reference

        # 4. Reset the stop event
        self.webcam_stream_stop_event = None

        # 5. Clear any remaining frames in the queue
        while not self.webcam_frame_queue.empty():
            try: self.webcam_frame_queue.get_nowait()
            except queue.Empty: break
        print("Webcam frame queue cleared.")

        # 6. Reset the webcam view label to placeholder (if page exists)
        if self.interview_page_instance:
            self.interview_page_instance.set_webcam_frame(None) # Pass None for default placeholder
        print("Webcam feed stopped completely.")

    def _update_webcam_view(self):
        """Gets a frame from the queue and displays it on the InterviewPage."""
        if not self.interview_page_instance or not hasattr(self.interview_page_instance, 'webcam_view_label'):
            # Silently return if the interview page or label isn't ready
            return

        # Only process if the Interview Page is the currently visible page
        if not self.stacked_widget or self.stacked_widget.currentIndex() != self.INTERVIEW_PAGE_INDEX:
             return

        try:
            # Get frame from queue without blocking
            frame = self.webcam_frame_queue.get_nowait()

            if frame is None:
                # None indicates the stream ended (e.g., camera error)
                print("Webcam view received None sentinel, stopping UI updates and feed.")
                self.stop_webcam_feed() # Stop everything related to webcam
                # Optionally display an error state on the webcam label
                if self.interview_page_instance:
                     placeholder = QPixmap(self.interview_page_instance.webcam_view_label.minimumSize())
                     placeholder.fill(QColor("black"))
                     painter = QPainter(placeholder)
                     painter.setPen(QColor("red"))
                     painter.setFont(getattr(self, 'font_default', QFont()))
                     painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, "Webcam Error / Disconnected")
                     painter.end()
                     self.interview_page_instance.set_webcam_frame(placeholder)
                return

            if isinstance(frame, np.ndarray):
                # Process valid numpy array frame
                try:
                    # Convert BGR (OpenCV default) to RGB (Qt default)
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    # Create QImage from numpy array data (no copy needed if data persists)
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    # Create QPixmap from QImage
                    qt_pixmap = QPixmap.fromImage(qt_image)
                    # Set the pixmap on the interview page label
                    self.interview_page_instance.set_webcam_frame(qt_pixmap)
                except cv2.error as cv_err:
                    print(f"OpenCV error during frame conversion: {cv_err}")
                    # Stop feed on conversion errors? Maybe too aggressive.
                    # self.stop_webcam_feed()
                except Exception as conv_err:
                    print(f"Error converting frame to QPixmap: {conv_err}")
                    # self.stop_webcam_feed()

            # Ignore unexpected data types silently after the first warning maybe?

        except queue.Empty:
            # Queue is empty, no new frame available this cycle - this is normal
            pass
        except Exception as e:
            # Catch-all for other unexpected errors during UI update
            print(f"Error updating webcam view: {e}")
            # Consider stopping the feed on repeated or critical errors
            # self.stop_webcam_feed()

    def closeEvent(self, event):
        """Handles cleanup when the application window is closed."""
        print("Close event triggered. Cleaning up application resources...")

        # Stop timers
        if hasattr(self, 'stt_timer') and self.stt_timer.isActive():
            self.stt_timer.stop()
            print("STT queue check timer stopped.")

        # Stop webcam feed cleanly
        self.stop_webcam_feed()

        # Signal any other running threads (e.g., if recording uses separate threads)
        if self.is_recording:
            print("Attempting to signal active recording/processing threads to stop...")
            # If core.recording has a specific stop function for background tasks, call it here
            # e.g., recording.stop_background_tasks()

        # Save config one last time? (Optional)
        # self._save_config()

        print("Main window cleanup finished.")
        event.accept() # Allow the window to close


# --- Entry Point (for running this file directly, if needed) ---
if __name__ == '__main__':
    # Set application details for better integration (especially on macOS)
    QApplication.setApplicationName("InterviewBotPro")
    QApplication.setOrganizationName("YourOrganizationName") # Replace if desired
    QApplication.setApplicationVersion("1.0") # Replace with actual version

    app = QApplication(sys.argv)

    # --- Icon Path Setup ---
    # Determine the base path (works for running script directly or as installed package)
    if getattr(sys, 'frozen', False): # Check if running as a bundled executable (PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent # Go up two levels from ui/main_window.py

    icon_folder_path = base_path / 'icons'
    icon_file_path = icon_folder_path / 'app_icon.png' # Or your specific icon file

    # Set window icon
    app_icon = QIcon(str(icon_file_path))
    if app_icon.isNull():
        print(f"Warning: Application icon not found at {icon_file_path}")
    app.setWindowIcon(app_icon)

    # Configure Gemini API at startup
    if not logic.configure_gemini():
         # Show a critical error message if Gemini config fails
         msg_box = QMessageBox()
         msg_box.setIcon(QMessageBox.Icon.Critical)
         msg_box.setWindowTitle("API Configuration Error")
         msg_box.setText("Failed to configure the Google Gemini API.")
         msg_box.setInformativeText(
             "Please ensure your API key is correctly stored in the system keyring "
             f"(Service: '{logic.KEYRING_SERVICE_NAME_GEMINI}') and that you have internet access.\n\n"
             "The application may not function correctly without the API."
         )
         msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
         msg_box.exec()
         # Decide whether to exit or continue with limited functionality
         # sys.exit(1) # Or allow to continue

    # Initialize and show the main window
    main_window = InterviewApp(icon_path=str(icon_folder_path))
    main_window.show()

    sys.exit(app.exec())