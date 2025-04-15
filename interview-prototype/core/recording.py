# core/recording.py
# Handles audio (STT via SpeechRecognition) and video (OpenCV) recording.

# --- Imports ---
import threading
import time
import os
import speech_recognition as sr
import queue
import cv2
import parselmouth
import subprocess
from pathlib import Path # Use pathlib for robust path handling

# --- Configuration ---
# <<< MODIFIED: Point to a user-specific directory inside Documents >>>
_APP_NAME_FOR_DIRS = "InterviewBotPro" # Use a consistent name

# Get the user's Documents directory in a cross-platform way
try:
    # Modern Python approach using pathlib
    _DOCUMENTS_DIR = str(Path.home() / "Documents")
    if not os.path.isdir(_DOCUMENTS_DIR): # Fallback if "Documents" doesn't exist
        _DOCUMENTS_DIR = str(Path.home())
except Exception:
    # Older fallback if Path.home() fails for some reason
    _DOCUMENTS_DIR = os.path.expanduser("~/Documents")
    if not os.path.isdir(_DOCUMENTS_DIR):
        _DOCUMENTS_DIR = os.path.expanduser("~")


# Define the recordings directory inside Documents
RECORDINGS_DIR = os.path.join(_DOCUMENTS_DIR, _APP_NAME_FOR_DIRS, "recordings")

print(f"Recording Handler: Using recordings directory: {RECORDINGS_DIR}")

# -- Praat Configuration --
PRAAT_EXECUTABLE = "praat"
# Try to find the script relative to this file's directory or the executable's directory
# Common structures:
# 1. project/core/recording.py and project/scripts/extract_features.praat
# 2. Packaged app structure where script is bundled.
try:
    # 1. Get the absolute path of this Python file
    current_file = os.path.abspath(__file__)
    print(f"[DEBUG] Current file path: {current_file}")

    # 2. Go up one level to get project root
    project_root = os.path.dirname(os.path.dirname(current_file))
    print(f"[DEBUG] Project root determined as: {project_root}")

    # 3. Build full path to the Praat script
    PRAAT_SCRIPT_PATH = os.path.join(project_root, "scripts", "extract_features.praat")
    print(f"[DEBUG] Full path to Praat script: {PRAAT_SCRIPT_PATH}")

    # 4. Check if file exists at that path
    if not os.path.isfile(PRAAT_SCRIPT_PATH):
        print(f"[DEBUG] File does NOT exist at: {PRAAT_SCRIPT_PATH}")
        PRAAT_SCRIPT_PATH = None
    else:
        print(f"[DEBUG] File FOUND at: {PRAAT_SCRIPT_PATH}")

except Exception as e:
    PRAAT_SCRIPT_PATH = None
    print(f"Recording Handler (Praat) Warning: Error determining Praat script path: {e}. Feature extraction will be skipped.")

# 5. Final flag for enabling/disabling feature extraction
PRAAT_FEATURE_EXTRACTION_ENABLED = PRAAT_SCRIPT_PATH is not None
print(f"[DEBUG] Feature extraction enabled: {PRAAT_FEATURE_EXTRACTION_ENABLED}")
# --- END MODIFICATION ---

# --- Video Recording Configuration ---
VIDEO_CAMERA_INDEX = 0 # Default webcam
VIDEO_CODEC = 'mp4v' # Common codec for .mp4 ('XVID' for AVI is another option)
VIDEO_EXTENSION = '.mp4'
# Define the TARGET Playback FPS
VIDEO_FPS = 20.0 # Target playback FPS
# Timeout for waiting for the video thread to finish writing
VIDEO_THREAD_JOIN_TIMEOUT = 7.0 # Seconds

# --- Initialize Shared Speech Recognition Components ---
stt_result_queue = queue.Queue() # Queue for STT results/status
_recognizer = sr.Recognizer()
# Use FIXED energy threshold for immediate listening
_recognizer.dynamic_energy_threshold = False
_ambient_noise_adjusted = False # Flag for one-time adjustment
_adjust_lock = threading.Lock() # Lock for one-time adjustment
print(f"Recording Handler (STT): Shared Recognizer initialized. Dynamic threshold DISABLED. Initial energy threshold: {_recognizer.energy_threshold}")
# --- End Shared Speech Recognition Components ---


# --- Recording Functions ---

