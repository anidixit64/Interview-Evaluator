# core/recording.py
"""
Handles audio (STT via SpeechRecognition) and video (OpenCV) recording.
Includes separate functions for continuous webcam streaming and triggered recording.
"""
import threading
import time
import os
import speech_recognition as sr
import queue
import cv2
from pathlib import Path
import numpy as np

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

print(f"Recording Handler: Using recordings directory: {RECORDINGS_DIR}")

# --- Video Recording Configuration ---
VIDEO_CAMERA_INDEX = 0
VIDEO_CODEC = 'mp4v'
VIDEO_EXTENSION = '.mp4'
VIDEO_FPS = 20.0 # Target playback FPS
VIDEO_THREAD_JOIN_TIMEOUT = 7.0

# --- Webcam Streaming Configuration ---
STREAMING_FPS_TARGET = 25.0 # Target FPS for UI display feed

# --- Initialize Shared Speech Recognition Components ---
stt_result_queue = queue.Queue()
_recognizer = sr.Recognizer()
_recognizer.dynamic_energy_threshold = False
_ambient_noise_adjusted = False
_adjust_lock = threading.Lock()
print(f"Rcd Hdlr (STT): Recognizer initialized. DynThrsh: OFF. InitThrsh: {_recognizer.energy_threshold}")


# === Webcam Streaming Function (for UI Display) ===

def stream_webcam(webcam_queue: queue.Queue, stop_event: threading.Event):
    """
    Continuously captures frames from the webcam and puts them onto a queue.
    Runs in its own thread, managed by the main UI.
    """
    print("Webcam Streamer: Thread starting...")
    capture = None
    frame_delay = 1.0 / STREAMING_FPS_TARGET # Delay between frame captures

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
                # Wait a bit before retrying or breaking
                time.sleep(0.1)
                if stop_event.is_set(): # Check again after sleep
                    break
                continue # Try reading again

            if isinstance(frame, np.ndarray):
                try:
                    # Put a *copy* onto the queue to avoid buffer issues
                    webcam_queue.put(frame.copy(), block=False)
                except queue.Full:
                    # If queue is full, discard frame to keep stream live
                    # print("Webcam Streamer: UI queue full, dropping frame.") # Avoid verbose logging
                    pass
                except Exception as q_err:
                    print(f"Webcam Streamer: Error putting frame to queue: {q_err}")

            # Calculate time elapsed and sleep to approximate target FPS
            elapsed = time.time() - start_time
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        print(f"Webcam Streamer: Error in streaming loop: {e}")
        # Signal error state? For now, just prints.
    finally:
        print("Webcam Streamer: Releasing camera...")
        if capture and capture.isOpened():
            capture.release()
        print("Webcam Streamer: Thread finished.")
        # Signal end of stream by putting None
        if webcam_queue is not None:
            try:
                webcam_queue.put(None, block=False)
            except Exception:
                 # Ignore queue errors on shutdown
                 pass


# === Video Recording Function (for Saving Answer Segments) ===

