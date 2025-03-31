# ui/dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit, QPushButton,
    QSizePolicy
)
from PyQt6.QtGui import QFont

class ReviewDialog(QDialog):
    """Dialog to display the final review and assessment."""
    def __init__(self, summary, assessment, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review & Assessment")
        self.setMinimumSize(800, 750)
        self.setModal(True) # Make it block the main window

        layout = QVBoxLayout(self)

        # Performance Summary Section
        summary_group = QGroupBox("Performance Summary")
        summary_layout = QVBoxLayout()
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Sans Serif", 10))
        self.summary_text.setText(summary or "N/A")
        summary_layout.addWidget(self.summary_text)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Qualification Assessment Section
        assessment_group = QGroupBox("Qualification Assessment")
        assessment_layout = QVBoxLayout()
        self.assessment_text = QTextEdit()
        self.assessment_text.setReadOnly(True)
        self.assessment_text.setFont(QFont("Sans Serif", 10))
        self.assessment_text.setText(assessment or "N/A")
        assessment_layout.addWidget(self.assessment_text)
        assessment_group.setLayout(assessment_layout)
        layout.addWidget(assessment_group)

        # Close Button
        self.close_button = QPushButton("Close & Reset")
        self.close_button.setFont(QFont("Sans Serif", 10, QFont.Weight.Bold))
        self.close_button.setFixedHeight(35)
        # Connect the button click to the dialog's accept slot (which closes it)
        # The actual reset logic will be triggered by the dialog's finished signal in the main app
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout() # Center the button
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)