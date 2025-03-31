# core/tts.py
# Handles Text-To-Speech (TTS) functions using Coqui TTS + afplay

# --- Imports ---
import threading
import time
import subprocess
import tempfile
import os
from TTS.api import TTS

# --- Configuration ---
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
    print(f"TTS Handler: Initializing Coqui TTS engine with model: {COQUI_MODEL_NAME}...")
    # Make sure to install TTS: pip install TTS
    tts_engine = TTS(model_name=COQUI_MODEL_NAME, progress_bar=False, gpu=COQUI_USE_GPU)
    print("TTS Handler: Coqui TTS engine initialized successfully.")
except ModuleNotFoundError:
    print("TTS Handler Error: 'TTS' package not found. Please install it: pip install TTS")
    print("TTS Handler: TTS functionality will be disabled.")
except Exception as e:
    print(f"TTS Handler Error: Failed to initialize Coqui TTS engine: {e}")
    print("TTS Handler: TTS functionality will be disabled.")
# --- End Coqui TTS Initialization ---


# --- Text-To-Speech (TTS) Functions ---

def speak_text(text_to_speak):
    """
    Generates speech using Coqui TTS and plays it using afplay.
    Runs synthesis and playback in a separate thread.
    Requires 'pip install TTS' and 'afplay' (macOS).
    """
    if not text_to_speak:
        print("TTS Handler: No text provided to speak.")
        return
    if tts_engine is None:
        print("TTS Handler Error: TTS engine not initialized. Cannot speak.")
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
        print("TTS Handler Error: Internal thread found TTS engine not initialized.")
        return # Should not happen if speak_text checks, but good practice

    temp_filename = None
    try:
        # Create a temporary file to store the WAV output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_f:
            temp_filename = temp_f.name

        # Synthesize speech to the temporary file
        print(f"TTS Handler: Synthesizing '{text[:30]}...' using Coqui TTS...")
        start_time = time.time()
        # Use the initialized tts_engine
        tts_engine.tts_to_file(text=text, file_path=temp_filename)
        end_time = time.time()
        print(f"TTS Handler: Synthesis complete ({end_time - start_time:.2f}s). Playing audio...")

        # Play the generated WAV file using afplay
        try:
            # Use subprocess.run for cleaner execution and error handling
            process = subprocess.run(['afplay', temp_filename],
                                     check=True, # Raise CalledProcessError on failure
                                     capture_output=True, # Capture stdout/stderr
                                     timeout=60) # Add a timeout
            # print(f"TTS Handler: afplay finished for '{text[:20]}...'. Output: {process.stdout.decode()}") # Optional stdout log
            print(f"TTS Handler: afplay finished for '{text[:20]}...'.")
        except FileNotFoundError:
             print("TTS Handler Error: 'afplay' command not found. Please ensure it's installed (macOS).")
        except subprocess.CalledProcessError as cpe:
             # Use stderr for potentially more informative errors from afplay
             error_message = cpe.stderr.decode().strip() if cpe.stderr else f"Return code {cpe.returncode}"
             print(f"TTS Handler Error: 'afplay' failed: {error_message}")
        except subprocess.TimeoutExpired:
             print(f"TTS Handler Error: 'afplay' timed out playing audio for '{text[:20]}...'.")
        except Exception as play_err:
             print(f"TTS Handler Error: Unexpected error during afplay: {play_err}")

    except Exception as synth_err:
        # Catch potential errors during TTS synthesis
        print(f"TTS Handler Error (Coqui): Failed to synthesize audio: {synth_err}")
    finally:
        # Clean up the temporary file
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                # print(f"TTS Handler: Deleted temp file {temp_filename}")
            except Exception as del_err:
                print(f"TTS Handler Warning: Failed to delete temp file {temp_filename}: {del_err}")

# --- End TTS Functions ---