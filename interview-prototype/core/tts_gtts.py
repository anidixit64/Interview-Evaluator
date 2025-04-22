# core/tts_gtts.py
import threading
import time
import os
import tempfile
import io
import sys

try:
    from gtts import gTTS
    _gtts_lib_imported = True
except ImportError:
    print("TTS_GTTS: gTTS library not found. Run: pip install gTTS")
    gTTS = None
    _gtts_lib_imported = False

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

dependencies_met = _gtts_lib_imported and _playsound_available

is_available = dependencies_met

DEFAULT_TTS_LANGUAGE = 'en'

_speech_thread = None
_stop_requested = threading.Event()

def _gtts_speak_worker(text_to_speak, lang):
    if not is_available: print("TTS_GTTS Worker Error: gTTS or playsound library not available."); return
    print(f"TTS_GTTS Worker: Synthesizing '{text_to_speak[:60]}...' (lang={lang})")
    start_time = time.time(); temp_audio_file = None
    try:
        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before synthesis."); return

        tts = gTTS(text=text_to_speak, lang=lang)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        generation_time = time.time()
        print(f"TTS_GTTS Worker: Generated audio in memory in {generation_time - start_time:.2f}s")

        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before playback."); return

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
             temp_audio_file = fp.name
             fp.write(mp3_fp.read())
             fp.flush()
             os.fsync(fp.fileno())

        mp3_fp.close()

        if _stop_requested.is_set(): print("TTS_GTTS Worker: Stop requested before playback (file created)."); return

        if temp_audio_file:
             print(f"TTS_GTTS Worker: Playing audio from {temp_audio_file}...");
             playsound(temp_audio_file)
             playback_time = time.time()
             print(f"TTS_GTTS Worker: Finished playback. Total time: {playback_time - start_time:.2f}s")

    except Exception as e:
         if not _stop_requested.is_set():
             print(f"TTS_GTTS Worker: Error during synthesis or playback: {type(e).__name__}: {e}");
    finally:
        if temp_audio_file and os.path.exists(temp_audio_file):
            try: os.remove(temp_audio_file)
            except Exception as clean_e: print(f"TTS_GTTS Worker: Error cleaning up temp file {temp_audio_file}: {clean_e}")
        print("TTS_GTTS Worker: Thread finished.")

def speak_text(text_to_speak, lang=DEFAULT_TTS_LANGUAGE, **kwargs):
    global _speech_thread
    if not is_available: print("TTS_GTTS Error: Not available. Cannot speak."); return
    if not text_to_speak: print("TTS_GTTS: No text provided."); return

    stop_playback()

    print("TTS_GTTS: Starting new speech request.")
    _stop_requested.clear()
    _speech_thread = threading.Thread(target=_gtts_speak_worker, args=(text_to_speak, lang), daemon=True);
    _speech_thread.start()

def stop_playback():
    global _speech_thread
    if _speech_thread and _speech_thread.is_alive():
        print("TTS_GTTS: Signaling stop request...")
        _stop_requested.set()
        _speech_thread.join(timeout=0.5)
        if _speech_thread.is_alive():
            print("TTS_GTTS: Warning - Worker thread still alive after stop signal (playback might continue).")
        else:
            print("TTS_GTTS: Worker thread stopped.")
    _speech_thread = None