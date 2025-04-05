# ui/results_page.py
"""
Defines the Results Page QWidget for the Interview App.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QGroupBox, QSizePolicy, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSize

# Import shared components
from .components import _load_icon

class ResultsPage(QWidget):
    """
    The results page displaying summary, assessment, and actions.
    """
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI elements for the results page."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(15)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window # Shortcut

        # Icons
        save_icon = _load_icon(pw.icon_path, "save.png")
        folder_icon = _load_icon(pw.icon_path, "folder.png")

        # --- Summary Section ---
        summary_group = QGroupBox("Performance Summary")
        summary_group.setFont(pw.font_large_bold)
        summary_layout = QVBoxLayout(summary_group)
        # Assign widgets to self
        self.summary_text_results = QTextEdit()
        self.summary_text_results.setReadOnly(True)
        self.summary_text_results.setFont(pw.font_small)
        self.summary_text_results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.summary_text_results.setAcceptRichText(True)
        summary_layout.addWidget(self.summary_text_results)
        page_layout.addWidget(summary_group, stretch=1)

        # --- Assessment Section ---
        assessment_group = QGroupBox("Qualification Assessment")
        assessment_group.setFont(pw.font_large_bold)
        assessment_layout = QVBoxLayout(assessment_group)
        self.assessment_text_results = QTextEdit()
        self.assessment_text_results.setReadOnly(True)
        self.assessment_text_results.setFont(pw.font_small)
        self.assessment_text_results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.assessment_text_results.setAcceptRichText(True)
        assessment_layout.addWidget(self.assessment_text_results)
        page_layout.addWidget(assessment_group, stretch=1)

        # --- Action Buttons Layout ---
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(15)

        # Save Report Button
        self.save_report_button = QPushButton("Save Report")
        if save_icon: self.save_report_button.setIcon(save_icon)
        self.save_report_button.setIconSize(pw.icon_size)
        self.save_report_button.setFont(pw.font_default)
        self.save_report_button.clicked.connect(pw._save_report) # Connect to parent's slot
        self.save_report_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.save_report_button)

        # Open Folder Button
        self.open_folder_button = QPushButton("Open Recordings Folder")
        if folder_icon: self.open_folder_button.setIcon(folder_icon)
        self.open_folder_button.setIconSize(pw.icon_size)
        self.open_folder_button.setFont(pw.font_default)
        self.open_folder_button.clicked.connect(pw._open_recordings_folder) # Connect to parent's slot
        self.open_folder_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.open_folder_button)

        action_buttons_layout.addStretch()

        # New Interview Button
        self.new_interview_button = QPushButton("Finish & Start New")
        self.new_interview_button.setFont(pw.font_bold)
        self.new_interview_button.setFixedHeight(40)
        self.new_interview_button.clicked.connect(pw._go_to_setup_page) # Connect to parent's slot
        action_buttons_layout.addWidget(self.new_interview_button)

        page_layout.addLayout(action_buttons_layout)

        self.setLayout(page_layout)

    def display_results(self, summary, assessment):
        """Sets the text for the results text areas."""
        if hasattr(self, 'summary_text_results'):
             self.summary_text_results.setMarkdown(summary or "*Summary generation failed or N/A*")
        if hasattr(self, 'assessment_text_results'):
             self.assessment_text_results.setMarkdown(assessment or "*Assessment generation failed or N/A*")

    def clear_fields(self):
        """Clears the results text areas."""
        if hasattr(self, 'summary_text_results'): self.summary_text_results.clear()
        if hasattr(self, 'assessment_text_results'): self.assessment_text_results.clear()