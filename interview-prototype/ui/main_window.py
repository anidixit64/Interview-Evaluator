# ui/main_window.py
import os
import sys
import queue
import platform
import subprocess
import html
import json
import shutil
from pathlib import Path

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QApplication, QStackedWidget,
    QLabel, QSizePolicy, QFrame, QListWidgetItem, QInputDialog, QLineEdit
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QCursor, QIcon, QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QUrl, QStandardPaths

# --- Project Imports ---
try:
    import core.logic as logic
    from core import tts, recording
    from core.recording import RECORDINGS_DIR
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import core.logic as logic
    from core import tts, recording
    from core.recording import RECORDINGS_DIR

# --- Import Page Classes & Constants ---
from .setup_page import SetupPage
from .interview_page import InterviewPage
from .results_page import ResultsPage
from .results_page import FIXED_SPEECH_DESCRIPTION, FIXED_SPEECH_SCORE

# --- Constants ---
CONFIG_FILE_NAME = "settings.json"
RESUMES_SUBDIR = "resumes"
MAX_RECENT_RESUMES = 10
MAX_RECENT_JDS = 10

class InterviewApp(QWidget):
    SETUP_PAGE_INDEX = 0
    INTERVIEW_PAGE_INDEX = 1
    RESULTS_PAGE_INDEX = 2

    def __init__(self, icon_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_path = icon_path
        self.setWindowTitle("Interview Bot Pro")
        self.setGeometry(100, 100, 850, 1000)

        self._setup_appearance()
        self._load_assets()
        self._init_state()
        self._ensure_app_dirs_exist()
        self.config = self._load_config()
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
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(50,50,50))
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
        self.icon_size = QSize(20, 20)
        self.font_default = QFont("Arial", 10)
        self.font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 9)
        self.font_large_bold = QFont("Arial", 12, QFont.Weight.Bold)
        self.font_history = QFont("Monospace", 9)

    def _init_state(self):
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
        self.is_recording = False
        self.last_question_asked = ""
        self.last_assessment_data = None
        self.last_content_score_data = None
        self.app_data_dir = self._get_app_data_dir()
        self.config_path = self.app_data_dir / CONFIG_FILE_NAME
        self.resumes_dir = self.app_data_dir / RESUMES_SUBDIR
        self.config = {"recent_resumes": [], "recent_job_descriptions": []}
        self.setup_page_instance = None
        self.interview_page_instance = None
        self.results_page_instance = None
        self.progress_indicator_label = None
        self.status_bar_label = None
        self.stacked_widget = None

    def _get_app_data_dir(self) -> Path:
        app_data_dir_str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not app_data_dir_str:
            app_data_dir_str = os.path.join(os.path.expanduser("~"), ".InterviewBotPro")
            print(f"Warning: Could not get standard AppDataLocation. Using fallback: {app_data_dir_str}")
        return Path(app_data_dir_str)

    def _ensure_app_dirs_exist(self):
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
            self.resumes_dir.mkdir(parents=True, exist_ok=True)
            print(f"Ensured app data directories exist: {self.app_data_dir}")
        except OSError as e:
            print(f"CRITICAL ERROR: Could not create app data directories: {e}")
            self.show_message_box("error", "Directory Error", f"Could not create necessary application directories:\n{self.app_data_dir}\n\nResumes cannot be saved.")

    def _load_config(self) -> dict:
        default_config = {"recent_resumes": [], "recent_job_descriptions": []}
        if not self.config_path.exists():
            print(f"Config file not found at {self.config_path}. Using default.")
            return default_config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            needs_save = False

            if not isinstance(config.get("recent_resumes"), list):
                print("Warning: 'recent_resumes' in config is not a list. Resetting.")
                config["recent_resumes"] = []
                needs_save = True
            else:
                valid_resumes = []
                for item in config.get("recent_resumes", []):
                    if (isinstance(item, dict) and 'name' in item and 'path' in item):
                        p = Path(item['path'])
                        if p.is_absolute() and p.exists() and p.is_relative_to(self.resumes_dir):
                            valid_resumes.append(item)
                        else:
                            needs_save = True
                            print(f"Pruning invalid resume: {item}")
                    else:
                        needs_save = True
                        print(f"Pruning malformed resume: {item}")
                if len(valid_resumes) != len(config.get("recent_resumes", [])):
                    config["recent_resumes"] = valid_resumes

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
        if not name or not path_in_resumes_dir:
            return

        p = Path(path_in_resumes_dir)
        if not p.is_absolute() or not p.is_relative_to(self.resumes_dir):
            print(f"Error: Attempted to add non-managed path: {path_in_resumes_dir}")
            return

        new_entry = {"name": name, "path": str(p)}
        recent_list = self.config.get("recent_resumes", [])

        existing_indices = [i for i, item in enumerate(recent_list) if item.get("path") == str(p)]
        for i in reversed(existing_indices):
            del recent_list[i]

        recent_list.insert(0, new_entry)

        self.config["recent_resumes"] = recent_list[:MAX_RECENT_RESUMES]
        self._save_config()
        self._update_ui_from_state()

    def _add_recent_jd(self, name: str, text: str):
        if not name or text is None:
            return

        new_entry = {"name": name, "text": text}
        jd_list = self.config.get("recent_job_descriptions", [])

        existing_indices = [i for i, item in enumerate(jd_list) if item.get("name") == name]
        for i in reversed(existing_indices):
            del jd_list[i]

        jd_list.insert(0, new_entry)
        self.config["recent_job_descriptions"] = jd_list[:MAX_RECENT_JDS]
        self._save_config()

    def _setup_ui(self):
        main_window_layout = QVBoxLayout(self)
        main_window_layout.setContentsMargins(0, 0, 0, 0)
        main_window_layout.setSpacing(0)
        self.progress_indicator_label = QLabel("...")
        self.progress_indicator_label.setObjectName("progressIndicator")
        self.progress_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_indicator_label.setTextFormat(Qt.TextFormat.RichText)
        main_window_layout.addWidget(self.progress_indicator_label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_window_layout.addWidget(line)
        self.stacked_widget = QStackedWidget()
        main_window_layout.addWidget(self.stacked_widget, stretch=1)
        self.setup_page_instance = SetupPage(self)
        self.interview_page_instance = InterviewPage(self)
        self.results_page_instance = ResultsPage(self)
        self.stacked_widget.addWidget(self.setup_page_instance)
        self.stacked_widget.addWidget(self.interview_page_instance)
        self.stacked_widget.addWidget(self.results_page_instance)
        self.status_bar_label = QLabel("Ready.")
        self.status_bar_label.setObjectName("statusBar")
        main_window_layout.addWidget(self.status_bar_label)
        self.setLayout(main_window_layout)

    def _update_ui_from_state(self):
        print("Updating UI from state...")
        pdf_loaded = bool(self.pdf_filepath and Path(self.pdf_filepath).exists())

        if self.setup_page_instance:
            recent_resumes_data = self.config.get("recent_resumes", [])
            recent_jd_data = self.config.get("recent_job_descriptions", [])
            self.setup_page_instance.update_widgets_from_state(
                recent_resumes_data=recent_resumes_data,
                current_selection_path=self.pdf_filepath,
                recent_jd_data=recent_jd_data,
                current_jd_name=self.selected_jd_name
            )

        if self.interview_page_instance:
            self.interview_page_instance.clear_fields()
        if self.results_page_instance:
            self.results_page_instance.clear_fields()
        self.update_status("Ready.")
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self.update_submit_button_text()

    def _update_progress_indicator(self):
        if not self.progress_indicator_label or not self.stacked_widget:
             return
        current_index = self.stacked_widget.currentIndex()
        steps = ["Step 1: Setup", "Step 2: Interview", "Step 3: Results"]
        progress_parts = [f'<font color="orange"><b>{step}</b></font>' if i == current_index else step for i, step in enumerate(steps)]
        self.progress_indicator_label.setText(" → ".join(progress_parts))

    def _go_to_setup_page(self):
        print("Navigating to Setup Page and Resetting...")
        self.reset_interview_state(clear_config=True)
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.SETUP_PAGE_INDEX)
        self._update_progress_indicator()

    def _go_to_interview_page(self):
        print("Navigating to Interview Page...")
        if self.interview_page_instance:
            self.interview_page_instance.clear_fields()
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.INTERVIEW_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview started. Waiting for question...")

    def _go_to_results_page(self, summary: str | None, assessment_data: dict | None, content_score_data: dict | None):
        print("Navigating to Results Page...")
        self.last_assessment_data = assessment_data
        self.last_content_score_data = content_score_data
        if self.results_page_instance:
            self.results_page_instance.display_results(summary, assessment_data, content_score_data)
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(self.RESULTS_PAGE_INDEX)
        self._update_progress_indicator()
        self.update_status("Interview complete. Results displayed.")

    def show_message_box(self, level, title, message):
        box = QMessageBox(self)
        icon_map = {"info": QMessageBox.Icon.Information, "warning": QMessageBox.Icon.Warning, "error": QMessageBox.Icon.Critical}
        box.setIcon(icon_map.get(level, QMessageBox.Icon.NoIcon))
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _adjust_value(self, value_type, amount):
        current_val = 0
        min_val = 0
        max_val = 0
        target_label_widget = None
        target_var_name = ""
        if value_type == 'topics' and self.setup_page_instance:
            target_label_widget = getattr(self.setup_page_instance, 'num_topics_label', None)
            current_val = self.num_topics
            min_val = logic.MIN_TOPICS
            max_val = logic.MAX_TOPICS
            target_var_name = 'num_topics'
        elif value_type == 'followups' and self.setup_page_instance:
            target_label_widget = getattr(self.setup_page_instance, 'max_follow_ups_label', None)
            current_val = self.max_follow_ups
            min_val = logic.MIN_FOLLOW_UPS
            max_val = logic.MAX_FOLLOW_UPS_LIMIT
            target_var_name = 'max_follow_ups'
        else:
            print(f"Warning: Cannot adjust value. Type '{value_type}' or setup page instance not found.")
            return
        new_value = current_val + amount
        if min_val <= new_value <= max_val:
            setattr(self, target_var_name, new_value)
            if target_label_widget:
                target_label_widget.setText(str(new_value))
            print(f"{target_var_name.replace('_',' ').title()} set to: {new_value}")
        else:
            print(f"Value {new_value} for {value_type} out of bounds ({min_val}-{max_val})")

    def update_status(self, message, busy=False):
        if self.status_bar_label:
            self.status_bar_label.setText(message)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def display_question(self, question_text):
        self.last_question_asked = question_text
        if self.interview_page_instance and hasattr(self.interview_page_instance, 'current_q_text'):
            self.interview_page_instance.current_q_text.setPlainText(question_text)
        else:
            self.update_status(f"Asking: {question_text[:30]}...")
        try:
            tts.speak_text(question_text)
        except Exception as e:
            print(f"TTS Error during speak_text call: {e}")
            self.show_message_box("warning", "TTS Error", f"Could not speak question: {e}")
        self.enable_interview_controls()
        answer_input = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input and not self.use_speech_input:
            answer_input.setFocus()

    def add_to_history(self, text, tag=None):
        if not self.interview_page_instance or not hasattr(self.interview_page_instance, 'history_text'):
            print("Warning: History text widget not found.")
            return
        history_widget = self.interview_page_instance.history_text
        cursor = history_widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        history_widget.setTextCursor(cursor)
        text_color_name = self.palette().color(QPalette.ColorRole.Text).name()
        escaped_text = html.escape(text).replace("\n", "<br>")
        html_content = ""
        if tag == "question_style":
            html_content = f'<font color="#569CD6">{escaped_text}</font>'
        elif tag == "answer_style":
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>'
        elif tag == "topic_marker":
            html_content = f'<font color="grey"><b>{escaped_text}</b></font>'
        else:
            html_content = f'<font color="{text_color_name}">{escaped_text}</font>'
        history_widget.insertHtml(html_content)
        history_widget.ensureCursorVisible()

    def set_setup_controls_state(self, pdf_loaded):
        if self.setup_page_instance:
            self.setup_page_instance.set_controls_enabled_state(pdf_loaded)

    def enable_interview_controls(self):
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(True)
            self.is_recording = False
            self.set_recording_button_state('idle')

    def disable_interview_controls(self, is_recording_stt=False):
        if self.interview_page_instance:
            self.interview_page_instance.set_controls_enabled(False, is_recording_stt)
            self.is_recording = is_recording_stt

    def reset_interview_state(self, clear_config=True):
        print(f"Resetting interview state (clear_config={clear_config})...")
        if clear_config:
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""
            self.selected_jd_name = None # Reset selected JD name
            self.num_topics = logic.DEFAULT_NUM_TOPICS
            self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input = False
            self.use_openai_tts = False
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
                        print("Reset TTS: ERROR - Could not set default or fallback.")
                else:
                    print(f"Reset TTS: Set to default '{default_provider}'.")
        self.initial_questions = []
        self.cleaned_initial_questions = set()
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.is_recording = False
        self.last_question_asked = ""
        self.last_assessment_data = None
        self.last_content_score_data = None
        self._update_ui_from_state()
        self.disable_interview_controls()
        QApplication.restoreOverrideCursor()
        print("Interview state reset complete.")

    def _clean_question_text(self, raw_q_text):
        cleaned = raw_q_text.strip()
        if cleaned and cleaned[0].isdigit():
            parts = cleaned.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit():
                return parts[1].strip()
            parts = cleaned.split(')', 1)
            if len(parts) > 1 and parts[0].isdigit():
                return parts[1].strip()
            parts = cleaned.split(' ', 1)
            if len(parts) > 1 and parts[0].isdigit():
                return parts[1].strip()
        return cleaned

    def save_transcript_to_file(self):
        if not self.current_full_interview_history:
            print("No history to save.")
            return
        if not self.initial_questions:
            print("Warning: Initial questions missing, cannot map topics.")
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
                 if topic_index != -1:
                    current_topic_num = topic_index + 1
                    if current_topic_num != last_topic_num and last_topic_num != -1:
                        transcript_lines.append("\n-------------------------")
                    transcript_lines.append(f"\nQuestion {current_topic_num}: {q_raw}\nAnswer: {a}")
                    last_topic_num = current_topic_num
                 else:
                    ctx = f"Topic {last_topic_num}" if last_topic_num > 0 else "General"
                    transcript_lines.append(f"\nFollow Up (re {ctx}): {q_raw}\nAnswer: {a}")
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving transcript to {filepath}...")
            final_transcript = "\n".join(line.strip() for line in transcript_lines if line.strip())
            with open(filepath, "w", encoding="utf-8") as f:
                 f.write(final_transcript.strip() + "\n")
            print("Transcript saved.")
        except Exception as e:
            print(f"Error saving transcript: {e}")
            self.show_message_box("error", "File Save Error", f"Could not save transcript: {e}")

    def set_recording_button_state(self, state):
        if not self.interview_page_instance:
            return
        target_button = getattr(self.interview_page_instance, 'submit_button', None)
        if not target_button:
            return
        target_icon = None
        target_text = "Submit Answer"
        submit_icon = getattr(self.interview_page_instance, 'submit_icon', None)
        record_icon = getattr(self.interview_page_instance, 'record_icon', None)
        listening_icon = getattr(self.interview_page_instance, 'listening_icon', None)
        processing_icon = getattr(self.interview_page_instance, 'processing_icon', None)
        if state == 'listening':
            target_text = "Listening..."
            target_icon = listening_icon
            target_button.setEnabled(False)
        elif state == 'processing':
            target_text = "Processing..."
            target_icon = processing_icon
            target_button.setEnabled(False)
        elif state == 'idle':
            target_button.setEnabled(True)
            if self.use_speech_input:
                target_text = "Record Answer"
                target_icon = record_icon
            else:
                target_text = "Submit Answer"
                target_icon = submit_icon
        else:
            target_button.setEnabled(True)
            if self.use_speech_input:
                target_text = "Record Answer"
                target_icon = record_icon
            else:
                target_text = "Submit Answer"
                target_icon = submit_icon
        target_button.setText(target_text)
        if target_icon and not target_icon.isNull():
            target_button.setIcon(target_icon)
            target_button.setIconSize(self.icon_size)
        else:
            target_button.setIcon(QIcon())

    def _process_selected_resume(self, resume_data: dict):
        original_filepath = resume_data.get("path")
        preferred_name = resume_data.get("name")

        if not original_filepath or not os.path.exists(original_filepath):
            self.show_message_box("error", "File Error", f"Selected file not found:\n{original_filepath}")
            self.update_status("Selected resume not found.")
            recent_list = self.config.get("recent_resumes", [])
            updated_list = [item for item in recent_list if item.get("path") != original_filepath]
            if len(updated_list) < len(recent_list):
                self.config["recent_resumes"] = updated_list
                self._save_config()
                self._update_ui_from_state()
            return

        filename = os.path.basename(original_filepath)
        target_filepath = self.resumes_dir / filename
        managed_path_str = str(target_filepath)
        custom_name = preferred_name

        needs_copy = True
        needs_name_prompt = False
        is_already_managed = False
        try:
            if target_filepath.exists() and os.path.samefile(original_filepath, managed_path_str):
                needs_copy = False
                is_already_managed = True
                if not custom_name:
                    for item in self.config.get("recent_resumes", []):
                        if item.get("path") == managed_path_str:
                            custom_name = item.get("name")
                            break
            else:
                needs_name_prompt = True
        except OSError:
             if original_filepath != managed_path_str:
                 needs_name_prompt = True
             else:
                 needs_copy = False
                 is_already_managed = True
                 if not custom_name:
                     for item in self.config.get("recent_resumes", []):
                        if item.get("path") == managed_path_str:
                            custom_name = item.get("name")
                            break

        if needs_name_prompt:
            suggested_name = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
            name, ok = QInputDialog.getText(
                self, "Name Resume", "Enter a display name for this resume:",
                QLineEdit.EchoMode.Normal,
                suggested_name
            )
            if ok and name:
                custom_name = name.strip()
            else:
                self.update_status("Resume loading cancelled.")
                return

        if not custom_name:
            custom_name = os.path.splitext(filename)[0]

        if needs_copy:
            try:
                print(f"Copying '{original_filepath}' to '{target_filepath}'...")
                shutil.copy2(original_filepath, target_filepath)
                print("Copy successful.")
            except (IOError, OSError, shutil.Error) as e:
                print(f"Error copying resume file: {e}")
                self.show_message_box("error", "File Error", f"Could not copy resume file:\n{e}")
                self.update_status("Failed to copy resume.")
                return

        self.update_status(f"Loading resume '{custom_name}'...", True)
        QApplication.processEvents()
        extracted_content = logic.extract_text_from_pdf(managed_path_str)
        self.update_status("", False)

        if extracted_content is None:
             self.show_message_box("error", "PDF Error", f"Failed to extract text from '{filename}'.")
             if self.setup_page_instance:
                 self.setup_page_instance.show_resume_selection_state(None)
             if self.pdf_filepath == managed_path_str:
                 self.pdf_filepath = None
                 self.resume_content = ""
             self.set_setup_controls_state(False)
             self.update_status("PDF extraction failed.")
             return

        self.pdf_filepath = managed_path_str
        self.resume_content = extracted_content
        self.update_status(f"Resume '{custom_name}' loaded.")
        self.set_setup_controls_state(True)
        self._add_recent_resume(custom_name, managed_path_str)
        if self.setup_page_instance:
            self.setup_page_instance.show_resume_selection_state(managed_path_str, custom_name)

    def _handle_openai_tts_change(self, check_state_value):
        checkbox = getattr(self.setup_page_instance, 'openai_tts_checkbox', None)
        is_checked = (check_state_value == Qt.CheckState.Checked.value)
        target_provider = "openai" if is_checked else tts.DEFAULT_PROVIDER
        print(f"OpenAI TTS change detected. Target provider: '{target_provider}'")
        if checkbox:
            checkbox.blockSignals(True)
        success = tts.set_provider(target_provider)
        if success:
            self.use_openai_tts = is_checked
            current_provider = tts.get_current_provider()
            self.update_status(f"TTS Provider set to: {current_provider}")
            print(f"Successfully set TTS provider to: {current_provider}")
        else:
            self.use_openai_tts = False
            if is_checked and checkbox:
                checkbox.setChecked(False)
            print(f"Failed to set provider '{target_provider}'. Attempting fallback...")
            if not tts.set_provider(tts.DEFAULT_PROVIDER):
                 potential = tts.get_potentially_available_providers()
                 final_fallback = potential[0] if potential else None
                 if final_fallback and tts.set_provider(final_fallback):
                      print(f"Fallback to first available '{final_fallback}' succeeded.")
                 else:
                      print("ERROR: Failed to set any TTS provider.")
                      self.show_message_box("error", "TTS Error", f"Failed to set TTS provider '{target_provider}' and could not fall back. Check console and dependencies/keyring.")
                      if checkbox:
                          checkbox.setEnabled(False)
                          checkbox.setToolTip("TTS provider error. Check console.")
            else:
                 print(f"Fallback to default provider '{tts.DEFAULT_PROVIDER}' succeeded.")
            current_provider = tts.get_current_provider()
            status_msg = f"Failed to set OpenAI TTS. Using: {current_provider or 'None'}"
            self.update_status(status_msg)
            if is_checked:
                 openai_keyring_info = ""
                 try:
                     openai_keyring_info = f"(Service: '{tts.tts_providers['openai'].KEYRING_SERVICE_NAME_OPENAI}')"
                 except (KeyError, AttributeError):
                     openai_keyring_info = "(Keyring details unavailable)"
                 self.show_message_box("warning", "OpenAI TTS Failed",
                                      f"Could not enable OpenAI TTS.\nPlease ensure:\n"
                                      f"- Dependencies are installed (openai, sounddevice, pydub, etc.).\n"
                                      f"- API key is stored correctly in keyring {openai_keyring_info}.\n"
                                      f"- FFmpeg is installed and accessible in PATH.\nCheck console logs for details. Currently using: {current_provider or 'None'}")
        if checkbox:
            checkbox.blockSignals(False)

    def update_submit_button_text(self, check_state_value=None):
        if check_state_value is not None:
            self.use_speech_input = (check_state_value == Qt.CheckState.Checked.value)
            print(f"Use Speech Input (STT) state changed to: {self.use_speech_input}")
        if not self.is_recording:
            self.set_recording_button_state('idle')
        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input_widget:
            is_text_mode = not self.use_speech_input
            submit_btn = getattr(self.interview_page_instance, 'submit_button', None)
            controls_generally_active = submit_btn and submit_btn.isEnabled() and not self.is_recording
            answer_input_widget.setReadOnly(not is_text_mode)
            answer_input_widget.setEnabled(is_text_mode and controls_generally_active)
            if is_text_mode and controls_generally_active:
                answer_input_widget.setFocus()
                answer_input_widget.setPlaceholderText("Type your answer here...")
            elif not is_text_mode:
                answer_input_widget.clear()
                answer_input_widget.setPlaceholderText("Click 'Record Answer' to speak...")
            else:
                 answer_input_widget.setPlaceholderText("Waiting for question or processing...")

    def select_resume_file(self):
        start_dir = os.path.expanduser("~")
        start_dir_native = os.path.normpath(start_dir)
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select New Resume PDF", start_dir_native, "PDF Files (*.pdf)"
        )
        if filepath:
            self._process_selected_resume({"path": filepath, "name": None})
        else:
            self.update_status("Resume selection cancelled.")

    def _handle_resume_widget_selected(self, resume_data: dict):
        print(f"ResumeWidget selected: {resume_data.get('name')}")
        if isinstance(resume_data, dict) and 'path' in resume_data:
            self._process_selected_resume(resume_data)
        else:
            print("Warning: Received invalid data from ResumeWidget click.")

    def _handle_add_new_jd(self):
        jd_text, ok = QInputDialog.getMultiLineText(
            self,
            "Add Job Description",
            "Paste the full job description text below:"
        )
        if ok and jd_text:
            jd_text = jd_text.strip()
            if not jd_text:
                self.show_message_box("warning", "Input Needed", "Job description text cannot be empty.")
                return
            name, ok_name = QInputDialog.getText(
                self,
                "Name Job Description",
                "Enter a short, unique name for this job description (e.g., 'Software Engineer - Acme'):"
            )
            if ok_name and name:
                name = name.strip()
                if not name:
                    self.show_message_box("warning", "Input Needed", "Job description name cannot be empty.")
                    return
                existing_names = [item.get("name") for item in self.config.get("recent_job_descriptions", [])]
                if name in existing_names:
                    reply = QMessageBox.question(self, 'Overwrite JD?',
                                                 f"A job description named '{name}' already exists. Overwrite it?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                 QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        return
                self._add_recent_jd(name, jd_text)
                self.selected_jd_name = name
                self.job_description_text = jd_text
                self._update_ui_from_state()
                self.update_status(f"Job description '{name}' added and selected.")
            else:
                self.update_status("Job description add cancelled (no name provided).")
        elif ok:
             self.show_message_box("warning", "Input Needed", "Job description text cannot be empty.")
        else:
            self.update_status("Job description add cancelled.")

    def _handle_jd_widget_selected(self, jd_data: dict):
        name = jd_data.get("name")
        text = jd_data.get("text")
        print(f"JDWidget selected: {name}")
        if name and text is not None:
            self.selected_jd_name = name
            self.job_description_text = text
            self._update_ui_from_state()
            self.update_status(f"Job description '{name}' selected.")
        else:
            print("Warning: Received invalid data from JDWidget click.")

    def start_interview_process(self):
        if not self.pdf_filepath or not self.resume_content:
            self.show_message_box("warning", "Input Missing", "Please select a valid resume PDF first.")
            return
        current_jd_text = self.job_description_text
        if self.use_openai_tts and "openai" not in tts.get_runtime_available_providers():
            self.show_message_box("error", "TTS Error", "OpenAI TTS selected but unavailable.")
            return
        print(f"Preparing Interview: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, STT={self.use_speech_input}, OpenAITTS={self.use_openai_tts}")
        self.reset_interview_state(clear_config=False)
        self.update_status(f"Generating {self.num_topics} questions...", True)
        self.set_setup_controls_state(False)
        upload_btn_widget = getattr(self.setup_page_instance, 'upload_resume_btn', None)
        add_jd_btn_widget = getattr(self.setup_page_instance, 'add_jd_btn', None)
        if upload_btn_widget: upload_btn_widget.setEnabled(False)
        if add_jd_btn_widget: add_jd_btn_widget.setEnabled(False)
        QApplication.processEvents()
        self.initial_questions = logic.generate_initial_questions(
            resume_text=self.resume_content,
            job_desc_text=current_jd_text,
            num_questions=self.num_topics
        )
        self.update_status("", False)
        pdf_loaded = bool(self.pdf_filepath)
        self.set_setup_controls_state(pdf_loaded)
        if upload_btn_widget: upload_btn_widget.setEnabled(True)
        if add_jd_btn_widget: add_jd_btn_widget.setEnabled(True)
        if not self.initial_questions:
            self.update_status("Error generating questions", False)
            self.show_message_box("error", "Gen Error", "Failed to generate questions.")
            return
        print(f"Generated {len(self.initial_questions)} questions.")
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        if len(self.initial_questions) < self.num_topics:
             print(f"Warn: Got {len(self.initial_questions)} questions (req {self.num_topics}).")
        self._go_to_interview_page()
        self.current_initial_q_index = 0
        self.start_next_topic()

    def start_next_topic(self):
        if not self.initial_questions:
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
            print(f"Asking Initial Question {self.current_initial_q_index + 1}: {self.current_topic_question}")
            self.display_question(raw_q_text)
        else:
            print("\n--- Interview Finished ---")
            self.update_status("Generating results...", True)
            self.disable_interview_controls()
            QApplication.processEvents()
            self.save_transcript_to_file()
            print("Generating summary review...")
            summary = logic.generate_summary_review(self.current_full_interview_history)
            print("Generating content score analysis...")
            content_score_data = logic.generate_content_score_analysis(self.current_full_interview_history)
            print("Generating qualification assessment...")
            assessment_data = logic.generate_qualification_assessment(self.resume_content, self.job_description_text, self.current_full_interview_history)
            self.update_status("Results ready.", False)
            if summary is None or summary.startswith(logic.ERROR_PREFIX):
                self.show_message_box("warning", "Summary Error", f"Could not generate summary.\n{summary or ''}")
            if assessment_data.get("error"):
                 if self.job_description_text:
                     self.show_message_box("warning", "Assessment Error", f"Could not generate assessment.\n{assessment_data.get('error', '')}")
            self._go_to_results_page(summary, assessment_data, content_score_data)

    def handle_answer_submission(self):
        if self.is_recording:
            print("Already recording, ignoring button press.")
            return
        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
        if self.use_speech_input:
            print("Record button clicked, starting STT...")
            self.disable_interview_controls(is_recording_stt=True)
            self.update_status_stt("STT_Status: Starting Mic...")
            if answer_input_widget:
                answer_input_widget.clear()
            topic_idx = self.current_initial_q_index + 1
            followup_idx = self.follow_up_count
            recording.start_speech_recognition(topic_idx, followup_idx)
        else:
            print("Submit button clicked, processing text answer.")
            if not answer_input_widget:
                print("Error: Answer input widget not found.")
                self.show_message_box("error", "Internal Error", "Cannot find answer input field.")
                return
            user_answer = answer_input_widget.toPlainText().strip()
            if not user_answer:
                self.show_message_box("warning", "Input Required", "Please type your answer before submitting.")
                return
            self.process_answer(user_answer)

    def update_status_stt(self, message):
        if not self.status_bar_label:
            return
        display_message = message
        button_state = 'idle'
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
             button_state = 'idle'
             self.is_recording = False
        elif message.startswith("STT_Error:"):
             error_detail = message.split(':', 1)[1].strip()
             display_message = f"[STT Error: {error_detail}]"
             button_state = 'idle'
             self.is_recording = False
        elif message.startswith("STT_Success:"):
             display_message = "[Speech Recognized Successfully]"
             button_state = 'idle'
        self.status_bar_label.setText(display_message)
        self.set_recording_button_state(button_state)
        QApplication.processEvents()

    def check_stt_queue(self):
        try:
            result = recording.stt_result_queue.get_nowait()
            print(f"STT Queue Received: {result}")
            if result.startswith("STT_Status:") or result.startswith("STT_Warning:") or result.startswith("STT_Error:"):
                self.update_status_stt(result)
                if result.startswith("STT_Warning:") or result.startswith("STT_Error:"):
                     if not self.is_recording:
                          self.enable_interview_controls()
            elif result.startswith("STT_Success:"):
                self.is_recording = False
                self.update_status_stt(result)
                transcript = result.split(":", 1)[1].strip()
                answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
                if answer_input_widget:
                    answer_input_widget.setEnabled(True)
                    answer_input_widget.setReadOnly(False)
                    answer_input_widget.setText(transcript)
                    answer_input_widget.setReadOnly(True)
                    answer_input_widget.setEnabled(False)
                self.process_answer(transcript)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error checking STT Queue: {e}")
            if self.is_recording:
                self.is_recording = False
                self.set_recording_button_state('idle')
                self.enable_interview_controls()
            self.update_status(f"Error checking speech recognition: {e}")

    def process_answer(self, user_answer):
        last_q = self.last_question_asked or "[Unknown Question]"
        print(f"Processing answer for Q: '{last_q[:50]}...' -> A: '{user_answer[:50]}...'")
        q_data = {"q": last_q, "a": user_answer}
        self.current_topic_history.append(q_data)
        self.current_full_interview_history.append(q_data)
        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")
        answer_input_widget = getattr(self.interview_page_instance, 'answer_input', None)
        if answer_input_widget:
            answer_input_widget.clear()
        self.disable_interview_controls()
        self.update_status("Generating response from interviewer...", True)
        QApplication.processEvents()
        proceed_to_next_topic = False
        if self.follow_up_count < self.max_follow_ups:
            follow_up_q = logic.generate_follow_up_question(
                self.current_topic_question,
                user_answer,
                self.current_topic_history
            )
            self.update_status("", False)
            if follow_up_q and follow_up_q.strip() and follow_up_q != "[END TOPIC]":
                self.follow_up_count += 1
                print(f"Asking Follow-up Question ({self.follow_up_count}/{self.max_follow_ups}): {follow_up_q}")
                self.display_question(follow_up_q)
            elif follow_up_q == "[END TOPIC]":
                print("Model signalled to end the current topic.")
                proceed_to_next_topic = True
            else:
                print("Follow-up question generation failed or returned invalid response.")
                self.show_message_box("warning", "Generation Error", "Error generating follow-up question. Moving to the next topic.")
                proceed_to_next_topic = True
        else:
             print(f"Max follow-ups ({self.max_follow_ups}) reached for this topic.")
             self.update_status("", False)
             proceed_to_next_topic = True
        if proceed_to_next_topic:
             self.current_initial_q_index += 1
             self.start_next_topic()
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def _save_report(self):
        if not self.results_page_instance:
            self.show_message_box("warning", "Internal Error", "Results page not found.")
            return
        content_score = 0
        content_analysis_text = "N/A"
        content_score_error = None
        if self.last_content_score_data:
            content_score = self.last_content_score_data.get('score', 0)
            content_analysis_text = self.last_content_score_data.get('analysis_text', 'N/A')
            content_score_error = self.last_content_score_data.get('error')
        assessment_error = None
        requirements_list = []
        overall_fit_text = "N/A"
        if self.last_assessment_data:
            assessment_error = self.last_assessment_data.get("error")
            requirements_list = self.last_assessment_data.get("requirements", [])
            overall_fit_text = self.last_assessment_data.get("overall_fit", "N/A")
        is_content_error = bool(content_score_error)
        is_assessment_error = bool(assessment_error)
        is_assessment_empty = not requirements_list and overall_fit_text == "N/A"
        content_widget = getattr(self.results_page_instance, 'content_score_text_edit', None)
        placeholder_summary_check = "*Content score analysis loading...*"
        placeholder_overall_fit_check = "<b>Overall Fit Assessment:</b> *Loading...*"
        current_content_text = content_widget.toPlainText().strip() if content_widget else ""
        current_overall_label = getattr(self.results_page_instance, 'overall_fit_label', None)
        current_overall_text = current_overall_label.text() if current_overall_label else ""
        if current_content_text == placeholder_summary_check and current_overall_text == placeholder_overall_fit_check :
             self.show_message_box("warning", "No Data", "Results have not been generated yet, nothing to save.")
             return
        report_lines = [
            f"Interview Report", f"{'='*16}\n",
            f"Speech Delivery Score: {FIXED_SPEECH_SCORE}%", f"{'-'*23}",
            FIXED_SPEECH_DESCRIPTION.replace('**', '').replace('*', ''), "\n",
            f"Response Content Score: {content_score}%", f"{'-'*24}"
        ]
        if content_score_error:
            report_lines.append(f"Content Analysis Error: {content_score_error}")
        else:
            report_lines.append(content_analysis_text.replace('**', '').replace('*', ''))
        report_lines.append("\n")
        report_lines.extend([f"Job Fit Analysis", f"{'-'*16}"])
        if assessment_error:
            report_lines.append(f"Assessment Error: {assessment_error}")
        elif requirements_list:
            for i, req in enumerate(requirements_list):
                report_lines.append(f"\nRequirement {i+1}: {req.get('requirement', 'N/A')}")
                report_lines.append(f"  Assessment: {req.get('assessment', 'N/A')}")
                report_lines.append(f"  Resume Evidence: {req.get('resume_evidence', 'N/A')}")
                report_lines.append(f"  Interview Evidence: {req.get('transcript_evidence', 'N/A')}")
            cleaned_overall_fit = overall_fit_text.replace('<b>','').replace('</b>','').replace('*','')
            report_lines.append(f"\nOverall Fit Assessment: {cleaned_overall_fit}")
        else:
            report_lines.append("No specific requirements assessment details available.")
            cleaned_overall_fit = overall_fit_text.replace('<b>','').replace('</b>','').replace('*','')
            if cleaned_overall_fit != "N/A":
                report_lines.append(f"\nOverall Fit Assessment: {cleaned_overall_fit}")
        report_content = "\n".join(report_lines)
        default_filename = "interview_report.txt"
        if self.pdf_filepath:
            base = os.path.splitext(os.path.basename(self.pdf_filepath))[0]
            default_filename = f"{base}_interview_report.txt"
        save_dir = RECORDINGS_DIR
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as e:
            print(f"Warn: Cannot create save dir {save_dir}: {e}")
            save_dir = os.path.expanduser("~")
        default_path = os.path.join(save_dir, default_filename)
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Interview Report", default_path, "Text Files (*.txt);;All Files (*)")
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                self.update_status(f"Report saved to {os.path.basename(filepath)}.")
                self.show_message_box("info", "Report Saved", f"Saved to:\n{filepath}")
            except Exception as e:
                print(f"Error saving report: {e}")
                self.show_message_box("error", "Save Error", f"Could not save:\n{e}")
        else:
            self.update_status("Report save cancelled.")

    def _open_recordings_folder(self):
        folder_path = RECORDINGS_DIR
        print(f"Attempting to open user recordings folder: {folder_path}")
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"Created recordings directory before opening: {folder_path}")
            except OSError as e:
                 print(f"Error creating recordings directory: {e}")
                 self.show_message_box("error", "Folder Error", f"Could not create the recordings folder:\n{folder_path}\nError: {e}")
                 self.update_status("Failed to create recordings folder.")
                 return
        url = QUrl.fromLocalFile(folder_path)
        if not QDesktopServices.openUrl(url):
            print(f"QDesktopServices failed to open {folder_path}. Trying platform-specific fallback...")
            self.update_status("Opening folder (using fallback)...")
            try:
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(['explorer', os.path.normpath(folder_path)])
                elif system == "Darwin":
                    subprocess.Popen(["open", folder_path])
                else:
                    subprocess.Popen(["xdg-open", folder_path])
                self.update_status("Opened recordings folder (using fallback).")
            except FileNotFoundError:
                 cmd = "explorer" if system == "Windows" else ("open" if system == "Darwin" else "xdg-open")
                 print(f"Error: Command '{cmd}' not found in system PATH.")
                 self.show_message_box("error", "Open Error", f"Could not find the command ('{cmd}') needed to open the folder.\nPlease open the folder manually:\n{folder_path}")
                 self.update_status("Failed to open folder (command missing).")
            except Exception as e:
                print(f"Fallback open error for {folder_path}: {e}")
                self.show_message_box("error", "Open Error", f"Could not open the recordings folder:\n{folder_path}\nError: {e}")
                self.update_status("Failed to open recordings folder.")
        else:
            self.update_status("Opened recordings folder.")

    def closeEvent(self, event):
        print("Close event triggered. Cleaning up...")
        if hasattr(self, 'stt_timer'):
            self.stt_timer.stop()
            print("STT queue check timer stopped.")
        print("Attempting to stop any active TTS playback...")
        try:
            tts.stop_playback()
            print("TTS stop signal sent (if applicable).")
        except Exception as tts_stop_err:
            print(f"Error trying to stop TTS playback: {tts_stop_err}")
        if self.is_recording:
            print("Signalling recording thread to stop (if implemented)...")
            # Example:
            # if hasattr(recording, 'stop_recording_flag'):
            #     recording.stop_recording_flag.set()
        print("Main window cleanup attempts complete.")
        event.accept()