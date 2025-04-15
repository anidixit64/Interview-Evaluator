# ui/requirement_widget.py
"""
Defines the RequirementWidget, a clickable and expandable frame for displaying
job requirement assessment details, redesigned using professional UI principles
for a DARK THEME, with larger text and rounded square icons.
Maintains the original __init__ interface.
"""

import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QPixmap, QCursor, QColor, QPainter
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer # Import necessary modules

class RequirementWidget(QFrame):
    """
    A redesigned, clickable, and expandable frame for requirement assessments,
    adapted for a DARK THEME with larger text and rounded square status indicators.
    Maintains the original external interface.

    Features:
    - Clear visual hierarchy using typography and spacing.
    - Color primarily used for status icon background/accent.
    - Dark background for content area.
    - Subtle hover effects and expand/collapse indicator.
    - Consistent padding and rounded corners.
    """
    # Signal emitted when the widget's expanded state changes
    expansion_changed = pyqtSignal()

    # --- Styling Constants (Dark Theme Redesign) ---
    BORDER_RADIUS = 6
    ICON_BORDER_RADIUS = 4 # For rounded square icon container
    BASE_PADDING = 14 # Slightly increased base padding
    SPACING = 10 # Slightly increased spacing
    FONT_FAMILY = "Segoe UI" # Default font family

    # Status color mapping (Icon BG, Details BG) - Adjusted for Dark Theme visibility
    # Using slightly brighter/more saturated icon colors and subtle detail backgrounds
    STATUS_COLORS = {
        "strong": ("#1FAB54", "#2A3C32"), # Brighter Green, Dark Subtle Green BG
        "potential": ("#F59E0B", "#41382A"), # Amber, Dark Subtle Amber BG
        "weak": ("#EF4444", "#492F2F"), # Red, Dark Subtle Red BG
        "gap": ("#EF4444", "#492F2F"), # Same as weak
        "insufficient": ("#A855F7", "#3E304A"), # Purple, Dark Subtle Purple BG
        "unknown": ("#717A87", "#363A40") # Grey, Dark Subtle Grey BG
    }
    DEFAULT_COLORS = STATUS_COLORS["unknown"]
    TEXT_COLOR_PRIMARY = "#E1E3E6" # Light grey for main text
    TEXT_COLOR_SECONDARY = "#A8B0B9" # Medium light grey for less important text/evidence
    TEXT_COLOR_HEADINGS = "#BDC3CB" # Slightly brighter light grey for headings
    BORDER_COLOR_DEFAULT = "#4B5158" # Darker border
    BORDER_COLOR_HOVER = "#6B747D" # Lighter border on hover
    BORDER_COLOR_EXPANDED = "#669DF6" # Accent color for expanded border (adjust for dark)
    BACKGROUND_COLOR_DEFAULT = "#282A2E" # Dark background
    BACKGROUND_COLOR_HOVER = "#313338" # Slightly lighter dark on hover

    def __init__(self, req_data: dict, icon_pixmap: QPixmap | None, parent_widget: QWidget, parent=None):
        """
        Args:
            req_data: Dictionary containing requirement, assessment, and evidence.
            icon_pixmap: The QPixmap for the status icon (e.g., check, cross).
                         This will be placed on a colored rounded square background.
            parent_widget: The main ResultsPage instance (used for font access).
            parent: The parent QWidget.
        """
        super().__init__(parent)
        self.req_data = req_data
        self.original_icon_pixmap = icon_pixmap # Store the provided icon
        self.parent_ref = parent_widget # Store reference for font access
        self.is_expanded = False
        self._is_hovering = False

        # --- Define Fonts (using parent_widget reference, INCREASED SIZES) ---
        self._define_fonts()

        # --- Get Status Specific Styling ---
        assessment_level_str = req_data.get("assessment", "Unknown").lower()
        status_key = self._map_assessment_to_status_key(assessment_level_str)
        self.status_icon_bg_color, self.status_details_bg_color = self.STATUS_COLORS.get(status_key, self.DEFAULT_COLORS)

        # --- Widget Setup ---
        self.setObjectName("requirementCardDark") # Use a more descriptive object name
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # --- Main Layout ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0) # Frame padding handled by stylesheet
        self.main_layout.setSpacing(0)

        # --- Summary Widget ---
        self._setup_summary_widget()

        # --- Details Widget (Initially Hidden) ---
        self._setup_details_widget()

        # --- Add Widgets to Layout ---
        self.main_layout.addWidget(self.summary_widget)
        self.main_layout.addWidget(self.details_widget)

        # --- Initial Style ---
        self._update_visual_state() # Apply initial styles

    def _define_fonts(self):
        """Define fonts, attempting to get them from parent_widget. INCREASED SIZES."""
        default_font_size = 11 # Increased default base size
        try:
            # Increase font sizes here
            self.font_req = self.parent_ref.parent_window.font_default_xl if hasattr(self.parent_ref.parent_window, 'font_default_xl') else QFont(self.FONT_FAMILY, 13) # Was 11
            # Ensure parent fonts are also larger or use larger defaults
            if hasattr(self.parent_ref.parent_window, 'font_default_xl') and self.font_req.pointSize() < 13:
                self.font_req.setPointSize(13) # Force minimum size

            self.font_heading = self.parent_ref.parent_window.font_default_large if hasattr(self.parent_ref.parent_window, 'font_default_large') else QFont(self.FONT_FAMILY, default_font_size + 1, QFont.Weight.Medium) # Was 10+1=11
            if hasattr(self.parent_ref.parent_window, 'font_default_large') and self.font_heading.pointSize() < 12:
                 self.font_heading.setPointSize(12)

            self.font_evidence = self.parent_ref.parent_window.font_default if hasattr(self.parent_ref.parent_window, 'font_default') else QFont(self.FONT_FAMILY, default_font_size) # Was 10
            if hasattr(self.parent_ref.parent_window, 'font_default') and self.font_evidence.pointSize() < 11:
                 self.font_evidence.setPointSize(11)

            self.font_indicator = QFont(self.FONT_FAMILY, 14) # Increased Chevron font size

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
        container_size = 30 # Adjusted container size
        container.setFixedSize(QSize(container_size, container_size))
        container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container.setToolTip(f"Assessment: {self.req_data.get('assessment', 'Unknown')}")

        # Style the container with the status background color and ROUNDED SQUARE corners
        container.setStyleSheet(f"""
            QLabel {{
                background-color: {self.status_icon_bg_color};
                border-radius: {self.ICON_BORDER_RADIUS}px; /* Rounded square */
            }}
        """)

        # Create an inner label for the actual icon pixmap
        icon_label = QLabel(container) # Child of the container
        icon_size = 20 # Adjusted icon size within container
        if self.original_icon_pixmap:
             # Ensure the icon uses a light color suitable for dark backgrounds
             # This might require modifying the pixmap itself or assuming it's already white/light
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

        # Center the icon label within the container label using a layout
        icon_layout = QVBoxLayout(container)
        icon_layout.setContentsMargins(0,0,0,0)
        icon_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        return container # Return the container label

    def _ensure_light_icon(self, pixmap: QPixmap) -> QPixmap:
        """ Checks if an icon is mostly dark and inverts it or makes it white. (Simple version) """
        # This is a placeholder. Real implementation might involve image analysis
        # or providing separate light/dark icons. For now, we assume the
        # passed icon_pixmap is designed to be visible on dark backgrounds or is simple.
        # A more robust approach might involve creating mask and recoloring.
        # Let's just return the original for now, assuming it's okay.
        # If icons are black, they would need processing here.
        return pixmap


    def _setup_summary_widget(self):
        """Creates and configures the summary (top, always visible) part."""
        self.summary_widget = QWidget()
        self.summary_widget.setObjectName("requirementSummary")
        summary_layout = QHBoxLayout(self.summary_widget)
        # Use redesign padding
        summary_layout.setContentsMargins(self.BASE_PADDING, self.BASE_PADDING, self.BASE_PADDING, self.BASE_PADDING)
        summary_layout.setSpacing(self.BASE_PADDING + 2) # Increased spacing between elements

        # Status Icon Container
        self.icon_container = self._create_status_icon_container()

        # Requirement Text
        self.req_label = QLabel(self.req_data.get('requirement', 'N/A'))
        self.req_label.setFont(self.font_req) # Uses larger font defined earlier
        self.req_label.setWordWrap(True)
        self.req_label.setStyleSheet(f"color: {self.TEXT_COLOR_PRIMARY}; background-color: transparent;")

        # Expand/Collapse Indicator (Chevron)
        self.expand_indicator_label = QLabel("▼") # Down arrow initially
        self.expand_indicator_label.setFont(self.font_indicator) # Uses larger font
        self.expand_indicator_label.setFixedWidth(18) # Adjusted width for larger font
        self.expand_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expand_indicator_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; background-color: transparent;")

        # Add to layout
        summary_layout.addWidget(self.icon_container, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        summary_layout.addWidget(self.req_label, stretch=1)
        summary_layout.addWidget(self.expand_indicator_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Install event filter for hover detection
        self.summary_widget.installEventFilter(self)

    def _setup_details_widget(self):
        """Creates and configures the details (collapsible) part."""
        self.details_widget = QWidget()
        self.details_widget.setObjectName("requirementDetails")
        details_layout = QVBoxLayout(self.details_widget)

        # Align details content with requirement text
        icon_area_width = self.icon_container.sizeHint().width()
        left_padding = icon_area_width + self.BASE_PADDING + 2 # Match summary spacing

        details_layout.setContentsMargins(left_padding, # Left padding aligns text
                                           self.SPACING,  # Top padding
                                           self.BASE_PADDING,  # Right padding
                                           self.BASE_PADDING * 2) # Bottom padding increased
        details_layout.setSpacing(self.SPACING * 2) # Spacing between evidence sections

        # --- Resume Evidence ---
        resume_evidence = self.req_data.get('resume_evidence', '').strip()
        self._add_evidence_section(
            details_layout,
            "Evidence from Resume:",
            resume_evidence if resume_evidence else "N/A"
        )

        # --- Separator ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"color: {self.BORDER_COLOR_DEFAULT};") # Use border color for separator
        details_layout.addWidget(separator)

        # --- Interview Evidence ---
        transcript_evidence = self.req_data.get('transcript_evidence', '').strip()
        self._add_evidence_section(
            details_layout,
            "Evidence from Interview:",
            transcript_evidence if transcript_evidence else "N/A"
        )

        self.details_widget.setVisible(False) # Initially hidden

    def _add_evidence_section(self, layout: QVBoxLayout, title: str, evidence: str):
        """Helper to add a title and evidence label pair to the details layout."""
        title_label = QLabel(title)
        title_label.setFont(self.font_heading) # Uses larger font
        title_label.setStyleSheet(f"color: {self.TEXT_COLOR_HEADINGS}; margin-bottom: {self.SPACING // 2}px; background-color: transparent;")

        evidence_label = QLabel(evidence)
        evidence_label.setFont(self.font_evidence) # Uses larger font
        evidence_label.setWordWrap(True)
        evidence_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; line-height: 140%; background-color: transparent;")
        evidence_label.setObjectName("evidenceText")

        layout.addWidget(title_label)
        layout.addWidget(evidence_label)

    # --- Event Handling ---
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


    # --- State Management ---
    def _toggle_details(self):
        """Toggles the visibility of the details section and updates styles."""
        self.is_expanded = not self.is_expanded
        self.details_widget.setVisible(self.is_expanded)
        self.expand_indicator_label.setText("▲" if self.is_expanded else "▼")
        self._update_visual_state()
        self.expansion_changed.emit() # Notify parent

    def _update_visual_state(self):
        """Applies the correct stylesheet based on hover and expanded state (DARK THEME)."""
        border_color = self.BORDER_COLOR_DEFAULT
        background_color = self.BACKGROUND_COLOR_DEFAULT
        summary_bg = "transparent" # Summary shows frame background by default

        if self.is_expanded:
            border_color = self.BORDER_COLOR_EXPANDED # Accent border when expanded
        elif self._is_hovering: # Only apply hover border if not expanded
            border_color = self.BORDER_COLOR_HOVER

        if self._is_hovering:
            summary_bg = self.BACKGROUND_COLOR_HOVER # Subtle hover bg on summary

        # --- Apply Styles ---
        # Main Frame Style (Card)
        self.setStyleSheet(f"""
            QFrame#requirementCardDark {{
                background-color: {background_color};
                border: 1px solid {border_color};
                border-radius: {self.BORDER_RADIUS}px;
                /* No margin */
            }}
        """)

        # Summary Widget Style (Handles hover background and rounded corners)
        self.summary_widget.setStyleSheet(f"""
            QWidget#requirementSummary {{
                background-color: {summary_bg};
                border-top-left-radius: {self.BORDER_RADIUS}px;
                border-top-right-radius: {self.BORDER_RADIUS}px;
                /* Adjust bottom radius based on expansion */
                border-bottom-left-radius: {self.BORDER_RADIUS if not self.is_expanded else 0}px;
                border-bottom-right-radius: {self.BORDER_RADIUS if not self.is_expanded else 0}px;
            }}
            /* Ensure child labels have transparent background */
            QWidget#requirementSummary QLabel {{
                background-color: transparent;
            }}
        """)

        # Details Widget Style (Background uses status accent color when visible)
        details_bg = self.status_details_bg_color if self.is_expanded else "transparent"
        self.details_widget.setStyleSheet(f"""
            QWidget#requirementDetails {{
                background-color: {details_bg};
                /* Top radius is always 0 */
                border-bottom-left-radius: {self.BORDER_RADIUS}px;
                border-bottom-right-radius: {self.BORDER_RADIUS}px;
            }}
            /* Ensure child labels have transparent background */
            QWidget#requirementDetails QLabel {{
                background-color: transparent;
            }}
        """)

        # Explicitly update text colors again after potential stylesheet override
        # (Important for themes where default widget palettes might interfere)
        self.req_label.setStyleSheet(f"color: {self.TEXT_COLOR_PRIMARY}; background-color: transparent;")
        self.expand_indicator_label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; background-color: transparent;")
        for label in self.details_widget.findChildren(QLabel):
            # Reapply styles based on font/object name to ensure dark theme colors persist
            if hasattr(label, 'font') and label.font().bold(): # Title labels
                 label.setStyleSheet(f"color: {self.TEXT_COLOR_HEADINGS}; margin-bottom: {self.SPACING // 2}px; background-color: transparent;")
            elif label.objectName() == "evidenceText": # Evidence text
                 label.setStyleSheet(f"color: {self.TEXT_COLOR_SECONDARY}; line-height: 140%; background-color: transparent;")
            # Icon container styling is static, icon label styling is static

    # --- Compatibility Methods ---
    def _get_colors_for_assessment(self, assessment_level: str):
        """
        Maintained for potential compatibility. Returns the primary status color
        and the details background color based on the assessment level (Dark Theme).
        """
        level_lower = assessment_level.lower()
        status_key = self._map_assessment_to_status_key(level_lower)
        return self.STATUS_COLORS.get(status_key, self.DEFAULT_COLORS)

    # _lighten_color helper is not used in this design, color constants are defined directly.
    # def _lighten_color(self, hex_color, percent): ... # Can be removed if unused elsewhere