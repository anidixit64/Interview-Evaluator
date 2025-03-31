# audio_handler.py
# Handles audio-related functions: TTS (Coqui TTS + afplay) and STT (SpeechRecognition)
# ADDED: Video Recording (OpenCV)

# --- Imports ---
import threading
import time
import subprocess
import tempfile
import os
import speech_recognition as sr
import queue
from TTS.api import TTS # <-- Import Coqui TTS
import cv2 # <-- Import OpenCV

# --- Configuration ---
RECORDINGS_DIR = "recorded_video" # Directory for STT recordings AND video

# --- Coqui TTS Configuration ---
COQUI_MODEL_NAME = "tts_models/en/ljspeech/vits"
COQUI_USE_GPU = False

# --- Video Recording Configuration ---
VIDEO_CAMERA_INDEX = 0 # Default webcam
VIDEO_CODEC = 'mp4v' # Codec for MP4 files
VIDEO_EXTENSION = '.mp4'
# You might need to adjust FPS based on your camera, typical webcam values are 15-30
VIDEO_FPS = 20.0

# --- Initialize Coqui TTS Engine ---
# (Existing TTS initialization code remains the same)
tts_engine = None
try:
    print(f"Audio Handler (TTS): Initializing Coqui TTS engine with model: {COQUI_MODEL_NAME}...")
    tts_engine = TTS(model_name=COQUI_MODEL_NAME, progress_bar=False, gpu=COQUI_USE_GPU)
    print("Audio Handler (TTS): Coqui TTS engine initialized successfully.")
except ModuleNotFoundError:
    print("Audio Handler Error (TTS): 'TTS' package not found. Please install it: pip install TTS")
    print("Audio Handler (TTS): TTS functionality will be disabled.")
except Exception as e:
    print(f"Audio Handler Error (TTS): Failed to initialize Coqui TTS engine: {e}")
    print("Audio Handler (TTS): TTS functionality will be disabled.")


# --- Text-To-Speech (TTS) Functions ---
# (Existing speak_text and _synthesize_and_play_coqui functions remain the same)

def speak_text(text_to_speak):
    """
    Generates speech using Coqui TTS and plays it using afplay.
    Runs synthesis and playback in a separate thread.
    Requires 'pip install TTS' and 'afplay' (macOS).
    """
    if not text_to_speak:
        print("Audio Handler (TTS): No text provided to speak.")
        return
    if tts_engine is None:
        print("Audio Handler Error (TTS): TTS engine not initialized. Cannot speak.")
        return

    thread = threading.Thread(target=_synthesize_and_play_coqui, args=(text_to_speak,), daemon=True)
    thread.start()

def _synthesize_and_play_coqui(text):
    """
    Internal function (run in a thread) to synthesize audio using Coqui TTS
    and play it with afplay.
    """
    global tts_engine
    if tts_engine is None:
        print("Audio Handler Error (TTS): Internal thread found TTS engine not initialized.")
        return

    temp_filename = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_f:
            temp_filename = temp_f.name

        print(f"Audio Handler (TTS): Synthesizing '{text[:30]}...' using Coqui TTS...")
        start_time = time.time()
        tts_engine.tts_to_file(text=text, file_path=temp_filename)
        end_time = time.time()
        print(f"Audio Handler (TTS): Synthesis complete ({end_time - start_time:.2f}s). Playing audio...")

        try:
            process = subprocess.run(['afplay', temp_filename], check=True, capture_output=True)
            print(f"Audio Handler (TTS): afplay finished for '{text[:20]}...'.")
        except FileNotFoundError:
             print("Audio Handler Error (TTS): 'afplay' command not found. Please ensure it's installed (macOS).")
        except subprocess.CalledProcessError as cpe:
             error_message = cpe.stderr.decode().strip() if cpe.stderr else f"Return code {cpe.returncode}"
             print(f"Audio Handler Error (TTS): 'afplay' failed: {error_message}")
        except Exception as play_err:
             print(f"Audio Handler Error (TTS): Unexpected error during afplay: {play_err}")

    except Exception as synth_err:
        print(f"Audio Handler Error (TTS - Coqui): Failed to synthesize audio: {synth_err}")
    finally:
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception as del_err:
                print(f"Audio Handler Warning (TTS): Failed to delete temp file {temp_filename}: {del_err}")


# --- Speech-To-Text (STT) & Video Recording Functions ---

stt_result_queue = queue.Queue()

