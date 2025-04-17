# core/recording.py
# MODIFIED: Ensured global declarations are the absolute first statements in _recognize_speech_thread.
#           Applied PEP 8 formatting, added whitespace for readability.
"""
Handles audio (STT via SpeechRecognition) and video (OpenCV) recording.
Includes separate functions for continuous webcam streaming and triggered recording.
Integrates prosody scoring for saved audio segments.
"""

import os
import queue
import threading
import time
from pathlib import Path
import cv2

import numpy as np

# --- Core Dependency Import (Pandas needed for function signature) ---
try:
    import pandas as pd
except ImportError:
    print("CRITICAL ERROR: pandas library not found. Install it (`pip install pandas`). Prosody scoring and potentially other features will fail.")
    class DummyDataFrame:
        pass
    # Create a mock object to allow file parsing, but prosody will be disabled.
    pd = type('PandasModule', (object,), {'DataFrame': DummyDataFrame})()

# --- Optional Prosody Imports ---
PROSODY_ENABLED = False
joblib = None
parselmouth = None
praat_call = None
try:
    import joblib
    import parselmouth
    from parselmouth.praat import call as praat_call
    PROSODY_ENABLED = True
    print("Prosody libraries found.")
except ImportError as e:
    print(f"Warning: Prosody libraries not found ({e}). Speech score will be unavailable.")

# --- Configuration ---
_APP_NAME_FOR_DIRS = "InterviewBotPro"
try:
    _DOCUMENTS_DIR = str(Path.home() / "Documents")
    if not os.path.isdir(_DOCUMENTS_DIR):
        _DOCUMENTS_DIR = str(Path.home())
except Exception:
    _DOCUMENTS_DIR = os.path.expanduser("~/Documents")
    if not os.path.isdir(_DOCUMENTS_DIR):
        _DOCUMENTS_DIR = os.path.expanduser("~")

RECORDINGS_DIR = Path(_DOCUMENTS_DIR) / _APP_NAME_FOR_DIRS / "recordings"
_CORE_DIR = Path(__file__).parent
_MODEL_OUTPUT_DIR = _CORE_DIR / "model_output"
_MODEL_PIPELINE_PATH = _MODEL_OUTPUT_DIR / "prosody_model_pipeline.joblib"
_MODEL_FEATURES_PATH = _MODEL_OUTPUT_DIR / "prosody_model_features.joblib"
print(f"Recording Handler: Using recordings directory: {RECORDINGS_DIR}")

VIDEO_CAMERA_INDEX = 0
VIDEO_CODEC = 'mp4v'
VIDEO_EXTENSION = '.mp4'
VIDEO_FPS = 20.0
VIDEO_THREAD_JOIN_TIMEOUT = 7.0
STREAMING_FPS_TARGET = 25.0

# --- Initialize Shared Speech Recognition Components ---
stt_result_queue = queue.Queue()
_recognizer = None # Initialize inside thread
_ambient_noise_adjusted = False
_adjust_lock = threading.Lock()

# --- Load Prosody Model ---
_prosody_pipeline = None
_prosody_features_list = None
if PROSODY_ENABLED:
    print("Rcd Hdlr (Prosody): Loading model...")
    if not _MODEL_PIPELINE_PATH.exists():
        print(f"Rcd Hdlr (Prosody) Error: Model pipeline not found at {_MODEL_PIPELINE_PATH}")
        PROSODY_ENABLED = False
    elif not _MODEL_FEATURES_PATH.exists():
        print(f"Rcd Hdlr (Prosody) Error: Model features list not found at {_MODEL_FEATURES_PATH}")
        PROSODY_ENABLED = False
    else:
        try:
            _prosody_pipeline = joblib.load(_MODEL_PIPELINE_PATH)
            _prosody_features_list = joblib.load(_MODEL_FEATURES_PATH)
            print("Rcd Hdlr (Prosody): Model and features loaded successfully.")
            if not isinstance(_prosody_features_list, list):
                 print("Rcd Hdlr (Prosody) Error: Loaded features file is not a list.")
                 PROSODY_ENABLED = False
                 _prosody_pipeline = None
                 _prosody_features_list = None
            else:
                 print(f"Rcd Hdlr (Prosody): Model expects {len(_prosody_features_list)} features.")
        except Exception as e:
            print(f"Rcd Hdlr (Prosody) Error: Failed to load model/features: {e}")
            PROSODY_ENABLED = False
            _prosody_pipeline = None
            _prosody_features_list = None
