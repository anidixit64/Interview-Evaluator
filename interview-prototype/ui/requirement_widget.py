# ui/requirement_widget.py
"""
Defines the RequirementWidget, a clickable and expandable frame for displaying
job requirement assessment details.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor # Make sure QFont is imported
from PyQt6.QtCore import Qt, QSize

class RequirementWidget(QFrame):
    """
    A clickable and expandable frame representing a single requirement assessment.
    Shows summary initially, expands to show evidence on click.
    """

    def __init__(self, req_data: dict, icon_pixmap: QPixmap | None, parent_widget: QWidget, parent=None):
        """
        Args:
            req_data: Dictionary containing requirement, assessment, and evidence.
            icon_pixmap: The QPixmap for the assessment icon.
            parent_widget: The main ResultsPage instance (which has parent_window attr).
            parent: The parent QWidget.
        """
        super().__init__(parent)
        self.req_data = req_data
        # Store parent_widget if needed for other things, or just access parent_window directly
        # self.parent_widget = parent_widget
        self.is_expanded = False

        self.setObjectName("requirementSection")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        # --- Main Layout ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Summary Widget (Clickable Area) ---
        self.summary_widget = QWidget()
        self.summary_widget.setObjectName("requirementSummary")
        self.summary_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.summary_widget.mousePressEvent = self._toggle_details

        summary_layout = QHBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(8, 6, 8, 6)
        summary_layout.setSpacing(10)

        # Icon
        icon_label = QLabel()
        if icon_pixmap:
            icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(QSize(20, 20))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        assessment_level = req_data.get("assessment", "Unknown")
        icon_label.setToolTip(f"Assessment: {assessment_level}")

        # Requirement Text
        req_text = req_data.get('requirement', 'N/A')
        req_label = QLabel(f"<b>{req_text}</b>")
        # *** CORRECTED FONT ACCESS ***
        req_label.setFont(parent_widget.parent_window.font_small) # Access via parent_widget.parent_window
        req_label.setWordWrap(True)
        req_label.setToolTip(f"Assessment: {assessment_level}\nClick to expand/collapse evidence.")

        summary_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        summary_layout.addWidget(req_label, stretch=1)

        # --- Details Widget (Initially Hidden) ---
        self.details_widget = QWidget()
        self.details_widget.setObjectName("requirementDetails")
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(15, 5, 10, 10)
        details_layout.setSpacing(5)

        resume_evidence = req_data.get('resume_evidence', 'N/A').strip()
        transcript_evidence = req_data.get('transcript_evidence', 'N/A').strip()

        resume_label_title = QLabel("<i>Evidence from Resume:</i>")
        # *** CORRECTED FONT ACCESS ***
        resume_label_title.setFont(parent_widget.parent_window.font_small)
        resume_evidence_label = QLabel(resume_evidence if resume_evidence else "N/A")
        # *** CORRECTED FONT ACCESS ***
        resume_evidence_label.setFont(parent_widget.parent_window.font_small)
        resume_evidence_label.setWordWrap(True)
        resume_evidence_label.setObjectName("evidenceText")

        transcript_label_title = QLabel("<i>Evidence from Interview:</i>")
        # *** CORRECTED FONT ACCESS ***
        transcript_label_title.setFont(parent_widget.parent_window.font_small)
        transcript_evidence_label = QLabel(transcript_evidence if transcript_evidence else "N/A")
        # *** CORRECTED FONT ACCESS ***
        transcript_evidence_label.setFont(parent_widget.parent_window.font_small)
        transcript_evidence_label.setWordWrap(True)
        transcript_evidence_label.setObjectName("evidenceText")

        details_layout.addWidget(resume_label_title)
        details_layout.addWidget(resume_evidence_label)
        details_layout.addWidget(transcript_label_title)
        details_layout.addWidget(transcript_evidence_label)

        self.details_widget.setVisible(False)

        # --- Add to Main Layout ---
        self.main_layout.addWidget(self.summary_widget)
        self.main_layout.addWidget(self.details_widget)

    def _toggle_details(self, event):
        """Toggles the visibility of the details section."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_expanded = not self.is_expanded
            self.details_widget.setVisible(self.is_expanded)
            self.setFrameShadow(QFrame.Shadow.Sunken if self.is_expanded else QFrame.Shadow.Raised)
            event.accept()
        else:
            event.ignore()