def _record_video_loop(video_capture, video_writer, stop_event, filename, target_fps):
    """
    Internal function run in a thread to capture frames from the webcam
    and write them to the video file until stop_event is set.
    """
    print(f"Recording Handler (Video): Starting video recording to {filename} at target {target_fps} FPS...")
    frame_count = 0
    frames_written = 0
    start_time = time.time()

    try:
        while not stop_event.is_set():
            ret, frame = video_capture.read()
            if not ret:
                if stop_event.is_set():
                     print(f"Recording Handler (Video): Stop event received during/after camera read for {filename}.")
                     break
                else:
                     print(f"Recording Handler (Video) Warning: Could not read frame from camera. Stopping capture for {filename}.")
                     break

            if video_writer.isOpened():
                try:
                    video_writer.write(frame)
                    frames_written += 1
                    # if frame_count == 0: # Reduce log noise
                    #      print(f"Recording Handler (Video): First frame written to {filename}.")
                    frame_count += 1
                except Exception as write_err:
                     print(f"Recording Handler (Video) Error writing frame to {filename}: {write_err}")
                     break
            else:
                if stop_event.is_set():
                     print(f"Recording Handler (Video): Stop event received; VideoWriter no longer open for {filename}.")
                     break
                else:
                    print(f"Recording Handler (Video) Error: VideoWriter for {filename} is not open during write attempt!")
                    break

    except Exception as e:
        print(f"Recording Handler (Video) Error during recording loop for {filename}: {e}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        actual_recorded_fps = frames_written / duration if duration > 0 else 0
        print(f"Recording Handler (Video): Stopping video recording loop for {filename}. Wrote {frames_written} frames in {duration:.2f}s (~{actual_recorded_fps:.1f} FPS recorded). Target playback FPS: {target_fps}")

def extract_features(audio_path, praat_executable_path, praat_script_path):
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if not os.path.isfile(praat_script_path):
        raise FileNotFoundError(f"Praat script not found: {praat_script_path}")

    features = {}
    print(f"Recording Handler (Praat): Extracting features from '{os.path.basename(audio_path)}' using script '{os.path.basename(praat_script_path)}'...")
    
    try:
        # Use '--run' which exits Praat after running the script
        # Pass the audio file path as an argument to the script
        # Praat script needs to be written to accept this argument (e.g., `form`, `Read from file...`, `arguments$()`)
        command = [praat_executable_path, '--run', praat_script_path, audio_path]
        print(f"Recording Handler (Praat): Running command: {' '.join(command)}") # Log the command being run

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False, # Don't raise exception on non-zero exit code, check manually
            encoding='utf-8' # Specify encoding
        )

        # Check for errors during execution
        if result.returncode != 0:
            raise RuntimeError(f"Praat script execution failed with exit code {result.returncode}. Stderr: {result.stderr.strip()}")

        # Parse the output (assuming script prints 'key=value' pairs, one per line)
        output = result.stdout.strip()
        if not output:
             print("Recording Handler (Praat) Warning: Praat script produced no standard output.")
             return {} # Return empty if no output

        print(f"Recording Handler (Praat): Raw script output:\n---\n{output}\n---") # Log raw output for debugging

        for line in output.splitlines(): # Split by newline
            line = line.strip()
            if '=' in line:
                parts = line.split('=', 1) # Split only on the first '='
                if len(parts) == 2:
                    key = parts[0].strip()
                    value_str = parts[1].strip()
                    try:
                        features[key] = float(value_str)
                    except ValueError:
                        print(f"Recording Handler (Praat) Warning: Could not convert value '{value_str}' to float for key '{key}'. Skipping.")
                else:
                     print(f"Recording Handler (Praat) Warning: Skipping malformed output line (expected 'key=value'): '{line}'")
            # else: # Optional: log lines that don't contain '=' if needed for debug
            #      print(f"Recording Handler (Praat) Debug: Skipping output line without '=': '{line}'")


        if not features:
             print("Recording Handler (Praat) Warning: No features extracted. Check script output format (needs 'key=value' lines).")

        print(f"Recording Handler (Praat): Successfully extracted {len(features)} features.")
        return features

    except FileNotFoundError:
        # Specific error if praat executable itself is not found
        print(f"Recording Handler (Praat) Error: Praat executable '{praat_executable_path}' not found or not executable. Make sure Praat is installed and in your system's PATH or provide the full path.")
        raise # Re-raise to signal critical failure
    except Exception as e:
        print(f"Recording Handler (Praat) Error during feature extraction: {e}")
        raise RuntimeError(f"Feature extraction failed: {e}") from e