# --- End Model Loading ---


# ==================================
# === Prosody Feature Extraction ===
# ==================================
def extract_prosodic_features(wav_path: str, feature_list: list) -> pd.DataFrame | None:
    """Extracts prosodic features using Parselmouth based on the provided list."""
    if not PROSODY_ENABLED or not feature_list or not parselmouth:
        return None

    if not praat_call:
        print("Rcd Hdlr (Prosody) Error: praat_call function not available.")
        return None

    try:
        sound = parselmouth.Sound(wav_path)
        if sound.duration < 0.1:
            print(f"Rcd Hdlr (Prosody) Warn: Audio file too short ({sound.duration:.2f}s) for analysis: {wav_path}")
            return None

        # --- Calculate Base Praat Objects ---
        pitch = sound.to_pitch()
        intensity = sound.to_intensity()
        formants = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5)
        harmonicity = sound.to_harmonicity()

        # --- Extract Pitch Features ---
        pitch_values = []
        if pitch:
             raw_pitch_values = pitch.selected_array['frequency']
             pitch_values = raw_pitch_values[raw_pitch_values != 0]

        # --- Extract Intensity Features ---
        intensity_values = []
        if intensity:
            intensity_values = intensity.values.flatten()

        # --- Extract HNR Features ---
        hnr_values = []
        if harmonicity:
            hnr_values = harmonicity.values[harmonicity.values != -200]

        # --- Extract Jitter/Shimmer Features ---
        jitter_local = 0.0
        jitter_rap = 0.0
        shimmer_local = 0.0
        point_process = None
        if pitch:
            point_process = praat_call(pitch, "To PointProcess")

        if point_process:
            try:
                num_points = point_process.get_number_of_points()
                if num_points > 1:
                    jitter_local = praat_call(point_process, "Get jitter (local)", 0.0, 0.0, 0.0001, 0.02, 1.3)
                    jitter_rap = praat_call(point_process, "Get jitter (rap)", 0.0, 0.0, 0.0001, 0.02, 1.3)
                    shimmer_local = praat_call([sound, point_process], "Get shimmer (local)", 0.0, 0.0, 0.0001, 0.02, 1.3, 1.6)
                else:
                    print(f"Rcd Hdlr (Prosody) Warn: Not enough points ({num_points}) for jitter/shimmer calc. Using 0.")
            except AttributeError:
                print(f"Rcd Hdlr (Prosody) Warn: Invalid object type for point process, cannot get points. Using 0 for jitter/shimmer.")
            except parselmouth.PraatError as e:
                 print(f"Rcd Hdlr (Prosody) Warn: Praat error during jitter/shimmer calc: {e}. Using 0.")
                 jitter_local = 0.0
                 jitter_rap = 0.0
                 shimmer_local = 0.0
        else:
            print(f"Rcd Hdlr (Prosody) Warn: No valid point process created for jitter/shimmer calc. Using 0.")

        # --- Extract Pause Features ---
        num_pauses = 0
        max_dur_pause = 0.0
        avg_dur_pause = 0.0
        try:
             pauses_textgrid = praat_call(sound, "To TextGrid (silences)", -25, 0.1, 0.05, "silent", "sounding")
             num_pauses = praat_call(pauses_textgrid, "Count intervals where", 1, "is equal to", "silent")

             if num_pauses > 0:
                 max_dur_pause = sound.duration / (num_pauses * 1.5 + 1) # Rough guess
                 avg_dur_pause = sound.duration / (num_pauses * 2 + 1) # Rough guess
        except parselmouth.PraatError as e:
            print(f"Rcd Hdlr (Prosody) Warn: Praat command 'To TextGrid (silences)' failed: {e}. Setting pause features to 0.")
            num_pauses = 0
            max_dur_pause = 0.0
            avg_dur_pause = 0.0
        except Exception as pause_e:
             print(f"Rcd Hdlr (Prosody) Warn: Error calculating pause features: {pause_e}. Setting pause features to 0.")
             num_pauses = 0
             max_dur_pause = 0.0
             avg_dur_pause = 0.0

        # --- Map Features to Dictionary ---
        feature_map = {
            'meanF0Hz': np.mean(pitch_values) if len(pitch_values) > 0 else 0.0,
            'stdevF0Hz': np.std(pitch_values) if len(pitch_values) > 1 else 0.0,
            'minF0Hz': np.min(pitch_values) if len(pitch_values) > 0 else 0.0,
            'maxF0Hz': np.max(pitch_values) if len(pitch_values) > 0 else 0.0,
            'jitterLocal': jitter_local,
            'jitterRap': jitter_rap,
            'shimmerLocal': shimmer_local,
            'intensityMean': np.mean(intensity_values) if len(intensity_values) > 0 else 0.0,
            'intensitySD': np.std(intensity_values) if len(intensity_values) > 1 else 0.0,
            'intensityMin': np.min(intensity_values) if len(intensity_values) > 0 else 0.0,
            'intensityMax': np.max(intensity_values) if len(intensity_values) > 0 else 0.0,
            'duration': sound.duration,
            'percentUnvoiced': (1 - (pitch.count_voiced_frames() / len(pitch.xs()))) * 100 if pitch and len(pitch.xs()) > 0 else 100.0,
            'maxDurPause': max_dur_pause,
            'avgDurPause': avg_dur_pause,
            'numPauses': float(num_pauses),
            'meanF1Hz': praat_call(formants, "Get mean", 1, 0, 0, 'Hertz') if formants else 0.0,
            'meanF2Hz': praat_call(formants, "Get mean", 2, 0, 0, 'Hertz') if formants else 0.0,
            'meanF3Hz': praat_call(formants, "Get mean", 3, 0, 0, 'Hertz') if formants else 0.0,
        }

        # --- Build DataFrame in Correct Order ---
        features = {}
        for feature_name in feature_list:
            features[feature_name] = feature_map.get(feature_name, 0.0)
            if feature_name not in feature_map:
                 print(f"Rcd Hdlr (Prosody) Warn: Feature '{feature_name}' requested but not implemented. Setting to 0.0.")

        features_df = pd.DataFrame([features], columns=feature_list)
        features_df = features_df.apply(pd.to_numeric, errors='coerce')

        if features_df.isnull().values.any():
            nan_cols = features_df.columns[features_df.isnull().any()].tolist()
            print(f"Rcd Hdlr (Prosody) Warn: NaN values found in features: {nan_cols}.")

        return features_df

    # --- Outer Error Handling for Feature Extraction ---
    except parselmouth.PraatError as e:
        print(f"Rcd Hdlr (Prosody) Error: Top-level Praat processing failed for {wav_path}: {e}")
        return None
    except FileNotFoundError:
        print(f"Rcd Hdlr (Prosody) Error: WAV file not found: {wav_path}")
        return None
    except Exception as e:
        print(f"Rcd Hdlr (Prosody) Error: Unexpected error extracting features for {wav_path}: {e}")
        return None


