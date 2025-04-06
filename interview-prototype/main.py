import sys
import os
import queue
import shutil
import platform
import subprocess

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# --- Project Imports ---
from core import logic
from core import recording # Import recording module
from core import tts       # Import tts module (NEW Facade)
# RECORDINGS_DIR is now the absolute user path from core.recording
from core.recording import RECORDINGS_DIR
from ui.main_window import InterviewApp

# --- Helper Function for Resource Paths ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not running bundled, use normal path relative to main.py script
        base_path = os.path.abspath(os.path.dirname(__file__))
    except Exception as e:
        # Fallback or error logging
        print(f"Resource Path Warning: Could not determine base path: {e}")
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

# --- Constants ---
# Use the helper function for bundled resources
ICON_PATH = resource_path("icons")
QSS_FILE = resource_path(os.path.join("ui", "styles.qss"))

# --- Function to load Stylesheet ---
def load_stylesheet(filepath):
    """Loads QSS data from a file."""
    # Filepath is already resolved by resource_path when QSS_FILE is defined
    try:
        with open(filepath, "r", encoding="utf-8") as f: # Specify encoding
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Stylesheet file not found at '{filepath}'. Using default styles.")
        return ""
    except Exception as e:
        print(f"Warning: Could not load stylesheet from '{filepath}': {e}")
        return ""

# --- Function to Clear Recordings Folder ---
def clear_recordings_folder():
    """Deletes all files and subdirectories within the user's RECORDINGS_DIR."""
    folder_path = RECORDINGS_DIR # Use the absolute path directly
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

# --- Check for ffmpeg ---
def check_ffmpeg():
    """Checks if ffmpeg is accessible in the system PATH."""
    cmd = "ffmpeg" if platform.system() != "Windows" else "ffmpeg.exe"
    try:
        # Use subprocess.run with DEVNULL to suppress output
        subprocess.run([cmd, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("ffmpeg check: Found and accessible.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ffmpeg check: Not found or inaccessible in system PATH.")
        return False
    except Exception as e:
        print(f"ffmpeg check: Error during check - {e}")
        return False

# --- Main Execution ---
if __name__ == "__main__":
    # Initial checks...
    if not os.path.exists(ICON_PATH):
        print(f"Warning: Icon folder '{ICON_PATH}' not found.")

    # Configure Gemini first (critical)
    if not logic.configure_gemini():
        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error",
                             "Failed to configure Gemini API.\n"
                             "Please ensure the API key is stored correctly in your system's keyring\n"
                             f"(Service: '{logic.KEYRING_SERVICE_NAME_GEMINI}', Username: '{logic.KEYRING_USERNAME_GEMINI}').\n"
                             "Check console output for details. Application will now exit.")
        sys.exit(1)


    # Create the main application instance
    q_app = QApplication(sys.argv)

    # Optional FFMPEG Warning (Commented out, enable if strictly needed)
    # if not check_ffmpeg():
    #      QMessageBox.warning(None, "Dependency Warning",
    #                          "ffmpeg was not found in your system's PATH.\n\n"
    #                          "The OpenAI TTS feature requires ffmpeg for audio decoding.\n\n"
    #                          "Please install ffmpeg and ensure it's added to your PATH.")


    # --- PERFORM RECORDINGS CLEANUP ---
    # Ensure RECORDINGS_DIR (absolute user path) exists
    try:
        if os.path.exists(RECORDINGS_DIR):
            clear_recordings_folder()
        else:
            os.makedirs(RECORDINGS_DIR, exist_ok=True) # Create if doesn't exist
            print(f"Created recordings directory: {RECORDINGS_DIR}")
    except OSError as e:
        print(f"Warning: Could not create or clear recordings directory '{RECORDINGS_DIR}': {e}")
        QMessageBox.warning(None, "Directory Warning", f"Could not create or clear recordings directory:\n{RECORDINGS_DIR}\n\nAudio/Video recording and saving might fail.")


    # --- LOAD AND APPLY THE STYLESHEET ---
    style_sheet_content = load_stylesheet(QSS_FILE)
    if style_sheet_content:
        q_app.setStyleSheet(style_sheet_content)
    # ------------------------------------

    # --- Microphone Check ---
    stt_backend_found = False
    audio_lib = "Not Checked"
    mic_warning_message = ""
    try:
        import sounddevice as sd
        if sd.query_devices(kind='input'):
            stt_backend_found = True
            audio_lib = "sounddevice"
        else:
            mic_warning_message = "No input devices found via sounddevice."
            raise ImportError("No input devices found by sounddevice, trying PyAudio.")
    except Exception as e_sd:
        print(f"Audio Input Check: sounddevice failed ({e_sd}). Trying PyAudio...")
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            input_devices_found = False
            try:
                default_info = p.get_default_input_device_info()
                if default_info['maxInputChannels'] > 0:
                    input_devices_found = True
                    print(f"Audio Input Check: Found default PyAudio input device: {default_info.get('name')}")
            except IOError:
                 print("Audio Input Check: No default PyAudio device found or error querying, checking all devices...")
                 for i in range(p.get_device_count()):
                     try:
                         dev_info = p.get_device_info_by_index(i)
                         if dev_info.get('maxInputChannels', 0) > 0:
                             input_devices_found = True
                             print(f"Audio Input Check: Found PyAudio input device at index {i}: {dev_info.get('name')}.")
                             break
                     except Exception as dev_e:
                         print(f"Audio Input Check: Error checking PyAudio device {i}: {dev_e}")
            finally:
                p.terminate()

            if input_devices_found:
                stt_backend_found = True
                audio_lib = "PyAudio"
            else:
                if mic_warning_message:
                    mic_warning_message += "\n"
                mic_warning_message += "No input devices found via PyAudio."
        except Exception as e_pa:
            if mic_warning_message:
                mic_warning_message += "\n"
            mic_warning_message += f"PyAudio check also failed: {e_pa}"

    if not stt_backend_found:
        full_warning = f"Could not detect a functioning microphone.\n\nDetails:\n{mic_warning_message}\n\nSpeech input (STT) will likely not function."
        QMessageBox.warning(None, "Audio Input Warning", full_warning)
    else:
        print(f"Audio Input Check: Found input devices via {audio_lib}.")
    # --- End Microphone Check ---

    # Create and show the main window
    # Pass the resolved ICON_PATH
    app_window = InterviewApp(icon_path=ICON_PATH)
    app_window.show()

    # Start the Qt event loop
    exit_code = q_app.exec()
    print("\n--- Program End ---")
    sys.exit(exit_code)