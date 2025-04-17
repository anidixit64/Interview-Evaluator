# FILE: ui/results_page_part1.py
# MODIFIED: Added import for RECORDINGS_DIR.
"""
Defines the first part of the results page, showing score summaries.
Displays calculated average Speech Delivery score and Content score.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt
import os
import re

# Import shared components (assuming files are in the same directory)
from .circular_progress_ring import CircularProgressBarRing
# --- ADDED Import ---
from core.recording import RECORDINGS_DIR # Import the missing constant
# --- End Import ---

# --- Constants ---
# Font size constants
LARGE_FONT_SIZE = 16  # For titles and labels
CONTENT_FONT_SIZE = 14  # For content text

class ResultsPagePart1(QWidget):
    """Displays Speech and Content scores."""
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs) # No parent needed here if managed by container
        self.parent_window = parent_window
        self.speech_score_ring = None
        self.content_score_ring = None
        self.content_score_text_edit = None
        self.transcript_text_edit = None # Added missing member initialization

        # Create larger fonts
        self.title_font = QFont()
        self.title_font.setPointSize(LARGE_FONT_SIZE + 2)  # Even larger for headings
        self.title_font.setBold(True)

        self.label_font = QFont()
        self.label_font.setPointSize(LARGE_FONT_SIZE)
        self.label_font.setBold(True)

        self.content_font = QFont()
        self.content_font.setPointSize(CONTENT_FONT_SIZE)

        self._init_ui()
        # Do not load transcript initially, wait for display_results

    def _create_score_ring_with_label(self, label_text: str, initial_score: int, size: int = 150) -> tuple[QWidget, CircularProgressBarRing]:
        """Creates a circular progress ring with a label underneath."""
        # (Code remains the same)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create the progress ring
        progress_ring = CircularProgressBarRing()
        progress_ring.setRange(0, 100)
        progress_ring.setValue(initial_score)
        progress_ring.setFixedSize(size, size)

        # Create the label with larger font
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(self.label_font)

        # Add widgets to layout
        layout.addWidget(progress_ring)
        layout.addWidget(label)

        return container, progress_ring

    def _create_content_analysis_section(self, initial_description: str) -> tuple[QWidget, QTextEdit]:
        """Creates the content analysis section with only text box."""
        # (Code remains the same)
        section_group = QGroupBox("Response Content Analysis")
        section_group.setFont(self.title_font)
        section_layout = QVBoxLayout(section_group)
        section_layout.setContentsMargins(15, 15, 15, 15)  # Increased margins

        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setMarkdown(initial_description)
        desc_edit.setFont(self.content_font)
        desc_edit.setObjectName("scoreDescriptionEdit")
        desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Set a minimum height to accommodate larger text
        desc_edit.setMinimumHeight(180)

        section_layout.addWidget(desc_edit)

        return section_group, desc_edit

    def _create_transcript_section(self) -> tuple[QWidget, QTextEdit]:
        """Creates the transcript section."""
        # (Code remains the same)
        section_group = QGroupBox("Interview Transcript")
        section_group.setFont(self.title_font)
        section_layout = QVBoxLayout(section_group)
        section_layout.setContentsMargins(15, 15, 15, 15)  # Increased margins

        transcript_edit = QTextEdit()
        transcript_edit.setReadOnly(True)
        transcript_edit.setFont(self.content_font)
        transcript_edit.setObjectName("transcriptEdit")
        transcript_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Set minimum height to show a reasonable amount of text
        transcript_edit.setMinimumHeight(250)  # Increased height further

        section_layout.addWidget(transcript_edit)

        return section_group, transcript_edit

    def _init_ui(self):
        """Initializes the UI elements for Part 1."""
        # (Code remains the same)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Increased margins
        layout.setSpacing(25)  # Increased spacing between sections
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Top rings section ---
        rings_container = QWidget()
        rings_layout = QHBoxLayout(rings_container)
        rings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rings_layout.setSpacing(40)  # Increased spacing between rings

        # Create speech score ring with label, initialized to 0
        speech_container, self.speech_score_ring = self._create_score_ring_with_label(
            "Speech Delivery", 0, size=200  # Initialize with 0
        )

        # Create content score ring with label, initialized to 0
        content_ring_container, self.content_score_ring = self._create_score_ring_with_label(
            "Content Score", 0, size=200  # Initialize with 0
        )

        # Add both ring containers to the layout
        rings_layout.addWidget(speech_container)
        rings_layout.addWidget(content_ring_container)

        layout.addWidget(rings_container)

        # --- Content Analysis Section ---
        content_section_group, self.content_score_text_edit = self._create_content_analysis_section(
            "*Content score analysis loading...*"
        )
        layout.addWidget(content_section_group)

        # --- Transcript Section ---
        transcript_section_group, self.transcript_text_edit = self._create_transcript_section()
        layout.addWidget(transcript_section_group)

        layout.addStretch(1) # Push everything up if space allows

    def _parse_transcript_text(self, text):
        """
        Parse the transcript text to separate questions, follow-ups, and answers.
        Handles the expanded format with follow-up questions.

        Format for dark mode using colors rather than backgrounds for better readability.
        """
        # (Code remains the same)
        formatted_html = "<div style='line-height: 1.5;'>"

        # Split the text into question-answer blocks by the separator or newline Q+A pattern
        # Updated regex to handle potential variations in separators
        blocks = re.split(r'\n-{10,}\n|\n(?=Question \d+:)', text)

        for block in blocks:
            if not block.strip():
                continue

            # Process a single block (Q/A/Follow-up cluster)
            block_html = ""
            current_indent = 0
            lines = block.strip().split('\n')
            is_first_question = True

            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue

                q_match = re.match(r'Question (\d+): (.*)', line)
                fu_match = re.match(r'Follow Up \(re Topic (\d+)\): (.*)', line)
                a_match = re.match(r'Answer: (.*)', line)

                if q_match:
                    q_num, q_text = q_match.groups()
                    block_html += f"""
                    {'<hr style="border: 0; height: 1px; background-color: #555555; margin: 20px 0;">' if not is_first_question else ''}
                    <div style='margin-top: {'10' if is_first_question else '25'}px; margin-left: {current_indent}px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+2}pt; color: #4fc3f7; font-weight: bold;'>Question {q_num}:</span>
                        <div style='margin-top: 10px; font-size: {CONTENT_FONT_SIZE}pt; color: #e0e0e0; padding-left: 10px;'>{q_text.strip()}</div>
                    </div>
                    """
                    current_indent = 25 # Indent answers relative to questions
                    is_first_question = False
                elif fu_match:
                    topic_num, fu_text = fu_match.groups()
                    current_indent = 15 # Indent follow-ups slightly
                    block_html += f"""
                    <div style='margin-top: 18px; margin-left: {current_indent}px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #81d4fa; font-weight: bold;'>Follow Up (Topic {topic_num}):</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #e0e0e0; padding-left: 15px;'>{fu_text.strip()}</div>
                    </div>
                    """
                    current_indent = 40 # Indent answers to follow-ups more
                elif a_match:
                    a_text = a_match.group(1)
                    # Extract multi-line answers
                    next_line_index = i + 1
                    while next_line_index < len(lines) and \
                          not re.match(r'Question \d+:', lines[next_line_index]) and \
                          not re.match(r'Follow Up \(re Topic \d+\):', lines[next_line_index]) and \
                          not re.match(r'Answer:', lines[next_line_index]) and \
                          not re.match(r'-{10,}', lines[next_line_index]):
                        a_text += "\n" + lines[next_line_index].strip()
                        next_line_index += 1
                        i += 1 # Skip these lines in the outer loop

                    block_html += f"""
                    <div style='margin-top: 12px; margin-left: {current_indent}px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #ffb74d; font-weight: bold;'>Answer:</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; padding-left: 15px; white-space: pre-wrap;'>{a_text.strip()}</div>
                    </div>
                    """
                    # Reset indent for potential next question in the same block (unlikely with split regex)
                    current_indent = 0
                # else: # Handle lines that don't match known patterns if necessary
                #     block_html += f"<div style='margin-left: {current_indent}px; color: #aaa;'>{line}</div>" # Example: show unmatched lines

            if block_html: # Only add if something was parsed
                formatted_html += block_html

        formatted_html += "</div>" # Close main div

        # Check if any formatting was actually applied
        if not re.search(r'<span.*?>', formatted_html):
            print("Warning: Transcript parsing failed to identify Q/A structure. Displaying raw text.")
            # Fallback to preformatted text if parsing fails
            return f"<pre style='font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; white-space: pre-wrap;'>{text}</pre>"

        return formatted_html

    def _load_transcript(self):
        """Loads the transcript from the file and displays it."""
        # Use the imported constant RECORDINGS_DIR
        transcript_path = os.path.join(RECORDINGS_DIR, "transcript.txt")

        try:
            if os.path.exists(transcript_path):
                with open(transcript_path, 'r', encoding='utf-8') as file:
                    transcript_text = file.read()

                # Parse and format the transcript
                formatted_transcript = self._parse_transcript_text(transcript_text)

                if self.transcript_text_edit:
                    self.transcript_text_edit.setHtml(formatted_transcript)
            else:
                if self.transcript_text_edit:
                    self.transcript_text_edit.setHtml(f"<div style='color: #ff6b6b; font-size: {CONTENT_FONT_SIZE}pt;'>Transcript file not found at: {transcript_path}</div>")
        except Exception as e:
            if self.transcript_text_edit:
                self.transcript_text_edit.setHtml(f"<div style='color: #ff6b6b; font-size: {CONTENT_FONT_SIZE}pt;'>Error loading transcript: {str(e)}</div>")

    def display_results(self, content_score_data: dict | None, avg_speech_score: int):
        """Updates the content score section and the speech score ring."""
        # (Code remains the same logic as previous version)
        placeholder_content_score = "*Content score analysis failed or N/A.*"

        # --- Update Speech Score Ring ---
        if self.speech_score_ring:
            score_to_set = ((avg_speech_score-3) / 3.0)**(1/2) * 100.0
            self.speech_score_ring.setValue(score_to_set)
            print(f"ResultsPagePart1: Setting speech score ring to {avg_speech_score}")

        # --- Update Content Score Ring and Text ---
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

        # --- Load Transcript ---
        self._load_transcript() # Load/reload transcript when results are displayed

    def clear_fields(self):
        """Clears the dynamic results widgets."""
        # (Code remains the same logic as previous version)
        if self.content_score_text_edit:
            self.content_score_text_edit.setMarkdown("*Content score analysis loading...*")
        if self.content_score_ring:
            self.content_score_ring.setValue(0)
        if self.speech_score_ring: # Added
            self.speech_score_ring.setValue(0)
        if self.transcript_text_edit:
            self.transcript_text_edit.setHtml("<div style='color: #e0e0e0; font-size: 14pt;'>Loading transcript...</div>")