# ==============================
# === Prosody Score Prediction ===
# ==============================
def predict_prosody_score(wav_path: str) -> float | None:
    """Extracts features and predicts score using the loaded pipeline."""
    if not PROSODY_ENABLED or _prosody_pipeline is None or _prosody_features_list is None:
        print("Rcd Hdlr (Prosody): Prediction skipped - prosody disabled or model not loaded.")
        return None

    print(f"Rcd Hdlr (Prosody): Predicting score for {wav_path}...")

    features_df = extract_prosodic_features(wav_path, _prosody_features_list)
    if features_df is None:
        print(f"Rcd Hdlr (Prosody): Feature extraction failed for {wav_path}. Cannot predict score.")
        return None

    if features_df.isnull().values.any():
         print(f"Rcd Hdlr (Prosody) Warn: NaN values present in features before prediction.")

    try:
        score_array = _prosody_pipeline.predict(features_df)
        predicted_score = score_array[0]

        clamped_score = np.clip(predicted_score, 0, 100)
        final_score = float(clamped_score)

        print(f"Rcd Hdlr (Prosody): Predicted score: {predicted_score:.2f}, Final score: {final_score:.2f}")
        return final_score
    except Exception as e:
        print(f"Rcd Hdlr (Prosody) Error: Failed to predict score for {wav_path}: {e}")
        return None


