# ui/setup_page.py
"""
Defines the Setup Page QWidget for the Interview App.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QCheckBox,
    QGroupBox, QSizePolicy, QFrame, QSpacerItem
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSize

# Import from core where needed
try:
    from core import logic # For default values, limits
    from core import tts   # To check tts availability
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from core import logic
    from core import tts

# Import shared components like _load_icon
from .components import _load_icon

class SetupPage(QWidget):
    """
    The setup page widget allowing users to load resume, configure, and start.
    """
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs) # Pass parent_window as parent
        self.parent_window = parent_window # Keep a reference if needed for complex interactions
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI elements for the setup page."""
        page_layout = QVBoxLayout(self)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(20)

        # Access parent_window attributes for shared resources (fonts, paths, state)
        pw = self.parent_window

        # Icons
        select_icon = _load_icon(pw.icon_path, "folder.png")
        start_icon = _load_icon(pw.icon_path, "play.png")
        plus_icon = _load_icon(pw.icon_path, "plus.png")
        minus_icon = _load_icon(pw.icon_path, "minus.png")
        button_icon_size = QSize(16, 16)

        # --- Resume Section ---
        resume_group = QGroupBox("Load Resume")
        resume_group.setFont(pw.font_large_bold)
        resume_layout = QGridLayout(resume_group)
        resume_layout.setSpacing(10)
        # Assign widgets to self attributes for access within this class if needed,
        # or parent_window if they must be accessed directly from there (less ideal).
        # Let's assign to self first. parent_window can access via page instance.
        self.select_btn = QPushButton("Select Resume PDF")
        if select_icon: self.select_btn.setIcon(select_icon)
        self.select_btn.setIconSize(pw.icon_size)
        self.select_btn.setFont(pw.font_default)
        self.select_btn.clicked.connect(pw.select_resume_file) # Connect to parent's slot

        self.file_label = QLineEdit("No resume selected.")
        self.file_label.setFont(pw.font_small)
        self.file_label.setReadOnly(True)
        resume_layout.addWidget(self.select_btn, 0, 0)
        resume_layout.addWidget(self.file_label, 0, 1)
        resume_layout.setColumnStretch(1, 1)

        # --- Configuration Section ---
        config_group = QGroupBox("Configure Interview")
        config_group.setFont(pw.font_large_bold)
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(25)

        # Topics Widget
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
        self.topic_minus_btn.clicked.connect(lambda: pw._adjust_value('topics', -1)) # Connect to parent's slot
        self.num_topics_label = QLabel(str(pw.num_topics)) # Read initial state from parent
        self.num_topics_label.setFont(pw.font_default)
        self.num_topics_label.setMinimumWidth(25)
        self.num_topics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.topic_plus_btn = QPushButton("")
        self.topic_plus_btn.setObjectName("adjustButton")
        if plus_icon: self.topic_plus_btn.setIcon(plus_icon)
        self.topic_plus_btn.setIconSize(button_icon_size)
        self.topic_plus_btn.setFixedSize(QSize(28, 28))
        self.topic_plus_btn.setToolTip("Increase topics")
        self.topic_plus_btn.clicked.connect(lambda: pw._adjust_value('topics', +1)) # Connect to parent's slot
        topics_inner_layout.addWidget(topics_label_prefix)
        topics_inner_layout.addWidget(self.topic_minus_btn)
        topics_inner_layout.addWidget(self.num_topics_label)
        topics_inner_layout.addWidget(self.topic_plus_btn)
        config_layout.addWidget(topics_widget)

        # Follow-ups Widget (similar structure, assigning widgets to self)
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
        self.max_follow_ups_label = QLabel(str(pw.max_follow_ups)) # Read initial state
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

        # Separator Line
        config_line = QFrame()
        config_line.setFrameShape(QFrame.Shape.VLine)
        config_line.setFrameShadow(QFrame.Shadow.Sunken)
        config_layout.addWidget(config_line)

        # Speech Input Checkbox
        self.speech_checkbox = QCheckBox("Use Speech Input (STT)")
        self.speech_checkbox.setFont(pw.font_default)
        self.speech_checkbox.stateChanged.connect(pw.update_submit_button_text) # Connect to parent's slot
        config_layout.addWidget(self.speech_checkbox)

        # OpenAI TTS Checkbox
        self.openai_tts_checkbox = QCheckBox("Use OpenAI TTS")
        self.openai_tts_checkbox.setFont(pw.font_default)
        openai_available = "openai" in tts.get_potentially_available_providers()
        if openai_available:
            self.openai_tts_checkbox.setToolTip("Use OpenAI for higher quality Text-to-Speech (requires API key in keyring).")
            self.openai_tts_checkbox.stateChanged.connect(pw._handle_openai_tts_change) # Connect to parent's slot
        else:
            self.openai_tts_checkbox.setToolTip("OpenAI TTS unavailable (missing dependencies or API key/init failed). Check console.")
            self.openai_tts_checkbox.setEnabled(False)
        config_layout.addWidget(self.openai_tts_checkbox)

        config_layout.addStretch()

        # --- Job Description Section ---
        jd_group = QGroupBox("Job Description (Optional)")
        jd_group.setFont(pw.font_large_bold)
        jd_layout = QVBoxLayout(jd_group)
        self.job_desc_input = QTextEdit()
        self.job_desc_input.setPlaceholderText("Paste job description here...")
        self.job_desc_input.setFont(pw.font_small)
        self.job_desc_input.setMinimumHeight(100)
        self.job_desc_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        jd_layout.addWidget(self.job_desc_input)

        # --- Add Groups to Page Layout ---
        page_layout.addWidget(resume_group)
        page_layout.addWidget(config_group)
        page_layout.addWidget(jd_group, stretch=1)

        # --- Start Button ---
        start_button_layout = QHBoxLayout()
        self.start_interview_btn = QPushButton("Next: Start Interview")
        if start_icon: self.start_interview_btn.setIcon(start_icon)
        self.start_interview_btn.setIconSize(pw.icon_size)
        self.start_interview_btn.setFont(pw.font_bold)
        self.start_interview_btn.setFixedHeight(40)
        self.start_interview_btn.clicked.connect(pw.start_interview_process) # Connect to parent's slot
        start_button_layout.addStretch()
        start_button_layout.addWidget(self.start_interview_btn)
        start_button_layout.addStretch()

        page_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        page_layout.addLayout(start_button_layout)

        self.setLayout(page_layout)

    # Add methods here if the setup page itself needs internal logic,
    # otherwise most logic remains in InterviewApp.
    # Example: A method to reset fields specific to this page.
    def clear_fields(self):
        if hasattr(self, 'file_label'): self.file_label.setText("No resume selected.")
        if hasattr(self, 'job_desc_input'): self.job_desc_input.clear()
        # Reset checkboxes based on parent state? Or parent resets state and calls update_ui?
        # Parent resetting state and calling _update_ui_from_state (which updates page widgets)
        # is generally cleaner.

    def update_widgets_from_state(self):
        """Updates widgets based on parent_window's state."""
        pw = self.parent_window
        pdf_loaded = bool(pw.pdf_filepath)

        if hasattr(self, 'file_label'):
            self.file_label.setText(os.path.basename(pw.pdf_filepath) if pdf_loaded else "No resume selected.")
        if hasattr(self, 'job_desc_input'):
             # Avoid overwriting if user is typing during a partial reset
             # Check if current text differs from state before setting? Or rely on full reset logic.
             # Let's assume parent's reset logic handles this state variable correctly.
             if self.job_desc_input.toPlainText() != pw.job_description_text:
                 self.job_desc_input.setPlainText(pw.job_description_text)
        if hasattr(self, 'num_topics_label'):
            self.num_topics_label.setText(str(pw.num_topics))
        if hasattr(self, 'max_follow_ups_label'):
            self.max_follow_ups_label.setText(str(pw.max_follow_ups))
        if hasattr(self, 'speech_checkbox'):
            self.speech_checkbox.setChecked(pw.use_speech_input)
        if hasattr(self, 'openai_tts_checkbox'):
             self.openai_tts_checkbox.blockSignals(True)
             self.openai_tts_checkbox.setChecked(pw.use_openai_tts)
             openai_deps_met = "openai" in tts.get_potentially_available_providers()
             # Enable state depends on deps AND whether PDF is loaded (handled by set_controls_state)
             self.openai_tts_checkbox.setEnabled(pdf_loaded and openai_deps_met)
             self.openai_tts_checkbox.blockSignals(False)

        self.set_controls_enabled_state(pdf_loaded)


    def set_controls_enabled_state(self, pdf_loaded):
        """Enable/disable controls based on whether a PDF is loaded."""
        # Controls within this page
        controls_to_manage = [
            (getattr(self, 'job_desc_input', None), True),
            (getattr(self, 'topic_minus_btn', None), True),
            (getattr(self, 'topic_plus_btn', None), True),
            (getattr(self, 'num_topics_label', None), True), # Label enable might be optional
            (getattr(self, 'followup_minus_btn', None), True),
            (getattr(self, 'followup_plus_btn', None), True),
            (getattr(self, 'max_follow_ups_label', None), True), # Label enable might be optional
            (getattr(self, 'speech_checkbox', None), True),
            (getattr(self, 'start_interview_btn', None), True),
            (getattr(self, 'openai_tts_checkbox', None), False) # Special handling
        ]

        openai_deps_met = "openai" in tts.get_potentially_available_providers()

        for widget, is_always_pdf_dependent in controls_to_manage:
            if widget:
                should_enable = pdf_loaded

                if widget == self.openai_tts_checkbox:
                    should_enable = pdf_loaded and openai_deps_met
                # 'select_btn' is always enabled initially, handled separately if needed

                widget.setEnabled(should_enable)

        # Ensure select button is always enabled (unless generating questions)
        if hasattr(self, 'select_btn'):
            # Parent window should handle disabling this during question generation
            pass # self.select_btn.setEnabled(True) # Assume enabled unless parent disables