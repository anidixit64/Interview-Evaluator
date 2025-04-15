# ui/results_page_part1.py
"""
Defines the first part of the results page, showing score summaries.
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

# --- Constants moved from original ResultsPage ---
FIXED_SPEECH_SCORE = 75
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
        self.transcript_text_edit = None
        
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
        self._load_transcript()

    def _create_score_ring_with_label(self, label_text: str, initial_score: int, size: int = 150) -> tuple[QWidget, CircularProgressBarRing]:
        """Creates a circular progress ring with a label underneath."""
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Increased margins
        layout.setSpacing(25)  # Increased spacing between sections
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Top rings section ---
        rings_container = QWidget()
        rings_layout = QHBoxLayout(rings_container)
        rings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rings_layout.setSpacing(40)  # Increased spacing between rings
        
        # Create speech score ring with label
        speech_container, self.speech_score_ring = self._create_score_ring_with_label(
            "Speech Delivery", FIXED_SPEECH_SCORE, size=200  # Increased ring size
        )
        
        # Create content score ring with label
        content_ring_container, self.content_score_ring = self._create_score_ring_with_label(
            "Content Score", 0, size=200  # Increased ring size
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
        formatted_html = "<div style='line-height: 1.5;'>"
        
        # Split the text into question-answer blocks by the separator
        blocks = re.split(r'-{10,}', text)
        
        for block in blocks:
            if not block.strip():
                continue
                
            # Extract the main question
            main_q_match = re.search(r'Question (\d+): (.*?)(?=Answer:|$)', block, re.DOTALL)
            if main_q_match:
                q_num, q_text = main_q_match.groups()
                formatted_html += f"""
                <div style='margin-bottom: 15px; margin-top: 25px;'>
                    <div>
                        <span style='font-size: {CONTENT_FONT_SIZE+2}pt; color: #4fc3f7; font-weight: bold;'>Question {q_num}:</span>
                        <div style='margin-top: 10px; font-size: {CONTENT_FONT_SIZE}pt; color: #e0e0e0; padding-left: 10px;'>{q_text.strip()}</div>
                    </div>
                """
            
            # Extract all answer and follow-up pairs
            qa_pairs = re.findall(r'(?:Answer|Follow Up \(re Topic \d+\)): (.*?)(?=(?:Answer|Follow Up \(re Topic \d+\))|$)', block, re.DOTALL)
            follow_up_questions = re.findall(r'Follow Up \(re Topic \d+\): (.*?)(?=Answer:|$)', block, re.DOTALL)
            
            # Extract all the questions (main + follow-ups)
            all_questions = []
            if main_q_match:
                all_questions.append(main_q_match.group(2))
            all_questions.extend(follow_up_questions)
            
            # Process the QA pairs
            last_was_followup = False
            answer_index = 0
            
            # First process the main answer
            if qa_pairs and answer_index < len(qa_pairs):
                a_text = qa_pairs[answer_index].strip()
                answer_index += 1
                
                formatted_html += f"""
                    <div style='margin-top: 12px; margin-left: 25px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+2}pt; color: #ff9800; font-weight: bold;'>Answer:</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; padding-left: 15px;'>{a_text}</div>
                    </div>
                """

            # Process follow-up questions and their answers
            follow_up_matches = re.finditer(r'Follow Up \(re Topic (\d+)\): (.*?)(?=Answer:|$)', block, re.DOTALL)
            for follow_up_match in follow_up_matches:
                topic_num, follow_up_text = follow_up_match.groups()
                
                # Add the follow-up question
                formatted_html += f"""
                    <div style='margin-top: 18px; margin-left: 15px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #81d4fa; font-weight: bold;'>Follow Up (Topic {topic_num}):</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #e0e0e0; padding-left: 15px;'>{follow_up_text.strip()}</div>
                    </div>
                """
                
                # Add corresponding answer if available
                if answer_index < len(qa_pairs):
                    a_text = qa_pairs[answer_index].strip()
                    answer_index += 1
                    
                    formatted_html += f"""
                        <div style='margin-top: 12px; margin-left: 40px;'>
                            <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #ffb74d; font-weight: bold;'>Answer:</span>
                            <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; padding-left: 15px;'>{a_text}</div>
                        </div>
                    """
            
            formatted_html += "</div>"
            formatted_html += "<hr style='border: 0; height: 1px; background-color: #555555; margin: 20px 0;'>"
        
        formatted_html += "</div>"
        
        # If no questions found, return original text
        if "<span" not in formatted_html:
            return f"<pre style='font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0;'>{text}</pre>"
            
        return formatted_html

    def _load_transcript(self):
        """Loads the transcript from the file and displays it."""
        # Use the correct path to the transcript file
        transcript_path = os.path.join(os.path.expanduser("~"), "Documents", "InterviewBotPro", "Recordings", "transcript.txt")
        
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

    def display_results(self, content_score_data: dict | None):
        """Updates the content score section."""
        placeholder_content_score = "*Content score analysis failed or N/A.*"

        if content_score_data and not content_score_data.get("error"):
            score = content_score_data.get('score', 0)
            analysis_text = content_score_data.get('analysis_text', placeholder_content_score)
            if self.content_score_ring: self.content_score_ring.setValue(score)
            if self.content_score_text_edit: self.content_score_text_edit.setMarkdown(f"**Content Analysis (Structure & Relevance):**\n\n{analysis_text}")
            # Reload transcript in case it was updated
            self._load_transcript()
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
        if self.transcript_text_edit:
            self.transcript_text_edit.setHtml("<div style='color: #e0e0e0; font-size: 14pt;'>Loading transcript...</div>")