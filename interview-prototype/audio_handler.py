# audio_handler.py
# Handles audio-related functions: TTS (gTTS+afplay) and STT (SpeechRecognition)

# --- Existing Imports ---
import threading
import io
import time
from gtts import gTTS, gTTSError
import subprocess
import tempfile
import os # <-- Add os import
import requests
import speech_recognition as sr
import queue

# --- Configuration ---
TTS_LANGUAGE = 'en'
TTS_TLD = 'com'
RECORDINGS_DIR = "recorded_audio" # <-- Define recordings directory

# --- Existing TTS Functions (_fetch_and_play_gtts, speak_text) ---
# [ Keep the gTTS + afplay code here... ]
def speak_text(text_to_speak):
    """
    Generates speech using gTTS and plays it using afplay.
    Runs network request and playback in a separate thread.
    """
    if not text_to_speak:
        print("Audio Handler (gTTS): No text provided to speak.")
        return
    thread = threading.Thread(target=_fetch_and_play_gtts, args=(text_to_speak,), daemon=True)
    thread.start()

def _fetch_and_play_gtts(text):
    """Internal function to fetch TTS audio from gTTS and play with afplay."""
    # [ Keep implementation from previous step ]
    play_obj = None
    try:
        mp3_fp = io.BytesIO()
        tts = gTTS(text=text, lang=TTS_LANGUAGE, tld=TTS_TLD, slow=False)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        audio_data = mp3_fp.read()
        mp3_fp.close()

        temp_filename = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_f:
                 temp_filename = temp_f.name
                 temp_f.write(audio_data)
            process = subprocess.run(['afplay', temp_filename], check=True, capture_output=True)
            print(f"Audio Handler (gTTS): afplay finished for '{text[:20]}...'.")
        except FileNotFoundError:
             print("Audio Handler Error (gTTS): 'afplay' command not found.")
        except subprocess.CalledProcessError as cpe:
             print(f"Audio Handler Error (gTTS): 'afplay' failed: {cpe.stderr.decode()}")
        except Exception as play_err:
             print(f"Audio Handler Error (gTTS): Unexpected error during afplay: {play_err}")
        finally:
            if temp_filename and os.path.exists(temp_filename):
                try: os.remove(temp_filename)
                except Exception: pass

    except gTTSError as gt_err: print(f"Audio Handler Error (gTTS): Failed to get audio: {gt_err}")
    except requests.exceptions.RequestException as req_err: print(f"Audio Handler Error (gTTS): Network error: {req_err}")
    except Exception as e: print(f"Audio Handler Error (gTTS): Unexpected error: {e}")


# --- Speech-To-Text Functions ---

stt_result_queue = queue.Queue()

# MODIFIED: Accept indices
def _recognize_speech_thread(topic_idx, follow_up_idx):
    """
    Internal function run in a thread to capture, SAVE, and recognize speech.
    Puts the result (text or error string) onto the stt_result_queue.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        print("Audio Handler (STT): Adjusting for ambient noise...")
        stt_result_queue.put("STT_Status: Adjusting...")
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print(f"Audio Handler (STT): Energy threshold set to {recognizer.energy_threshold:.2f}")
        except Exception as e:
             print(f"Audio Handler (STT): Error adjusting noise: {e}")
             stt_result_queue.put(f"STT_Error: Mic Noise Adjust Failed: {e}")
             return

        print("Audio Handler (STT): Listening for speech...")
        stt_result_queue.put("STT_Status: Listening...")
        audio = None # Initialize audio object reference
        try:
            # Listen for audio input
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
            print("Audio Handler (STT): Audio captured.")

            # --- NEW: Save captured audio ---
            if audio:
                try:
                    # Ensure the recordings directory exists
                    os.makedirs(RECORDINGS_DIR, exist_ok=True)
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
                    print("Audio Handler (STT): Recognizing using Google...")
                    text = recognizer.recognize_google(audio)
                    print(f"Audio Handler (STT): Recognized: '{text}'")
                    stt_result_queue.put(f"STT_Success: {text}")
                except sr.UnknownValueError:
                    print("Audio Handler (STT): Google could not understand audio")
                    stt_result_queue.put("STT_Error: Could not understand audio.")
                except sr.RequestError as e:
                    print(f"Audio Handler (STT): Google API request failed; {e}")
                    stt_result_queue.put(f"STT_Error: API/Network Error: {e}")
                except Exception as recog_e:
                    print(f"Audio Handler (STT): Unknown error during recognition: {recog_e}")
                    stt_result_queue.put(f"STT_Error: Recognition Failed: {recog_e}")
            else:
                 # This case shouldn't normally happen if listen() doesn't raise WaitTimeoutError
                 print("Audio Handler (STT): No audio data captured, skipping recognition.")
                 stt_result_queue.put("STT_Error: No audio captured.")


        except sr.WaitTimeoutError:
            print("Audio Handler (STT): No speech detected within timeout.")
            stt_result_queue.put("STT_Error: No speech detected.")
        except Exception as listen_e:
             print(f"Audio Handler (STT): Error during listening: {listen_e}")
             stt_result_queue.put(f"STT_Error: Listening Failed: {listen_e}")

# MODIFIED: Accept indices
def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition process in a separate thread, passing indices.
    Results/status will be put onto stt_result_queue.
    """
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break

    print(f"Audio Handler (STT): Starting recognition thread for {topic_idx}.{follow_up_idx}...")
    # Pass indices to the target function
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()

# --- Example Usage ---
# [ Keep example usage commented out ]