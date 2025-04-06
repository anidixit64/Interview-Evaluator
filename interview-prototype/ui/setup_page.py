# ui/setup_page.py
"""
Defines the Setup Page QWidget for the Interview App.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QCheckBox, QGroupBox, QSizePolicy, QFrame,
    QSpacerItem, QScrollArea
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSize

try:
    from core import logic, tts
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from core import logic, tts

from .components import _load_icon
from .resume_widget import ResumeWidget
from .jd_widget import JDWidget # Import the new JD Widget

class SetupPage(QWidget):
    """
    The setup page widget allowing users to select/load resume, configure, and start.
    """
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._selected_resume_widget = None
        self._selected_jd_widget = None
        self._init_ui()

    def _init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(20)

        pw = self.parent_window

        # Icons
        upload_icon = _load_icon(pw.icon_path, "upload.png")
        add_icon = _load_icon(pw.icon_path, "plus_alt.png") # Ensure this icon exists
        start_icon = _load_icon(pw.icon_path, "play.png")
        plus_icon = _load_icon(pw.icon_path, "plus.png")
        minus_icon = _load_icon(pw.icon_path, "minus.png")
        button_icon_size = QSize(16, 16)

        # --- Resume Section ---
        resume_group = QGroupBox("Load Resume")
        resume_group.setFont(pw.font_large_bold)
        resume_layout = QVBoxLayout(resume_group)
        resume_layout.setSpacing(10)
        list_label_res = QLabel("Select a recent resume or upload a new one:")
        list_label_res.setFont(pw.font_default)
        self.resume_scroll_area = QScrollArea()
        self.resume_scroll_area.setWidgetResizable(True)
        self.resume_scroll_area.setObjectName("resumeScrollArea")
        self.resume_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.resume_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.resume_scroll_area.setMinimumHeight(80)
        self.resume_scroll_area.setMaximumHeight(180)
        self.resume_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.resume_list_container = QWidget()
        self.resume_list_layout = QVBoxLayout(self.resume_list_container)
        self.resume_list_layout.setContentsMargins(2, 2, 2, 2)
        self.resume_list_layout.setSpacing(4)
        self.resume_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.resume_scroll_area.setWidget(self.resume_list_container)
        self.resume_status_label = QLabel("No resume selected.")
        self.resume_status_label.setFont(pw.font_small)
        self.resume_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_resume_btn = QPushButton(" Upload New Resume PDF...")
        if upload_icon: self.upload_resume_btn.setIcon(upload_icon)
        self.upload_resume_btn.setIconSize(pw.icon_size)
        self.upload_resume_btn.setFont(pw.font_default)
        self.upload_resume_btn.clicked.connect(pw.select_resume_file)
        resume_layout.addWidget(list_label_res)
        resume_layout.addWidget(self.resume_scroll_area)
        resume_layout.addWidget(self.resume_status_label)
        resume_layout.addWidget(self.upload_resume_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Configuration Section ---
        config_group = QGroupBox("Configure Interview")
        config_group.setFont(pw.font_large_bold)
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(25)
        topics_widget = QWidget()
        topics_inner_layout = QHBoxLayout(topics_widget)
        topics_inner_layout.setContentsMargins(0,0,0,0)
        topics_inner_layout.setSpacing(5)
        topics_label_prefix = QLabel("Topics:")
        topics_label_prefix.setFont(pw.font_default)
        self.topic_minus_btn = QPushButton("")
        self.topic_minus_btn.setObjectName("adjustButton")
        if minus_icon: self.topic_minus_btn.setIcon(minus_icon)
        self.topic_minus_btn.setIconSize(button_icon_size)
        self.topic_minus_btn.setFixedSize(QSize(28, 28))
        self.topic_minus_btn.setToolTip("Decrease topics")
        self.topic_minus_btn.clicked.connect(lambda: pw._adjust_value('topics', -1))
        self.num_topics_label = QLabel(str(pw.num_topics))
        self.num_topics_label.setFont(pw.font_default)
        self.num_topics_label.setMinimumWidth(25)
        self.num_topics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.topic_plus_btn = QPushButton("")
        self.topic_plus_btn.setObjectName("adjustButton")
        if plus_icon: self.topic_plus_btn.setIcon(plus_icon)
        self.topic_plus_btn.setIconSize(button_icon_size)
        self.topic_plus_btn.setFixedSize(QSize(28, 28))
        self.topic_plus_btn.setToolTip("Increase topics")
        self.topic_plus_btn.clicked.connect(lambda: pw._adjust_value('topics', +1))
        topics_inner_layout.addWidget(topics_label_prefix)
        topics_inner_layout.addWidget(self.topic_minus_btn)
        topics_inner_layout.addWidget(self.num_topics_label)
        topics_inner_layout.addWidget(self.topic_plus_btn)
        config_layout.addWidget(topics_widget)
        followups_widget = QWidget()
        followups_inner_layout = QHBoxLayout(followups_widget)
        followups_inner_layout.setContentsMargins(0,0,0,0)
        followups_inner_layout.setSpacing(5)
        followups_label_prefix = QLabel("Max Follow-ups:")
        followups_label_prefix.setFont(pw.font_default)
        self.followup_minus_btn = QPushButton("")
        self.followup_minus_btn.setObjectName("adjustButton")
        if minus_icon: self.followup_minus_btn.setIcon(minus_icon)
        self.followup_minus_btn.setIconSize(button_icon_size)
        self.followup_minus_btn.setFixedSize(QSize(28, 28))
        self.followup_minus_btn.setToolTip("Decrease follow-ups")
        self.followup_minus_btn.clicked.connect(lambda: pw._adjust_value('followups', -1))
        self.max_follow_ups_label = QLabel(str(pw.max_follow_ups))
        self.max_follow_ups_label.setFont(pw.font_default)
        self.max_follow_ups_label.setMinimumWidth(25)
        self.max_follow_ups_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.followup_plus_btn = QPushButton("")
        self.followup_plus_btn.setObjectName("adjustButton")
        if plus_icon: self.followup_plus_btn.setIcon(plus_icon)
        self.followup_plus_btn.setIconSize(button_icon_size)
        self.followup_plus_btn.setFixedSize(QSize(28, 28))
        self.followup_plus_btn.setToolTip("Increase follow-ups")
        self.followup_plus_btn.clicked.connect(lambda: pw._adjust_value('followups', +1))
        followups_inner_layout.addWidget(followups_label_prefix)
        followups_inner_layout.addWidget(self.followup_minus_btn)
        followups_inner_layout.addWidget(self.max_follow_ups_label)
        followups_inner_layout.addWidget(self.followup_plus_btn)
        config_layout.addWidget(followups_widget)
        config_line = QFrame()
        config_line.setFrameShape(QFrame.Shape.VLine)
        config_line.setFrameShadow(QFrame.Shadow.Sunken)
        config_layout.addWidget(config_line)
        self.speech_checkbox = QCheckBox("Use Speech Input (STT)")
        self.speech_checkbox.setFont(pw.font_default)
        self.speech_checkbox.stateChanged.connect(pw.update_submit_button_text)
        config_layout.addWidget(self.speech_checkbox)
        self.openai_tts_checkbox = QCheckBox("Use OpenAI TTS")
        self.openai_tts_checkbox.setFont(pw.font_default)
        openai_available = "openai" in tts.get_potentially_available_providers()
        if openai_available:
            self.openai_tts_checkbox.setToolTip("Requires API key in keyring.")
            self.openai_tts_checkbox.stateChanged.connect(pw._handle_openai_tts_change)
        else:
            self.openai_tts_checkbox.setToolTip("OpenAI TTS unavailable.")
            self.openai_tts_checkbox.setEnabled(False)
        config_layout.addWidget(self.openai_tts_checkbox)
        config_layout.addStretch()

        # --- Job Description Section ---
        jd_group = QGroupBox("Job Description (Optional)")
        jd_group.setFont(pw.font_large_bold)
        jd_layout = QVBoxLayout(jd_group)
        jd_layout.setSpacing(10)
        list_label_jd = QLabel("Select recent or add new job description:")
        list_label_jd.setFont(pw.font_default)
        self.jd_scroll_area = QScrollArea()
        self.jd_scroll_area.setWidgetResizable(True)
        self.jd_scroll_area.setObjectName("jdScrollArea")
        self.jd_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.jd_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.jd_scroll_area.setMinimumHeight(60)
        self.jd_scroll_area.setMaximumHeight(120)
        self.jd_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.jd_list_container = QWidget()
        self.jd_list_layout = QVBoxLayout(self.jd_list_container)
        self.jd_list_layout.setContentsMargins(2, 2, 2, 2)
        self.jd_list_layout.setSpacing(4)
        self.jd_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.jd_scroll_area.setWidget(self.jd_list_container)
        self.add_jd_btn = QPushButton(" Add New Job Description...")
        if add_icon: self.add_jd_btn.setIcon(add_icon)
        self.add_jd_btn.setIconSize(pw.icon_size)
        self.add_jd_btn.setFont(pw.font_default)
        self.add_jd_btn.clicked.connect(pw._handle_add_new_jd)
        self.jd_status_label = QLabel("No job description selected.")
        self.jd_status_label.setFont(pw.font_small)
        self.jd_display_edit = QTextEdit()
        self.jd_display_edit.setReadOnly(True)
        self.jd_display_edit.setFont(pw.font_small)
        self.jd_display_edit.setPlaceholderText("Selected job description text will appear here...")
        self.jd_display_edit.setObjectName("jdDisplayEdit")
        self.jd_display_edit.setMinimumHeight(80)
        self.jd_display_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        jd_layout.addWidget(list_label_jd)
        jd_layout.addWidget(self.jd_scroll_area)
        jd_layout.addWidget(self.add_jd_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        jd_layout.addWidget(self.jd_status_label)
        jd_layout.addWidget(self.jd_display_edit, stretch=1)

        # --- Add Groups to Page Layout ---
        page_layout.addWidget(resume_group)
        page_layout.addWidget(config_group)
        page_layout.addWidget(jd_group, stretch=1)

        # --- Start Button ---
        start_button_layout = QHBoxLayout()
        self.start_interview_btn = QPushButton("Next: Start Interview")
        if start_icon:
            self.start_interview_btn.setIcon(start_icon)
        self.start_interview_btn.setIconSize(pw.icon_size)
        self.start_interview_btn.setFont(pw.font_bold)
        self.start_interview_btn.setFixedHeight(40)
        self.start_interview_btn.clicked.connect(pw.start_interview_process)
        start_button_layout.addStretch()
        start_button_layout.addWidget(self.start_interview_btn)
        start_button_layout.addStretch()
        page_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        page_layout.addLayout(start_button_layout)

        self.setLayout(page_layout)

    def update_widgets_from_state(self,
                                  recent_resumes_data: list[dict],
                                  current_selection_path: str | None,
                                  recent_jd_data: list[dict],
                                  current_jd_name: str | None):
        pw = self.parent_window
        pdf_loaded = bool(current_selection_path)

        # Populate Recent Resumes
        while (item := self.resume_list_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
        self._selected_resume_widget = None
        if recent_resumes_data:
            for item_data in recent_resumes_data:
                path = item_data.get("path")
                if path:
                    resume_widget = ResumeWidget(item_data, self)
                    resume_widget.resume_selected.connect(pw._handle_resume_widget_selected)
                    self.resume_list_layout.addWidget(resume_widget)
                    if path == current_selection_path:
                        resume_widget.set_selected(True)
                        self._selected_resume_widget = resume_widget
        else:
            placeholder_label_res = QLabel("<i>No recent resumes found. Upload one below.</i>")
            placeholder_label_res.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder_label_res.setFont(pw.font_small)
            self.resume_list_layout.addWidget(placeholder_label_res)
        self.resume_list_layout.addStretch(1)
        current_selection_name_res = None
        if self._selected_resume_widget:
            current_selection_name_res = self._selected_resume_widget.resume_data.get("name")
        self.show_resume_selection_state(current_selection_path, current_selection_name_res)

        # Populate Recent Job Descriptions
        while (item := self.jd_list_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
        self._selected_jd_widget = None
        if recent_jd_data:
            for item_data in recent_jd_data:
                name = item_data.get("name")
                if name:
                    jd_widget = JDWidget(item_data, self)
                    jd_widget.jd_selected.connect(pw._handle_jd_widget_selected)
                    self.jd_list_layout.addWidget(jd_widget)
                    if name == current_jd_name:
                        jd_widget.set_selected(True)
                        self._selected_jd_widget = jd_widget
        else:
            placeholder_label_jd = QLabel("<i>No recent JDs found. Add one below.</i>")
            placeholder_label_jd.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder_label_jd.setFont(pw.font_small)
            self.jd_list_layout.addWidget(placeholder_label_jd)
        self.jd_list_layout.addStretch(1)
        self.show_jd_selection_state(current_jd_name)

        # Update Config Widgets
        if hasattr(self, 'num_topics_label'):
            self.num_topics_label.setText(str(pw.num_topics))
        if hasattr(self, 'max_follow_ups_label'):
            self.max_follow_ups_label.setText(str(pw.max_follow_ups))
        if hasattr(self, 'speech_checkbox'):
            self.speech_checkbox.blockSignals(True)
            self.speech_checkbox.setChecked(pw.use_speech_input)
            self.speech_checkbox.blockSignals(False)
        if hasattr(self, 'openai_tts_checkbox'):
             self.openai_tts_checkbox.blockSignals(True)
             self.openai_tts_checkbox.setChecked(pw.use_openai_tts)
             openai_deps_met = "openai" in tts.get_potentially_available_providers()
             self.openai_tts_checkbox.setEnabled(pdf_loaded and openai_deps_met)
             self.openai_tts_checkbox.blockSignals(False)

        self.set_controls_enabled_state(pdf_loaded)

    def show_resume_selection_state(self, selected_path: str | None, selected_name: str | None = None):
        if selected_path:
            display_name = selected_name or os.path.basename(selected_path)
            self.resume_status_label.setText(f"Selected: {display_name}")
        else:
            self.resume_status_label.setText("No resume selected.")
        # Highlighting is done in update_widgets_from_state

    def show_jd_selection_state(self, selected_jd_name: str | None):
        selected_jd_text = ""
        newly_selected_widget = None
        for i in range(self.jd_list_layout.count()):
            item = self.jd_list_layout.itemAt(i)
            if item is None: continue
            widget = item.widget()
            if isinstance(widget, JDWidget):
                is_this_one_selected = (widget.jd_data.get("name") == selected_jd_name)
                widget.set_selected(is_this_one_selected)
                if is_this_one_selected:
                    newly_selected_widget = widget
                    selected_jd_text = widget.jd_data.get("text", "")
        self._selected_jd_widget = newly_selected_widget
        if selected_jd_name:
            self.jd_status_label.setText(f"Selected JD: {selected_jd_name}")
            self.jd_display_edit.setPlainText(selected_jd_text)
        else:
            self.jd_status_label.setText("No job description selected.")
            self.jd_display_edit.clear()
            self.jd_display_edit.setPlaceholderText("Selected job description text will appear here...")

    def set_controls_enabled_state(self, pdf_loaded):
        controls_to_manage = [
            (getattr(self, 'topic_minus_btn', None), True),
            (getattr(self, 'topic_plus_btn', None), True),
            (getattr(self, 'num_topics_label', None), True),
            (getattr(self, 'followup_minus_btn', None), True),
            (getattr(self, 'followup_plus_btn', None), True),
            (getattr(self, 'max_follow_ups_label', None), True),
            (getattr(self, 'speech_checkbox', None), True),
            (getattr(self, 'start_interview_btn', None), True),
            (getattr(self, 'openai_tts_checkbox', None), False)
        ]
        openai_deps_met = "openai" in tts.get_potentially_available_providers()
        for widget, _ in controls_to_manage:
            if widget:
                should_enable = pdf_loaded
                if widget == self.openai_tts_checkbox:
                    should_enable = pdf_loaded and openai_deps_met
                widget.setEnabled(should_enable)
        if hasattr(self, 'upload_resume_btn'):
            self.upload_resume_btn.setEnabled(True)
        if hasattr(self, 'add_jd_btn'):
            self.add_jd_btn.setEnabled(True)