# ===============================================
# === Webcam Streaming Function (for UI Feed) ===
# ===============================================
def stream_webcam(webcam_queue: queue.Queue, stop_event: threading.Event):
    """
    Continuously captures frames from the webcam and puts them onto a queue.
    Runs in its own thread, managed by the main UI.
    """
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV (cv2) library not found. Webcam streaming disabled.")
        return

    print("Webcam Streamer: Thread starting...")
    capture = None
    frame_delay = 1.0 / STREAMING_FPS_TARGET

    try:
        print(f"Webcam Streamer: Initializing camera index {VIDEO_CAMERA_INDEX}...")
        capture = cv2.VideoCapture(VIDEO_CAMERA_INDEX)
        if not capture.isOpened():
            raise IOError(f"Cannot open webcam (index {VIDEO_CAMERA_INDEX})")
        print("Webcam Streamer: Camera opened successfully.")

        while not stop_event.is_set():
            start_time = time.time()
            ret, frame = capture.read()

            if not ret:
                print("Webcam Streamer: Warning - Could not read frame.")
                time.sleep(0.1)
                if stop_event.is_set():
                    break
                continue

            if isinstance(frame, np.ndarray):
                try:
                    webcam_queue.put(frame.copy(), block=False)
                except queue.Full:
                    pass
                except Exception as q_err:
                    print(f"Webcam Streamer: Error putting frame to queue: {q_err}")

            elapsed = time.time() - start_time
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        print(f"Webcam Streamer: Error in streaming loop: {e}")
    finally:
        print("Webcam Streamer: Releasing camera...")
        if capture and capture.isOpened():
            capture.release()
        print("Webcam Streamer: Thread finished.")

        if webcam_queue is not None:
            try:
                webcam_queue.put(None, block=False, timeout=0.1)
            except Exception:
                 print("Webcam Streamer: Warn - Could not put None sentinel in queue on exit.")
                 pass


