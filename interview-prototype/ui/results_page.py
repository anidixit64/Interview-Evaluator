# ui/results_page.py
"""
Defines the Results Page QWidget for the Interview App.
Displays scores for speech and content, and an expandable job fit analysis.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QMessageBox,
    QGroupBox, QSizePolicy, QFrame, QScrollArea, QSpacerItem, QGridLayout # Added QGridLayout
)
from PyQt6.QtGui import QFont, QColor, QPixmap
from PyQt6.QtCore import Qt, QSize

# Import shared components
from .components import _load_icon
# Import the custom widgets
from .circular_progress_ring import CircularProgressBarRing
from .requirement_widget import RequirementWidget

# --- Constants ---
FIXED_SPEECH_SCORE = 75
FIXED_SPEECH_DESCRIPTION = """
**Prosody Analysis:**
*(Keep your original text)*

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
        self._load_icons()
        self.content_score_ring = None
        self.content_score_text_edit = None
        self._init_ui()

    def _load_icons(self):
        pw = self.parent_window; icon_size = QSize(16, 16)
        self.icon_met = _load_icon(pw.icon_path, "check.png", size=icon_size)
        self.icon_partial = _load_icon(pw.icon_path, "question.png", size=icon_size)
        self.icon_gap = _load_icon(pw.icon_path, "cross.png", size=icon_size)
        self.icon_unknown = _load_icon(pw.icon_path, "minus_circle.png", size=icon_size)

    def _get_assessment_icon(self, assessment_level: str) -> QPixmap | None:
        level_lower = assessment_level.lower(); icon = None
        if "strong" in level_lower: icon = self.icon_met
        elif "potential" in level_lower: icon = self.icon_partial
        elif "weak" in level_lower or "gap" in level_lower: icon = self.icon_gap
        elif "insufficient" in level_lower: icon = self.icon_unknown
        else: icon = self.icon_unknown
        return icon.pixmap(QSize(16, 16)) if icon and not icon.isNull() else None

    def _create_score_section(self, title: str, initial_description: str, initial_score: int) -> tuple[QWidget, CircularProgressBarRing, QTextEdit]:
        section_group = QGroupBox(title)
        section_group.setFont(self.parent_window.font_large_bold)
        section_layout = QHBoxLayout(section_group)
        section_layout.setSpacing(15); section_layout.setContentsMargins(10, 5, 10, 10)
        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True); desc_edit.setMarkdown(initial_description)
        desc_edit.setFont(self.parent_window.font_small); desc_edit.setObjectName("scoreDescriptionEdit")
        desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        progress_container = QWidget(); progress_layout = QVBoxLayout(progress_container)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); progress_layout.setContentsMargins(0,0,0,0)
        progress_ring = CircularProgressBarRing()
        progress_ring.setRange(0, 100); progress_ring.setValue(initial_score)
        circle_size = 100; progress_ring.setFixedSize(circle_size, circle_size)
        progress_layout.addWidget(progress_ring); section_layout.addWidget(desc_edit, stretch=3)
        section_layout.addWidget(progress_container, stretch=1)
        return section_group, progress_ring, desc_edit


    def _init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(15, 15, 15, 15); page_layout.setSpacing(20)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window

        # --- Score Sections ---
        speech_section_group, _, _ = self._create_score_section(
            "Speech Delivery Score", FIXED_SPEECH_DESCRIPTION, FIXED_SPEECH_SCORE
        )
        content_section_group, self.content_score_ring, self.content_score_text_edit = self._create_score_section(
            "Response Content Score", "*Content score analysis loading...*", 0
        )

        # --- Job Fit Analysis Section ---
        job_fit_group = QGroupBox("Job Fit Analysis - Requirements Breakdown (Click to expand)")
        job_fit_group.setFont(pw.font_large_bold)
        job_fit_outer_layout = QVBoxLayout(job_fit_group)
        job_fit_outer_layout.setContentsMargins(10, 5, 10, 10); job_fit_outer_layout.setSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("requirementsScrollArea")

        self.requirements_container = QWidget()
        # *** Use QGridLayout ***
        self.requirements_layout = QGridLayout(self.requirements_container)
        self.requirements_layout.setContentsMargins(5, 5, 5, 5)
        self.requirements_layout.setSpacing(10) # Spacing between grid items
        # No alignment needed for grid layout itself

        self.scroll_area.setWidget(self.requirements_container)

        self.overall_fit_label = QLabel("<b>Overall Fit Assessment:</b> *Loading...*")
        self.overall_fit_label.setFont(pw.font_small); self.overall_fit_label.setWordWrap(True)
        self.overall_fit_label.setContentsMargins(0, 10, 0, 0)

        job_fit_outer_layout.addWidget(self.scroll_area, stretch=1)
        job_fit_outer_layout.addWidget(self.overall_fit_label)

        page_layout.addWidget(speech_section_group)
        page_layout.addWidget(content_section_group)
        page_layout.addWidget(job_fit_group, stretch=1)

        # --- Action Buttons ---
        action_buttons_layout = QHBoxLayout(); action_buttons_layout.setSpacing(15)
        save_icon = _load_icon(pw.icon_path, "save.png"); folder_icon = _load_icon(pw.icon_path, "folder.png")
        self.save_report_button = QPushButton("Save Report")
        if save_icon: self.save_report_button.setIcon(save_icon)
        self.save_report_button.setIconSize(pw.icon_size); self.save_report_button.setFont(pw.font_default)
        self.save_report_button.clicked.connect(pw._save_report); self.save_report_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.save_report_button)
        self.open_folder_button = QPushButton("Open Recordings Folder")
        if folder_icon: self.open_folder_button.setIcon(folder_icon)
        self.open_folder_button.setIconSize(pw.icon_size); self.open_folder_button.setFont(pw.font_default)
        self.open_folder_button.clicked.connect(pw._open_recordings_folder); self.open_folder_button.setFixedHeight(35)
        action_buttons_layout.addWidget(self.open_folder_button)
        action_buttons_layout.addStretch()
        self.new_interview_button = QPushButton("Finish & Start New")
        self.new_interview_button.setFont(pw.font_bold); self.new_interview_button.setFixedHeight(40)
        self.new_interview_button.clicked.connect(pw._go_to_setup_page)
        action_buttons_layout.addWidget(self.new_interview_button)
        page_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        page_layout.addLayout(action_buttons_layout)

        self.setLayout(page_layout)

    # --- MODIFIED Function ---
    def display_results(self, summary: str | None, assessment_data: dict | None, content_score_data: dict | None):
        """
        Sets the dynamic text and populates requirement sections in a grid layout.
        Updates the content score based on provided data.
        """
        placeholder_summary = "*Summary generation failed or N/A*"
        placeholder_assessment = "*Assessment generation failed or N/A.*"
        placeholder_content_score = "*Content score analysis failed or N/A.*"
        placeholder_req_error = "Could not load requirements."

        # Update Content Score Section
        if content_score_data and not content_score_data.get("error"):
            score = content_score_data.get('score', 0)
            analysis_text = content_score_data.get('analysis_text', placeholder_content_score)
            if self.content_score_ring: self.content_score_ring.setValue(score)
            if self.content_score_text_edit: self.content_score_text_edit.setMarkdown(f"**Content Analysis (Structure & Relevance):**\n\n{analysis_text}")
        else:
            error_msg = content_score_data.get("error") if content_score_data else placeholder_content_score
            if self.content_score_ring: self.content_score_ring.setValue(0)
            if self.content_score_text_edit: self.content_score_text_edit.setMarkdown(f"**Content Analysis (Structure & Relevance):**\n\n*Error: {error_msg}*")

        # Clear previous requirements
        while (item := self.requirements_layout.takeAt(0)) is not None:
            if item.widget(): item.widget().deleteLater()

        # Populate Job Fit Requirements in a Grid
        if assessment_data and not assessment_data.get("error"):
            requirements = assessment_data.get("requirements", [])
            overall_fit = assessment_data.get("overall_fit", placeholder_assessment)

            if requirements:
                row, col = 0, 0
                for req_data in requirements:
                    assessment_level = req_data.get("assessment", "Unknown")
                    icon_pixmap = self._get_assessment_icon(assessment_level)
                    req_widget = RequirementWidget(req_data, icon_pixmap, self)
                    # Add widget to the grid layout
                    self.requirements_layout.addWidget(req_widget, row, col)
                    # Alternate columns, move to next row after second column
                    col += 1
                    if col > 1:
                        col = 0
                        row += 1
            else:
                 error_label = QLabel(placeholder_req_error)
                 self.requirements_layout.addWidget(error_label, 0, 0, 1, 2) # Span error across columns

            self.overall_fit_label.setText(f"<b>Overall Fit Assessment:</b> {overall_fit}")

        else:
            error_msg = assessment_data.get("error") if assessment_data else placeholder_assessment
            error_label = QLabel(f"<i>{error_msg}</i>"); error_label.setWordWrap(True)
            self.requirements_layout.addWidget(error_label, 0, 0, 1, 2) # Span error
            self.overall_fit_label.setText(f"<b>Overall Fit Assessment:</b> N/A")

        # *** Remove stretch for grid layout ***
        # self.requirements_layout.addStretch(1) # Not typically needed/used with grid

    # --- _show_reasoning_dialog REMOVED ---

    def clear_fields(self):
        """Clears the dynamic results widgets."""
        if hasattr(self, 'content_score_text_edit') and self.content_score_text_edit:
            self.content_score_text_edit.setMarkdown("*Content score analysis loading...*")
        if hasattr(self, 'content_score_ring') and self.content_score_ring:
            self.content_score_ring.setValue(0)
        if hasattr(self, 'requirements_layout') and self.requirements_layout:
             while (item := self.requirements_layout.takeAt(0)) is not None:
                if item.widget(): item.widget().deleteLater()
        if hasattr(self, 'overall_fit_label') and self.overall_fit_label:
            self.overall_fit_label.setText("<b>Overall Fit Assessment:</b> *Loading...*")