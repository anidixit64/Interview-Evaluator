# ui/results_page.py
"""
Defines the Results Page QWidget for the Interview App.
Displays scores for speech and content, and a job fit analysis.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QGroupBox, QSizePolicy, QFrame, QProgressBar, QSpacerItem # Keep QProgressBar if needed elsewhere, otherwise remove
)
from PyQt6.QtGui import QFont, QColor # Added QColor
from PyQt6.QtCore import Qt, QSize

# Import shared components
from .components import _load_icon
# Import the custom widget
from .circular_progress_ring import CircularProgressBarRing

# --- Constants for Fixed Content ---
FIXED_SPEECH_SCORE = 75
FIXED_SPEECH_DESCRIPTION = """
**Prosody Analysis:**
The candidate's speech demonstrated good variation in pitch and tone, keeping the listener engaged. Pacing was generally appropriate, although there were moments of slight hesitation. Volume was consistent and easily audible.

*(Note: This is a placeholder analysis.)*
"""
FIXED_CONTENT_SCORE = 88

class ResultsPage(QWidget):
    """
    The results page displaying scores, analysis, and actions.
    """
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._init_ui()

    def _create_score_section(self, title: str, description: str, score: int) -> QWidget:
        """Helper function to create a score section (Speech or Content)."""
        section_group = QGroupBox(title)
        section_group.setFont(self.parent_window.font_large_bold)
        section_layout = QHBoxLayout(section_group)
        section_layout.setSpacing(15)
        section_layout.setContentsMargins(10, 5, 10, 10)

        # Description Text Area
        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setMarkdown(description)
        desc_edit.setFont(self.parent_window.font_small)
        desc_edit.setObjectName("scoreDescriptionEdit")
        desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Container for centering the progress ring
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.setContentsMargins(0,0,0,0)

        # *** Use the custom CircularProgressBarRing widget ***
        progress_ring = CircularProgressBarRing()
        progress_ring.setRange(0, 100)
        progress_ring.setValue(score)
        # Set custom colors if desired (otherwise uses defaults)
        # progress_ring.setProgressColor(QColor("#your_hex_code"))
        # progress_ring.setBackgroundColor(QColor("#your_bg_hex"))
        # progress_ring.setTextColor(QColor("#your_text_hex"))
        # progress_ring.setRingThickness(10.0)

        # Set fixed size for consistent appearance
        circle_size = 100
        progress_ring.setFixedSize(circle_size, circle_size)
        # No object name needed for QSS styling of the ring itself now

        progress_layout.addWidget(progress_ring)
        # Removed addStretch as AlignCenter should suffice

        # Add widgets to section layout
        section_layout.addWidget(desc_edit, stretch=3)
        section_layout.addWidget(progress_container, stretch=1)

        # Store reference to text edit if needed later
        # We'll handle this outside based on title

        return section_group


    def _init_ui(self):
        """Initialize the UI elements for the results page."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(20)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window

        # --- Create Score Sections ---
        speech_section = self._create_score_section(
            "Speech Delivery Score",
            FIXED_SPEECH_DESCRIPTION,
            FIXED_SPEECH_SCORE
        )

        content_section = self._create_score_section(
            "Response Content Score",
            "*Content analysis will appear here based on the interview summary.*",
            FIXED_CONTENT_SCORE
        )
        # Find the QTextEdit within the created group box to update later
        # Need to be careful with findChild if structure changes, but okay here.
        self.content_score_text_edit = content_section.findChild(QTextEdit) # Find the first QTextEdit


        # --- Job Fit Analysis Section ---
        job_fit_group = QGroupBox("Job Fit Analysis")
        job_fit_group.setFont(pw.font_large_bold)
        job_fit_layout = QVBoxLayout(job_fit_group)
        job_fit_layout.setContentsMargins(10, 5, 10, 10)

        self.job_fit_text_edit = QTextEdit()
        self.job_fit_text_edit.setReadOnly(True)
        self.job_fit_text_edit.setFont(pw.font_small)
        self.job_fit_text_edit.setMarkdown("*Job fit assessment will appear here.*")
        self.job_fit_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.job_fit_text_edit.setMinimumHeight(150)
        job_fit_layout.addWidget(self.job_fit_text_edit)

        # --- Add Sections to Page Layout ---
        page_layout.addWidget(speech_section)
        page_layout.addWidget(content_section)
        page_layout.addWidget(job_fit_group, stretch=1)


        # --- Action Buttons Layout ---
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(15)

        save_icon = _load_icon(pw.icon_path, "save.png")
        folder_icon = _load_icon(pw.icon_path, "folder.png")

        self.save_report_button = QPushButton("Save Report")
        if save_icon: self.save_report_button.setIcon(save_icon)
        self.save_report_button.setIconSize(pw.icon_size)
        self.save_report_button.setFont(pw.font_default)
        self.save_report_button.clicked.connect(pw._save_report)
        self.save_report_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.save_report_button)

        self.open_folder_button = QPushButton("Open Recordings Folder")
        if folder_icon: self.open_folder_button.setIcon(folder_icon)
        self.open_folder_button.setIconSize(pw.icon_size)
        self.open_folder_button.setFont(pw.font_default)
        self.open_folder_button.clicked.connect(pw._open_recordings_folder)
        self.open_folder_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.open_folder_button)

        action_buttons_layout.addStretch()

        self.new_interview_button = QPushButton("Finish & Start New")
        self.new_interview_button.setFont(pw.font_bold)
        self.new_interview_button.setFixedHeight(40)
        self.new_interview_button.clicked.connect(pw._go_to_setup_page)
        action_buttons_layout.addWidget(self.new_interview_button)

        page_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        page_layout.addLayout(action_buttons_layout)

        self.setLayout(page_layout)

    def display_results(self, summary, assessment):
        """Sets the dynamic text for the results page."""
        placeholder_summary = "*Summary generation failed or N/A*"
        placeholder_assessment = "*Assessment generation failed or N/A (No Job Description provided).*"

        if self.content_score_text_edit:
             content_desc = f"**Content Analysis (Summary):**\n\n{summary or placeholder_summary}"
             self.content_score_text_edit.setMarkdown(content_desc)
        else:
            print("Warning: content_score_text_edit not found in ResultsPage.")

        if self.job_fit_text_edit:
             self.job_fit_text_edit.setMarkdown(assessment or placeholder_assessment)
        else:
            print("Warning: job_fit_text_edit not found in ResultsPage.")

    def clear_fields(self):
        """Clears the dynamic results text areas."""
        if hasattr(self, 'content_score_text_edit') and self.content_score_text_edit:
            self.content_score_text_edit.setMarkdown(
                "*Content analysis will appear here based on the interview summary.*"
            )
        if hasattr(self, 'job_fit_text_edit') and self.job_fit_text_edit:
            self.job_fit_text_edit.setMarkdown("*Job fit assessment will appear here.*")
        # Reset dynamic scores here if they become dynamic
        # e.g., self.findChild(CircularProgressBarRing).setValue(0) # Need better way to find it