# =================================================================
# === Video Recording Function (for Saving Answer Segments Only) ===
# =================================================================
def _record_video_loop_for_saving(video_capture: cv2.VideoCapture,
                                  video_writer: cv2.VideoWriter,
                                  stop_event: threading.Event,
                                  filename: str,
                                  target_fps: float):
    """
    Internal function run in a thread *specifically for saving* video frames
    to a file during an answer recording segment.
    """
    # Assuming cv2 was imported successfully either globally or in _recognize_speech_thread
    try:
        import cv2
    except ImportError:
        print("VidSaveLoop Error: cv2 not available.")
        return # Cannot proceed if cv2 isn't loaded

    print(f"VidSaveLoop: Starting video save to {filename} @ {target_fps} FPS...")
    frames_written = 0
    start_time = time.time()

    try:
        while not stop_event.is_set():
            ret, frame = video_capture.read()

            if not ret:
                if stop_event.is_set():
                    print(f"VidSaveLoop: Stop event received during/after failed read for {filename}.")
                else:
                    print(f"VidSaveLoop Warn: Could not read frame for {filename}. Retrying shortly...")
                    time.sleep(0.1)
                    if not stop_event.is_set():
                        continue
                    else:
                        print(f"VidSaveLoop: Stop event received during retry wait for {filename}.")
                        break
                break

            if video_writer.isOpened():
                try:
                    video_writer.write(frame)
                    frames_written += 1
                except Exception as write_err:
                    print(f"VidSaveLoop Error writing frame to {filename}: {write_err}")
                    break
            else:
                if stop_event.is_set():
                    print(f"VidSaveLoop: Stop event Writer closed for {filename}.")
                else:
                    print(f"VidSaveLoop Error: Writer for {filename} closed unexpectedly.")
                break

    except Exception as e:
        print(f"VidSaveLoop Error during recording loop for {filename}: {e}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        actual_fps = frames_written / duration if duration > 0 else 0
        print(f"VidSaveLoop: Stopping loop for {filename}. Wrote {frames_written} frames in {duration:.2f}s (~{actual_fps:.1f} FPS recorded). Target: {target_fps} FPS")


# =======================================
# === Combined STT and Saving Thread ===
# =======================================
def _recognize_speech_thread(topic_idx: int, follow_up_idx: int):
    """
    Internal function run in a thread to manage STT and SAVE video recording.
    Opens its own camera instance just for the duration of saving.
    Also performs prosody analysis on the saved audio.
    """
    # --- CORRECT: Global declarations are the VERY FIRST statements ---
    global _recognizer
    global _ambient_noise_adjusted
    global _adjust_lock
    global stt_result_queue
    # --- End global declarations ---

    # --- Imports specific to this thread (AFTER globals) ---
    try:
        import speech_recognition as sr
    except ImportError:
        print("Rcd Hdlr (STT) Error: speech_recognition library not found.")
        # Use the now-declared global queue
        stt_result_queue.put("STT_Error: Library Missing")
        return
    try:
        import cv2
    except ImportError:
        print("Rcd Hdlr (SaveVid) Error: OpenCV (cv2) library not found.")
        # Allow proceeding, video init check will handle it
        pass

    # --- Initialize Recognizer if first time ---
    if _recognizer is None:
        try:
            _recognizer = sr.Recognizer()
            _recognizer.dynamic_energy_threshold = False
            # NOTE: energy_threshold isn't set here, relies on adjust_for_ambient_noise
            print(f"Rcd Hdlr (STT): Recognizer initialized in thread. DynThrsh: OFF. Initial Energy: {_recognizer.energy_threshold}")
        except Exception as init_err:
            print(f"Rcd Hdlr (STT) Error: Failed to initialize Recognizer in thread: {init_err}")
            stt_result_queue.put("STT_Error: Recognizer Init Failed")
            return

    # --- Thread Local Variables ---
    video_capture_save = None
    video_writer = None
    video_save_thread = None
    stop_video_save_event = threading.Event()
    video_filepath_obj = None
    audio_filepath_obj = None
    video_recording_started = False
    audio_processing_done = False

    try:
        # --- Ensure Recordings Directory ---
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        # --- Adjust Ambient Noise (Once) ---
        if not _ambient_noise_adjusted:
             with _adjust_lock: # Use global lock
                 if not _ambient_noise_adjusted: # Double-check
                     print("Rcd Hdlr (STT): Initial ambient noise adjustment...")
                     stt_result_queue.put("STT_Status: Adjusting Mic...")
                     initial_threshold = _recognizer.energy_threshold
                     try:
                         with sr.Microphone() as source:
                             _recognizer.adjust_for_ambient_noise(source, duration=1.0)
                         print(f"Rcd Hdlr (STT): Adjustment complete. Fixed threshold: {_recognizer.energy_threshold:.2f}")
                         _ambient_noise_adjusted = True # Modify global flag
                     except sr.WaitTimeoutError:
                          print(f"Rcd Hdlr (STT) Warn: Mic adjust timeout. Using default: {initial_threshold}")
                          stt_result_queue.put(f"STT_Warning: Mic Adjust Timeout")
                          _recognizer.energy_threshold = initial_threshold
                          _ambient_noise_adjusted = True # Modify global flag
                     except Exception as e:
                          print(f"Rcd Hdlr (STT) Warn: Mic adjust failed: {e}. Using default: {initial_threshold}")
                          stt_result_queue.put(f"STT_Warning: Mic Adjust Failed")
                          _recognizer.energy_threshold = initial_threshold
                          _ambient_noise_adjusted = True # Modify global flag

        # --- Initialize Video Saving ---
        try:
            # Check if cv2 import succeeded before trying to use it
            if 'cv2' not in locals() and 'cv2' not in globals():
                 raise ImportError("cv2 not loaded, cannot save video.")

            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath_obj = RECORDINGS_DIR / video_filename
            video_filepath_str = str(video_filepath_obj)

            print(f"Rcd Hdlr (SaveVid): Initializing camera {VIDEO_CAMERA_INDEX} for saving...")
            video_capture_save = cv2.VideoCapture(VIDEO_CAMERA_INDEX)
            if not video_capture_save.isOpened():
                raise IOError("Cannot open webcam for saving")

            frame_width = int(video_capture_save.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(video_capture_save.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"Rcd Hdlr (SaveVid): Camera opened. Res: {frame_width}x{frame_height}")

            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            print(f"Rcd Hdlr (SaveVid): Preparing writer for {video_filepath_str} @ {VIDEO_FPS} FPS")
            video_writer = cv2.VideoWriter(video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height))

            if not video_writer.isOpened():
                print(f"Rcd Hdlr (SaveVid): Initial VideoWriter open failed. Retrying...")
                time.sleep(0.5)
                video_writer = cv2.VideoWriter(video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height))
                if not video_writer.isOpened():
                    raise IOError(f"Could not open VideoWriter after retry: {video_filepath_str}")
                else:
                    print(f"Rcd Hdlr (SaveVid): VideoWriter succeeded on retry.")

            video_save_thread = threading.Thread(
                target=_record_video_loop_for_saving,
                args=(video_capture_save, video_writer, stop_video_save_event, video_filename, VIDEO_FPS),
                daemon=True
            )
            video_save_thread.start()
            video_recording_started = True
            print(f"Rcd Hdlr (SaveVid): Saving thread started for {video_filename}.")

        except Exception as video_init_err:
            print(f"Rcd Hdlr (SaveVid) Warn: Failed to init video saving: {video_init_err}")
            if video_writer is not None and video_writer.isOpened(): video_writer.release()
            if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
            video_capture_save = None
            video_writer = None
            video_save_thread = None
            video_recording_started = False

        # --- Audio Recording / STT / Prosody ---
        try:
             with sr.Microphone() as source:
                 print("Rcd Hdlr (STT): Listening for speech...")
                 stt_result_queue.put("STT_Status: Listening...")
                 audio = None
                 try:
                     audio = _recognizer.listen(source, timeout=7, phrase_time_limit=45)
                     print("Rcd Hdlr (STT): Audio captured.")
                 except sr.WaitTimeoutError:
                     print("Rcd Hdlr (STT): No speech detected within timeout.")
                     stt_result_queue.put("STT_Error: No speech detected.")
                 except Exception as listen_e:
                     print(f"Rcd Hdlr (STT): Error during listening: {listen_e}")
                     stt_result_queue.put(f"STT_Error: Listening Failed")

                 if audio:
                     # Save Audio
                     try:
                         audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                         audio_filepath_obj = RECORDINGS_DIR / audio_filename
                         print(f"Rcd Hdlr (STT): Saving audio to {audio_filepath_obj}...")
                         wav_data = audio.get_wav_data()
                         with open(audio_filepath_obj, "wb") as f:
                             f.write(wav_data)
                         print(f"Rcd Hdlr (STT): Audio saved.")
                     except Exception as save_err:
                         print(f"Rcd Hdlr (STT) Warn: Failed to save audio: {save_err}")
                         audio_filepath_obj = None

                     # Recognize Speech & Predict Score
                     stt_result_queue.put("STT_Status: Processing...")
                     text = None
                     prosody_score = None
                     try:
                         print("Rcd Hdlr (STT): Recognizing using Google Web Speech API...")
                         text = _recognizer.recognize_google(audio)
                         print(f"Rcd Hdlr (STT): Recognized: '{text}'")

                         if audio_filepath_obj and audio_filepath_obj.exists():
                             prosody_score = predict_prosody_score(str(audio_filepath_obj))
                         else:
                             print("Rcd Hdlr (Prosody): Skipping score prediction - audio file not available.")

                         score_str = f"{prosody_score:.1f}" if prosody_score is not None else "N/A"
                         stt_result_queue.put(f"STT_Success: {text} | Score: {score_str}")

                     except sr.UnknownValueError:
                         print("Rcd Hdlr (STT): Google could not understand audio")
                         stt_result_queue.put("STT_Error: Could not understand audio.")
                     except sr.RequestError as e:
                         print(f"Rcd Hdlr (STT): Google API request failed {e}")
                         stt_result_queue.put(f"STT_Error: API/Network Error")
                     except Exception as recog_e:
                         print(f"Rcd Hdlr (STT): Unknown recognition or scoring error: {recog_e}")
                         stt_result_queue.put(f"STT_Error: Recognition/Score Failed")

        # Handle specific errors related to microphone access/setup
        except OSError as e:
             if "Invalid input device" in str(e) or "No Default Input Device Available" in str(e):
                 print(f"Rcd Hdlr (STT) Error: Mic device error: {e}")
                 stt_result_queue.put(f"STT_Error: Mic Device Unavailable")
             else:
                 print(f"Rcd Hdlr (STT) Error: Mic OS Error: {e}")
                 stt_result_queue.put(f"STT_Error: Mic Access Failed")
        except AttributeError as e:
             if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
                 print("Rcd Hdlr (STT) Error: PyAudio missing/failed.")
                 stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
             else:
                 print(f"Rcd Hdlr (STT) Error: Attribute Error: {e}")
                 stt_result_queue.put(f"STT_Error: Setup Attribute Error")
        except Exception as setup_e:
             print(f"Rcd Hdlr (STT) Error: Failed to setup mic: {setup_e}")
             stt_result_queue.put(f"STT_Error: Mic Setup Failed")

        audio_processing_done = True

    # Handle outer try block exceptions (e.g., directory creation)
    except OSError as e:
        print(f"Rcd Hdlr Error: Cannot create recordings dir '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
    except Exception as main_err:
        print(f"Rcd Hdlr Error: Unexpected STT/Save thread error: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error")
        if video_save_thread is not None and video_save_thread.is_alive(): stop_video_save_event.set()
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()

    finally:
        # --- GUARANTEED CLEANUP ---
        print(f"Rcd Hdlr: FINALLY for {topic_idx}.{follow_up_idx}. Audio done: {audio_processing_done}")
        thread_joined = False

        if video_recording_started and stop_video_save_event and not stop_video_save_event.is_set():
            print("Rcd Hdlr (SaveVid): Signaling save thread stop.")
            stop_video_save_event.set()

        if video_save_thread is not None:
            print(f"Rcd Hdlr (SaveVid): Joining save thread (timeout={VIDEO_THREAD_JOIN_TIMEOUT}s)...")
            try:
                if isinstance(video_save_thread, threading.Thread):
                     video_save_thread.join(timeout=VIDEO_THREAD_JOIN_TIMEOUT)
                     if video_save_thread.is_alive():
                         print("Rcd Hdlr (SaveVid) Warn: Save thread join timeout.")
                     else:
                         print("Rcd Hdlr (SaveVid): Save thread joined.")
                         thread_joined = True
            except Exception as join_err:
                print(f"Rcd Hdlr (SaveVid) Error joining save thread: {join_err}")

        if video_writer is not None and video_writer.isOpened():
            print("Rcd Hdlr (SaveVid): Releasing VideoWriter...")
            try:
                video_writer.release()
                print("Rcd Hdlr (SaveVid): VideoWriter released.")
            except Exception as vw_rel_err:
                 print(f"Rcd Hdlr (SaveVid) Error releasing VideoWriter: {vw_rel_err}")

        if video_capture_save is not None and video_capture_save.isOpened():
            print("Rcd Hdlr (SaveVid): Releasing VideoCapture (save)...")
            try:
                video_capture_save.release()
                print("Rcd Hdlr (SaveVid): VideoCapture (save) released.")
            except Exception as vc_rel_err:
                 print(f"Rcd Hdlr (SaveVid) Error releasing VideoCapture: {vc_rel_err}")

        print(f"Rcd Hdlr: STT/Save thread FINALLY finished for {topic_idx}.{follow_up_idx}.")


# ==========================================
# === Public Function to Start Recording ===
# ==========================================
def start_speech_recognition(topic_idx: int, follow_up_idx: int):
    """
    Starts the speech recognition AND video saving process in a separate thread.
    Puts results (text, prosody score) or errors onto the stt_result_queue.
    """
    while not stt_result_queue.empty():
        try:
            stt_result_queue.get_nowait()
        except queue.Empty:
            break
        except Exception as e:
            print(f"Rcd Hdlr (STT): Error clearing queue before start: {e}")

    print(f"Rcd Hdlr: Starting STT/Save thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(
        target=_recognize_speech_thread,
        args=(topic_idx, follow_up_idx),
        daemon=True
    )
    stt_thread.start()

# --- End Recording Functions ---