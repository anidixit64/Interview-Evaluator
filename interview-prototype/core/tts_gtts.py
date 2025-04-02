# core/tts_gtts.py
# Implements TTS using gTTS (Google Text-to-Speech).
# Based on the gTTS conversion provided earlier.

import threading
import time
import os
import tempfile
import io
import sys # Added for platform check

# --- gTTS and Playback Imports ---
try:
    from gtts import gTTS
    _gtts_lib_imported = True # NEW STATIC FLAG
except ImportError:
    print("TTS_GTTS: gTTS library not found. Run: pip install gTTS")
    gTTS = None
    _gtts_lib_imported = False # NEW STATIC FLAG

try:
    from playsound import playsound
    _playsound_available = True
    if sys.platform == 'darwin':
        try: import AppKit
        except ImportError: pass
except ImportError:
    playsound = None
    _playsound_available = False
except Exception as e:
    print(f"TTS_GTTS: Error importing playsound: {e}")
    playsound = None
    _playsound_available = False

# --- NEW: Static check for basic dependencies ---
dependencies_met = _gtts_lib_imported and _playsound_available

# --- is_available still tracks runtime readiness (always true if deps met) ---
is_available = dependencies_met

# --- Configuration ---
DEFAULT_TTS_LANGUAGE = 'en'

# --- Implementation ---
_speech_thread = None
_stop_requested = threading.Event() # ADDED: Event to signal stop

# --- _gtts_speak_worker and speak_text remain the same ---
def _gtts_speak_worker(text_to_speak, lang):
    # ... (original minimal code adapted for stop) ...
    if not is_available: print("TTS_GTTS Worker Error: gTTS or playsound library not available."); return
    print(f"TTS_GTTS Worker: Synthesizing '{text_to_speak[:60]}...' (lang={lang})")
    start_time = time.time(); temp_audio_file = None
    try:
        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before synthesis."); return

        tts = gTTS(text=text_to_speak, lang=lang)
        # Use BytesIO to avoid filesystem issues if possible, fallback to temp file
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        generation_time = time.time()
        print(f"TTS_GTTS Worker: Generated audio in memory in {generation_time - start_time:.2f}s")

        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before playback."); return

        # Write to temp file ONLY if needed by playsound (some backends might need file paths)
        # Note: playsound *can* often handle file-like objects, but it's less consistent.
        # Using a temp file is safer across platforms/backends.
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
             temp_audio_file = fp.name
             fp.write(mp3_fp.read())
             fp.flush()
             os.fsync(fp.fileno()) # Ensure data is written

        mp3_fp.close() # Close the BytesIO object

        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before playback (file created)."); return

        if temp_audio_file:
             print(f"TTS_GTTS Worker: Playing audio from {temp_audio_file}...");
             playsound(temp_audio_file) # playsound is blocking, can't easily interrupt it directly
             playback_time = time.time()
             print(f"TTS_GTTS Worker: Finished playback. Total time: {playback_time - start_time:.2f}s")

    except Exception as e:
         # Avoid printing during shutdown if stop was requested
         if not _stop_requested.is_set():
             print(f"TTS_GTTS Worker: Error during synthesis or playback: {type(e).__name__}: {e}");
             # import traceback; traceback.print_exc() # Uncomment for more detail
    finally:
        if temp_audio_file and os.path.exists(temp_audio_file):
            try: os.remove(temp_audio_file)
            except Exception as clean_e: print(f"TTS_GTTS Worker: Error cleaning up temp file {temp_audio_file}: {clean_e}")
        print("TTS_GTTS Worker: Thread finished.")


def speak_text(text_to_speak, lang=DEFAULT_TTS_LANGUAGE, **kwargs):
    # ... (original minimal code adapted for stop) ...
    global _speech_thread
    if not is_available: print("TTS_GTTS Error: Not available. Cannot speak."); return
    if not text_to_speak: print("TTS_GTTS: No text provided."); return

    # Stop previous thread if running
    stop_playback() # Use the new stop function

    print("TTS_GTTS: Starting new speech request.")
    _stop_requested.clear() # Clear stop flag for new request
    _speech_thread = threading.Thread(target=_gtts_speak_worker, args=(text_to_speak, lang), daemon=True);
    _speech_thread.start()

# --- ADDED: Stop Function ---
def stop_playback():
    """Signals the gTTS playback worker to stop (best effort)."""
    global _speech_thread
    if _speech_thread and _speech_thread.is_alive():
        print("TTS_GTTS: Signaling stop request...")
        _stop_requested.set()
        # Note: playsound itself might not be interruptible once started.
        # We wait briefly for the thread to potentially check the flag before/after playsound.
        _speech_thread.join(timeout=0.5) # Wait briefly
        if _speech_thread.is_alive():
            print("TTS_GTTS: Warning - Worker thread still alive after stop signal (playback might continue).")
        else:
            print("TTS_GTTS: Worker thread stopped.")
    _speech_thread = None # Clear reference