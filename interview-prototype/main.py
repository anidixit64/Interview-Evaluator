# main.py
import sys
import os
import queue
import shutil # <-- Import shutil for removing directories

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# --- Project Imports ---
from core import logic
from core import recording # Import recording module
from core import tts       # Import tts module
# MODIFIED: Import the constant
from core.recording import RECORDINGS_DIR
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

# --- Function to Clear Recordings Folder ---
def clear_recordings_folder():
    """Deletes all files and subdirectories within the RECORDINGS_DIR."""
    folder_path = os.path.abspath(RECORDINGS_DIR)
    print(f"Checking recordings folder for cleanup: {folder_path}")
    if not os.path.isdir(folder_path):
        print("Recordings folder does not exist, no cleanup needed.")
        return

    print(f"Clearing contents of recordings folder: {folder_path}...")
    errors_occurred = False
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path) # Remove file or link
                print(f"  Deleted file: {filename}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path) # Remove directory and all its contents
                print(f"  Deleted directory: {filename}")
        except Exception as e:
            print(f"  ERROR: Failed to delete {file_path}. Reason: {e}")
            errors_occurred = True

    if not errors_occurred:
        print("Recordings folder contents cleared successfully.")
    else:
        print("Errors occurred during recordings folder cleanup.")
        # Optionally show a non-critical warning message box
        QMessageBox.warning(None, "Cleanup Warning",
                            f"Could not delete all items in the '{RECORDINGS_DIR}' folder.\n"
                            "Check file permissions or if files are in use.")


# --- Main Execution ---
if __name__ == "__main__":
    # Initial checks...
    if not os.path.exists(ICON_PATH): print(f"Warning: Icon folder '{ICON_PATH}' not found.")

    # Configure Gemini first (critical)
    if not logic.configure_gemini():
        temp_app = QApplication.instance()
        if temp_app is None: temp_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error",
                             "Failed to configure Gemini API.\n"
                             "Please ensure GOOGLE_API_KEY is set correctly in a .env file.\n"
                             "Application will now exit.")
        sys.exit(1)

    # Create the main application instance
    q_app = QApplication(sys.argv)

    # --- PERFORM RECORDINGS CLEANUP ---
    clear_recordings_folder()
    # --- END RECORDINGS CLEANUP ---

    # --- LOAD AND APPLY THE STYLESHEET ---
    style_sheet_content = load_stylesheet(QSS_FILE)
    if style_sheet_content:
        q_app.setStyleSheet(style_sheet_content)
    # ------------------------------------

    # Check for .env file *after* QApplication is initialized for the warning box
    if not os.path.exists(".env"):
         QMessageBox.warning(None, "Configuration Warning",
                             f"'.env' file not found in the project directory.\n"
                             "Make sure it exists and contains your GOOGLE_API_KEY.")

    # --- Microphone Check ---
    # (Mic check logic remains the same)
    stt_backend_found = False
    audio_lib = "Not Checked"
    mic_warning_message = ""
    try:
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            stt_backend_found = True; audio_lib = "sounddevice"
        else:
            mic_warning_message = "No input devices found via sounddevice."
            raise ImportError("No input devices found by sounddevice, trying PyAudio.")
    except Exception as e_sd:
        print(f"Audio Input Check: sounddevice failed ({e_sd}). Trying PyAudio...")
        try:
            import pyaudio
            p = pyaudio.PyAudio(); input_devices_found = False
            try:
                if p.get_default_input_device_info()['maxInputChannels'] > 0: input_devices_found = True
            except IOError:
                 print("Audio Input Check: Default PyAudio device failed, checking all devices...")
                 for i in range(p.get_device_count()):
                     try:
                         if p.get_device_info_by_index(i).get('maxInputChannels', 0) > 0:
                             input_devices_found = True; print(f"Audio Input Check: Found PyAudio input device at index {i}."); break
                     except Exception as dev_e: print(f"Audio Input Check: Error checking PyAudio device {i}: {dev_e}")
            finally: p.terminate()
            if input_devices_found: stt_backend_found = True; audio_lib = "PyAudio"
            else:
                if mic_warning_message: mic_warning_message += "\n"
                mic_warning_message += "No input devices found via PyAudio."
        except Exception as e_pa:
            if mic_warning_message: mic_warning_message += "\n"
            mic_warning_message += f"PyAudio check also failed: {e_pa}"
    if not stt_backend_found:
        full_warning = f"Could not detect a functioning microphone.\n\nDetails:\n{mic_warning_message}\n\nSpeech input will likely not function."
        QMessageBox.warning(None, "Audio Input Warning", full_warning)
    else:
        print(f"Audio Input Check: Found input devices via {audio_lib}.")
    # --- End Microphone Check ---

    # Create and show the main window
    app_window = InterviewApp(icon_path=ICON_PATH)
    app_window.show()

    # Start the Qt event loop
    exit_code = q_app.exec()
    print("\n--- Program End ---")
    sys.exit(exit_code)