# main.py
import sys
import os
import queue

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# --- Project Imports ---
from core import logic, audio_handler
from ui.main_window import InterviewApp

# --- Constants ---
ICON_PATH = "icons"

# --- QSS Stylesheet ---
STYLE_SHEET = """
/* Global Rounded Corners for specific widget types */
QGroupBox, QLineEdit, QTextEdit, QPushButton {
    border-radius: 8px;
    /* Exclude QSpinBox if it were still present */
}

/* Style for QGroupBox Frame */
QGroupBox {
    border: 1px solid #555555;
    margin-top: 10px;
}

/* Style for QGroupBox Title */
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px 0 5px;
    margin-left: 5px;
}


/* Specific Button Styling (Submit, Start, Select) - Default Style */
QPushButton {
    background-color: white;
    color: black;
    border: 1px solid #BBBBBB;
    padding: 5px 10px;
    min-height: 20px;
    /* border-radius inherited */
}

/* General Button States */
QPushButton:hover {
    background-color: #F0F0F0;
    border-color: #999999;
}

QPushButton:pressed {
    background-color: #E0E0E0;
    border-color: #777777;
}

QPushButton:disabled {
    background-color: #DCDCDC;
    color: #A0A0A0;
    border-color: #C0C0C0;
}

/* --- MODIFIED Styling for the custom +/- buttons --- */
QPushButton#adjustButton {
    background-color: white;     /* CHANGE: Make background white */
    border: 1px solid #AAAAAA;   /* CHANGE: Slightly darker border for white bg */
    color: black;                /* CHANGE: Ensure icon tint (if applicable) is dark */
    min-height: 20px;
    min-width: 20px;
    padding: 2px;
    /* border-radius inherited */
}

QPushButton#adjustButton:hover {
    background-color: #F0F0F0;   /* CHANGE: Consistent hover with other buttons */
    border-color: #888888;
}

QPushButton#adjustButton:pressed {
    background-color: #E0E0E0;   /* CHANGE: Consistent press with other buttons */
    border-color: #666666;
}

QPushButton#adjustButton:disabled {
    background-color: #EAEAEA;   /* CHANGE: Lighter disabled for white bg */
    border-color: #C0C0C0;
    /* Icon should auto-disable or appear grayed out */
}
/* --- END MODIFICATION --- */


/* Ensure TextEdit and LineEdit have visible borders with the radius */
QTextEdit, QLineEdit {
   border: 1px solid #555555;
   padding: 2px; /* Add slight padding inside */
   /* border-radius inherited */
}

/* Style QLabels used for displaying numbers */
/* If needed, add objectName to QLabel in components.py and style here */
/* Example: QLabel#numberDisplayLabel { border: none; background: transparent; } */


/* Checkboxes use default theme style */
"""

# --- Main Execution ---
if __name__ == "__main__":
    # Initial checks...
    if not os.path.exists(ICON_PATH): print(f"Warning: Icon folder '{ICON_PATH}' not found.")
    if not os.path.exists(".env"): pass # Warning shown after QApplication

    if not logic.configure_gemini():
        temp_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", "Failed to configure Gemini API...")
        sys.exit(1)

    # Create the main application instance
    q_app = QApplication(sys.argv)

    # --- APPLY THE STYLESHEET ---
    q_app.setStyleSheet(STYLE_SHEET)
    # ---------------------------

    if not os.path.exists(".env"):
         QMessageBox.warning(None, "Configuration Warning", f"'.env' file not found...")

    # --- Microphone Check ---
    # (Keep the microphone check code as before)
    stt_backend_found = False; audio_lib = "Not Checked"; mic_warning_message = ""
    try:
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            print("Audio Input Check: Found input devices via sounddevice.")
            stt_backend_found = True; audio_lib = "sounddevice"
        else: mic_warning_message = "No input devices found via sounddevice."
    except Exception as e_sd:
        print(f"Audio Input Check: sounddevice failed ({e_sd}). Trying PyAudio...")
        try:
            import pyaudio; p = pyaudio.PyAudio()
            input_devices_found = False
            try:
                if p.get_default_input_device_info()['maxInputChannels'] > 0: input_devices_found = True
            except IOError:
                 for i in range(p.get_device_count()):
                     if p.get_device_info_by_index(i).get('maxInputChannels', 0) > 0: input_devices_found = True; break
            p.terminate()
            if input_devices_found: print("Audio Input Check: Found PyAudio input devices."); stt_backend_found = True; audio_lib = "PyAudio"
            else: mic_warning_message = "No input devices found via PyAudio."
        except Exception as e_pa: mic_warning_message = f"Audio check failed: {e_sd}, {e_pa}"
    if not stt_backend_found:
        full_warning = f"{mic_warning_message}\n\nSpeech input may not function."
        QMessageBox.warning(None, "Audio Input Warning", full_warning)
    # --- End Microphone Check ---


    # Create and show the main window
    app_window = InterviewApp(icon_path=ICON_PATH)
    app_window.show()

    # Start the Qt event loop
    exit_code = q_app.exec()
    print("\n--- Program End ---")
    sys.exit(exit_code)