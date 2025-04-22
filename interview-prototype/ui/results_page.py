# FILE: ui/results_page.py -> ResultsContainerPage
# MODIFIED: Accepts avg_speech_score in display_results and passes it down.
"""
Defines the container page for displaying interview results,
managing navigation between scores and analysis sub-pages.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget,
    QSizePolicy, QFrame, QSpacerItem
)
from PyQt6.QtGui import QFont, QColor, QPixmap
from PyQt6.QtCore import Qt, QSize
from .components import _load_icon
from .results_page_part1 import ResultsPagePart1
from .results_page_part2 import ResultsPagePart2

class ResultsContainerPage(QWidget): # Renamed class
    """
    Container widget holding the results sub-pages (Scores, Analysis)
    and overall action buttons.
    """
    SCORES_PAGE_INDEX = 0
    ANALYSIS_PAGE_INDEX = 1

    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(parent=parent_window, *args, **kwargs)
        self.parent_window = parent_window
        self.results_page_part1 = None
        self.results_page_part2 = None
        self.stacked_widget = None
        self.next_button = None
        self.back_button = None
        self.save_report_button = None
        self.open_folder_button = None
        self.new_interview_button = None

        self._init_ui()
        self._update_navigation_buttons() 

    def _init_ui(self):
        """Initializes the container UI."""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(15)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window

        # --- Stacked Widget for Sub-Pages ---
        self.stacked_widget = QStackedWidget()
        self.results_page_part1 = ResultsPagePart1(pw) 
        self.results_page_part2 = ResultsPagePart2(pw) 
        self.stacked_widget.addWidget(self.results_page_part1)
        self.stacked_widget.addWidget(self.results_page_part2)
        self.stacked_widget.currentChanged.connect(self._update_navigation_buttons)

        page_layout.addWidget(self.stacked_widget, stretch=1) 

        # --- Navigation Buttons  ---
        navigation_layout = QHBoxLayout()
        navigation_layout.setSpacing(10)

        self.back_button = QPushButton("<- Back to Scores")
        self.back_button.setFont(pw.font_default)
        self.back_button.setFixedHeight(35)
        self.back_button.clicked.connect(self.go_to_previous_page)
        navigation_layout.addWidget(self.back_button)

        navigation_layout.addStretch(1) 

        self.next_button = QPushButton("Next: Job Fit ->")
        self.next_button.setFont(pw.font_default)
        self.next_button.setFixedHeight(35)
        self.next_button.clicked.connect(self.go_to_next_page)
        navigation_layout.addWidget(self.next_button)

        page_layout.addLayout(navigation_layout) 

        # --- Separator ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        page_layout.addWidget(line) 

        # --- Action Buttons ---
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

        page_layout.addLayout(action_buttons_layout)

        self.setLayout(page_layout)

    def go_to_next_page(self):
        """Switches the stacked widget to the next page."""
        current_index = self.stacked_widget.currentIndex()
        if current_index < self.stacked_widget.count() - 1:
            self.stacked_widget.setCurrentIndex(current_index + 1)

    def go_to_previous_page(self):
        """Switches the stacked widget to the previous page."""
        current_index = self.stacked_widget.currentIndex()
        if current_index > 0:
            self.stacked_widget.setCurrentIndex(current_index - 1)

    def _update_navigation_buttons(self):
        """Shows/hides navigation buttons based on the current page index."""
        current_index = self.stacked_widget.currentIndex()
        count = self.stacked_widget.count()

        self.back_button.setVisible(current_index > 0)
        self.next_button.setVisible(current_index < count - 1)

    def display_results(self, summary: str | None,
                        assessment_data: dict | None,
                        content_score_data: dict | None,
                        avg_speech_score: int): 
        """Delegates result data to the appropriate sub-pages."""
        print("ResultsContainerPage: Delegating results display...")
        if self.results_page_part1:
            self.results_page_part1.display_results(content_score_data, avg_speech_score)
        if self.results_page_part2:
            self.results_page_part2.display_results(assessment_data) 
        self.stacked_widget.setCurrentIndex(self.SCORES_PAGE_INDEX)
        self._update_navigation_buttons() 

    def clear_fields(self):
        """Delegates clearing fields to sub-pages."""
        print("ResultsContainerPage: Clearing fields...")
        if self.results_page_part1:
            self.results_page_part1.clear_fields()
        if self.results_page_part2:
            self.results_page_part2.clear_fields()
        self.stacked_widget.setCurrentIndex(self.SCORES_PAGE_INDEX)
        self._update_navigation_buttons()
