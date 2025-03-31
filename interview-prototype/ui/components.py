# ui/components.py
"""
Functions to create the main UI component groups (Setup, Interview, History).
These functions take the parent window (InterviewApp instance) as an argument
to set widget attributes on it and connect signals.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QCheckBox,
    QGroupBox, QSizePolicy, QFrame, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QTextCursor, QColor, QPalette, QCursor
from PyQt6.QtCore import Qt, QSize

# Assuming core logic is imported in main_window which calls these
from core import logic

# Helper function (can be here or in a dedicated ui/utils.py)
def _load_icon(icon_path_base, filename, size=None):
    try:
        path = os.path.join(icon_path_base, filename)
        if not os.path.exists(path):
            print(f"Warning: Icon not found at {path}")
            return None
        # Load as QIcon directly for buttons
        return QIcon(path)
    except Exception as e:
        print(f"Error loading icon {filename}: {e}")
        return None


def create_setup_group(parent_window):
    """Creates the 'Setup' QGroupBox and its widgets."""
    setup_group = QGroupBox("Setup")
    setup_group.setFont(parent_window.font_large_bold)
    setup_layout = QGridLayout() # Use Grid for this section
    setup_layout.setSpacing(10)
    setup_layout.setContentsMargins(10, 15, 10, 10) # top margin adjusted

    # Icons
    select_icon = _load_icon(parent_window.icon_path, "folder.png", parent_window.icon_size)
    start_icon = _load_icon(parent_window.icon_path, "play.png", parent_window.icon_size)
    # --- Load Plus/Minus Icons ---
    plus_icon = _load_icon(parent_window.icon_path, "plus.png") # Load new icons
    minus_icon = _load_icon(parent_window.icon_path, "minus.png")
    button_icon_size = QSize(16, 16) # Smaller size for +/- buttons

    # Row 0: Resume
    parent_window.select_btn = QPushButton("Select Resume PDF")
    if select_icon: parent_window.select_btn.setIcon(select_icon)
    parent_window.select_btn.setIconSize(parent_window.icon_size)
    parent_window.select_btn.setFont(parent_window.font_default)
    # Connect signal to method in parent_window
    parent_window.select_btn.clicked.connect(parent_window.select_resume_file)
    parent_window.file_label = QLineEdit("No resume selected.")
    parent_window.file_label.setFont(parent_window.font_small)
    parent_window.file_label.setReadOnly(True)

    setup_layout.addWidget(parent_window.select_btn, 0, 0) # row, col
    setup_layout.addWidget(parent_window.file_label, 0, 1, 1, 3) # row, col, rowspan, colspan

    # Row 1: Job Description
    jd_label = QLabel("Job Description (Optional):")
    jd_label.setFont(parent_window.font_default)
    parent_window.job_desc_input = QTextEdit()
    parent_window.job_desc_input.setPlaceholderText("Paste job description here...")
    parent_window.job_desc_input.setFont(parent_window.font_small)
    parent_window.job_desc_input.setFixedHeight(100)
    parent_window.job_desc_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    setup_layout.addWidget(jd_label, 1, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    setup_layout.addWidget(parent_window.job_desc_input, 1, 1, 1, 3)

    # Row 2: Configuration (Topics, Followups) using custom +/- components
    config_outer_layout = QHBoxLayout() # Layout to hold both config groups
    config_outer_layout.setSpacing(20) # Space between topics and followups

    # --- Topics Component ---
    topics_layout = QHBoxLayout()
    topics_layout.setSpacing(2) # Tight spacing for +/-/label group

    topics_label_prefix = QLabel("Topics:") # Label for the group
    topics_label_prefix.setFont(parent_window.font_default)

    parent_window.topic_minus_btn = QPushButton("") # Text can be empty
    parent_window.topic_minus_btn.setObjectName("adjustButton") # Add object name
    if minus_icon: parent_window.topic_minus_btn.setIcon(minus_icon)
    parent_window.topic_minus_btn.setIconSize(button_icon_size)
    parent_window.topic_minus_btn.setFixedSize(QSize(28, 28)) # Make it square
    parent_window.topic_minus_btn.setToolTip("Decrease number of topics")
    # Connect signal using lambda to call the handler in parent_window
    parent_window.topic_minus_btn.clicked.connect(lambda: parent_window._adjust_value('topics', -1))

    parent_window.num_topics_label = QLabel(str(parent_window.num_topics))
    parent_window.num_topics_label.setFont(parent_window.font_default)
    parent_window.num_topics_label.setMinimumWidth(25) # Ensure minimum width
    parent_window.num_topics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    parent_window.topic_plus_btn = QPushButton("")
    parent_window.topic_plus_btn.setObjectName("adjustButton") # Add object name
    if plus_icon: parent_window.topic_plus_btn.setIcon(plus_icon)
    parent_window.topic_plus_btn.setIconSize(button_icon_size)
    parent_window.topic_plus_btn.setFixedSize(QSize(28, 28))
    parent_window.topic_plus_btn.setToolTip("Increase number of topics")
    parent_window.topic_plus_btn.clicked.connect(lambda: parent_window._adjust_value('topics', +1))

    # Add widgets to the topics layout
    topics_layout.addWidget(topics_label_prefix)
    topics_layout.addWidget(parent_window.topic_minus_btn)
    topics_layout.addWidget(parent_window.num_topics_label)
    topics_layout.addWidget(parent_window.topic_plus_btn)
    # ------------------------

    # --- Follow-ups Component ---
    followups_layout = QHBoxLayout()
    followups_layout.setSpacing(2)

    followups_label_prefix = QLabel("Max Follow-ups:")
    followups_label_prefix.setFont(parent_window.font_default)

    parent_window.followup_minus_btn = QPushButton("")
    parent_window.followup_minus_btn.setObjectName("adjustButton") # Add object name
    if minus_icon: parent_window.followup_minus_btn.setIcon(minus_icon)
    parent_window.followup_minus_btn.setIconSize(button_icon_size)
    parent_window.followup_minus_btn.setFixedSize(QSize(28, 28))
    parent_window.followup_minus_btn.setToolTip("Decrease max follow-ups")
    parent_window.followup_minus_btn.clicked.connect(lambda: parent_window._adjust_value('followups', -1))

    parent_window.max_follow_ups_label = QLabel(str(parent_window.max_follow_ups))
    parent_window.max_follow_ups_label.setFont(parent_window.font_default)
    parent_window.max_follow_ups_label.setMinimumWidth(25)
    parent_window.max_follow_ups_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    parent_window.followup_plus_btn = QPushButton("")
    parent_window.followup_plus_btn.setObjectName("adjustButton") # Add object name
    if plus_icon: parent_window.followup_plus_btn.setIcon(plus_icon)
    parent_window.followup_plus_btn.setIconSize(button_icon_size)
    parent_window.followup_plus_btn.setFixedSize(QSize(28, 28))
    parent_window.followup_plus_btn.setToolTip("Increase max follow-ups")
    parent_window.followup_plus_btn.clicked.connect(lambda: parent_window._adjust_value('followups', +1))

    # Add widgets to the followups layout
    followups_layout.addWidget(followups_label_prefix)
    followups_layout.addWidget(parent_window.followup_minus_btn)
    followups_layout.addWidget(parent_window.max_follow_ups_label)
    followups_layout.addWidget(parent_window.followup_plus_btn)
    # --------------------------

    # Add both component layouts to the outer layout
    config_outer_layout.addLayout(topics_layout)
    config_outer_layout.addLayout(followups_layout)
    config_outer_layout.addStretch() # Push components to the left

    setup_layout.addLayout(config_outer_layout, 2, 0, 1, 4) # Add the outer layout to the grid

    # Row 3: Input Mode Checkbox and Start Button (remains the same)
    start_layout = QHBoxLayout()
    start_layout.setSpacing(15)
    parent_window.speech_checkbox = QCheckBox("Use Speech Input")
    parent_window.speech_checkbox.setFont(parent_window.font_default)
    parent_window.speech_checkbox.stateChanged.connect(parent_window.update_submit_button_text)

    parent_window.start_interview_btn = QPushButton("Start Interview")
    if start_icon: parent_window.start_interview_btn.setIcon(start_icon)
    parent_window.start_interview_btn.setIconSize(parent_window.icon_size)
    parent_window.start_interview_btn.setFont(parent_window.font_bold)
    parent_window.start_interview_btn.clicked.connect(parent_window.start_interview_process)

    start_layout.addWidget(parent_window.speech_checkbox)
    start_layout.addStretch()
    start_layout.addWidget(parent_window.start_interview_btn)

    setup_layout.addLayout(start_layout, 3, 0, 1, 4)

    setup_group.setLayout(setup_layout)
    return setup_group


def create_interview_group(parent_window):
    """Creates the 'Interview' QGroupBox and its widgets."""
    # (This function remains unchanged from the previous version)
    interview_group = QGroupBox("Interview")
    interview_group.setFont(parent_window.font_large_bold)
    interview_layout = QVBoxLayout()
    interview_layout.setSpacing(8)
    interview_layout.setContentsMargins(10, 15, 10, 10)

    # Icons
    submit_icon = _load_icon(parent_window.icon_path, "send.png", parent_window.icon_size)
    # Ensure record_icon is loaded here and stored on parent
    parent_window.record_icon = _load_icon(parent_window.icon_path, "mic_black_36dp.png", parent_window.icon_size) # Make sure mic icon exists


    current_q_label = QLabel("Interviewer:")
    current_q_label.setFont(parent_window.font_bold)
    parent_window.current_q_text = QTextEdit()
    parent_window.current_q_text.setReadOnly(True)
    parent_window.current_q_text.setFont(parent_window.font_default)
    parent_window.current_q_text.setFixedHeight(80)
    parent_window.current_q_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    answer_label = QLabel("Your Answer:")
    answer_label.setFont(parent_window.font_bold)
    parent_window.answer_input = QTextEdit()
    parent_window.answer_input.setPlaceholderText("Type your answer here, or use the record button...")
    parent_window.answer_input.setFont(parent_window.font_default)
    parent_window.answer_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    parent_window.submit_button = QPushButton("Submit Answer")
    if submit_icon: parent_window.submit_button.setIcon(submit_icon)
    parent_window.submit_button.setIconSize(parent_window.icon_size)
    parent_window.submit_button.setFont(parent_window.font_bold)
    parent_window.submit_button.clicked.connect(parent_window.handle_answer_submission)
    parent_window.submit_button.setFixedHeight(35)

    # Layout for submit button (centered)
    submit_button_layout = QHBoxLayout()
    submit_button_layout.addStretch()
    submit_button_layout.addWidget(parent_window.submit_button)
    submit_button_layout.addStretch()

    interview_layout.addWidget(current_q_label)
    interview_layout.addWidget(parent_window.current_q_text)
    interview_layout.addWidget(answer_label)
    interview_layout.addWidget(parent_window.answer_input)
    interview_layout.addLayout(submit_button_layout)

    interview_group.setLayout(interview_layout)
    interview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return interview_group


def create_history_group(parent_window):
    """Creates the 'History' QGroupBox and its widgets."""
    # (This function remains unchanged)
    history_group = QGroupBox("History")
    history_group.setFont(parent_window.font_large_bold)
    history_layout = QVBoxLayout()
    history_layout.setContentsMargins(10, 15, 10, 10)

    parent_window.history_text = QTextEdit()
    parent_window.history_text.setReadOnly(True)
    parent_window.history_text.setFont(parent_window.font_history)
    parent_window.history_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

    history_layout.addWidget(parent_window.history_text)
    history_group.setLayout(history_layout)
    return history_group