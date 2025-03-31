# core/recording.py
# Handles audio (STT via SpeechRecognition) and video (OpenCV) recording.

# --- Imports ---
import threading
import time
import os
import speech_recognition as sr
import queue
import cv2

# --- Configuration ---
RECORDINGS_DIR = "recordings" # Directory for ALL recorded files (audio, video, transcript)

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
                    if frame_count == 0:
                         print(f"Recording Handler (Video): First frame written to {filename}.")
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

    try:
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
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Failed: {e}")
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True # Prevent retries
        else:
            print(f"Recording Handler (STT): Using pre-calibrated fixed energy threshold: {_recognizer.energy_threshold:.2f}")
        # --- End Adjustment ---

        # --- Initialize Video Recording ---
        try:
            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath = os.path.join(RECORDINGS_DIR, video_filename)
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

            if not video_writer.isOpened():
                 if video_capture is not None and video_capture.isOpened(): video_capture.release()
                 print(f"Recording Handler (Video): Retrying VideoWriter initialization for {video_filepath}...")
                 video_writer = cv2.VideoWriter(video_filepath, fourcc, fps_for_writer, (frame_width, frame_height))
                 if not video_writer.isOpened():
                      raise IOError(f"Could not open VideoWriter for file after retry: {video_filepath}")
                 else:
                      print(f"Recording Handler (Video): VideoWriter succeeded on retry. Re-opening camera...")
                      video_capture = cv2.VideoCapture(VIDEO_CAMERA_INDEX)
                      if not video_capture.isOpened():
                           raise IOError("Could not re-open webcam after writer success on retry")

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
                    audio = _recognizer.listen(source, timeout=5, phrase_time_limit=30)
                    print("Recording Handler (STT): Audio captured.")
                except sr.WaitTimeoutError:
                    print("Recording Handler (STT): No speech detected within timeout.")
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception as listen_e:
                     print(f"Recording Handler (STT): Error during listening phase: {listen_e}")
                     stt_result_queue.put(f"STT_Error: Listening Failed: {listen_e}")

                # Save audio
                if audio:
                    try:
                        audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                        audio_filepath = os.path.join(RECORDINGS_DIR, audio_filename)
                        print(f"Recording Handler (STT): Saving audio to {audio_filepath}...")
                        wav_data = audio.get_wav_data()
                        with open(audio_filepath, "wb") as f:
                            f.write(wav_data)
                        print(f"Recording Handler (STT): Audio saved successfully.")
                    except Exception as save_err:
                        print(f"Recording Handler (STT) Warning: Failed to save audio file {audio_filename}: {save_err}")

                # Recognize audio
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
                        stt_result_queue.put(f"STT_Error: API/Network Error: {e}")
                    except Exception as recog_e:
                        print(f"Recording Handler (STT): Unknown error during recognition: {recog_e}")
                        stt_result_queue.put(f"STT_Error: Recognition Failed: {recog_e}")

        except OSError as e:
             print(f"Recording Handler (STT) Error: Microphone OS Error: {e}")
             stt_result_queue.put(f"STT_Error: Microphone Access Failed: {e}")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
                 print("Recording Handler (STT) Error: PyAudio not found or failed to initialize.")
                 stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
            else:
                 print(f"Recording Handler (STT) Error: Attribute Error during setup: {e}")
                 stt_result_queue.put(f"STT_Error: Setup Attribute Error: {e}")
        except Exception as setup_e:
            print(f"Recording Handler (STT) Error: Failed to setup microphone: {setup_e}")
            stt_result_queue.put(f"STT_Error: Mic Setup Failed: {setup_e}")
        # --- End Audio Recording and STT ---

        audio_processing_done = True

    except OSError as e:
        print(f"Recording Handler Error: Could not create recordings directory '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()
    except Exception as main_err:
        print(f"Recording Handler Error: Unexpected error in recognition thread: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error: {main_err}")
        if video_thread is not None and video_thread.is_alive():
            stop_video_event.set()
        video_recording_started = False
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()

    finally:
        # --- GUARANTEED CLEANUP: Video Finalization ---
        print(f"Recording Handler: Entering FINALLY block for {topic_idx}.{follow_up_idx}. Audio done: {audio_processing_done}")
        thread_was_joined_cleanly = False

        if video_recording_started and stop_video_event:
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

        if video_writer is not None:
            if video_writer.isOpened():
                print("Recording Handler (Video): Releasing VideoWriter...")
                try:
                    video_writer.release()
                    print("Recording Handler (Video): VideoWriter released.")
                    if not thread_was_joined_cleanly:
                         print("Recording Handler (Video) Warning: VideoWriter released after thread join timeout/failure. File may be incomplete.")
                except Exception as vw_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoWriter: {vw_rel_err}")
            # else: print("Recording Handler (Video): VideoWriter was not opened or already released.") # Optional log

        if video_capture is not None:
            if video_capture.isOpened():
                print("Recording Handler (Video): Releasing VideoCapture...")
                try:
                    video_capture.release()
                    print("Recording Handler (Video): VideoCapture released.")
                except Exception as vc_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoCapture: {vc_rel_err}")
            # else: print("Recording Handler (Video): VideoCapture was not opened or already released.") # Optional log

        print(f"Recording Handler: Recognition thread FINALLY block finished for {topic_idx}.{follow_up_idx}.")
        # --- End GUARANTEED CLEANUP ---


def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition AND video recording process in a separate thread.
    Performs initial ambient noise check/adjustment if not already done.
    Results/status will be put onto stt_result_queue.
    Clears the queue before starting.
    """
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break
        except Exception as e: print(f"Recording Handler (STT): Error clearing queue: {e}")

    print(f"Recording Handler: Starting recognition & video thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()

# --- End Recording Functions ---