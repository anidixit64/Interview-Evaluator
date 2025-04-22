# ui/results_page_part1.py
import os
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

from .circular_progress_ring import CircularProgressBarRing
from core.recording import RECORDINGS_DIR

LARGE_FONT_SIZE = 16
CONTENT_FONT_SIZE = 14

class ResultsPagePart1(QWidget):
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_window = parent_window
        self.speech_score_ring = None
        self.content_score_ring = None
        self.content_score_text_edit = None
        self.transcript_text_edit = None

        self.title_font = QFont()
        self.title_font.setPointSize(LARGE_FONT_SIZE + 2)
        self.title_font.setBold(True)

        self.label_font = QFont()
        self.label_font.setPointSize(LARGE_FONT_SIZE)
        self.label_font.setBold(True)

        self.content_font = QFont()
        self.content_font.setPointSize(CONTENT_FONT_SIZE)

        self._init_ui()

    def _create_score_ring_with_label(self, label_text: str, initial_score: int, size: int = 150) -> tuple[QWidget, CircularProgressBarRing]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)

        progress_ring = CircularProgressBarRing()
        progress_ring.setRange(0, 100)
        progress_ring.setValue(initial_score)
        progress_ring.setFixedSize(size, size)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(self.label_font)

        layout.addWidget(progress_ring)
        layout.addWidget(label)

        return container, progress_ring

    def _create_content_analysis_section(self, initial_description: str) -> tuple[QWidget, QTextEdit]:
        section_group = QGroupBox("Response Content Analysis")
        section_group.setFont(self.title_font)
        section_layout = QVBoxLayout(section_group)
        section_layout.setContentsMargins(15, 15, 15, 15)

        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setMarkdown(initial_description)
        desc_edit.setFont(self.content_font)
        desc_edit.setObjectName("scoreDescriptionEdit")
        desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        desc_edit.setMinimumHeight(180)

        section_layout.addWidget(desc_edit)

        return section_group, desc_edit

    def _create_transcript_section(self) -> tuple[QWidget, QTextEdit]:
        section_group = QGroupBox("Interview Transcript")
        section_group.setFont(self.title_font)
        section_layout = QVBoxLayout(section_group)
        section_layout.setContentsMargins(15, 15, 15, 15)

        transcript_edit = QTextEdit()
        transcript_edit.setReadOnly(True)
        transcript_edit.setFont(self.content_font)
        transcript_edit.setObjectName("transcriptEdit")
        transcript_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        transcript_edit.setMinimumHeight(250)

        section_layout.addWidget(transcript_edit)

        return section_group, transcript_edit

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(25)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        rings_container = QWidget()
        rings_layout = QHBoxLayout(rings_container)
        rings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rings_layout.setSpacing(40)

        speech_container, self.speech_score_ring = self._create_score_ring_with_label(
            "Speech Delivery", 0, size=200
        )

        content_ring_container, self.content_score_ring = self._create_score_ring_with_label(
            "Content Score", 0, size=200
        )

        rings_layout.addWidget(speech_container)
        rings_layout.addWidget(content_ring_container)

        layout.addWidget(rings_container)

        content_section_group, self.content_score_text_edit = self._create_content_analysis_section(
            "*Content score analysis loading...*"
        )
        layout.addWidget(content_section_group)

        transcript_section_group, self.transcript_text_edit = self._create_transcript_section()
        layout.addWidget(transcript_section_group)

        layout.addStretch(1)

    def _parse_transcript_text(self, text):
        """
        Format for dark mode using colors rather than backgrounds for better readability.
        """
        formatted_html = "<div style='line-height: 1.5;'>"

        blocks = re.split(r'\n-{10,}\n|\n(?=Question \d+:)', text)

        for block in blocks:
            if not block.strip():
                continue

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
                    current_indent = 25
                    is_first_question = False
                elif fu_match:
                    topic_num, fu_text = fu_match.groups()
                    current_indent = 15
                    block_html += f"""
                    <div style='margin-top: 18px; margin-left: {current_indent}px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #81d4fa; font-weight: bold;'>Follow Up (Topic {topic_num}):</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #e0e0e0; padding-left: 15px;'>{fu_text.strip()}</div>
                    </div>
                    """
                    current_indent = 40
                elif a_match:
                    a_text = a_match.group(1)
                    next_line_index = i + 1
                    while next_line_index < len(lines) and \
                          not re.match(r'Question \d+:', lines[next_line_index]) and \
                          not re.match(r'Follow Up \(re Topic \d+\):', lines[next_line_index]) and \
                          not re.match(r'Answer:', lines[next_line_index]) and \
                          not re.match(r'-{10,}', lines[next_line_index]):
                        a_text += "\n" + lines[next_line_index].strip()
                        next_line_index += 1
                        i += 1

                    block_html += f"""
                    <div style='margin-top: 12px; margin-left: {current_indent}px;'>
                        <span style='font-size: {CONTENT_FONT_SIZE+1}pt; color: #ffb74d; font-weight: bold;'>Answer:</span>
                        <div style='margin-top: 8px; font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; padding-left: 15px; white-space: pre-wrap;'>{a_text.strip()}</div>
                    </div>
                    """
                    current_indent = 0

            if block_html:
                formatted_html += block_html

        formatted_html += "</div>"

        if not re.search(r'<span.*?>', formatted_html):
            print("Warning: Transcript parsing failed to identify Q/A structure. Displaying raw text.")
            return f"<pre style='font-size: {CONTENT_FONT_SIZE}pt; color: #f0f0f0; white-space: pre-wrap;'>{text}</pre>"

        return formatted_html

    def _load_transcript(self):
        transcript_path = os.path.join(RECORDINGS_DIR, "transcript.txt")

        try:
            if os.path.exists(transcript_path):
                with open(transcript_path, 'r', encoding='utf-8') as file:
                    transcript_text = file.read()

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
        placeholder_content_score = "*Content score analysis failed or N/A.*"

        if self.speech_score_ring:
            score_to_set = ((avg_speech_score-3) / 3.0)**(1/2) * 100.0
            self.speech_score_ring.setValue(score_to_set)
            print(f"ResultsPagePart1: Setting speech score ring to {avg_speech_score}")

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

        self._load_transcript()

    def clear_fields(self):
        if self.content_score_text_edit:
            self.content_score_text_edit.setMarkdown("*Content score analysis loading...*")
        if self.content_score_ring:
            self.content_score_ring.setValue(0)
        if self.speech_score_ring:
            self.speech_score_ring.setValue(0)
        if self.transcript_text_edit:
            self.transcript_text_edit.setHtml("<div style='color: #e0e0e0; font-size: 14pt;'>Loading transcript...</div>")