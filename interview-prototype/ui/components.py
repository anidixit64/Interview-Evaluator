# ui/components.py
"""
Functions to create the main UI PAGES (QWidget instances).
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QCheckBox,
    QGroupBox, QSizePolicy, QFrame, QMessageBox, QFileDialog,
    QSpacerItem, QSpacerItem
)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QTextCursor, QColor, QPalette, QCursor
from PyQt6.QtCore import Qt, QSize

from core import logic # For default values, limits

# Helper function
def _load_icon(icon_path_base, filename, size=None):
    try:
        path = os.path.join(icon_path_base, filename)
        if not os.path.exists(path):
            print(f"Warn: Icon not found: {path}")
            return None
        return QIcon(path)
    except Exception as e:
        print(f"Error loading icon {filename}: {e}")
        return None

# --- Page 1: Setup ---
def create_setup_page(parent_window):
    page_widget = QWidget(parent_window)
    page_layout = QVBoxLayout(page_widget)
    page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    page_layout.setContentsMargins(15, 15, 15, 15)
    page_layout.setSpacing(20)

    # Icons
    select_icon = _load_icon(parent_window.icon_path, "folder.png", parent_window.icon_size)
    start_icon = _load_icon(parent_window.icon_path, "play.png", parent_window.icon_size)
    plus_icon = _load_icon(parent_window.icon_path, "plus.png")
    minus_icon = _load_icon(parent_window.icon_path, "minus.png")
    button_icon_size = QSize(16, 16)

    # --- Resume Section ---
    resume_group = QGroupBox("1. Load Resume")
    resume_group.setFont(parent_window.font_large_bold)
    resume_layout = QGridLayout(resume_group)
    resume_layout.setSpacing(10)
    parent_window.select_btn = QPushButton("Select Resume PDF")
    if select_icon: parent_window.select_btn.setIcon(select_icon)
    parent_window.select_btn.setIconSize(parent_window.icon_size)
    parent_window.select_btn.setFont(parent_window.font_default)
    parent_window.select_btn.clicked.connect(parent_window.select_resume_file)
    parent_window.file_label = QLineEdit("No resume selected.")
    parent_window.file_label.setFont(parent_window.font_small)
    parent_window.file_label.setReadOnly(True)
    resume_layout.addWidget(parent_window.select_btn, 0, 0)
    resume_layout.addWidget(parent_window.file_label, 0, 1)
    resume_layout.setColumnStretch(1, 1)

    # --- Configuration Section ---
    config_group = QGroupBox("2. Configure Interview")
    config_group.setFont(parent_window.font_large_bold)
    config_layout = QHBoxLayout(config_group)
    config_layout.setSpacing(25)
    # Topics
    topics_widget = QWidget()
    topics_inner_layout = QHBoxLayout(topics_widget)
    topics_inner_layout.setContentsMargins(0,0,0,0)
    topics_inner_layout.setSpacing(5)
    topics_label_prefix = QLabel("Topics:")
    topics_label_prefix.setFont(parent_window.font_default)
    parent_window.topic_minus_btn = QPushButton("")
    parent_window.topic_minus_btn.setObjectName("adjustButton")
    if minus_icon: parent_window.topic_minus_btn.setIcon(minus_icon)
    parent_window.topic_minus_btn.setIconSize(button_icon_size)
    parent_window.topic_minus_btn.setFixedSize(QSize(28, 28))
    parent_window.topic_minus_btn.setToolTip("Decrease topics")
    parent_window.topic_minus_btn.clicked.connect(lambda: parent_window._adjust_value('topics', -1))
    parent_window.num_topics_label = QLabel(str(parent_window.num_topics))
    parent_window.num_topics_label.setFont(parent_window.font_default)
    parent_window.num_topics_label.setMinimumWidth(25)
    parent_window.num_topics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    parent_window.topic_plus_btn = QPushButton("")
    parent_window.topic_plus_btn.setObjectName("adjustButton")
    if plus_icon: parent_window.topic_plus_btn.setIcon(plus_icon)
    parent_window.topic_plus_btn.setIconSize(button_icon_size)
    parent_window.topic_plus_btn.setFixedSize(QSize(28, 28))
    parent_window.topic_plus_btn.setToolTip("Increase topics")
    parent_window.topic_plus_btn.clicked.connect(lambda: parent_window._adjust_value('topics', +1))
    topics_inner_layout.addWidget(topics_label_prefix)
    topics_inner_layout.addWidget(parent_window.topic_minus_btn)
    topics_inner_layout.addWidget(parent_window.num_topics_label)
    topics_inner_layout.addWidget(parent_window.topic_plus_btn)
    config_layout.addWidget(topics_widget)
    # Follow-ups
    followups_widget = QWidget()
    followups_inner_layout = QHBoxLayout(followups_widget)
    followups_inner_layout.setContentsMargins(0,0,0,0)
    followups_inner_layout.setSpacing(5)
    followups_label_prefix = QLabel("Max Follow-ups:")
    followups_label_prefix.setFont(parent_window.font_default)
    parent_window.followup_minus_btn = QPushButton("")
    parent_window.followup_minus_btn.setObjectName("adjustButton")
    if minus_icon: parent_window.followup_minus_btn.setIcon(minus_icon)
    parent_window.followup_minus_btn.setIconSize(button_icon_size)
    parent_window.followup_minus_btn.setFixedSize(QSize(28, 28))
    parent_window.followup_minus_btn.setToolTip("Decrease follow-ups")
    parent_window.followup_minus_btn.clicked.connect(lambda: parent_window._adjust_value('followups', -1))
    parent_window.max_follow_ups_label = QLabel(str(parent_window.max_follow_ups))
    parent_window.max_follow_ups_label.setFont(parent_window.font_default)
    parent_window.max_follow_ups_label.setMinimumWidth(25)
    parent_window.max_follow_ups_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    parent_window.followup_plus_btn = QPushButton("")
    parent_window.followup_plus_btn.setObjectName("adjustButton")
    if plus_icon: parent_window.followup_plus_btn.setIcon(plus_icon)
    parent_window.followup_plus_btn.setIconSize(button_icon_size)
    parent_window.followup_plus_btn.setFixedSize(QSize(28, 28))
    parent_window.followup_plus_btn.setToolTip("Increase follow-ups")
    parent_window.followup_plus_btn.clicked.connect(lambda: parent_window._adjust_value('followups', +1))
    followups_inner_layout.addWidget(followups_label_prefix)
    followups_inner_layout.addWidget(parent_window.followup_minus_btn)
    followups_inner_layout.addWidget(parent_window.max_follow_ups_label)
    followups_inner_layout.addWidget(parent_window.followup_plus_btn)
    config_layout.addWidget(followups_widget)
    # Speech Input
    parent_window.speech_checkbox = QCheckBox("Use Speech Input")
    parent_window.speech_checkbox.setFont(parent_window.font_default)
    parent_window.speech_checkbox.stateChanged.connect(parent_window.update_submit_button_text)
    config_layout.addWidget(parent_window.speech_checkbox)
    config_layout.addStretch()

    # --- Job Description Section ---
    jd_group = QGroupBox("3. Job Description (Optional)")
    jd_group.setFont(parent_window.font_large_bold)
    jd_layout = QVBoxLayout(jd_group)
    parent_window.job_desc_input = QTextEdit()
    parent_window.job_desc_input.setPlaceholderText("Paste job description here...")
    parent_window.job_desc_input.setFont(parent_window.font_small)
    parent_window.job_desc_input.setMinimumHeight(100)
    parent_window.job_desc_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    jd_layout.addWidget(parent_window.job_desc_input)

    # --- Add Groups to Page Layout (Reordered) ---
    page_layout.addWidget(resume_group)
    page_layout.addWidget(config_group)
    page_layout.addWidget(jd_group, stretch=1)

    # --- Start Button ---
    start_button_layout = QHBoxLayout()
    parent_window.start_interview_btn = QPushButton("Next: Start Interview")
    if start_icon: parent_window.start_interview_btn.setIcon(start_icon)
    parent_window.start_interview_btn.setIconSize(parent_window.icon_size)
    parent_window.start_interview_btn.setFont(parent_window.font_bold)
    parent_window.start_interview_btn.setFixedHeight(40)
    parent_window.start_interview_btn.clicked.connect(parent_window.start_interview_process)
    start_button_layout.addStretch()
    start_button_layout.addWidget(parent_window.start_interview_btn)
    start_button_layout.addStretch()

    page_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
    page_layout.addLayout(start_button_layout)

    page_widget.setLayout(page_layout)
    return page_widget

# --- Page 2: Interview ---
def create_interview_page(parent_window):
    page_widget = QWidget(parent_window)
    page_layout = QVBoxLayout(page_widget)
    page_layout.setContentsMargins(15, 15, 15, 15)
    page_layout.setSpacing(15)

    # Icons
    submit_icon = _load_icon(parent_window.icon_path, "send.png", parent_window.icon_size)
    parent_window.record_icon = _load_icon(parent_window.icon_path, "mic_black_36dp.png", parent_window.icon_size)
    parent_window.listening_icon = _load_icon(parent_window.icon_path, "record_wave.png", parent_window.icon_size)
    parent_window.processing_icon = _load_icon(parent_window.icon_path, "spinner.png", parent_window.icon_size)

    # --- Interview Area ---
    interview_group = QGroupBox("Interview")
    interview_group.setFont(parent_window.font_large_bold)
    interview_layout = QVBoxLayout(interview_group)
    interview_layout.setSpacing(10)

    current_q_label = QLabel("Interviewer Question:")
    current_q_label.setFont(parent_window.font_bold)
    parent_window.current_q_text = QTextEdit()
    parent_window.current_q_text.setReadOnly(True)
    parent_window.current_q_text.setFont(parent_window.font_default)
    parent_window.current_q_text.setObjectName("interviewerQuestion")
    parent_window.current_q_text.setMinimumHeight(80)
    parent_window.current_q_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    line1 = QFrame()
    line1.setFrameShape(QFrame.Shape.HLine)
    line1.setFrameShadow(QFrame.Shadow.Sunken)

    answer_label = QLabel("Your Answer:")
    answer_label.setFont(parent_window.font_bold)
    parent_window.answer_input = QTextEdit()
    parent_window.answer_input.setPlaceholderText("Type answer or use record...")
    parent_window.answer_input.setFont(parent_window.font_default)
    parent_window.answer_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    parent_window.submit_button = QPushButton("Submit Answer")
    parent_window.submit_button.setObjectName("recordSubmitButton")
    if submit_icon: parent_window.submit_button.setIcon(submit_icon)
    parent_window.submit_button.setIconSize(parent_window.icon_size)
    parent_window.submit_button.setFont(parent_window.font_bold)
    parent_window.submit_button.clicked.connect(parent_window.handle_answer_submission)
    parent_window.submit_button.setFixedHeight(35)
    submit_button_layout = QHBoxLayout()
    submit_button_layout.addStretch()
    submit_button_layout.addWidget(parent_window.submit_button)
    submit_button_layout.addStretch()

    interview_layout.addWidget(current_q_label)
    interview_layout.addWidget(parent_window.current_q_text)
    interview_layout.addWidget(line1)
    interview_layout.addWidget(answer_label)
    interview_layout.addWidget(parent_window.answer_input)
    interview_layout.addLayout(submit_button_layout)

    page_layout.addWidget(interview_group, stretch=3)

    # --- Separator ---
    line2 = QFrame()
    line2.setFrameShape(QFrame.Shape.HLine)
    line2.setFrameShadow(QFrame.Shadow.Sunken)
    page_layout.addWidget(line2)

    # --- History/Transcript Area ---
    history_group = QGroupBox("Transcript")
    history_group.setFont(parent_window.font_large_bold)
    history_layout = QVBoxLayout(history_group)
    parent_window.history_text = QTextEdit()
    parent_window.history_text.setReadOnly(True)
    parent_window.history_text.setFont(parent_window.font_history)
    parent_window.history_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    history_layout.addWidget(parent_window.history_text)
    page_layout.addWidget(history_group, stretch=2) # Adjusted stretch

    page_widget.setLayout(page_layout)
    return page_widget

# --- Page 3: Results ---
def create_results_page(parent_window):
    page_widget = QWidget(parent_window)
    page_layout = QVBoxLayout(page_widget)
    page_layout.setContentsMargins(15, 15, 15, 15)
    page_layout.setSpacing(15)
    page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    # Icons
    save_icon = _load_icon(parent_window.icon_path, "save.png", parent_window.icon_size)
    folder_icon = _load_icon(parent_window.icon_path, "folder.png", parent_window.icon_size)

    # --- Summary Section ---
    summary_group = QGroupBox("Performance Summary")
    summary_group.setFont(parent_window.font_large_bold)
    summary_layout = QVBoxLayout(summary_group)
    parent_window.summary_text_results = QTextEdit()
    parent_window.summary_text_results.setReadOnly(True)
    parent_window.summary_text_results.setFont(parent_window.font_small)
    parent_window.summary_text_results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    parent_window.summary_text_results.setAcceptRichText(True)
    summary_layout.addWidget(parent_window.summary_text_results)
    page_layout.addWidget(summary_group, stretch=1)

    # --- Assessment Section ---
    assessment_group = QGroupBox("Qualification Assessment")
    assessment_group.setFont(parent_window.font_large_bold)
    assessment_layout = QVBoxLayout(assessment_group)
    parent_window.assessment_text_results = QTextEdit()
    parent_window.assessment_text_results.setReadOnly(True)
    parent_window.assessment_text_results.setFont(parent_window.font_small)
    parent_window.assessment_text_results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    parent_window.assessment_text_results.setAcceptRichText(True)
    assessment_layout.addWidget(parent_window.assessment_text_results)
    page_layout.addWidget(assessment_group, stretch=1)

    # --- Action Buttons Layout ---
    action_buttons_layout = QHBoxLayout()
    action_buttons_layout.setSpacing(15)

    # Save Report Button
    parent_window.save_report_button = QPushButton("Save Report")
    if save_icon: parent_window.save_report_button.setIcon(save_icon)
    parent_window.save_report_button.setIconSize(parent_window.icon_size)
    parent_window.save_report_button.setFont(parent_window.font_default)
    parent_window.save_report_button.clicked.connect(parent_window._save_report)
    parent_window.save_report_button.setFixedHeight(35)
    action_buttons_layout.addWidget(parent_window.save_report_button)

    # Open Folder Button
    parent_window.open_folder_button = QPushButton("Open Recordings Folder")
    if folder_icon: parent_window.open_folder_button.setIcon(folder_icon)
    parent_window.open_folder_button.setIconSize(parent_window.icon_size)
    parent_window.open_folder_button.setFont(parent_window.font_default)
    parent_window.open_folder_button.clicked.connect(parent_window._open_recordings_folder)
    parent_window.open_folder_button.setFixedHeight(35)
    action_buttons_layout.addWidget(parent_window.open_folder_button)

    action_buttons_layout.addStretch()

    # New Interview Button
    parent_window.new_interview_button = QPushButton("Finish & Start New")
    parent_window.new_interview_button.setFont(parent_window.font_bold)
    parent_window.new_interview_button.setFixedHeight(40)
    parent_window.new_interview_button.clicked.connect(parent_window._go_to_setup_page)
    action_buttons_layout.addWidget(parent_window.new_interview_button)

    page_layout.addLayout(action_buttons_layout)

    page_widget.setLayout(page_layout)
    return page_widget