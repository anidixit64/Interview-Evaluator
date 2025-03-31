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
QSS_FILE = os.path.join("ui", "styles.qss") # Path to the QSS file

# --- Function to load Stylesheet ---
def load_stylesheet(filepath):
    """Loads QSS data from a file."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Stylesheet file not found at '{filepath}'. Using default styles.")
        return ""
    except Exception as e:
        print(f"Warning: Could not load stylesheet from '{filepath}': {e}")
        return ""

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

    # --- LOAD AND APPLY THE STYLESHEET ---
    style_sheet_content = load_stylesheet(QSS_FILE)
    if style_sheet_content:
        q_app.setStyleSheet(style_sheet_content)
    # ------------------------------------

    if not os.path.exists(".env"):
         QMessageBox.warning(None, "Configuration Warning", f"'.env' file not found...")

    # --- Microphone Check ---
    stt_backend_found = False
    audio_lib = "Not Checked"
    mic_warning_message = ""
    try: # Sounddevice check
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            print("Audio Input Check: Found input devices via sounddevice.")
            stt_backend_found = True
            audio_lib = "sounddevice"
        else: mic_warning_message = "No input devices found via sounddevice."
    except Exception as e_sd: # PyAudio fallback check
        print(f"Audio Input Check: sounddevice failed ({e_sd}). Trying PyAudio...")
        try:
            import pyaudio
            p = pyaudio.PyAudio()
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
    if not stt_backend_found: # Show warning if no input found
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