# audio_handler.py
# Handles audio-related functions: TTS (Coqui TTS + afplay) and STT (SpeechRecognition)

# --- Imports ---
import threading
# import io # No longer needed for gTTS
import time
# from gtts import gTTS, gTTSError # No longer needed
import subprocess
import tempfile
import os
# import requests # No longer needed for gTTS
import speech_recognition as sr
import queue
from TTS.api import TTS # <-- Import Coqui TTS

# --- Configuration ---
# TTS_LANGUAGE = 'en' # No longer needed for Coqui TTS model specification
# TTS_TLD = 'com' # No longer needed for Coqui TTS
RECORDINGS_DIR = "recorded_audio" # Directory for STT recordings

# --- Coqui TTS Configuration ---
# Select a Coqui TTS model. Examples:
# - FastSpeech2 + HiFiGAN (Good quality): "tts_models/en/ljspeech/fastspeech2-hifigan"
# - VITS (Often faster, good quality): "tts_models/en/ljspeech/vits"
# - VITS (VCTK multi-speaker, might need speaker selection): "tts_models/en/vctk/vits"
# Check available models: `tts --list_models`
COQUI_MODEL_NAME = "tts_models/en/ljspeech/vits"
COQUI_USE_GPU = False # Set to True if you have a compatible GPU and PyTorch installed with CUDA support

# --- Initialize Coqui TTS Engine ---
# Load the TTS model once when the module is imported for efficiency
tts_engine = None
try:
    print(f"Audio Handler (TTS): Initializing Coqui TTS engine with model: {COQUI_MODEL_NAME}...")
    # Make sure to install TTS: pip install TTS
    tts_engine = TTS(model_name=COQUI_MODEL_NAME, progress_bar=False, gpu=COQUI_USE_GPU)
    print("Audio Handler (TTS): Coqui TTS engine initialized successfully.")
except ModuleNotFoundError:
    print("Audio Handler Error (TTS): 'TTS' package not found. Please install it: pip install TTS")
    print("Audio Handler (TTS): TTS functionality will be disabled.")
except Exception as e:
    print(f"Audio Handler Error (TTS): Failed to initialize Coqui TTS engine: {e}")
    print("Audio Handler (TTS): TTS functionality will be disabled.")
# --- End Coqui TTS Initialization ---


# --- Text-To-Speech (TTS) Functions ---

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

    # Start synthesis and playback in a background thread
    thread = threading.Thread(target=_synthesize_and_play_coqui, args=(text_to_speak,), daemon=True)
    thread.start()

def _synthesize_and_play_coqui(text):
    """
    Internal function (run in a thread) to synthesize audio using Coqui TTS
    and play it with afplay.
    """
    global tts_engine # Access the globally initialized engine
    if tts_engine is None:
        print("Audio Handler Error (TTS): Internal thread found TTS engine not initialized.")
        return # Should not happen if speak_text checks, but good practice

    temp_filename = None
    try:
        # Create a temporary file to store the WAV output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_f:
            temp_filename = temp_f.name

        # Synthesize speech to the temporary file
        print(f"Audio Handler (TTS): Synthesizing '{text[:30]}...' using Coqui TTS...")
        start_time = time.time()
        # Use the initialized tts_engine
        tts_engine.tts_to_file(text=text, file_path=temp_filename)
        end_time = time.time()
        print(f"Audio Handler (TTS): Synthesis complete ({end_time - start_time:.2f}s). Playing audio...")

        # Play the generated WAV file using afplay
        try:
            process = subprocess.run(['afplay', temp_filename], check=True, capture_output=True)
            print(f"Audio Handler (TTS): afplay finished for '{text[:20]}...'.")
        except FileNotFoundError:
             print("Audio Handler Error (TTS): 'afplay' command not found. Please ensure it's installed (macOS).")
        except subprocess.CalledProcessError as cpe:
             # Use stderr for potentially more informative errors from afplay
             error_message = cpe.stderr.decode().strip() if cpe.stderr else f"Return code {cpe.returncode}"
             print(f"Audio Handler Error (TTS): 'afplay' failed: {error_message}")
        except Exception as play_err:
             print(f"Audio Handler Error (TTS): Unexpected error during afplay: {play_err}")

    except Exception as synth_err:
        # Catch potential errors during TTS synthesis
        print(f"Audio Handler Error (TTS - Coqui): Failed to synthesize audio: {synth_err}")
    finally:
        # Clean up the temporary file
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                # print(f"Audio Handler (TTS): Deleted temp file {temp_filename}")
            except Exception as del_err:
                print(f"Audio Handler Warning (TTS): Failed to delete temp file {temp_filename}: {del_err}")


# --- Speech-To-Text (STT) Functions ---

stt_result_queue = queue.Queue()