def _recognize_speech_thread(topic_idx, follow_up_idx):
    """
    Internal function run in a thread to manage STT and video recording.
    Performs initial ambient noise adjustment ONCE per app run (sets fixed threshold).
    Ensures proper finalization of the video file.
    Puts the STT result (text or error string) onto the stt_result_queue.
    """
    global _recognizer
    global _ambient_noise_adjusted
    global _adjust_lock

    video_capture = None
    video_writer = None
    video_thread = None
    stop_video_event = threading.Event()
    video_filepath = None
    video_recording_started = False
    audio_processing_done = False
    extracted_audio_features = None

    try:
        # Ensure user-specific directory exists before recording
        os.makedirs(RECORDINGS_DIR, exist_ok=True)

        # --- Adjust for ambient noise ONCE ---
        if not _ambient_noise_adjusted:
            with _adjust_lock:
                if not _ambient_noise_adjusted:
                    print("Recording Handler (STT): Performing initial ambient noise adjustment (for fixed threshold)...")
                    stt_result_queue.put("STT_Status: Adjusting Mic...")
                    initial_threshold = _recognizer.energy_threshold
                    try:
                        with sr.Microphone() as source:
                            _recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        print(f"Recording Handler (STT): Initial adjustment complete. Fixed energy threshold set to {_recognizer.energy_threshold:.2f}")
                        _ambient_noise_adjusted = True
                    except sr.WaitTimeoutError:
                         print(f"Recording Handler (STT) Warning: Timeout during initial ambient noise adjustment. Using default threshold: {initial_threshold}")
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Timeout")
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True # Prevent retries
                    except Exception as e:
                         print(f"Recording Handler (STT) Warning: Initial ambient noise adjustment failed: {e}. Using default threshold: {initial_threshold}")
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Failed") # Simplified message
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True # Prevent retries
        # else: # Reduce log noise
            # print(f"Recording Handler (STT): Using pre-calibrated fixed energy threshold: {_recognizer.energy_threshold:.2f}")
        # --- End Adjustment ---

        # --- Initialize Video Recording ---
        try:
            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath = os.path.join(RECORDINGS_DIR, video_filename) # Use absolute path
            print(f"Recording Handler (Video): Initializing camera index {VIDEO_CAMERA_INDEX}...")
            video_capture = cv2.VideoCapture(VIDEO_CAMERA_INDEX)

            if not video_capture.isOpened():
                raise IOError(f"Cannot open webcam (index {VIDEO_CAMERA_INDEX})")

            frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            camera_fps = video_capture.get(cv2.CAP_PROP_FPS)
            print(f"Recording Handler (Video): Camera opened. Res: {frame_width}x{frame_height}, Reported FPS: {camera_fps:.1f}")

            fps_for_writer = VIDEO_FPS
            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            print(f"Recording Handler (Video): Preparing writer for {video_filepath} with TARGET FPS: {fps_for_writer}")
            video_writer = cv2.VideoWriter(video_filepath, fourcc, fps_for_writer, (frame_width, frame_height))

            # Retry logic for VideoWriter opening (can sometimes fail intermittently)
            if not video_writer.isOpened():
                 print(f"Recording Handler (Video): Initial VideoWriter open failed for {video_filepath}. Retrying...")
                 time.sleep(0.5) # Brief pause before retry
                 video_writer = cv2.VideoWriter(video_filepath, fourcc, fps_for_writer, (frame_width, frame_height))
                 if not video_writer.isOpened():
                      raise IOError(f"Could not open VideoWriter for file after retry: {video_filepath}")
                 else:
                      print(f"Recording Handler (Video): VideoWriter succeeded on retry.")
                      # No need to reopen camera if it was opened successfully before

            video_thread = threading.Thread(
                target=_record_video_loop,
                args=(video_capture, video_writer, stop_video_event, video_filename, fps_for_writer),
                daemon=True
            )
            video_thread.start()
            video_recording_started = True
            print(f"Recording Handler (Video): Recording thread started for {video_filename}.")

        except Exception as video_init_err:
            print(f"Recording Handler (Video) Warning: Failed to initialize video recording: {video_init_err}")
            # Clean up resources if init failed partially
            if video_writer is not None and video_writer.isOpened(): video_writer.release()
            if video_capture is not None and video_capture.isOpened(): video_capture.release()
            video_capture = video_writer = video_thread = None
            video_recording_started = False
        # --- End Initialize Video Recording ---


        # --- Audio Recording and STT ---
        try:
            with sr.Microphone() as source:
                print("Recording Handler (STT): Listening for speech (immediate start)...")
                stt_result_queue.put("STT_Status: Listening...")
                audio = None
                try:
                    # Listen with timeout and phrase limit
                    audio = _recognizer.listen(source, timeout=5, phrase_time_limit=30)
                    print("Recording Handler (STT): Audio captured.")

                except sr.WaitTimeoutError:
                    print("Recording Handler (STT): No speech detected within timeout.")
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception as listen_e:
                     print(f"Recording Handler (STT): Error during listening phase: {listen_e}")
                     stt_result_queue.put(f"STT_Error: Listening Failed") # Simplified

                # Save audio file if captured
                if audio:
                    try:
                        audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                        audio_filepath = os.path.join(RECORDINGS_DIR, audio_filename) # Use absolute path
                        print(f"Recording Handler (STT): Saving audio to {audio_filepath}...")
                        wav_data = audio.get_wav_data()
                        with open(audio_filepath, "wb") as f:
                            f.write(wav_data)
                        print(f"Recording Handler (STT): Audio saved successfully.")

                        if PRAAT_FEATURE_EXTRACTION_ENABLED and audio_filepath:
                             try:
                                 # Make sure the file handle is closed before Praat tries to access it
                                 extracted_audio_features = extract_features(audio_filepath, PRAAT_EXECUTABLE, PRAAT_SCRIPT_PATH)
                                 if extracted_audio_features:
                                     print(f"Recording Handler (Praat): Extracted Features for {audio_filename}:")
                                     # You can format this output better if needed
                                     for key, val in extracted_audio_features.items():
                                         print(f"  - {key}: {val:.4f}")
                                     # TODO: Decide what to do with features (save to file, queue, database?)
                                     # Example: Put on queue (requires modifying queue consumer)
                                     # stt_result_queue.put({"type": "features", "topic": topic_idx, "follow_up": follow_up_idx, "data": extracted_audio_features})
                                 else:
                                     print(f"Recording Handler (Praat): No features were extracted for {audio_filename}.")

                             except FileNotFoundError:
                                 print(f"Recording Handler (Praat) Error: Cannot run feature extraction. Praat executable or script not found. Disabling for this session.")
                                 # Optionally disable future attempts if this is critical
                                 # global PRAAT_FEATURE_EXTRACTION_ENABLED
                                 # PRAAT_FEATURE_EXTRACTION_ENABLED = False
                             except RuntimeError as praat_err:
                                 # Catch errors from Praat script execution/parsing
                                 print(f"Recording Handler (Praat) Error: Failed to extract features for {audio_filename}: {praat_err}")
                             except Exception as feat_err:
                                 # Catch any other unexpected errors during feature extraction
                                 print(f"Recording Handler (Praat) Error: Unexpected error during feature extraction for {audio_filename}: {feat_err}")
                        elif not PRAAT_FEATURE_EXTRACTION_ENABLED:
                            print("Recording Handler (Praat): Feature extraction is disabled (script not found or configured).")
                    except Exception as save_err:
                        print(f"Recording Handler (STT) Warning: Failed to save audio file {audio_filename}: {save_err}")

                # Recognize audio if captured
                if audio:
                    stt_result_queue.put("STT_Status: Processing...")
                    try:
                        print("Recording Handler (STT): Recognizing using Google Web Speech API...")
                        text = _recognizer.recognize_google(audio)
                        print(f"Recording Handler (STT): Recognized: '{text}'")
                        stt_result_queue.put(f"STT_Success: {text}")


                    except sr.UnknownValueError:
                        print("Recording Handler (STT): Google Web Speech API could not understand audio")
                        stt_result_queue.put("STT_Error: Could not understand audio.")
                    except sr.RequestError as e:
                        print(f"Recording Handler (STT): Google Web Speech API request failed; {e}")
                        stt_result_queue.put(f"STT_Error: API/Network Error") # Simplified
                    except Exception as recog_e:
                        print(f"Recording Handler (STT): Unknown error during recognition: {recog_e}")
                        stt_result_queue.put(f"STT_Error: Recognition Failed") # Simplified

        except OSError as e:
             # Specific check for device unavailable error
             if "Invalid input device" in str(e) or "No Default Input Device Available" in str(e):
                 print(f"Recording Handler (STT) Error: Microphone device error: {e}")
                 stt_result_queue.put(f"STT_Error: Microphone Device Unavailable")
             else:
                 print(f"Recording Handler (STT) Error: Microphone OS Error: {e}")
                 stt_result_queue.put(f"STT_Error: Microphone Access Failed")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
                 print("Recording Handler (STT) Error: PyAudio not found or failed to initialize.")
                 stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
            else:
                 print(f"Recording Handler (STT) Error: Attribute Error during setup: {e}")
                 stt_result_queue.put(f"STT_Error: Setup Attribute Error")
        except Exception as setup_e:
            print(f"Recording Handler (STT) Error: Failed to setup microphone: {setup_e}")
            stt_result_queue.put(f"STT_Error: Mic Setup Failed")
        # --- End Audio Recording and STT ---

        audio_processing_done = True

    except OSError as e:
        print(f"Recording Handler Error: Could not create recordings directory '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False # Ensure video flag is off
        # Clean up video resources if directory creation failed after video init attempt
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()
    except Exception as main_err:
        print(f"Recording Handler Error: Unexpected error in recognition thread: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error")
        # Ensure video resources are cleaned up on unexpected error
        if video_thread is not None and video_thread.is_alive():
            stop_video_event.set()
        video_recording_started = False # Ensure video flag is off
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()

    finally:
        # --- GUARANTEED CLEANUP: Video Finalization ---
        print(f"Recording Handler: Entering FINALLY block for {topic_idx}.{follow_up_idx}. Audio done: {audio_processing_done}")
        thread_was_joined_cleanly = False

        if video_recording_started and stop_video_event and not stop_video_event.is_set():
            print("Recording Handler (Video): Signaling video thread to stop.")
            stop_video_event.set()

        if video_thread is not None:
            print(f"Recording Handler (Video): Attempting to join video thread (timeout={VIDEO_THREAD_JOIN_TIMEOUT}s)...")
            try:
                if isinstance(video_thread, threading.Thread):
                    video_thread.join(timeout=VIDEO_THREAD_JOIN_TIMEOUT)
                    if video_thread.is_alive():
                        print("Recording Handler (Video) Warning: Video thread did not finish within timeout.")
                    else:
                        print("Recording Handler (Video): Video thread joined successfully.")
                        thread_was_joined_cleanly = True
                else:
                     print("Recording Handler (Video) Error: video_thread object is not a Thread.")
            except Exception as join_err:
                 print(f"Recording Handler (Video) Error during video thread join: {join_err}")

        # Ensure VideoWriter is released AFTER attempting to join the thread
        if video_writer is not None:
            if video_writer.isOpened():
                print("Recording Handler (Video): Releasing VideoWriter...")
                try:
                    video_writer.release()
                    print("Recording Handler (Video): VideoWriter released.")
                    # Log if release happened after timeout
                    if video_recording_started and not thread_was_joined_cleanly:
                         print("Recording Handler (Video) Warning: VideoWriter released after thread join timeout/failure. File may be incomplete or corrupted.")
                except Exception as vw_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoWriter: {vw_rel_err}")
            # else: print("Recording Handler (Video): VideoWriter was not open or already released.") # Optional log

        # Ensure VideoCapture is released
        if video_capture is not None:
            if video_capture.isOpened():
                print("Recording Handler (Video): Releasing VideoCapture...")
                try:
                    video_capture.release()
                    print("Recording Handler (Video): VideoCapture released.")
                except Exception as vc_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoCapture: {vc_rel_err}")
            # else: print("Recording Handler (Video): VideoCapture was not open or already released.") # Optional log

        print(f"Recording Handler: Recognition thread FINALLY block finished for {topic_idx}.{follow_up_idx}.")
        # --- End GUARANTEED CLEANUP ---


def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition AND video recording process in a separate thread.
    Performs initial ambient noise check/adjustment if not already done.
    Results/status will be put onto stt_result_queue.
    Clears the queue before starting.
    """
    # Clear queue safely
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break
        except Exception as e: print(f"Recording Handler (STT): Error clearing queue: {e}")

    print(f"Recording Handler: Starting recognition & video thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()

# --- End Recording Functions ---