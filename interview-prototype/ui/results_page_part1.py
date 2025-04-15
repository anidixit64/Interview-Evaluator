# ui/results_page_part1.py
"""
Defines the first part of the results page, showing score summaries.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# Import shared components (assuming files are in the same directory)
from .circular_progress_ring import CircularProgressBarRing

# --- Constants moved from original ResultsPage ---
FIXED_SPEECH_SCORE = 75
FIXED_SPEECH_DESCRIPTION = """
**Prosody Analysis:**
*(Keep your original text)*

*(Note: This is a placeholder analysis.)*
"""
# FIXED_CONTENT_SCORE removed as it's now dynamic

class ResultsPagePart1(QWidget):
    """Displays Speech and Content scores."""
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs) # No parent needed here if managed by container
        self.parent_window = parent_window
        self.content_score_ring = None
        self.content_score_text_edit = None
        self._init_ui()

    def _create_score_section(self, title: str, initial_description: str, initial_score: int) -> tuple[QWidget, CircularProgressBarRing | None, QTextEdit | None]:
        """Creates a standard score section with a ring and description."""
        # Note: parent_window is accessible via self.parent_window
        section_group = QGroupBox(title)
        section_group.setFont(self.parent_window.font_large_bold)
        section_layout = QHBoxLayout(section_group)
        section_layout.setSpacing(15)
        section_layout.setContentsMargins(10, 5, 10, 10)

        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setMarkdown(initial_description)
        desc_edit.setFont(self.parent_window.font_small)
        desc_edit.setObjectName("scoreDescriptionEdit")
        desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.setContentsMargins(0,0,0,0)

        progress_ring = CircularProgressBarRing()
        progress_ring.setRange(0, 100)
        progress_ring.setValue(initial_score)
        circle_size = 100 # Consistent size
        progress_ring.setFixedSize(circle_size, circle_size)

        progress_layout.addWidget(progress_ring)
        section_layout.addWidget(desc_edit, stretch=3)
        section_layout.addWidget(progress_container, stretch=1)

        return section_group, progress_ring, desc_edit

    def _init_ui(self):
        """Initializes the UI elements for Part 1."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Container will handle margins
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Score Sections ---
        # Speech Score (Fixed)
        speech_section_group, _, _ = self._create_score_section(
            "Speech Delivery Score", FIXED_SPEECH_DESCRIPTION, FIXED_SPEECH_SCORE
        )
        layout.addWidget(speech_section_group)

        # Content Score (Dynamic)
        content_section_group, self.content_score_ring, self.content_score_text_edit = self._create_score_section(
            "Response Content Score", "*Content score analysis loading...*", 0
        )
        layout.addWidget(content_section_group)

        layout.addStretch(1) # Push scores up if space allows

    def display_results(self, content_score_data: dict | None):
        """Updates the content score section."""
        placeholder_content_score = "*Content score analysis failed or N/A.*"

        if content_score_data and not content_score_data.get("error"):
            score = content_score_data.get('score', 0)
            analysis_text = content_score_data.get('analysis_text', placeholder_content_score)
            if self.content_score_ring: self.content_score_ring.setValue(score)
            if self.content_score_text_edit: self.content_score_text_edit.setMarkdown(f"**Content Analysis (Structure & Relevance):**\n\n{analysis_text}")
        else:
            error_msg = content_score_data.get("error") if content_score_data else "Analysis unavailable"
            if self.content_score_ring: self.content_score_ring.setValue(0)
            if self.content_score_text_edit:
                self.content_score_text_edit.setMarkdown(f"**Content Analysis (Structure & Relevance):**\n\n*Error: {error_msg}*")

    def clear_fields(self):
        """Clears the dynamic results widgets."""
        if self.content_score_text_edit:
            self.content_score_text_edit.setMarkdown("*Content score analysis loading...*")
        if self.content_score_ring:
            self.content_score_ring.setValue(0)