def _record_video_loop_for_saving(video_capture: cv2.VideoCapture,
                                  video_writer: cv2.VideoWriter,
                                  stop_event: threading.Event,
                                  filename: str,
                                  target_fps: float):
    """
    Internal function run in a thread *specifically for saving* video frames
    to a file during an answer recording segment. Reads from its own camera instance.
    """
    print(f"VidSaveLoop: Starting video save to {filename} @ {target_fps} FPS...")
    frames_written = 0
    start_time = time.time()

    try:
        while not stop_event.is_set():
            ret, frame = video_capture.read() # Read from the dedicated capture object
            if not ret:
                if stop_event.is_set():
                    print(f"VidSaveLoop: Stop event received during/after read {filename}.")
                else:
                    print(f"VidSaveLoop Warn: Could not read frame. Stopping save {filename}.")
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
                    print(f"VidSaveLoop: Stop event; Writer closed for {filename}.")
                else:
                    print(f"VidSaveLoop Error: Writer for {filename} closed unexpectedly.")
                break

    except Exception as e:
        print(f"VidSaveLoop Error during recording loop for {filename}: {e}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        actual_fps = frames_written / duration if duration > 0 else 0
        print(f"VidSaveLoop: Stopping loop for {filename}. "
              f"Wrote {frames_written} frames in {duration:.2f}s "
              f"(~{actual_fps:.1f} FPS recorded). Target: {target_fps} FPS")


# === Combined STT and Saving Thread ===

def _recognize_speech_thread(topic_idx: int, follow_up_idx: int):
    """
    Internal function run in a thread to manage STT and SAVE video recording.
    Opens its own camera instance just for the duration of saving.
    """
    global _recognizer
    global _ambient_noise_adjusted
    global _adjust_lock

    video_capture_save = None # Separate capture object for saving
    video_writer = None
    video_save_thread = None
    stop_video_save_event = threading.Event()
    video_filepath_obj = None
    video_recording_started = False
    audio_processing_done = False

    try:
        # Ensure recordings directory exists
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        # --- Adjust ambient noise (only if not done yet) ---
        if not _ambient_noise_adjusted:
            with _adjust_lock:
                if not _ambient_noise_adjusted:
                    # ... (Ambient noise adjustment logic remains the same) ...
                    print("Rcd Hdlr (STT): Initial ambient noise adjustment...")
                    stt_result_queue.put("STT_Status: Adjusting Mic...")
                    initial_threshold = _recognizer.energy_threshold
                    try:
                        with sr.Microphone() as source:
                            _recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        print(f"Rcd Hdlr (STT): Adjustment complete. Fixed threshold: {_recognizer.energy_threshold:.2f}")
                        _ambient_noise_adjusted = True
                    except sr.WaitTimeoutError:
                         print(f"Rcd Hdlr (STT) Warn: Mic adjust timeout. Using default: {initial_threshold}")
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Timeout")
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True
                    except Exception as e:
                         print(f"Rcd Hdlr (STT) Warn: Mic adjust failed: {e}. Using default: {initial_threshold}")
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Failed")
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True


        # --- Initialize Video SAVING Components ---
        try:
            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath_obj = RECORDINGS_DIR / video_filename
            video_filepath_str = str(video_filepath_obj)

            print(f"Rcd Hdlr (SaveVid): Initializing camera {VIDEO_CAMERA_INDEX} for saving...")
            video_capture_save = cv2.VideoCapture(VIDEO_CAMERA_INDEX) # Open for saving

            if not video_capture_save.isOpened():
                raise IOError(f"Cannot open webcam (index {VIDEO_CAMERA_INDEX}) for saving")

            frame_width = int(video_capture_save.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(video_capture_save.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"Rcd Hdlr (SaveVid): Camera opened. Res: {frame_width}x{frame_height}")

            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            print(f"Rcd Hdlr (SaveVid): Preparing writer for {video_filepath_str} @ {VIDEO_FPS} FPS")
            video_writer = cv2.VideoWriter(
                video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height)
            )

            if not video_writer.isOpened(): # Retry logic
                print(f"Rcd Hdlr (SaveVid): Initial VideoWriter open failed. Retrying...")
                time.sleep(0.5)
                video_writer = cv2.VideoWriter(
                    video_filepath_str, fourcc, VIDEO_FPS, (frame_width, frame_height)
                )
                if not video_writer.isOpened():
                    raise IOError(f"Could not open VideoWriter after retry: {video_filepath_str}")
                else:
                    print(f"Rcd Hdlr (SaveVid): VideoWriter succeeded on retry.")

            video_save_thread = threading.Thread(
                target=_record_video_loop_for_saving, # Use the saving loop
                args=(video_capture_save, video_writer, stop_video_save_event,
                      video_filename, VIDEO_FPS),
                daemon=True
            )
            video_save_thread.start()
            video_recording_started = True # Indicates saving has started
            print(f"Rcd Hdlr (SaveVid): Saving thread started for {video_filename}.")

        except Exception as video_init_err:
            print(f"Rcd Hdlr (SaveVid) Warn: Failed to init video saving: {video_init_err}")
            if video_writer is not None and video_writer.isOpened(): video_writer.release()
            if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
            video_capture_save = video_writer = video_save_thread = None
            video_recording_started = False


        # --- Audio Recording and STT (remains largely the same) ---
        try:
            with sr.Microphone() as source:
                print("Rcd Hdlr (STT): Listening for speech...")
                stt_result_queue.put("STT_Status: Listening...")
                audio = None
                try:
                    audio = _recognizer.listen(source, timeout=5, phrase_time_limit=30)
                    print("Rcd Hdlr (STT): Audio captured.")
                except sr.WaitTimeoutError:
                    print("Rcd Hdlr (STT): No speech detected within timeout.")
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception as listen_e:
                    print(f"Rcd Hdlr (STT): Error during listening: {listen_e}")
                    stt_result_queue.put(f"STT_Error: Listening Failed")

                if audio:
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

                if audio:
                    stt_result_queue.put("STT_Status: Processing...")
                    try:
                        print("Rcd Hdlr (STT): Recognizing using Google Web Speech API...")
                        text = _recognizer.recognize_google(audio)
                        print(f"Rcd Hdlr (STT): Recognized: '{text}'")
                        stt_result_queue.put(f"STT_Success: {text}")
                    except sr.UnknownValueError:
                        print("Rcd Hdlr (STT): Google could not understand audio")
                        stt_result_queue.put("STT_Error: Could not understand audio.")
                    except sr.RequestError as e:
                        print(f"Rcd Hdlr (STT): Google API request failed; {e}")
                        stt_result_queue.put(f"STT_Error: API/Network Error")
                    except Exception as recog_e:
                        print(f"Rcd Hdlr (STT): Unknown recognition error: {recog_e}")
                        stt_result_queue.put(f"STT_Error: Recognition Failed")

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

    except OSError as e:
        print(f"Rcd Hdlr Error: Cannot create recordings dir '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False
        # Ensure saving resources are cleaned up if dir creation fails
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()
    except Exception as main_err:
        print(f"Rcd Hdlr Error: Unexpected STT/Save thread error: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error")
        if video_save_thread is not None and video_save_thread.is_alive():
            stop_video_save_event.set()
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture_save is not None and video_capture_save.isOpened(): video_capture_save.release()

    finally:
        # --- GUARANTEED CLEANUP: Video Saving Finalization ---
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
                else:
                    print("Rcd Hdlr (SaveVid) Error: video_save_thread not a Thread.")
            except Exception as join_err:
                print(f"Rcd Hdlr (SaveVid) Error joining save thread: {join_err}")

        if video_writer is not None:
            if video_writer.isOpened():
                print("Rcd Hdlr (SaveVid): Releasing VideoWriter...")
                try:
                    video_writer.release()
                    print("Rcd Hdlr (SaveVid): VideoWriter released.")
                    if video_recording_started and not thread_joined:
                         print("Rcd Hdlr (SaveVid) Warn: Writer released after thread join timeout.")
                except Exception as vw_rel_err:
                     print(f"Rcd Hdlr (SaveVid) Error releasing VideoWriter: {vw_rel_err}")

        if video_capture_save is not None:
            if video_capture_save.isOpened():
                print("Rcd Hdlr (SaveVid): Releasing VideoCapture (save)...")
                try:
                    video_capture_save.release()
                    print("Rcd Hdlr (SaveVid): VideoCapture (save) released.")
                except Exception as vc_rel_err:
                     print(f"Rcd Hdlr (SaveVid) Error releasing VideoCapture: {vc_rel_err}")

        print(f"Rcd Hdlr: STT/Save thread FINALLY finished for {topic_idx}.{follow_up_idx}.")


# --- Public Function to Start STT/Saving ---

def start_speech_recognition(topic_idx: int, follow_up_idx: int):
    """
    Starts the speech recognition AND video saving process in a separate thread.
    Does NOT handle the webcam display feed.
    """
    # Clear STT result queue safely before starting
    while not stt_result_queue.empty():
        try:
            stt_result_queue.get_nowait()
        except queue.Empty:
            break
        except Exception as e:
            print(f"Rcd Hdlr (STT): Error clearing queue: {e}")

    print(f"Rcd Hdlr: Starting STT/Save thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(
        target=_recognize_speech_thread,
        args=(topic_idx, follow_up_idx), # No webcam_queue passed here
        daemon=True
    )
    stt_thread.start()

# --- End Recording Functions ---