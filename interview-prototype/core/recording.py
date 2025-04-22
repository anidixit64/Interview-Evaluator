# core/recording.py
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

try:
    import pandas as pd
except ImportError:
    class DummyDataFrame:
        pass
    pd = type('PandasModule', (object,), {'DataFrame': DummyDataFrame})()

PROSODY_ENABLED = False
joblib = None
parselmouth = None
praat_call = None
try:
    import joblib
    import parselmouth
    from parselmouth.praat import call as praat_call
    PROSODY_ENABLED = True
except ImportError:
    pass

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

VIDEO_CAMERA_INDEX = 0
VIDEO_CODEC = 'mp4v'
VIDEO_EXTENSION = '.mp4'
VIDEO_FPS = 20.0
VIDEO_THREAD_JOIN_TIMEOUT = 7.0
STREAMING_FPS_TARGET = 25.0

stt_result_queue = queue.Queue()
_recognizer = None
_ambient_noise_adjusted = False
_adjust_lock = threading.Lock()

_prosody_pipeline = None
_prosody_features_list = None
if PROSODY_ENABLED:
    if not _MODEL_PIPELINE_PATH.exists():
        PROSODY_ENABLED = False
    elif not _MODEL_FEATURES_PATH.exists():
        PROSODY_ENABLED = False
    else:
        try:
            _prosody_pipeline = joblib.load(_MODEL_PIPELINE_PATH)
            _prosody_features_list = joblib.load(_MODEL_FEATURES_PATH)
            if not isinstance(_prosody_features_list, list):
                PROSODY_ENABLED = False
                _prosody_pipeline = None
                _prosody_features_list = None
        except Exception:
            PROSODY_ENABLED = False
            _prosody_pipeline = None
            _prosody_features_list = None

def extract_prosodic_features(wav_path: str, feature_list: list) -> pd.DataFrame | None:
    if not PROSODY_ENABLED or not feature_list or not parselmouth:
        return None

    if not praat_call:
        return None

    try:
        sound = parselmouth.Sound(wav_path)
        if sound.duration < 0.1:
            return None

        pitch = sound.to_pitch()
        intensity = sound.to_intensity()
        formants = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5)
        harmonicity = sound.to_harmonicity()

        pitch_values = []
        if pitch:
            raw_pitch_values = pitch.selected_array['frequency']
            pitch_values = raw_pitch_values[raw_pitch_values != 0]

        intensity_values = []
        if intensity:
            intensity_values = intensity.values.flatten()

        hnr_values = []
        if harmonicity:
            hnr_values = harmonicity.values[harmonicity.values != -200]

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
            except AttributeError:
                jitter_local = 0.0
                jitter_rap = 0.0
                shimmer_local = 0.0
            except parselmouth.PraatError:
                jitter_local = 0.0
                jitter_rap = 0.0
                shimmer_local = 0.0

        num_pauses = 0
        max_dur_pause = 0.0
        avg_dur_pause = 0.0
        try:
            pauses_textgrid = praat_call(sound, "To TextGrid (silences)", -25, 0.1, 0.05, "silent", "sounding")
            num_pauses = praat_call(pauses_textgrid, "Count intervals where", 1, "is equal to", "silent")
            if num_pauses > 0:
                max_dur_pause = sound.duration / (num_pauses * 1.5 + 1)
                avg_dur_pause = sound.duration / (num_pauses * 2 + 1)
        except parselmouth.PraatError:
            num_pauses = 0
            max_dur_pause = 0.0
            avg_dur_pause = 0.0
        except Exception:
            num_pauses = 0
            max_dur_pause = 0.0
            avg_dur_pause = 0.0

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

        features = {}
        for feature_name in feature_list:
            features[feature_name] = feature_map.get(feature_name, 0.0)

        features_df = pd.DataFrame([features], columns=feature_list)
        features_df = features_df.apply(pd.to_numeric, errors='coerce')

        return features_df

    except parselmouth.PraatError:
        return None
    except FileNotFoundError:
        return None
    except Exception:
        return None