def _record_video_loop(video_capture, video_writer, stop_event, filename):
    """
    Internal function run in a thread to capture frames from the webcam
    and write them to the video file until stop_event is set.
    """
    print(f"Audio Handler (Video): Starting video recording to {filename}...")
    frame_count = 0
    start_time = time.time()
    try:
        while not stop_event.is_set():
            ret, frame = video_capture.read()
            if not ret:
                print(f"Audio Handler (Video) Warning: Could not read frame from camera.")
                # Optionally break or sleep shortly
                time.sleep(0.1) # Prevent tight loop on error
                continue
            if video_writer.isOpened():
                video_writer.write(frame)
                frame_count += 1
            else:
                print(f"Audio Handler (Video) Error: VideoWriter for {filename} is not open!")
                break # Stop trying if writer failed

            # Add a small sleep to prevent hogging CPU if FPS is low or camera is slow
            # Adjust based on desired FPS and performance
            # time.sleep(1 / (VIDEO_FPS * 1.5)) # Sleep slightly longer than frame time
            time.sleep(0.01) # Small sleep is usually sufficient

    except Exception as e:
        print(f"Audio Handler (Video) Error during recording loop for {filename}: {e}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        actual_fps = frame_count / duration if duration > 0 else 0
        print(f"Audio Handler (Video): Stopping video recording for {filename}. Recorded {frame_count} frames in {duration:.2f}s (~{actual_fps:.1f} FPS).")
        # Release is handled in the main STT thread's finally block

def _recognize_speech_thread(topic_idx, follow_up_idx):
    """
    Internal function run in a thread to:
    1. Start video recording (in a nested thread).
    2. Capture, SAVE audio, and recognize speech.
    3. Stop video recording.
    Puts the STT result (text or error string) onto the stt_result_queue.
    Requires 'pip install SpeechRecognition PyAudio opencv-python'.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    # --- Video Recording Variables ---
    video_capture = None
    video_writer = None
    video_thread = None
    stop_video_event = threading.Event()
    video_filepath = None
    video_recording_started = False
    # --- End Video Recording Variables ---

    try:
        # Ensure recordings directory exists
        os.makedirs(RECORDINGS_DIR, exist_ok=True)

        # --- Initialize Video Recording ---
        try:
            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath = os.path.join(RECORDINGS_DIR, video_filename)
            print(f"Audio Handler (Video): Initializing camera index {VIDEO_CAMERA_INDEX}...")
            video_capture = cv2.VideoCapture(VIDEO_CAMERA_INDEX)

            if not video_capture.isOpened():
                raise IOError(f"Cannot open webcam (index {VIDEO_CAMERA_INDEX})")

            # Get camera properties for VideoWriter
            frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            # Sometimes CAP_PROP_FPS returns 0, use default if so
            camera_fps = video_capture.get(cv2.CAP_PROP_FPS)
            actual_fps = camera_fps if camera_fps > 0 else VIDEO_FPS
            print(f"Audio Handler (Video): Camera opened. Resolution: {frame_width}x{frame_height}, FPS: {actual_fps:.1f}")

            # Define the codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            print(f"Audio Handler (Video): Preparing writer for {video_filepath}...")
            video_writer = cv2.VideoWriter(video_filepath, fourcc, actual_fps, (frame_width, frame_height))

            if not video_writer.isOpened():
                 raise IOError(f"Could not open VideoWriter for file: {video_filepath}")

            # Start the video recording loop in its own thread
            video_thread = threading.Thread(
                target=_record_video_loop,
                args=(video_capture, video_writer, stop_video_event, video_filename),
                daemon=True
            )
            video_thread.start()
            video_recording_started = True
            print(f"Audio Handler (Video): Recording thread started.")

        except Exception as video_init_err:
            print(f"Audio Handler (Video) Warning: Failed to initialize video recording: {video_init_err}")
            print("Audio Handler (Video): Proceeding with audio only.")
            # Clean up partially initialized resources if necessary
            if video_writer is not None and video_writer.isOpened(): video_writer.release()
            if video_capture is not None and video_capture.isOpened(): video_capture.release()
            video_capture = None
            video_writer = None
            video_thread = None # Ensure thread isn't joined later if it never started
        # --- End Initialize Video Recording ---


        # --- Audio Recording and STT ---
        try:
            with sr.Microphone() as source:
                print("Audio Handler (STT): Adjusting for ambient noise...")
                stt_result_queue.put("STT_Status: Adjusting...")
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                    print(f"Audio Handler (STT): Energy threshold set to {recognizer.energy_threshold:.2f}")
                except Exception as e:
                     print(f"Audio Handler (STT): Error adjusting noise: {e}")
                     stt_result_queue.put(f"STT_Warning: Mic Noise Adjust Failed: {e}")

                print("Audio Handler (STT): Listening for speech...")
                stt_result_queue.put("STT_Status: Listening...")
                audio = None
                try:
                    # Listen for audio input
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
                    print("Audio Handler (STT): Audio captured.")

                except sr.WaitTimeoutError:
                    print("Audio Handler (STT): No speech detected within timeout.")
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception as listen_e:
                     print(f"Audio Handler (STT): Error during listening phase: {listen_e}")
                     stt_result_queue.put(f"STT_Error: Listening Failed: {listen_e}")

                # --- Save captured audio ---
                if audio:
                    try:
                        # Construct audio filename (e.g., "1.0.wav")
                        audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                        audio_filepath = os.path.join(RECORDINGS_DIR, audio_filename)
                        print(f"Audio Handler (STT): Saving audio to {audio_filepath}...")
                        wav_data = audio.get_wav_data()
                        with open(audio_filepath, "wb") as f:
                            f.write(wav_data)
                        print(f"Audio Handler (STT): Audio saved successfully.")
                    except Exception as save_err:
                        print(f"Audio Handler (STT) Warning: Failed to save audio file {audio_filename}: {save_err}")
                # --- End Save captured audio ---

                # Proceed with STT recognition ONLY if audio was captured
                if audio:
                    stt_result_queue.put("STT_Status: Processing...")
                    try:
                        print("Audio Handler (STT): Recognizing using Google Web Speech API...")
                        text = recognizer.recognize_google(audio)
                        print(f"Audio Handler (STT): Recognized: '{text}'")
                        stt_result_queue.put(f"STT_Success: {text}")
                    except sr.UnknownValueError:
                        print("Audio Handler (STT): Google Web Speech API could not understand audio")
                        stt_result_queue.put("STT_Error: Could not understand audio.")
                    except sr.RequestError as e:
                        print(f"Audio Handler (STT): Google Web Speech API request failed; {e}")
                        stt_result_queue.put(f"STT_Error: API/Network Error: {e}")
                    except Exception as recog_e:
                        print(f"Audio Handler (STT): Unknown error during recognition: {recog_e}")
                        stt_result_queue.put(f"STT_Error: Recognition Failed: {recog_e}")
                # elif not stt_result_queue.full(): # Only put error if no result/error already queued
                #      # Check if an error wasn't already put (like timeout)
                #      # This logic might need refinement depending on desired error priority
                #      if not any(msg.startswith("STT_Error:") for msg in list(stt_result_queue.queue)):
                #          stt_result_queue.put("STT_Error: No audio captured for recognition.")
                # This case is handled by WaitTimeoutError or other listen errors putting messages on queue

        except OSError as e:
             print(f"Audio Handler (STT) Error: Microphone OS Error: {e}")
             stt_result_queue.put(f"STT_Error: Microphone Access Failed: {e}")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
                 print("Audio Handler (STT) Error: PyAudio not found or failed to initialize. Is it installed? (pip install PyAudio)")
                 stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
            else:
                 print(f"Audio Handler (STT) Error: Attribute Error during setup: {e}")
                 stt_result_queue.put(f"STT_Error: Setup Attribute Error: {e}")
        except Exception as setup_e:
            print(f"Audio Handler (STT) Error: Failed to setup microphone: {setup_e}")
            stt_result_queue.put(f"STT_Error: Mic Setup Failed: {setup_e}")
        # --- End Audio Recording and STT ---

    except OSError as e:
        # Error creating directory
        print(f"Audio Handler Error: Could not create recordings directory '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
    except Exception as main_err:
        # Catch-all for unexpected errors in the thread setup
        print(f"Audio Handler Error: Unexpected error in recognition thread: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error: {main_err}")
    finally:
        # --- Stop Video Recording ---
        if video_recording_started and stop_video_event:
            print("Audio Handler (Video): Signaling video thread to stop.")
            stop_video_event.set() # Signal the video loop to exit

        if video_thread is not None:
            print("Audio Handler (Video): Waiting for video thread to finish...")
            video_thread.join(timeout=3.0) # Wait for the thread to complete (with timeout)
            if video_thread.is_alive():
                print("Audio Handler (Video) Warning: Video thread did not finish within timeout.")

        # Release video resources
        if video_writer is not None:
            if video_writer.isOpened():
                print("Audio Handler (Video): Releasing VideoWriter.")
                video_writer.release()
            else:
                 print("Audio Handler (Video): VideoWriter was not open, no release needed.")
        if video_capture is not None:
            if video_capture.isOpened():
                print("Audio Handler (Video): Releasing VideoCapture.")
                video_capture.release()
            else:
                 print("Audio Handler (Video): VideoCapture was not open, no release needed.")

        print(f"Audio Handler: Recognition thread for {topic_idx}.{follow_up_idx} finished.")
        # --- End Stop Video Recording ---


def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition AND video recording process in a separate thread.
    Results/status will be put onto stt_result_queue.
    Clears the queue before starting.
    """
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break
        except Exception as e: print(f"Audio Handler (STT): Error clearing queue: {e}")

    print(f"Audio Handler: Starting recognition & video thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()