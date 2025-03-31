# main.py
import sys
import os
import queue

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# --- Project Imports ---
# MODIFIED Imports
from core import logic
from core import recording # Import recording module
from core import tts       # Import tts module
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
    # .env check warning moved after QApplication init

    # Configure Gemini first (critical)
    if not logic.configure_gemini():
        # Need a temporary QApplication to show the message box if GUI hasn't started
        temp_app = QApplication.instance() # Check if already exists
        if temp_app is None:
             temp_app = QApplication(sys.argv) # Create if doesn't exist

        QMessageBox.critical(None, "Fatal Error",
                             "Failed to configure Gemini API.\n"
                             "Please ensure GOOGLE_API_KEY is set correctly in a .env file.\n"
                             "Application will now exit.")
        sys.exit(1) # Exit if Gemini setup fails

    # Create the main application instance
    q_app = QApplication(sys.argv)

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
    # This check verifies basic audio input capability needed by recording.py
    stt_backend_found = False
    audio_lib = "Not Checked"
    mic_warning_message = ""
    try:
        # Try sounddevice first (often works well across platforms)
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            stt_backend_found = True
            audio_lib = "sounddevice"
        else:
            mic_warning_message = "No input devices found via sounddevice."
            # Fallback to PyAudio check if sounddevice found no devices
            raise ImportError("No input devices found by sounddevice, trying PyAudio.")
    except Exception as e_sd:
        # If sounddevice failed (ImportError or other exception), try PyAudio
        print(f"Audio Input Check: sounddevice failed ({e_sd}). Trying PyAudio...")
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            input_devices_found = False
            try:
                # Check default device first
                if p.get_default_input_device_info()['maxInputChannels'] > 0:
                    input_devices_found = True
            except IOError:
                 # If default fails, iterate through all devices
                 print("Audio Input Check: Default PyAudio device failed, checking all devices...")
                 for i in range(p.get_device_count()):
                     try:
                         if p.get_device_info_by_index(i).get('maxInputChannels', 0) > 0:
                             input_devices_found = True
                             print(f"Audio Input Check: Found PyAudio input device at index {i}.")
                             break # Stop searching once one is found
                     except Exception as dev_e:
                         print(f"Audio Input Check: Error checking PyAudio device {i}: {dev_e}")
            finally:
                 p.terminate() # Ensure PyAudio is terminated

            if input_devices_found:
                stt_backend_found = True
                audio_lib = "PyAudio"
            else:
                # Combine messages if both failed
                if mic_warning_message: mic_warning_message += "\n"
                mic_warning_message += "No input devices found via PyAudio."
        except Exception as e_pa:
            # Combine messages if PyAudio check also failed
            if mic_warning_message: mic_warning_message += "\n"
            mic_warning_message += f"PyAudio check also failed: {e_pa}"

    # Show warning only if NO input device was found by either library
    if not stt_backend_found:
        full_warning = f"Could not detect a functioning microphone.\n\nDetails:\n{mic_warning_message}\n\nSpeech input will likely not function."
        QMessageBox.warning(None, "Audio Input Warning", full_warning)
    else:
        print(f"Audio Input Check: Found input devices via {audio_lib}.") # Log success

    # --- End Microphone Check ---

    # Create and show the main window
    # Pass required dependencies (icon path)
    app_window = InterviewApp(icon_path=ICON_PATH)
    app_window.show()

    # Start the Qt event loop
    exit_code = q_app.exec()
    print("\n--- Program End ---")
    sys.exit(exit_code)