# ui/requirement_widget.py
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor, QColor, QPainter
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
class RequirementWidget(QFrame):
    
    expansion_changed = pyqtSignal()
    
    BORDER_RADIUS = 6
    ICON_BORDER_RADIUS = 4
    BASE_PADDING = 14
    SPACING = 10
    FONT_FAMILY = "Segoe UI"
    
    STATUS_COLORS = {
        "strong": ("#1FAB54", "#2A3C32"),
        "potential": ("#F59E0B", "#41382A"),
        "weak": ("#EF4444", "#492F2F"),
        "gap": ("#EF4444", "#492F2F"),
        "insufficient": ("#A855F7", "#3E304A"),
        "unknown": ("#717A87", "#363A40")
    }
    DEFAULT_COLORS = STATUS_COLORS["unknown"]
    TEXT_COLOR_PRIMARY = "#E1E3E6"
    TEXT_COLOR_SECONDARY = "#A8B0B9"
    TEXT_COLOR_HEADINGS = "#BDC3CB"
    BORDER_COLOR_DEFAULT = "#4B5158"
    BORDER_COLOR_HOVER = "#6B747D"
    BORDER_COLOR_EXPANDED = "#669DF6"
    BACKGROUND_COLOR_DEFAULT = "#282A2E"
    BACKGROUND_COLOR_HOVER = "#313338"
    
    def __init__(self, req_data: dict, icon_pixmap: QPixmap | None, parent_widget: QWidget, parent=None):
        super().__init__(parent)
        self.req_data = req_data
        self.original_icon_pixmap = icon_pixmap
        self.parent_ref = parent_widget
        self.is_expanded = False
        self._is_hovering = False
        
        self._define_fonts()
        
        assessment_level_str = req_data.get("assessment", "Unknown").lower()
        status_key = self._map_assessment_to_status_key(assessment_level_str)
        self.status_icon_bg_color, self.status_details_bg_color = self.STATUS_COLORS.get(status_key, self.DEFAULT_COLORS)
        
        self.setObjectName("requirementCardDark")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self._setup_summary_widget()
        
        self._setup_details_widget()
        
        self.main_layout.addWidget(self.summary_widget)
        self.main_layout.addWidget(self.details_widget)
        
        self._update_visual_state()
    def _define_fonts(self):
        """Define fonts, attempting to get them from parent_widget. INCREASED SIZES."""
        default_font_size = 11
        try:
            
            self.font_req = self.parent_ref.parent_window.font_default_xl if hasattr(self.parent_ref.parent_window, 'font_default_xl') else QFont(self.FONT_FAMILY, 13)
            
            if hasattr(self.parent_ref.parent_window, 'font_default_xl') and self.font_req.pointSize() < 13:
                self.font_req.setPointSize(13)
            self.font_heading = self.parent_ref.parent_window.font_default_large if hasattr(self.parent_ref.parent_window, 'font_default_large') else QFont(self.FONT_FAMILY, default_font_size + 1, QFont.Weight.Medium)
            if hasattr(self.parent_ref.parent_window, 'font_default_large') and self.font_heading.pointSize() < 12:
                 self.font_heading.setPointSize(12)
            self.font_evidence = self.parent_ref.parent_window.font_default if hasattr(self.parent_ref.parent_window, 'font_default') else QFont(self.FONT_FAMILY, default_font_size)
            if hasattr(self.parent_ref.parent_window, 'font_default') and self.font_evidence.pointSize() < 11:
                 self.font_evidence.setPointSize(11)
            self.font_indicator = QFont(self.FONT_FAMILY, 14)
        except AttributeError:
            print(f"Warning: Could not access expected fonts via parent_widget in {self.__class__.__name__}. Using defaults with increased size.")
            self.font_req = QFont(self.FONT_FAMILY, 13)
            self.font_heading = QFont(self.FONT_FAMILY, 12, QFont.Weight.Medium)
            self.font_evidence = QFont(self.FONT_FAMILY, 11)
            self.font_indicator = QFont(self.FONT_FAMILY, 14)
    def _map_assessment_to_status_key(self, assessment_str: str) -> str:
        """Maps potentially varied assessment strings to defined status keys."""
        if "strong" in assessment_str: return "strong"
        if "potential" in assessment_str: return "potential"
        if "weak" in assessment_str: return "weak"
        if "gap" in assessment_str: return "gap"
        if "insufficient" in assessment_str: return "insufficient"
        return "unknown"
    def _create_status_icon_container(self) -> QLabel:
        """Creates a label container for the icon with a colored rounded square background."""
        container = QLabel()
        container_size = 30
        container.setFixedSize(QSize(container_size, container_size))
        container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container.setToolTip(f"Assessment: {self.req_data.get('assessment', 'Unknown')}")
        
        container.setStyleSheet(f"""
            QLabel {{
                background-color: {self.status_icon_bg_color};
                border-radius: {self.ICON_BORDER_RADIUS}px;
            }}
        """)
        
        icon_label = QLabel(container)
        icon_size = 20
        if self.original_icon_pixmap:
             
             
             
             light_icon_pixmap = self._ensure_light_icon(self.original_icon_pixmap)
             scaled_pixmap = light_icon_pixmap.scaled(
                 QSize(icon_size, icon_size),
                 Qt.AspectRatioMode.KeepAspectRatio,
                 Qt.TransformationMode.SmoothTransformation
             )
             icon_label.setPixmap(scaled_pixmap)
        icon_label.setFixedSize(QSize(icon_size, icon_size))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background-color: transparent; border: none;")
        
        icon_layout = QVBoxLayout(container)
        icon_layout.setContentsMargins(0,0,0,0)
        icon_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        return container
    def _ensure_light_icon(self, pixmap: QPixmap) -> QPixmap:
        """ Checks if an icon is mostly dark and inverts it or makes it white. (Simple version) """
        
        
        
        return pixmap

    def _setup_summary_widget(self):
        """Creates and configures the summary (top, always visible) part."""
        self.summary_widget = QWidget()
        self.summary_widget.setObjectName("requirementSummary")
        summary_layout = QHBoxLayout(self.summary_widget)
        
        summary_layout.setContentsMargins(self.BASE_PADDING, self.BASE_PADDING, self.BASE_PADDING, self.BASE_PADDING)
        summary_layout.setSpacing(self.BASE_PADDING + 2)
        
        self.icon_container = self._create_status_icon_container()
        
        self.req_label = QLabel(self.req_data.get('requirement', 'N/A'))
        self.req_label.setFont(self.font_req)
        self.req_label.setWordWrap(True)
        self.req_label.setStyleSheet(f"color: {self.TEXT_COLOR_PRIMARY}; background-color: transparent;")
        
        self.expand_indicator_label = QLabel("▼")
        self.expand_indicator_label.setFont(self.font_indicator)
        self.expand_indicator_label.setFixedWidth(18)
        self.expand_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expand_indicator_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; background-color: transparent;")
        
        summary_layout.addWidget(self.icon_container, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        summary_layout.addWidget(self.req_label, stretch=1)
        summary_layout.addWidget(self.expand_indicator_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        self.summary_widget.installEventFilter(self)
    def _setup_details_widget(self):
        """Creates and configures the details (collapsible) part."""
        self.details_widget = QWidget()
        self.details_widget.setObjectName("requirementDetails")
        details_layout = QVBoxLayout(self.details_widget)
        
        icon_area_width = self.icon_container.sizeHint().width()
        left_padding = icon_area_width + self.BASE_PADDING + 2
        details_layout.setContentsMargins(left_padding,
                                           self.SPACING,
                                           self.BASE_PADDING,
                                           self.BASE_PADDING * 2)
        details_layout.setSpacing(self.SPACING * 2)
        
        resume_evidence = self.req_data.get('resume_evidence', '').strip()
        self._add_evidence_section(
            details_layout,
            "Evidence from Resume:",
            resume_evidence if resume_evidence else "N/A"
        )
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"color: {self.BORDER_COLOR_DEFAULT};")
        details_layout.addWidget(separator)
        
        transcript_evidence = self.req_data.get('transcript_evidence', '').strip()
        self._add_evidence_section(
            details_layout,
            "Evidence from Interview:",
            transcript_evidence if transcript_evidence else "N/A"
        )
        self.details_widget.setVisible(False)
    def _add_evidence_section(self, layout: QVBoxLayout, title: str, evidence: str):
        """Helper to add a title and evidence label pair to the details layout."""
        title_label = QLabel(title)
        title_label.setFont(self.font_heading)
        title_label.setStyleSheet(f"color: {self.TEXT_COLOR_HEADINGS}; margin-bottom: {self.SPACING // 2}px; background-color: transparent;")
        evidence_label = QLabel(evidence)
        evidence_label.setFont(self.font_evidence)
        evidence_label.setWordWrap(True)
        evidence_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; line-height: 140%; background-color: transparent;")
        evidence_label.setObjectName("evidenceText")
        layout.addWidget(title_label)
        layout.addWidget(evidence_label)
    
    def eventFilter(self, source, event):
        """Filters events for hover effects on the summary widget."""
        if source is self.summary_widget:
            if event.type() == event.Type.Enter:
                self._is_hovering = True
                self._update_visual_state()
            elif event.type() == event.Type.Leave:
                self._is_hovering = False
                self._update_visual_state()
        return super().eventFilter(source, event)
    def mousePressEvent(self, event):
        """Handle clicks on summary area to toggle expansion."""
        if event.button() == Qt.MouseButton.LeftButton and self.summary_widget.geometry().contains(event.pos()):
            self._toggle_details()
            event.accept()
        else:
            super().mousePressEvent(event)

    
    def _toggle_details(self):
        """Toggles the visibility of the details section and updates styles."""
        self.is_expanded = not self.is_expanded
        self.details_widget.setVisible(self.is_expanded)
        self.expand_indicator_label.setText("▲" if self.is_expanded else "▼")
        self._update_visual_state()
        self.expansion_changed.emit()
    def _update_visual_state(self):
        """Applies the correct stylesheet based on hover and expanded state (DARK THEME)."""
        border_color = self.BORDER_COLOR_DEFAULT
        background_color = self.BACKGROUND_COLOR_DEFAULT
        summary_bg = "transparent"
        if self.is_expanded:
            border_color = self.BORDER_COLOR_EXPANDED
        elif self._is_hovering:
            border_color = self.BORDER_COLOR_HOVER
        if self._is_hovering:
            summary_bg = self.BACKGROUND_COLOR_HOVER
        
        
        self.setStyleSheet(f"""
            QFrame#requirementCardDark {{
                background-color: {background_color};
                border: 1px solid {border_color};
                border-radius: {self.BORDER_RADIUS}px;
                
            }}
        """)
        
        self.summary_widget.setStyleSheet(f"""
            QWidget#requirementSummary {{
                background-color: {summary_bg};
                border-top-left-radius: {self.BORDER_RADIUS}px;
                border-top-right-radius: {self.BORDER_RADIUS}px;
                
                border-bottom-left-radius: {self.BORDER_RADIUS if not self.is_expanded else 0}px;
                border-bottom-right-radius: {self.BORDER_RADIUS if not self.is_expanded else 0}px;
            }}
            
            QWidget#requirementSummary QLabel {{
                background-color: transparent;
            }}
        """)
        
        details_bg = self.status_details_bg_color if self.is_expanded else "transparent"
        self.details_widget.setStyleSheet(f"""
            QWidget#requirementDetails {{
                background-color: {details_bg};
                
                border-bottom-left-radius: {self.BORDER_RADIUS}px;
                border-bottom-right-radius: {self.BORDER_RADIUS}px;
            }}
            
            QWidget#requirementDetails QLabel {{
                background-color: transparent;
            }}
        """)
        
        
        self.req_label.setStyleSheet(f"color: {self.TEXT_COLOR_PRIMARY}; background-color: transparent;")
        self.expand_indicator_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; background-color: transparent;")
        for label in self.details_widget.findChildren(QLabel):
            
            if hasattr(label, 'font') and label.font().bold():
                 label.setStyleSheet(f"color: {self.TEXT_COLOR_HEADINGS}; margin-bottom: {self.SPACING // 2}px; background-color: transparent;")
            elif label.objectName() == "evidenceText":
                 label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; line-height: 140%; background-color: transparent;")
            
    
    def _get_colors_for_assessment(self, assessment_level: str):
        """
        Maintained for potential compatibility. Returns the primary status color
        and the details background color based on the assessment level (Dark Theme).
        """
        level_lower = assessment_level.lower()
        status_key = self._map_assessment_to_status_key(level_lower)
        return self.STATUS_COLORS.get(status_key, self.DEFAULT_COLORS)