# MODIFIED: Accept indices
def _recognize_speech_thread(topic_idx, follow_up_idx):
    """
    Internal function run in a thread to capture, SAVE, and recognize speech.
    Puts the result (text or error string) onto the stt_result_queue.
    Requires 'pip install SpeechRecognition PyAudio' (PyAudio needed for Microphone).
    """
    recognizer = sr.Recognizer()
    # Consider making energy threshold settings configurable if needed
    recognizer.dynamic_energy_threshold = True # Adjusts based on ambient noise
    # recognizer.energy_threshold = 400 # Or set a fixed threshold

    # Ensure recordings directory exists before trying to use Microphone
    try:
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
    except OSError as e:
        print(f"Audio Handler (STT) Error: Could not create recordings directory '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        return # Cannot proceed without directory for saving

    try:
        with sr.Microphone() as source:
            print("Audio Handler (STT): Adjusting for ambient noise...")
            stt_result_queue.put("STT_Status: Adjusting...")
            try:
                # Adjust for ambient noise - consider making duration configurable
                recognizer.adjust_for_ambient_noise(source, duration=1)
                print(f"Audio Handler (STT): Energy threshold set to {recognizer.energy_threshold:.2f}")
            except Exception as e:
                 print(f"Audio Handler (STT): Error adjusting noise: {e}")
                 # Non-fatal, might still work but could be less accurate
                 stt_result_queue.put(f"STT_Warning: Mic Noise Adjust Failed: {e}")


            print("Audio Handler (STT): Listening for speech...")
            stt_result_queue.put("STT_Status: Listening...")
            audio = None # Initialize audio object reference
            try:
                # Listen for audio input - consider making timeouts configurable
                # timeout: max seconds to wait for speech to start
                # phrase_time_limit: max seconds of speech to record
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
                print("Audio Handler (STT): Audio captured.")

                # --- Save captured audio ---
                if audio:
                    try:
                        # Construct filename (e.g., "1.0.wav", "1.1.wav")
                        filename = f"{topic_idx}.{follow_up_idx}.wav"
                        filepath = os.path.join(RECORDINGS_DIR, filename)
                        print(f"Audio Handler (STT): Saving audio to {filepath}...")
                        # Get WAV data from the AudioData object
                        wav_data = audio.get_wav_data()
                        # Write the WAV data to a file
                        with open(filepath, "wb") as f:
                            f.write(wav_data)
                        print(f"Audio Handler (STT): Audio saved successfully.")
                    except Exception as save_err:
                        # Log error but continue with recognition
                        print(f"Audio Handler (STT) Warning: Failed to save audio file {filename}: {save_err}")
                # --- End Save captured audio ---

                # Proceed with recognition ONLY if audio was captured
                if audio:
                    stt_result_queue.put("STT_Status: Processing...")
                    try:
                        print("Audio Handler (STT): Recognizing using Google Web Speech API...")
                        # Other options: recognize_sphinx (offline), recognize_whisper (offline, need setup)
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
                else:
                     # This case shouldn't normally happen if listen() doesn't raise WaitTimeoutError
                     print("Audio Handler (STT): No audio data captured (internal logic error?), skipping recognition.")
                     stt_result_queue.put("STT_Error: No audio captured.")


            except sr.WaitTimeoutError:
                print("Audio Handler (STT): No speech detected within timeout.")
                stt_result_queue.put("STT_Error: No speech detected.")
            except Exception as listen_e:
                 print(f"Audio Handler (STT): Error during listening phase: {listen_e}")
                 stt_result_queue.put(f"STT_Error: Listening Failed: {listen_e}")

    except OSError as e:
         # Specific handling for microphone access issues (e.g., permissions, device not found)
         print(f"Audio Handler (STT) Error: Microphone OS Error: {e}")
         stt_result_queue.put(f"STT_Error: Microphone Access Failed: {e}")
    except AttributeError as e:
        # Often happens if PyAudio is not installed or cannot be used
        if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
             print("Audio Handler (STT) Error: PyAudio not found or failed to initialize. Is it installed? (pip install PyAudio)")
             stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
        else:
             print(f"Audio Handler (STT) Error: Attribute Error during setup: {e}")
             stt_result_queue.put(f"STT_Error: Setup Attribute Error: {e}")
    except Exception as setup_e:
        # Catch-all for other microphone setup issues
        print(f"Audio Handler (STT) Error: Failed to setup microphone: {setup_e}")
        stt_result_queue.put(f"STT_Error: Mic Setup Failed: {setup_e}")


# MODIFIED: Accept indices
def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition process in a separate thread, passing indices.
    Results/status will be put onto stt_result_queue.
    Clears the queue before starting.
    """
    # Clear any old messages from the queue before starting a new recognition
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break
        except Exception as e: print(f"Audio Handler (STT): Error clearing queue: {e}") # Should not happen

    print(f"Audio Handler (STT): Starting recognition thread for {topic_idx}.{follow_up_idx}...")
    # Pass indices to the target function
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()
