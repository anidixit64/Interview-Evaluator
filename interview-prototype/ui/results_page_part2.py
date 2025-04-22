# ui/results_page_part2.py

import os
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QSizePolicy, QScrollArea, QGridLayout
)
from PyQt6.QtGui import QFont, QPixmap, QColor
from PyQt6.QtCore import Qt, QSize

from .components import _load_icon
from .requirement_widget import RequirementWidget
from .circular_progress_ring import CircularProgressBarRing

class ResultsPagePart2(QWidget):
    

    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_window = parent_window
        
        self.requirements_layout = None
        self.overall_fit_reasoning_label = None
        self.overall_fit_ring = None
        self.scroll_area = None
        self.requirements_container = None
        self.icon_met = None
        self.icon_partial = None
        self.icon_gap = None
        self.icon_unknown = None
        
        self._load_icons()
        self._init_ui()

    def _load_icons(self):
        
        pw = self.parent_window
        icon_size = QSize(16, 16)
        icon_path = getattr(pw, 'icon_path', 'icons')
        self.icon_met = _load_icon(icon_path, "check.png", size=icon_size)
        self.icon_partial = _load_icon(icon_path, "question.png", size=icon_size)
        self.icon_gap = _load_icon(icon_path, "cross.png", size=icon_size)
        self.icon_unknown = _load_icon(icon_path, "minus_circle.png", size=icon_size)


    def _get_assessment_icon(self, assessment_level: str) -> QPixmap | None:
        
        level_lower = assessment_level.lower()
        icon = None
        if "strong" in level_lower: icon = self.icon_met
        elif "potential" in level_lower: icon = self.icon_partial
        elif "weak" in level_lower or "gap" in level_lower: icon = self.icon_gap
        elif "insufficient" in level_lower: icon = self.icon_unknown
        else: icon = self.icon_unknown
        return icon.pixmap(QSize(16, 16)) if icon and not icon.isNull() else None


    def _map_fit_to_score(self, fit_rating_text: str | None) -> int:
        
        if not fit_rating_text:
            return 0

        text_lower = fit_rating_text.lower().strip()
        
        if text_lower == "strong fit": return 95
        if text_lower == "potential fit": return 65
        if text_lower == "weak fit/gap": return 35
        if text_lower == "insufficient information": return 20
        if text_lower == "unlikely fit": return 10

        
        if "strong" in text_lower: return 90
        if "good" in text_lower: return 80
        if "potential" in text_lower: return 60
        if "moderate" in text_lower: return 50
        if "weak" in text_lower or "gap" in text_lower: return 30
        if "limited" in text_lower: return 25
        if "insufficient" in text_lower: return 15
        if "poor" in text_lower: return 10
        if "unlikely" in text_lower: return 5
        if "no fit" in text_lower: return 5

        print(f"Warning: Could not map rating text '{fit_rating_text}' to score. Defaulting to 0.")
        return 0

    def _parse_overall_fit(self, full_text: str | None) -> tuple[str | None, str | None]:
        
        
        
        rating = None
        reasoning = None
        placeholder_reasoning = "Could not parse reasoning."

        if not full_text or full_text == "N/A" or full_text.startswith("*"):
            return None, full_text

        
        
        
        
        conclusion_pattern = r"^\s*(?:-\s*)?(?:\*{1,2})?Conclusion:(?:\*{1,2})?\s*(.*?)(?=\s*(?:-\s*)?(?:\*{1,2})?Reasoning:|\Z)"
        conclusion_match = re.search(conclusion_pattern, full_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)

        if conclusion_match:
            
            rating = conclusion_match.group(1).strip().rstrip('-* ')
            print(f"DEBUG: Parsed Rating: '{rating}'")
        else:
            print(f"Warning: Could not find structured 'Conclusion:' line in overall fit text.")

        
        reasoning_pattern = r"^\s*(?:-\s*)?(?:\*{1,2})?Reasoning:(?:\*{1,2})?\s*(.*)"
        reasoning_match = re.search(reasoning_pattern, full_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)

        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
            print(f"DEBUG: Parsed Reasoning: '{reasoning[:50]}...'")
        else:
            print(f"Warning: Could not find structured 'Reasoning:' line in overall fit text.")
            
            if rating and conclusion_match:
                 potential_reasoning = full_text[conclusion_match.end():].strip()
                 
                 if potential_reasoning.startswith("-"):
                     potential_reasoning = potential_reasoning[1:].lstrip()
                 
                 potential_reasoning = re.sub(r"^\s*(?:\*{1,2})?Reasoning:(?:\*{1,2})?\s*", "", potential_reasoning, flags=re.IGNORECASE)

                 if potential_reasoning:
                     reasoning = potential_reasoning
                     print(f"DEBUG: Using fallback reasoning: '{reasoning[:50]}...'")
                 else:
                     reasoning = placeholder_reasoning
            else:
                 reasoning = full_text

        
        if not rating:
            print("DEBUG: Rating extraction failed, using full text as reasoning.")
            reasoning = full_text
            
            text_lower = full_text.lower()
            if "strong fit" in text_lower: rating = "Strong Fit"
            elif "potential fit" in text_lower: rating = "Potential Fit"
            elif "weak fit" in text_lower or "gap" in text_lower: rating = "Weak Fit/Gap"
            elif "insufficient information" in text_lower: rating = "Insufficient Information"
            elif "unlikely fit" in text_lower: rating = "Unlikely Fit"
            print(f"DEBUG: Fallback rating search found: '{rating}'")

        return rating, reasoning if reasoning else placeholder_reasoning


    def _init_ui(self):
        
        page_v_layout = QVBoxLayout(self)
        page_v_layout.setContentsMargins(0, 0, 0, 0)
        page_v_layout.setSpacing(15)
        page_v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window

        
        job_fit_group = QGroupBox("Job Fit Analysis")
        job_fit_group.setFont(pw.font_large_bold)
        job_fit_outer_layout = QVBoxLayout(job_fit_group)
        job_fit_outer_layout.setContentsMargins(15, 15, 15, 15)
        job_fit_outer_layout.setSpacing(20)

        
        overall_fit_container = QWidget()
        overall_fit_layout = QHBoxLayout(overall_fit_container)
        overall_fit_layout.setContentsMargins(0, 0, 0, 0)
        overall_fit_layout.setSpacing(25)

        
        self.overall_fit_ring = CircularProgressBarRing()
        self.overall_fit_ring.setRange(0, 100)
        self.overall_fit_ring.setValue(0)
        ring_size = 130
        self.overall_fit_ring.setFixedSize(ring_size, ring_size)
        self.overall_fit_ring.setRingThickness(14.0)
        self.overall_fit_ring.setShowText(True)
        self.overall_fit_ring._font_size_factor = 0.25

        
        self.overall_fit_reasoning_label = QLabel("<b>Overall Fit Reasoning:</b> *Loading...*")
        self.overall_fit_reasoning_label.setFont(pw.font_default_xxl)
        self.overall_fit_reasoning_label.setWordWrap(True)
        self.overall_fit_reasoning_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        overall_fit_layout.addWidget(self.overall_fit_ring)
        overall_fit_layout.addWidget(self.overall_fit_reasoning_label, stretch=1)

        
        requirements_title_label = QLabel("Requirements Breakdown (Click to expand)")
        requirements_title_label.setFont(pw.font_bold)
        requirements_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("requirementsScrollArea")
        self.scroll_area.setMinimumHeight(200)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        
        self.requirements_container = QWidget()
        self.requirements_layout = QGridLayout(self.requirements_container)
        self.requirements_layout.setContentsMargins(5, 5, 5, 5)
        self.requirements_layout.setSpacing(10)
        self.requirements_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        loading_label = QLabel("<i>Loading requirements...</i>")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requirements_layout.addWidget(loading_label, 0, 0)
        self.scroll_area.setWidget(self.requirements_container)

        
        job_fit_outer_layout.addWidget(overall_fit_container, stretch=0)
        job_fit_outer_layout.addWidget(requirements_title_label)
        job_fit_outer_layout.addWidget(self.scroll_area, stretch=1)

        page_v_layout.addWidget(job_fit_group, stretch=1)


    def display_results(self, assessment_data: dict | None):
        
        placeholder_assessment = "Assessment generation failed or N/A."
        placeholder_req_error = "Could not load requirements details."

        new_requirements_container = QWidget()
        
        
        main_layout = QHBoxLayout(new_requirements_container)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        
        left_column = QVBoxLayout()
        right_column = QVBoxLayout()
        left_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        main_layout.addLayout(left_column)
        main_layout.addLayout(right_column)

        full_overall_fit_text = placeholder_assessment

        if assessment_data and not assessment_data.get("error"):
            requirements = assessment_data.get("requirements", [])
            full_overall_fit_text = assessment_data.get("overall_fit", placeholder_assessment)
            if requirements:
                
                for i, req_data in enumerate(requirements):
                    assessment_level = req_data.get("assessment", "Unknown")
                    icon_pixmap = self._get_assessment_icon(assessment_level)
                    req_widget = RequirementWidget(req_data, icon_pixmap, self)
                    
                    
                    if i % 2 == 0:
                        left_column.addWidget(req_widget)
                    else:
                        right_column.addWidget(req_widget)
                        
                
                left_column.addStretch(1)
                right_column.addStretch(1)
            else:
                info_label = QLabel("<i>No specific requirements breakdown available.</i>")
                info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                main_layout.addWidget(info_label)
        else:
            error_msg = assessment_data.get("error") if assessment_data else placeholder_assessment
            full_overall_fit_text = f"Error: {error_msg}"
            error_label = QLabel(f"<i>Requirements Error: {error_msg}</i>")
            error_label.setWordWrap(True)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(error_label)

        
        parsed_rating, parsed_reasoning = self._parse_overall_fit(full_overall_fit_text)

        
        reasoning_display_text = parsed_reasoning if parsed_reasoning else "N/A"
        if self.overall_fit_reasoning_label:
            self.overall_fit_reasoning_label.setText(f"<b>Overall Fit Reasoning:</b> {reasoning_display_text}")
            tooltip_text = f"Original Assessment: {full_overall_fit_text}\nParsed Rating: {parsed_rating or 'N/A'}"
            self.overall_fit_reasoning_label.setToolTip(tooltip_text)

        
        fit_score = self._map_fit_to_score(parsed_rating)
        if self.overall_fit_ring:
            self.overall_fit_ring.setValue(fit_score)
            tooltip_text = f"Overall Fit Score: {fit_score}% (Derived from: '{parsed_rating or 'N/A'}')"
            self.overall_fit_ring.setToolTip(tooltip_text)

        
        if self.scroll_area:
            old_widget = self.scroll_area.takeWidget()
            if old_widget: old_widget.deleteLater()
            self.scroll_area.setWidget(new_requirements_container)
            self.requirements_container = new_requirements_container
            self.requirements_layout = main_layout
        else: 
            print("ERROR: Scroll area not initialized in display_results")

    def clear_fields(self):
        
        placeholder_container = QWidget()
        placeholder_layout = QGridLayout(placeholder_container)
        placeholder_layout.setContentsMargins(5, 5, 5, 5)
        loading_label = QLabel("<i>Results cleared. Waiting for next interview...</i>")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(loading_label, 0, 0)

        if self.scroll_area:
            old_widget = self.scroll_area.takeWidget()
            if old_widget: old_widget.deleteLater()
            self.scroll_area.setWidget(placeholder_container)
            self.requirements_container = placeholder_container
            self.requirements_layout = placeholder_layout
        else: print("DEBUG: Clearing fields - Scroll area not found.")

        
        if self.overall_fit_reasoning_label:
            self.overall_fit_reasoning_label.setText("<b>Overall Fit Reasoning:</b> *Loading...*")
            self.overall_fit_reasoning_label.setToolTip("")

        
        if self.overall_fit_ring:
            self.overall_fit_ring.setValue(0)
            self.overall_fit_ring.setToolTip("")