def predict_prosody_score(wav_path: str) -> float | None:
    if not PROSODY_ENABLED or _prosody_pipeline is None or _prosody_features_list is None:
        return None

    features_df = extract_prosodic_features(wav_path, _prosody_features_list)
    if features_df is None:
        return None

    try:
        score_array = _prosody_pipeline.predict(features_df)
        predicted_score = score_array[0]
        clamped_score = np.clip(predicted_score, 0, 100)
        final_score = float(clamped_score)
        return final_score
    except Exception:
        return None

def stream_webcam(webcam_queue: queue.Queue, stop_event: threading.Event):
    try:
        import cv2
    except ImportError:
        return

    capture = None
    frame_delay = 1.0 / STREAMING_FPS_TARGET

    try:
        capture = cv2.VideoCapture(VIDEO_CAMERA_INDEX)
        if not capture.isOpened():
            raise IOError(f"Cannot open webcam (index {VIDEO_CAMERA_INDEX})")

        while not stop_event.is_set():
            start_time = time.time()
            ret, frame = capture.read()

            if not ret:
                time.sleep(0.1)
                if stop_event.is_set():
                    break
                continue

            if isinstance(frame, np.ndarray):
                try:
                    webcam_queue.put(frame.copy(), block=False)
                except queue.Full:
                    pass

            elapsed = time.time() - start_time
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception:
        pass
    finally:
        if capture and capture.isOpened():
            capture.release()

        if webcam_queue is not None:
            try:
                webcam_queue.put(None, block=False, timeout=0.1)
            except Exception:
                pass

def _record_video_loop_for_saving(video_capture: cv2.VideoCapture,
                                  video_writer: cv2.VideoWriter,
                                  stop_event: threading.Event,
                                  filename: str,
                                  target_fps: float):
    try:
        import cv2
    except ImportError:
        return

    frames_written = 0
    start_time = time.time()

    try:
        while not stop_event.is_set():
            ret, frame = video_capture.read()

            if not ret:
                time.sleep(0.1)
                if stop_event.is_set():
                    break
                continue

            if video_writer.isOpened():
                try:
                    video_writer.write(frame)
                    frames_written += 1
                except Exception:
                    break

    except Exception:
        pass
    finally:
        end_time = time.time()
        duration = end_time - start_time

