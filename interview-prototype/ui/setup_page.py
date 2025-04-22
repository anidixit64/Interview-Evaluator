# ui/setup_page.py
import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QCheckBox, QGroupBox, QSizePolicy, QFrame,
    QSpacerItem, QScrollArea, QToolButton
)
from PyQt6.QtGui import QFont, QIcon, QResizeEvent
from PyQt6.QtCore import Qt, QSize, QRect

try:
    from core import logic, tts
    from .components import _load_icon
    from .resume_widget import ResumeWidget
    from .jd_widget import JDWidget
except ImportError:
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    )
    from core import logic, tts
    from ui.components import _load_icon
    from ui.resume_widget import ResumeWidget
    from ui.jd_widget import JDWidget


class SetupPage(QWidget):
    SIDEBAR_MIN_WIDTH = 240

    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._selected_resume_widget = None
        self._selected_jd_widget = None
        self.sidebar_frame = QFrame(self)

        self._init_ui()

        if self.sidebar_frame.layout():
            self.sidebar_frame.layout().activate()
        self._update_sidebar_geometry()
        self.sidebar_frame.hide()

    def _init_ui(self):
        pw = self.parent_window

        font_default_xxl = getattr(pw, 'font_default_xxl', QFont("Arial", 16))
        font_bold_xxl = getattr(
            pw, 'font_bold_xxl', QFont("Arial", 16, QFont.Weight.Bold)
        )
        font_small_xxl = getattr(pw, 'font_small_xxl', QFont("Arial", 15))
        font_group_title_xxl = getattr(
            pw, 'font_group_title_xxl', QFont("Arial", 18, QFont.Weight.Bold)
        )

        icon_path = getattr(pw, 'icon_path', 'icons')
        upload_icon = _load_icon(icon_path, "upload.png")
        add_icon = _load_icon(icon_path, "plus_alt.png")
        start_icon = _load_icon(icon_path, "play.png")
        plus_icon = _load_icon(icon_path, "plus.png")
        minus_icon = _load_icon(icon_path, "minus.png")
        menu_icon = _load_icon(icon_path, "menu.png")
        close_icon = _load_icon(icon_path, "cross_circle.png")

        button_icon_size = QSize(28, 28)
        small_button_icon_size = QSize(22, 22)
        toggle_icon_size = QSize(44, 44)
        adjust_button_size = QSize(44, 44)
        action_button_height = 55
        start_button_height = 60
        sidebar_close_icon_size = QSize(38, 38)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(15, 10, 15, 10)

        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setObjectName("sidebarToggleButton")
        if menu_icon and not menu_icon.isNull():
            self.sidebar_toggle_btn.setIcon(menu_icon)
        else:
            self.sidebar_toggle_btn.setText("☰")
            self.sidebar_toggle_btn.setFont(font_default_xxl)
            print("Warning: Could not load menu.png icon for sidebar toggle.")
        self.sidebar_toggle_btn.setIconSize(toggle_icon_size)
        self.sidebar_toggle_btn.setFixedSize(toggle_icon_size + QSize(12, 12))
        self.sidebar_toggle_btn.setToolTip("Toggle Sidebar Settings")
        self.sidebar_toggle_btn.setCheckable(True)
        self.sidebar_toggle_btn.setChecked(False)
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar_from_button)

        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(self.sidebar_toggle_btn)

        self.main_content_frame = QFrame()
        self.main_content_frame.setObjectName("mainContentFrame")
        self.main_content_frame.setFrameShape(QFrame.Shape.NoFrame)

        main_content_layout = QVBoxLayout(self.main_content_frame)
        main_content_layout.setContentsMargins(45, 30, 45, 45)
        main_content_layout.setSpacing(45)

        page_layout.addLayout(top_bar_layout)
        page_layout.addWidget(self.main_content_frame, stretch=1)

        self.sidebar_frame.setObjectName("setupSidebar")
        self.sidebar_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.sidebar_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.sidebar_frame.setMinimumWidth(self.SIDEBAR_MIN_WIDTH)
        self.sidebar_frame.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )

        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_margins = QSize(30, 30)
        sidebar_layout.setContentsMargins(
            self.sidebar_margins.width(),
            15,
            self.sidebar_margins.width(),
            self.sidebar_margins.height()
        )
        sidebar_layout.setSpacing(35)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        sidebar_top_bar_layout = QHBoxLayout()
        sidebar_top_bar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_top_bar_layout.addStretch(1)

        self.sidebar_close_btn = QToolButton()
        self.sidebar_close_btn.setObjectName("sidebarCloseButton")
        if close_icon and not close_icon.isNull():
            self.sidebar_close_btn.setIcon(close_icon)
        else:
            self.sidebar_close_btn.setText("X")
            print("Warning: Could not load close icon (e.g., cross_circle.png).")
        self.sidebar_close_btn.setIconSize(sidebar_close_icon_size)
        self.sidebar_close_btn.setFixedSize(sidebar_close_icon_size + QSize(10, 10))
        self.sidebar_close_btn.setToolTip("Close Settings")
        self.sidebar_close_btn.clicked.connect(self.hide_sidebar)

        sidebar_top_bar_layout.addWidget(self.sidebar_close_btn)

        sidebar_layout.addLayout(sidebar_top_bar_layout)
        sidebar_layout.addSpacerItem(
            QSpacerItem(10, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        sidebar_config_group = QGroupBox("Interview Settings")
        sidebar_config_group.setFont(font_group_title_xxl)

        sidebar_config_layout = QVBoxLayout(sidebar_config_group)
        sidebar_config_layout.setSpacing(30)
        sidebar_config_layout.setContentsMargins(25, 25, 25, 25)
        sidebar_config_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        topics_section_layout = QVBoxLayout()
        topics_section_layout.setSpacing(8)

        topics_label = QLabel("Topics:")
        topics_label.setFont(font_default_xxl)
        topics_section_layout.addWidget(topics_label)

        topics_button_layout = QHBoxLayout()
        topics_button_layout.setSpacing(10)

        self.topic_minus_btn = QPushButton("")
        self.topic_minus_btn.setObjectName("adjustButton")
        if minus_icon:
            self.topic_minus_btn.setIcon(minus_icon)
        self.topic_minus_btn.setIconSize(small_button_icon_size)
        self.topic_minus_btn.setFixedSize(adjust_button_size)
        self.topic_minus_btn.setToolTip("Decrease topics")
        self.topic_minus_btn.clicked.connect(lambda: pw._adjust_value('topics', -1))

        self.num_topics_label = QLabel(str(pw.num_topics))
        self.num_topics_label.setFont(font_default_xxl)
        self.num_topics_label.setMinimumWidth(50)
        self.num_topics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.topic_plus_btn = QPushButton("")
        self.topic_plus_btn.setObjectName("adjustButton")
        if plus_icon:
            self.topic_plus_btn.setIcon(plus_icon)
        self.topic_plus_btn.setIconSize(small_button_icon_size)
        self.topic_plus_btn.setFixedSize(adjust_button_size)
        self.topic_plus_btn.setToolTip("Increase topics")
        self.topic_plus_btn.clicked.connect(lambda: pw._adjust_value('topics', +1))

        topics_button_layout.addWidget(self.topic_minus_btn)
        topics_button_layout.addWidget(self.num_topics_label)
        topics_button_layout.addWidget(self.topic_plus_btn)
        topics_button_layout.addStretch(1)
        topics_section_layout.addLayout(topics_button_layout)

        sidebar_config_layout.addLayout(topics_section_layout)

        followups_section_layout = QVBoxLayout()
        followups_section_layout.setSpacing(8)

        followups_label = QLabel("Max Follow-ups per Topic:")
        followups_label.setFont(font_default_xxl)
        followups_section_layout.addWidget(followups_label)

        followups_button_layout = QHBoxLayout()
        followups_button_layout.setSpacing(10)

        self.followup_minus_btn = QPushButton("")
        self.followup_minus_btn.setObjectName("adjustButton")
        if minus_icon:
            self.followup_minus_btn.setIcon(minus_icon)
        self.followup_minus_btn.setIconSize(small_button_icon_size)
        self.followup_minus_btn.setFixedSize(adjust_button_size)
        self.followup_minus_btn.setToolTip("Decrease follow-ups")
        self.followup_minus_btn.clicked.connect(lambda: pw._adjust_value('followups', -1))

        self.max_follow_ups_label = QLabel(str(pw.max_follow_ups))
        self.max_follow_ups_label.setFont(font_default_xxl)
        self.max_follow_ups_label.setMinimumWidth(50)
        self.max_follow_ups_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.followup_plus_btn = QPushButton("")
        self.followup_plus_btn.setObjectName("adjustButton")
        if plus_icon:
            self.followup_plus_btn.setIcon(plus_icon)
        self.followup_plus_btn.setIconSize(small_button_icon_size)
        self.followup_plus_btn.setFixedSize(adjust_button_size)
        self.followup_plus_btn.setToolTip("Increase follow-ups")
        self.followup_plus_btn.clicked.connect(lambda: pw._adjust_value('followups', +1))

        followups_button_layout.addWidget(self.followup_minus_btn)
        followups_button_layout.addWidget(self.max_follow_ups_label)
        followups_button_layout.addWidget(self.followup_plus_btn)
        followups_button_layout.addStretch(1)
        followups_section_layout.addLayout(followups_button_layout)

        sidebar_config_layout.addLayout(followups_section_layout)

        self.speech_checkbox = QCheckBox("Use Speech Input (STT)")
        self.speech_checkbox.setFont(font_default_xxl)
        self.speech_checkbox.stateChanged.connect(pw.update_submit_button_text)
        sidebar_config_layout.addWidget(self.speech_checkbox)

        self.openai_tts_checkbox = QCheckBox("Use OpenAI TTS")
        self.openai_tts_checkbox.setFont(font_default_xxl)
        openai_available = "openai" in tts.get_potentially_available_providers()
        if openai_available:
            self.openai_tts_checkbox.setToolTip("Requires API key in keyring.")
            self.openai_tts_checkbox.stateChanged.connect(pw._handle_openai_tts_change)
        else:
            self.openai_tts_checkbox.setToolTip("OpenAI TTS unavailable.")
            self.openai_tts_checkbox.setEnabled(False)
        sidebar_config_layout.addWidget(self.openai_tts_checkbox)

        sidebar_config_layout.addStretch(1)

        sidebar_layout.addWidget(sidebar_config_group, stretch=1)

        resume_group = QGroupBox()
        resume_group.setFont(font_group_title_xxl)

        resume_layout = QVBoxLayout(resume_group)
        resume_layout.setSpacing(20)
        resume_layout.setContentsMargins(25, 25, 25, 25)

        list_label_res = QLabel("Resume:")
        list_label_res.setFont(font_group_title_xxl)

        self.resume_scroll_area = QScrollArea()
        self.resume_scroll_area.setWidgetResizable(True)
        self.resume_scroll_area.setObjectName("resumeScrollArea")
        self.resume_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.resume_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.resume_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.resume_scroll_area.setMinimumHeight(400)

        self.resume_list_container = QWidget()
        self.resume_list_layout = QVBoxLayout(self.resume_list_container)
        self.resume_list_layout.setContentsMargins(10, 10, 10, 10)
        self.resume_list_layout.setSpacing(10)
        self.resume_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.resume_scroll_area.setWidget(self.resume_list_container)

        self.resume_status_label = QLabel("No resume selected.")
        self.resume_status_label.setFont(font_small_xxl)
        self.resume_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.upload_resume_btn = QPushButton(" Upload New Resume PDF...")
        if upload_icon:
            self.upload_resume_btn.setIcon(upload_icon)
        self.upload_resume_btn.setIconSize(button_icon_size)
        self.upload_resume_btn.setFont(font_default_xxl)
        self.upload_resume_btn.setFixedHeight(action_button_height)
        self.upload_resume_btn.clicked.connect(pw.select_resume_file)

        resume_layout.addWidget(list_label_res)
        resume_layout.addWidget(self.resume_scroll_area, stretch=1)
        resume_layout.addWidget(self.resume_status_label)
        resume_layout.addWidget(
            self.upload_resume_btn, alignment=Qt.AlignmentFlag.AlignCenter
        )

        jd_group = QGroupBox()
        jd_group.setFont(font_group_title_xxl)

        jd_layout = QVBoxLayout(jd_group)
        jd_layout.setSpacing(20)
        jd_layout.setContentsMargins(25, 25, 25, 25)

        list_label_jd = QLabel("Job Description:")
        list_label_jd.setFont(font_group_title_xxl)

        self.jd_scroll_area = QScrollArea()
        self.jd_scroll_area.setWidgetResizable(True)
        self.jd_scroll_area.setObjectName("jdScrollArea")
        self.jd_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.jd_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.jd_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.jd_scroll_area.setMinimumHeight(400)

        self.jd_list_container = QWidget()
        self.jd_list_layout = QVBoxLayout(self.jd_list_container)
        self.jd_list_layout.setContentsMargins(10, 10, 10, 10)
        self.jd_list_layout.setSpacing(10)
        self.jd_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.jd_scroll_area.setWidget(self.jd_list_container)

        self.add_jd_btn = QPushButton(" Add New Job Description...")
        if add_icon:
            self.add_jd_btn.setIcon(add_icon)
        self.add_jd_btn.setIconSize(button_icon_size)
        self.add_jd_btn.setFont(font_default_xxl)
        self.add_jd_btn.setFixedHeight(action_button_height)
        self.add_jd_btn.clicked.connect(pw._handle_add_new_jd)

        self.jd_status_label = QLabel("No job description selected.")
        self.jd_status_label.setFont(font_small_xxl)
        self.jd_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        jd_layout.addWidget(list_label_jd)
        jd_layout.addWidget(self.jd_scroll_area, stretch=1)
        jd_layout.addWidget(self.jd_status_label)
        jd_layout.addWidget(
            self.add_jd_btn, alignment=Qt.AlignmentFlag.AlignCenter
        )

        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(45)
        lists_layout.addWidget(resume_group, stretch=1)
        lists_layout.addWidget(jd_group, stretch=1)

        self.start_interview_btn = QPushButton("Next: Start Interview")
        if start_icon:
            self.start_interview_btn.setIcon(start_icon)
        self.start_interview_btn.setIconSize(button_icon_size)
        self.start_interview_btn.setFont(font_bold_xxl)
        self.start_interview_btn.setFixedHeight(start_button_height)
        self.start_interview_btn.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.start_interview_btn.clicked.connect(pw.start_interview_process)

        start_button_layout = QHBoxLayout()
        start_button_layout.addStretch(1)
        start_button_layout.addWidget(self.start_interview_btn)
        start_button_layout.addStretch(1)

        main_content_layout.addLayout(lists_layout, stretch=1)
        main_content_layout.addSpacerItem(
            QSpacerItem(20, 60, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        main_content_layout.addLayout(start_button_layout, stretch=0)

        self.setLayout(page_layout)

    def _update_sidebar_geometry(self):
        page_rect = self.rect()
        sidebar_height = page_rect.height()

        hint_width = 0
        if self.sidebar_frame.layout():
            hint_width = self.sidebar_frame.layout().minimumSize().width()

        total_width = hint_width + self.sidebar_margins.width() * 2
        actual_width = max(self.SIDEBAR_MIN_WIDTH, total_width)
        sidebar_x = page_rect.width() - actual_width
        sidebar_y = 0
        self.sidebar_frame.setGeometry(
            sidebar_x, sidebar_y, actual_width, sidebar_height
        )

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_sidebar_geometry()
        if self.sidebar_frame.isVisible():
            self.sidebar_frame.raise_()

    def _toggle_sidebar(self, visible: bool):
        sidebar_exists = hasattr(self, 'sidebar_frame')
        toggle_exists = hasattr(self, 'sidebar_toggle_btn')
        if not sidebar_exists or not toggle_exists:
            print("Error: Sidebar frame or toggle button not initialized.")
            return

        print(f"Setting sidebar overlay visibility to: {visible}")

        if visible:
            self._update_sidebar_geometry()
            self.sidebar_frame.raise_()
            self.sidebar_frame.show()
        else:
            self.sidebar_frame.hide()

        self.sidebar_toggle_btn.setChecked(self.sidebar_frame.isVisible())

    def _toggle_sidebar_from_button(self, checked: bool):
        self._toggle_sidebar(checked)

    def hide_sidebar(self):
        self._toggle_sidebar(False)

    def update_widgets_from_state(self,
                                  recent_resumes_data: list[dict],
                                  current_selection_path: str | None,
                                  recent_jd_data: list[dict],
                                  current_jd_name: str | None):
        pw = self.parent_window
        pdf_loaded = bool(current_selection_path)
        jd_loaded = bool(pw.job_description_text)

        font_default_xxl = getattr(pw, 'font_default_xxl', QFont("Arial", 16))
        font_small_xxl = getattr(pw, 'font_small_xxl', QFont("Arial", 15))

        while self.resume_list_layout.count():
            item = self.resume_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if recent_resumes_data:
            for item_data in recent_resumes_data:
                path = item_data.get("path")
                if path:
                    resume_widget = ResumeWidget(item_data, self)
                    resume_widget.resume_selected.connect(pw._handle_resume_widget_selected)
                    self.resume_list_layout.addWidget(resume_widget)
        else:
            lbl = QLabel("<i>No recent resumes found.</i>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(font_small_xxl)
            self.resume_list_layout.addWidget(lbl)
        self.resume_list_layout.addStretch(1)

        self.show_resume_selection_state(current_selection_path)

        while self.jd_list_layout.count():
            item = self.jd_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if recent_jd_data:
            for item_data in recent_jd_data:
                name = item_data.get("name")
                if name:
                    jd_widget = JDWidget(item_data, self)
                    jd_widget.jd_selected.connect(pw._handle_jd_widget_selected)
                    self.jd_list_layout.addWidget(jd_widget)
        else:
            lbl = QLabel("<i>No recent JDs found.</i>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(font_small_xxl)
            self.jd_list_layout.addWidget(lbl)
        self.jd_list_layout.addStretch(1)

        self.show_jd_selection_state(current_jd_name)

        if hasattr(self, 'num_topics_label'):
            self.num_topics_label.setText(str(pw.num_topics))
            self.num_topics_label.setFont(font_default_xxl)
        if hasattr(self, 'max_follow_ups_label'):
            self.max_follow_ups_label.setText(str(pw.max_follow_ups))
            self.max_follow_ups_label.setFont(font_default_xxl)
        if hasattr(self, 'speech_checkbox'):
            self.speech_checkbox.blockSignals(True)
            self.speech_checkbox.setChecked(pw.use_speech_input)
            self.speech_checkbox.blockSignals(False)
        if hasattr(self, 'openai_tts_checkbox'):
            self.openai_tts_checkbox.blockSignals(True)
            self.openai_tts_checkbox.setChecked(pw.use_openai_tts)
            self.openai_tts_checkbox.blockSignals(False)

        self.set_controls_enabled_state(pdf_loaded, jd_loaded)

    def show_resume_selection_state(self, selected_path: str | None):
        selected_name_internal = None
        if hasattr(self, 'resume_list_layout'):
            for i in range(self.resume_list_layout.count()):
                item = self.resume_list_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, ResumeWidget) and hasattr(widget, 'resume_data'):
                    is_selected = (widget.resume_data.get("path") == selected_path)
                    widget.set_selected(is_selected)
                    if is_selected:
                        selected_name_internal = widget.resume_data.get("name")

        if hasattr(self, 'resume_status_label'):
            font_small_xxl = getattr(
                self.parent_window, 'font_small_xxl', QFont("Arial", 15)
            )
            self.resume_status_label.setFont(font_small_xxl)

            if selected_path:
                display_name = selected_name_internal or Path(selected_path).stem
                max_len = 40
                if len(display_name) > max_len:
                    display_name = display_name[:max_len - 3] + "..."
                self.resume_status_label.setText(f"Selected: <b>{display_name}</b>")
                self.resume_status_label.setToolTip(selected_path)
            else:
                self.resume_status_label.setText("No resume selected.")
                self.resume_status_label.setToolTip("")

    def show_jd_selection_state(self, selected_jd_name: str | None):
        if hasattr(self, 'jd_list_layout'):
            for i in range(self.jd_list_layout.count()):
                item = self.jd_list_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, JDWidget) and hasattr(widget, 'jd_data'):
                    is_selected = (widget.jd_data.get("name") == selected_jd_name)
                    widget.set_selected(is_selected)

        if hasattr(self, 'jd_status_label'):
            font_small_xxl = getattr(
                self.parent_window, 'font_small_xxl', QFont("Arial", 15)
            )
            self.jd_status_label.setFont(font_small_xxl)

            if selected_jd_name:
                display_name = selected_jd_name
                max_len = 40
                if len(display_name) > max_len:
                    display_name = display_name[:max_len - 3] + "..."
                self.jd_status_label.setText(f"Selected: <b>{display_name}</b>")
                self.jd_status_label.setToolTip(
                    selected_jd_name if display_name != selected_jd_name else ""
                )
            else:
                self.jd_status_label.setText("No job description selected.")
                self.jd_status_label.setToolTip("")

    def set_controls_enabled_state(self, pdf_loaded: bool, jd_loaded: bool):
        sidebar_controls_names = [
            'topic_minus_btn', 'topic_plus_btn', 'num_topics_label',
            'followup_minus_btn', 'followup_plus_btn', 'max_follow_ups_label',
            'speech_checkbox', 'openai_tts_checkbox'
        ]
        openai_deps_met = "openai" in tts.get_potentially_available_providers()

        for name in sidebar_controls_names:
            widget = getattr(self, name, None)
            if widget:
                enable = True
                if widget == self.openai_tts_checkbox:
                    enable = openai_deps_met
                widget.setEnabled(enable)

        main_controls_names = [
            'start_interview_btn', 'upload_resume_btn', 'add_jd_btn',
            'resume_scroll_area', 'jd_scroll_area'
        ]
        for name in main_controls_names:
            widget = getattr(self, name, None)
            if widget:
                enable = True
                if widget == self.start_interview_btn:
                    enable = pdf_loaded and jd_loaded
                widget.setEnabled(enable)