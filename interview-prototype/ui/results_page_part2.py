# ui/results_page_part2.py
"""
Defines the second part of the results page, showing job fit analysis.
Includes debugging prints and uses widget replacement strategy.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QSizePolicy, QScrollArea, QGridLayout
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt, QSize

# Import shared components
from .components import _load_icon
from .requirement_widget import RequirementWidget # Needs this

class ResultsPagePart2(QWidget):
    """Displays Job Fit Analysis."""
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2.__init__ called. self id: {id(self)}")
        self.parent_window = parent_window
        # Initialize attributes to None BEFORE calling _init_ui
        self.requirements_layout = None
        self.overall_fit_label = None
        self.scroll_area = None
        self.requirements_container = None
        self.icon_met = None
        self.icon_partial = None
        self.icon_gap = None
        self.icon_unknown = None
        # Call initialization methods
        self._load_icons()
        self._init_ui() # This method MUST assign the layout correctly

    def _load_icons(self):
        """Loads icons used for assessment levels."""
        pw = self.parent_window
        icon_size = QSize(16, 16)
        icon_path = getattr(pw, 'icon_path', 'icons') # Safe access to icon_path
        self.icon_met = _load_icon(icon_path, "check.png", size=icon_size)
        self.icon_partial = _load_icon(icon_path, "question.png", size=icon_size)
        self.icon_gap = _load_icon(icon_path, "cross.png", size=icon_size)
        self.icon_unknown = _load_icon(icon_path, "minus_circle.png", size=icon_size)

    def _get_assessment_icon(self, assessment_level: str) -> QPixmap | None:
        """Returns the appropriate icon pixmap for the assessment level."""
        level_lower = assessment_level.lower()
        icon = None
        if "strong" in level_lower: icon = self.icon_met
        elif "potential" in level_lower: icon = self.icon_partial
        elif "weak" in level_lower or "gap" in level_lower: icon = self.icon_gap
        elif "insufficient" in level_lower: icon = self.icon_unknown
        else: icon = self.icon_unknown
        # Return pixmap only if icon loaded successfully
        return icon.pixmap(QSize(16, 16)) if icon and not icon.isNull() else None

    def _init_ui(self):
        """Initializes the UI elements for Part 2."""
        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2._init_ui START. self id: {id(self)}")

        # Main layout for this widget part
        page_v_layout = QVBoxLayout(self)
        page_v_layout.setContentsMargins(0, 0, 0, 0) # Container handles margins
        page_v_layout.setSpacing(15)
        page_v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pw = self.parent_window

        # --- Job Fit Analysis Section ---
        job_fit_group = QGroupBox("Job Fit Analysis - Requirements Breakdown (Click to expand)")
        job_fit_group.setFont(pw.font_large_bold)
        # Layout *inside* the group box
        job_fit_outer_layout = QVBoxLayout(job_fit_group)
        job_fit_outer_layout.setContentsMargins(10, 5, 10, 10)
        job_fit_outer_layout.setSpacing(8)

        # Scroll Area - Initialize but DON'T set a widget yet
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("requirementsScrollArea")
        self.scroll_area.setMinimumHeight(250)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create INITIAL placeholder container and layout - these will be replaced
        self.requirements_container = QWidget()
        self.requirements_layout = QGridLayout(self.requirements_container)
        self.requirements_layout.setContentsMargins(5, 5, 5, 5)
        self.requirements_layout.setSpacing(10)
        self.requirements_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Add a loading label initially
        loading_label = QLabel("<i>Loading requirements...</i>")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requirements_layout.addWidget(loading_label, 0, 0)
        self.scroll_area.setWidget(self.requirements_container) # Set initial widget

        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2._init_ui INITIAL layout assignment. self.requirements_layout is {self.requirements_layout} (type: {type(self.requirements_layout)})")


        # Overall Fit Label
        self.overall_fit_label = QLabel("<b>Overall Fit Assessment:</b> *Loading...*")
        self.overall_fit_label.setFont(pw.font_small) # Access font via parent_window
        self.overall_fit_label.setWordWrap(True)
        self.overall_fit_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.overall_fit_label.setContentsMargins(0, 10, 0, 0) # Add top margin


        # Add scroll area and label to the group box's layout
        job_fit_outer_layout.addWidget(self.scroll_area, stretch=1)
        job_fit_outer_layout.addWidget(self.overall_fit_label, stretch=0)

        # Add the group box to the page's main layout
        page_v_layout.addWidget(job_fit_group, stretch=1)

        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2._init_ui END. self.requirements_layout is {self.requirements_layout}")

    def display_results(self, assessment_data: dict | None):
        """Populates the requirements grid and overall fit label by replacing the scroll area widget."""
        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2.display_results called. self id: {id(self)}. Initial Layout is {self.requirements_layout}")

        placeholder_assessment = "*Assessment generation failed or N/A.*"
        placeholder_req_error = "Could not load requirements details."

        # --- Create a NEW container and layout for the new results ---
        new_requirements_container = QWidget()
        new_requirements_layout = QGridLayout(new_requirements_container)
        new_requirements_layout.setContentsMargins(5, 5, 5, 5)
        new_requirements_layout.setSpacing(10)
        new_requirements_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        # Populate the NEW Grid Layout
        if assessment_data and not assessment_data.get("error"):
            requirements = assessment_data.get("requirements", [])
            overall_fit = assessment_data.get("overall_fit", placeholder_assessment)

            if requirements:
                row, col = 0, 0
                max_cols = 2
                for req_data in requirements:
                    assessment_level = req_data.get("assessment", "Unknown")
                    icon_pixmap = self._get_assessment_icon(assessment_level)
                    # Pass 'self' (ResultsPagePart2 instance) as parent_widget to RequirementWidget
                    req_widget = RequirementWidget(req_data, icon_pixmap, self)
                    # Add to the NEW layout
                    new_requirements_layout.addWidget(req_widget, row, col)
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
                # Add stretch to the bottom row of the NEW layout
                new_requirements_layout.setRowStretch(row + (col > 0), 1)

            else:
                 # If no requirements listed, but assessment was successful
                 info_label = QLabel("<i>No specific requirements breakdown available.</i>")
                 info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                 # Add to the NEW layout
                 new_requirements_layout.addWidget(info_label, 0, 0, 1, max_cols) # Span message

            # Update overall fit label (clean HTML/Markdown)
            cleaned_fit = overall_fit.replace('<b>','').replace('</b>','').replace('*','')
            # Check if overall_fit_label exists before setting text
            if self.overall_fit_label:
                self.overall_fit_label.setText(f"<b>Overall Fit Assessment:</b> {cleaned_fit}")

        else:
            # Handle error in assessment data or if assessment_data is None
            error_msg = assessment_data.get("error") if assessment_data else placeholder_assessment
            error_label = QLabel(f"<i>{error_msg}</i>")
            error_label.setWordWrap(True)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Add error label to the NEW layout
            new_requirements_layout.addWidget(error_label, 0, 0, 1, 2) # Span error message
            # Check if overall_fit_label exists before setting text
            if self.overall_fit_label:
                self.overall_fit_label.setText(f"<b>Overall Fit Assessment:</b> N/A (Error)")

        # --- Replace the widget in the scroll area ---
        print(f"DEBUG: Replacing scroll area widget. Old container: {self.requirements_container}")
        old_widget = self.scroll_area.takeWidget() # Take the old widget out
        if old_widget:
            print(f"DEBUG: Deleting old container widget: {old_widget}")
            old_widget.deleteLater() # Schedule the old container (and its layout/widgets) for deletion

        print(f"DEBUG: Setting new scroll area widget: {new_requirements_container}")
        self.scroll_area.setWidget(new_requirements_container) # Put the new container in

        # Update the instance variables to point to the new container and layout
        self.requirements_container = new_requirements_container
        self.requirements_layout = new_requirements_layout
        print(f"DEBUG: Updated instance variables. New layout is {self.requirements_layout}")


    def clear_fields(self):
        """Clears the dynamic results widgets by replacing the scroll area widget."""
        # --- Debug Print ---
        print(f"DEBUG: ResultsPagePart2.clear_fields called. self id: {id(self)}. Layout is {self.requirements_layout}")

        # Create a new placeholder container and layout
        placeholder_container = QWidget()
        placeholder_layout = QGridLayout(placeholder_container)
        placeholder_layout.setContentsMargins(5, 5, 5, 5)
        loading_label = QLabel("<i>Results cleared. Waiting for next interview...</i>")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(loading_label, 0, 0)
        # No need to explicitly set layout on container if done in constructor like QGridLayout(container)
        # placeholder_container.setLayout(placeholder_layout) # Generally not needed

        # Replace the widget in the scroll area
        # Check if scroll_area exists before using it
        if self.scroll_area:
            print(f"DEBUG: Clearing fields - Replacing scroll area widget.")
            old_widget = self.scroll_area.takeWidget()
            if old_widget:
                print(f"DEBUG: Clearing fields - Deleting old container widget: {old_widget}")
                old_widget.deleteLater()

            self.scroll_area.setWidget(placeholder_container)

            # Update instance variables
            self.requirements_container = placeholder_container
            self.requirements_layout = placeholder_layout
        else:
            print("DEBUG: Clearing fields - Scroll area not found.")


        # Reset overall fit label
        if self.overall_fit_label:
            self.overall_fit_label.setText("<b>Overall Fit Assessment:</b> *Loading...*")
        print(f"DEBUG: Fields cleared. New layout is {self.requirements_layout}")