def _recognize_speech_thread(topic_idx: int, follow_up_idx: int):
    global _recognizer
    global _ambient_noise_adjusted
    global _adjust_lock
    global stt_result_queue

    try:
        import speech_recognition as sr
    except ImportError:
        stt_result_queue.put("STT_Error: Library Missing")
        return
    try:
        import cv2
    except ImportError:
        pass

    if _recognizer is None:
        try:
            _recognizer = sr.Recognizer()
            _recognizer.dynamic_energy_threshold = False
        except Exception:
            stt_result_queue.put("STT_Error: Recognizer Init Failed")
            return

    video_capture_save = None
    video_writer = None
    video_save_thread = None
    stop_video_save_event = threading.Event()
    video_filepath_obj = None
    audio_filepath_obj = None
    video_recording_started = False
    audio_processing_done = False

    try:
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        if not _ambient_noise_adjusted:
            with _adjust_lock:
                if not _ambient_noise_adjusted:
                    initial_threshold = _recognizer.energy_threshold
                    try:
                        with sr.Microphone() as source:
                            _recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        _ambient_noise_adjusted = True
                    except sr.WaitTimeoutError:
                        _recognizer.energy_threshold = initial_threshold
                        _ambient_noise_adjusted = True
                    except Exception:
                        _recognizer.energy_threshold = initial_threshold
                        _ambient_noise_adjusted = True

        try:
            if 'cv2' not in locals() and 'cv2' not in globals():
                raise ImportError("cv2 not loaded, cannot save video.")

            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath_obj = RECORDINGS_DIR / video_filename
            video_filepath_str = str(video_filepath_obj)

            video_capture_save = cv2.VideoCapture(VIDEO_CAMERA_INDEX)
            if not video_capture_save.isOpened():
                raise IOError("Cannot open webcam for saving")

            frame_width = int(video_capture_save.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(video_capture_save.get(cv2.CAP_PROP_FRAME_HEIGHT))

            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            video_writer = cv2.VideoWriter(video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height))

            if not video_writer.isOpened():
                time.sleep(0.5)
                video_writer = cv2.VideoWriter(video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height))
                if not video_writer.isOpened():
                    raise IOError(f"Could not open VideoWriter after retry: {video_filepath_str}")

            video_save_thread = threading.Thread(
                target=_record_video_loop_for_saving,
                args=(video_capture_save, video_writer, stop_video_save_event, video_filename, VIDEO_FPS),
                daemon=True
            )
            video_save_thread.start()
            video_recording_started = True

        except Exception:
            if video_writer is not None and video_writer.isOpened(): video_writer.release()
            if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
            video_capture_save = None
            video_writer = None
            video_save_thread = None
            video_recording_started = False

        try:
            with sr.Microphone() as source:
                audio = None
                try:
                    audio = _recognizer.listen(source, timeout=7, phrase_time_limit=45)
                except sr.WaitTimeoutError:
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception:
                    stt_result_queue.put(f"STT_Error: Listening Failed")

                if audio:
                    try:
                        audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                        audio_filepath_obj = RECORDINGS_DIR / audio_filename
                        wav_data = audio.get_wav_data()
                        with open(audio_filepath_obj, "wb") as f:
                            f.write(wav_data)
                    except Exception:
                        audio_filepath_obj = None

                    stt_result_queue.put("STT_Status: Processing...")
                    text = None
                    prosody_score = None
                    try:
                        text = _recognizer.recognize_google(audio)
                        if audio_filepath_obj and audio_filepath_obj.exists():
                            prosody_score = predict_prosody_score(str(audio_filepath_obj))
                        score_str = f"{prosody_score:.1f}" if prosody_score is not None else "N/A"
                        stt_result_queue.put(f"STT_Success: {text} | Score: {score_str}")
                    except sr.UnknownValueError:
                        stt_result_queue.put("STT_Error: Could not understand audio.")
                    except sr.RequestError:
                        stt_result_queue.put(f"STT_Error: API/Network Error")
                    except Exception:
                        stt_result_queue.put(f"STT_Error: Recognition/Score Failed")

        except OSError as e:
            stt_result_queue.put(f"STT_Error: Mic Device Unavailable")
        except AttributeError:
            stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
        except Exception:
            stt_result_queue.put(f"STT_Error: Mic Setup Failed")

        audio_processing_done = True

    except OSError:
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
    except Exception:
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error")
        if video_save_thread is not None and video_save_thread.is_alive(): stop_video_save_event.set()
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()

    finally:
        thread_joined = False

        if video_recording_started and stop_video_save_event and not stop_video_save_event.is_set():
            stop_video_save_event.set()

        if video_save_thread is not None:
            try:
                if isinstance(video_save_thread, threading.Thread):
                    video_save_thread.join(timeout=VIDEO_THREAD_JOIN_TIMEOUT)
                    if not video_save_thread.is_alive():
                        thread_joined = True
            except Exception:
                pass

        if video_writer is not None and video_writer.isOpened():
            try:
                video_writer.release()
            except Exception:
                pass

        if video_capture_save is not None and video_capture_save.isOpened():
            try:
                video_capture_save.release()
            except Exception:
                pass

def start_speech_recognition(topic_idx: int, follow_up_idx: int):
    while not stt_result_queue.empty():
        try:
            stt_result_queue.get_nowait()
        except queue.Empty:
            break
        except Exception:
            pass

    stt_thread = threading.Thread(
        target=_recognize_speech_thread,
        args=(topic_idx, follow_up_idx),
        daemon=True
    )
    stt_thread.start()