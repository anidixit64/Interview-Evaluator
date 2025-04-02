# core/tts_openai.py
# Implements TTS using OpenAI's API, batched by sentence/length for lower perceived latency.
# Combines sentences into batches meeting a minimum length before API calls.
# REQUIRES: sounddevice, pydub, numpy, nltk, and ffmpeg (with mp3 support) installed system-wide.

import threading
import time
import io
import numpy
import queue

# --- NLTK Import for Sentence Splitting ---
try:
    import nltk
    # Ensure 'punkt' tokenizer is available
    try:
        nltk.data.find('tokenizers/punkt')
    except (LookupError, nltk.downloader.DownloadError):
         print("TTS_OpenAI INFO: NLTK 'punkt' model not found. Attempting download...")
         try:
            nltk.download('punkt', quiet=True) # Download silently if possible
            nltk.data.find('tokenizers/punkt') # Verify download
            print("TTS_OpenAI INFO: NLTK 'punkt' model downloaded successfully.")
         except Exception as download_err:
             print(f"TTS_OpenAI ERROR: Failed to download NLTK 'punkt' model: {download_err}")
             print("                 Sentence splitting will likely fail. Please run 'python -m nltk.downloader punkt' manually.")
             nltk = None # Disable NLTK features
    _nltk_available = nltk is not None
except ImportError:
    print("TTS_OpenAI Error: nltk library not found. Run: pip install nltk")
    print("                Sentence splitting for reduced latency is disabled.")
    nltk = None
    _nltk_available = False


# --- OpenAI Import ---
try:
    from openai import OpenAI, APIError, APITimeoutError, RateLimitError, AuthenticationError
    _openai_lib_imported = True
except ImportError:
    print("TTS_OpenAI: openai library not found. Run: pip install openai")
    OpenAI = None
    APIError = APITimeoutError = RateLimitError = AuthenticationError = Exception # Placeholder
    _openai_lib_imported = False

# --- Playback/Decoding Imports ---
try:
    import sounddevice as sd
    _sounddevice_available = True
    print("TTS_OpenAI: sounddevice loaded.")
except ImportError:
    print("TTS_OpenAI Error: sounddevice library not found. Run: pip install sounddevice")
    sd = None
    _sounddevice_available = False
except Exception as sd_err:
     print(f"TTS_OpenAI Error: Failed to import/init sounddevice: {sd_err}")
     sd = None
     _sounddevice_available = False

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    _pydub_available = True
    print("TTS_OpenAI: pydub loaded.")
    import shutil
    if not shutil.which("ffmpeg") and not shutil.which("avconv"):
         print("TTS_OpenAI WARNING: ffmpeg or libav not found in PATH. pydub decoding will likely fail.")
         print("                 Install ffmpeg (e.g., 'brew install ffmpeg' or download from ffmpeg.org).")
    else:
         print("TTS_OpenAI: Found ffmpeg/avconv.")

except ImportError:
    print("TTS_OpenAI Error: pydub library not found. Run: pip install pydub")
    AudioSegment = None
    CouldntDecodeError = Exception # Placeholder
    _pydub_available = False

# --- Keyring Import ---
try:
    import keyring
    _keyring_available = True
except ImportError:
    print("TTS_OpenAI: keyring library not found. Run: pip install keyring")
    keyring = None
    _keyring_available = False

# --- Static check for basic dependencies ---
dependencies_met = (
    _openai_lib_imported
    and _sounddevice_available
    and _pydub_available
    and _keyring_available
    # NLTK is optional for the core functionality but required for sentence batching
)
# Feature flag based on NLTK availability
sentence_batching_enabled = _nltk_available

# --- Configuration ---
DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"
RESPONSE_FORMAT = "mp3" # MP3 is generally reliable for decoding
EXPECTED_SAMPLE_RATE = 24000
EXPECTED_CHANNELS = 1 # Mono
EXPECTED_DTYPE = 'int16'

# --- Minimum characters per batch sent to API ---
# Adjust this value as needed. Shorter sentences will be combined until this length is met.
MIN_BATCH_LENGTH_CHARS = 60 # Example value

KEYRING_SERVICE_NAME_OPENAI = "InterviewBotPro_OpenAI"
KEYRING_USERNAME_OPENAI = "openai_api_key"

# --- State ---
_openai_client = None
_client_initialized = False
_api_key_checked = False
is_available = False # Tracks successful initialization and deps

_playback_thread = None
_sentence_thread = None # Thread to manage sentence fetching/decoding
_playback_queue = queue.Queue(maxsize=50) # Queue holds numpy arrays (decoded audio)
_stop_event = threading.Event() # Single event to signal stop to all threads

# --- Initialization ---
def initialize_client():
    """Initializes the OpenAI client using the API key from keyring."""
    global _openai_client, _client_initialized, _api_key_checked, is_available
    if _client_initialized:
        return True
    if not dependencies_met: # Core dependencies check
        print("TTS_OpenAI: Core dependencies not met.")
        is_available = False
        return False
    if _api_key_checked: # Avoid repeatedly trying keychain if it failed once
        return _client_initialized
    _api_key_checked = True # Mark that we are attempting key check now

    api_key = None
    try:
        print(f"TTS_OpenAI: Retrieving API key (Service: '{KEYRING_SERVICE_NAME_OPENAI}')...")
        api_key = keyring.get_password(KEYRING_SERVICE_NAME_OPENAI, KEYRING_USERNAME_OPENAI)
        if not api_key:
            print("TTS_OpenAI Error: OpenAI API key not found in keyring.")
            is_available = False
            return False
        print("TTS_OpenAI: OpenAI API key retrieved.")
    except Exception as e:
        print(f"TTS_OpenAI Error: Keychain/keyring access failed: {e}")
        is_available = False
        return False

    try:
        print("TTS_OpenAI: Initializing OpenAI client...")
        _openai_client = OpenAI(api_key=api_key)
        # Perform a simple test call (optional but recommended)
        # Example: list models, or a very short TTS call
        # _openai_client.models.list() # Example test
        _client_initialized = True
        is_available = True # Mark as available *after* successful init
        print("TTS_OpenAI: Client initialized successfully.")
        # Report if sentence batching is available
        if sentence_batching_enabled:
             print("TTS_OpenAI: NLTK found, sentence batching enabled.")
        else:
             print("TTS_OpenAI: NLTK not found or 'punkt' model missing, sentence batching disabled (will process full text).")
        return True
    except AuthenticationError:
        print(f"TTS_OpenAI Error: Client init failed - AuthenticationError (Invalid API Key?).")
        is_available = False # Ensure availability reflects failure
        _client_initialized = False
        return False
    except APIError as e:
        print(f"TTS_OpenAI Error: Client init failed - APIError: {e}")
        is_available = False
        _client_initialized = False
        return False
    except Exception as e:
        print(f"TTS_OpenAI Error: Client init failed unexpectedly: {e}")
        _openai_client = None
        is_available = False
        _client_initialized = False
        return False


# --- Playback Worker ---
def _playback_worker():
    """Worker thread to play raw audio chunks (numpy arrays) from the queue."""
    stream = None
    stream_started = False
    # Use slightly smaller buffer than before, as we queue decoded data
    block_duration_ms = 150
    blocksize = int(EXPECTED_SAMPLE_RATE * block_duration_ms / 1000)
    samplerate = EXPECTED_SAMPLE_RATE
    channels = EXPECTED_CHANNELS
    dtype = EXPECTED_DTYPE

    print(f"Playback thread: Starting... Config: {samplerate}Hz, {channels}ch, {dtype}, Blocksize: {blocksize} ({block_duration_ms}ms)")

    try:
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            blocksize=blocksize
        )
        stream.start()
        stream_started = True
        print("Playback thread: sounddevice OutputStream started.")

        while not _stop_event.is_set():
            try:
                # Get data (numpy array) from queue
                pcm_chunk = _playback_queue.get(timeout=0.1) # Timeout allows checking stop event

                if pcm_chunk is None: # Sentinel value indicates end of all sentences
                    print("Playback thread: Received None (end signal).")
                    break # Exit loop

                if pcm_chunk.size > 0:
                    stream.write(pcm_chunk)
                    # print(f"Playback thread: Wrote sentence chunk of size {pcm_chunk.shape}") # Debug
                else:
                     print("Playback thread: Warning - received empty sentence chunk.")

                _playback_queue.task_done()

            except queue.Empty:
                # Queue empty, just loop again to check stop event or wait for data
                continue
            except sd.PortAudioError as pae:
                 # Handle potential stream errors during write (e.g., device unplugged)
                 print(f"Playback thread: PortAudioError writing to stream: {pae}")
                 _stop_event.set() # Signal other threads to stop
                 _playback_queue.task_done()
                 break # Exit loop
            except Exception as e:
                print(f"Playback thread: Error writing to stream: {e}")
                _playback_queue.task_done() # Mark done even on error
                # Consider breaking if error is severe

        print("Playback thread: Playback loop finished.")
        # Wait briefly for any buffered data to play out ONLY if stream is still valid
        if stream_started and not stream.stopped and not _stop_event.is_set():
            time.sleep(block_duration_ms / 1000.0 + 0.05)

    except sd.PortAudioError as pae:
         print(f"Playback thread: sounddevice PortAudioError during init/start: {pae}")
         _stop_event.set() # Signal stop if stream init fails
    except Exception as e:
        print(f"Playback thread: Error initializing or running stream: {e}")
        _stop_event.set() # Signal stop on unexpected error
        # import traceback
        # traceback.print_exc()
    finally:
        if stream is not None and stream_started:
            try:
                if not stream.stopped:
                    stream.abort(ignore_errors=True) # Use abort for quicker stop
                stream.close(ignore_errors=True)
                print("Playback thread: Closed sounddevice OutputStream.")
            except Exception as close_e:
                print(f"Playback thread: Error closing stream: {close_e}")
        print("Playback thread: Exiting.")

# --- Batch Synthesis ---
def _synthesize_batch(batch_text, voice, model):
    """Synthesizes a text batch (one or more sentences) and returns the decoded numpy array."""
    if not batch_text or not _openai_client or not _client_initialized:
        print("TTS_OpenAI Synth Batch Error: Client not ready or no text.")
        return None

    # Ensure text is clean before sending
    clean_batch_text = batch_text.strip()
    if not clean_batch_text:
        return None

    try:
        # print(f"Synth Batch: Requesting '{clean_batch_text[:50]}...'") # Debug
        response = _openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=clean_batch_text,
            response_format=RESPONSE_FORMAT
        )
        audio_bytes = response.content

        # Decode using pydub
        audio_stream = io.BytesIO(audio_bytes)
        segment = AudioSegment.from_file(audio_stream, format=RESPONSE_FORMAT)

        # Ensure correct audio format
        if segment.frame_rate != EXPECTED_SAMPLE_RATE: segment = segment.set_frame_rate(EXPECTED_SAMPLE_RATE)
        if segment.channels != EXPECTED_CHANNELS: segment = segment.set_channels(EXPECTED_CHANNELS)
        if segment.sample_width != numpy.dtype(EXPECTED_DTYPE).itemsize: segment = segment.set_sample_width(numpy.dtype(EXPECTED_DTYPE).itemsize)

        # Convert to numpy array
        samples = numpy.array(segment.get_array_of_samples()).astype(EXPECTED_DTYPE)
        # print(f"Synth Batch: Decoded '{clean_batch_text[:50]}...' ({len(samples)} samples)") # Debug
        return samples

    except CouldntDecodeError as decode_err:
        print(f"TTS_OpenAI Synth Batch Error: Failed to decode ({RESPONSE_FORMAT}): {decode_err} for batch: '{clean_batch_text[:60]}...'")
        return None
    except RateLimitError:
         print(f"TTS_OpenAI Synth Batch Error: OpenAI API Rate limit exceeded.")
         _stop_event.set() # Signal stop if rate limited
         return None
    except AuthenticationError:
         print(f"TTS_OpenAI Synth Batch Error: OpenAI API AuthenticationError (API Key Issue?).")
         _stop_event.set() # Signal stop on auth error
         return None
    except (APIError, APITimeoutError) as api_err:
         print(f"TTS_OpenAI Synth Batch Error: OpenAI API Error: {type(api_err).__name__}: {api_err}")
         # Don't necessarily stop on transient errors, just fail this batch
         return None
    except Exception as e:
        print(f"TTS_OpenAI Synth Batch Error: Unexpected error synthesizing batch '{clean_batch_text[:60]}...': {type(e).__name__}: {e}")
        # import traceback
        # traceback.print_exc()
        return None


# --- Sentence Batching Worker ---
def _sentence_batch_worker(full_text, voice, model):
    """
    Worker thread: Splits text, combines short sentences into batches,
    synthesizes each batch sequentially, and puts the resulting numpy arrays
    onto the playback queue.
    """
    global _playback_queue
    first_batch_queued = False
    start_time = time.time()
    sentence_batches = [] # This will hold the final text chunks to send to the API

    if sentence_batching_enabled and nltk:
        try:
            sentences = nltk.sent_tokenize(full_text)
            # print(f"Sentence Worker: Split into {len(sentences)} initial sentences.") # Debug

            # --- Combine short sentences into batches ---
            current_batch = ""
            for sentence in sentences:
                cleaned_sentence = sentence.strip()
                if not cleaned_sentence:
                    continue

                # Add sentence to current batch (with space if needed)
                if current_batch:
                    current_batch += " " + cleaned_sentence
                else:
                    current_batch = cleaned_sentence

                # If batch reaches minimum length, finalize it
                if len(current_batch) >= MIN_BATCH_LENGTH_CHARS:
                    sentence_batches.append(current_batch)
                    current_batch = "" # Reset for next batch

            # Add any remaining text in current_batch (handles the end of the text)
            if current_batch:
                sentence_batches.append(current_batch)
            # --- End of batch combination ---

            if not sentence_batches: # Handle cases where input was only whitespace
                 print("Sentence Worker: No valid text found after cleaning sentences.")
                 sentence_batches = [] # Prevent fallback from running

            # print(f"Sentence Worker: Combined into {len(sentence_batches)} batches (Min length: {MIN_BATCH_LENGTH_CHARS} chars).") # Debug

        except Exception as e:
            print(f"Sentence Worker: Error during NLTK processing or batching: {e}. Falling back to full text.")
            sentence_batches = [full_text.strip()] # Fallback: treat whole text as one batch
    else:
        # print("Sentence Worker: NLTK/batching disabled. Processing full text as one batch.") # Debug
        sentence_batches = [full_text.strip()] # Process the whole text if no NLTK

    # Filter out any empty batches that might have slipped through
    sentence_batches = [batch for batch in sentence_batches if batch]

    if not sentence_batches:
         print("Sentence Worker: No text batches to process.")
         # Signal end immediately if no batches
         try: _playback_queue.put(None, block=False)
         except queue.Full: pass
         print("Sentence Worker: Exiting early.")
         return

    total_batches = len(sentence_batches)
    processed_count = 0

    # --- Process the finalized batches ---
    for i, batch in enumerate(sentence_batches):
        if _stop_event.is_set():
            print("Sentence Worker: Stop event detected. Halting batch processing.")
            break

        # print(f"Sentence Worker: Processing batch {i+1}/{total_batches}...") # Debug
        pcm_data = _synthesize_batch(batch, voice, model) # Use the batch synthesis function

        if _stop_event.is_set():
            print("Sentence Worker: Stop event detected after synthesis call. Halting.")
            break

        if pcm_data is not None and pcm_data.size > 0:
            try:
                # Wait if queue is full, but check stop event periodically
                while not _stop_event.is_set():
                    try:
                        _playback_queue.put(pcm_data, timeout=0.2) # Put with timeout
                        processed_count += 1
                        if not first_batch_queued:
                            first_batch_latency = time.time() - start_time
                            print(f"Sentence Worker: First batch queued (Latency: {first_batch_latency:.2f}s)")
                            first_batch_queued = True
                        break # Exit inner loop once successfully put
                    except queue.Full:
                        # Queue is full, wait briefly and check stop event
                        # print("Sentence Worker: Playback queue full, waiting...") # Debug
                        time.sleep(0.1)
                        continue # Go back to check stop event and try putting again

                if _stop_event.is_set(): # Check if stop happened while waiting for queue
                     print("Sentence Worker: Stop event detected while waiting for queue.")
                     break

            except Exception as q_err:
                 print(f"Sentence Worker: Error putting data onto queue: {q_err}")
                 _stop_event.set() # Signal stop on queue error
                 break
        elif pcm_data is None:
             print(f"Sentence Worker: Failed to get audio for batch {i+1}. Skipping.")
             # Consider stopping if synthesis repeatedly fails:
             # _stop_event.set()
             # break

    # Signal end of playback ONLY if stop wasn't requested
    if not _stop_event.is_set():
        print(f"Sentence Worker: Finished processing {processed_count}/{total_batches} batches.")
        try:
            _playback_queue.put(None, timeout=1.0) # Signal end
        except queue.Full:
             print("Sentence Worker: Queue full when trying to signal end.")
             # Ensure stop is signaled if we can't put the end marker
             if not _stop_event.is_set():
                  _stop_event.set()
    else:
         # If stop was requested, still try to put None non-blockingly to end playback sooner
         try: _playback_queue.put(None, block=False)
         except queue.Full: pass # Ignore if full, stop event should handle it

    print("Sentence Worker: Exiting.")


# --- Thread Management ---
def _start_threads(text_to_speak, voice, model):
    """Starts the playback and sentence processing threads."""
    global _playback_thread, _sentence_thread

    if not is_available or not _openai_client or not _client_initialized:
        print("TTS_OpenAI Error: Cannot start threads, client not ready.")
        return False

    # Clear the stop event for the new operation
    _stop_event.clear()

    # Ensure previous threads are fully stopped and resources released
    # Calling stop_playback here might be redundant if called before, but ensures cleanup
    # stop_playback() # Optional: uncomment if extra safety needed

    # Clear the queue before starting new threads
    while not _playback_queue.empty():
        try: _playback_queue.get_nowait()
        except queue.Empty: break
    print("TTS_OpenAI: Cleared playback queue.")


    # Start playback worker
    _playback_thread = threading.Thread(target=_playback_worker, daemon=True)
    _playback_thread.start()
    time.sleep(0.05) # Very brief pause to allow thread startup
    if not _playback_thread.is_alive():
        print("TTS_OpenAI Error: Playback thread failed to start.")
        _stop_event.set() # Ensure stop is signaled
        return False

    # Start sentence processing worker
    _sentence_thread = threading.Thread(
        target=_sentence_batch_worker,
        args=(text_to_speak, voice, model),
        daemon=True
    )
    _sentence_thread.start()
    time.sleep(0.05) # Very brief pause
    if not _sentence_thread.is_alive():
        print("TTS_OpenAI Error: Sentence processing thread failed to start.")
        # Stop playback thread if sentence thread failed
        _stop_event.set()
        try: _playback_queue.put(None, block=False) # Try to signal playback thread end
        except queue.Full: pass
        if _playback_thread.is_alive():
            _playback_thread.join(timeout=0.5) # Short join timeout
        return False

    print("TTS_OpenAI: Playback and Sentence Processing threads started.")
    return True

def stop_playback():
    """Stops ongoing TTS playback and sentence processing."""
    global _playback_thread, _sentence_thread

    if not _stop_event.is_set():
        print("TTS_OpenAI: Signaling stop...")
        _stop_event.set()
    else:
        # Avoid spamming logs if called multiple times
        pass

    # Try to wake up playback thread if it's waiting on queue get()
    try:
        _playback_queue.put(None, block=False) # Non-blocking put of end signal
    except queue.Full:
        # If queue is full, thread might be blocked on put() or already processing.
        # Stop event should still cause it to exit.
        pass

    # Wait for threads to finish, capturing current thread references
    current_sentence_thread = _sentence_thread
    if current_sentence_thread and current_sentence_thread.is_alive():
        # print("TTS_OpenAI: Waiting for sentence thread to stop...") # Debug
        current_sentence_thread.join(timeout=1.0) # Reduced timeout
        if current_sentence_thread.is_alive():
            print("TTS_OpenAI: Warning - Sentence thread join timed out.")

    current_playback_thread = _playback_thread
    if current_playback_thread and current_playback_thread.is_alive():
        # print("TTS_OpenAI: Waiting for playback thread to stop...") # Debug
        current_playback_thread.join(timeout=1.0) # Reduced timeout
        if current_playback_thread.is_alive():
             print("TTS_OpenAI: Warning - Playback thread join timed out.")

    # Clear thread references only if they are the ones we waited for
    # This prevents issues if a new thread started before join completed
    if _sentence_thread == current_sentence_thread:
        _sentence_thread = None
    if _playback_thread == current_playback_thread:
        _playback_thread = None

    # Clear the queue after threads have likely stopped
    # print("TTS_OpenAI: Clearing playback queue...") # Debug
    while not _playback_queue.empty():
        try:
            _playback_queue.get_nowait()
            _playback_queue.task_done()
        except queue.Empty:
            break
    # print("TTS_OpenAI: Stop complete.") # Debug


# --- Main `speak_text` function ---
def speak_text(text_to_speak, voice=DEFAULT_VOICE, model=DEFAULT_MODEL, **kwargs):
    """
    Public function: Speaks text using OpenAI TTS, batched by sentence/length.
    Stops previous playback before starting new. Returns immediately.
    """

    # --- Initial Checks ---
    # Try initializing here if not already done
    if not _client_initialized:
        print("TTS_OpenAI: First use, attempting initialization...")
        if not initialize_client():
            print("TTS_OpenAI Error: Initialization failed. Cannot speak.")
            return

    # Check availability *after* attempting init
    if not is_available:
        print("TTS_OpenAI Error: Not available (check dependencies/API key). Cannot speak.")
        return

    if not text_to_speak:
        print("TTS_OpenAI: No text provided.")
        return
    if not sd:
        print("TTS_OpenAI Error: sounddevice not available for playback.")
        return
    if not AudioSegment:
        print("TTS_OpenAI Error: pydub not available for decoding.")
        return
    # Check NLTK only if batching is supposed to be enabled
    if sentence_batching_enabled and not _nltk_available:
         print("TTS_OpenAI Warning: NLTK library imported but unusable (maybe 'punkt' missing?). Sentence batching disabled.")
         # Potentially force sentence_batching_enabled = False here if needed

    # --- Stop Previous Activity ---
    # print("TTS_OpenAI: Stopping previous activity (if any)...") # Debug
    stop_playback() # Use the function to handle stopping/cleanup

    # --- Start New Playback ---
    print("TTS_OpenAI: Starting new sentence-batched playback...")

    if not _start_threads(text_to_speak, voice, model):
         print("TTS_OpenAI Error: Failed to start processing threads.")
         # Ensure stop is signaled and cleanup attempted if threads failed
         if not _stop_event.is_set():
             _stop_event.set()
             stop_playback() # Attempt cleanup again
         return

    # print("TTS_OpenAI: speak_text call complete (processing runs in background).") # Debug


# --- Example Usage (if run directly) ---
if __name__ == '__main__':
    print("--- TTS_OpenAI Self-Test ---")
    print(f"Dependencies Met: {dependencies_met}")
    print(f"NLTK Available: {_nltk_available}")
    print(f"Sentence Batching Enabled: {sentence_batching_enabled}")
    print(f"Min Batch Length Chars: {MIN_BATCH_LENGTH_CHARS}")
    print("-" * 30)

    if not dependencies_met:
        print("Missing core dependencies. Cannot run test. Exiting.")
        exit(1)

    # Explicitly initialize for testing
    if initialize_client():
        print("\n--- Test 1: Multi-sentence text ---")
        try:
            # Test text with short sentences
            test_text = "Hello there. This is a test using OpenAI's text-to-speech API. Short sentences are batched together. This sentence is deliberately made a bit longer to ensure it likely forms its own batch for processing. What happens next? Another short one. The end."
            print(f"\nSpeaking text (Batching Enabled: {sentence_batching_enabled}):\n{test_text}\n")
            speak_text(test_text, voice="nova")

            # Keep main thread alive to hear the playback
            print("\n[ Main thread waiting for playback... Press Ctrl+C to stop test ]")
            # Wait until playback thread finishes (or gets stopped)
            test_playback_thread = _playback_thread # Capture current thread
            while test_playback_thread and test_playback_thread.is_alive():
                 time.sleep(0.5)
            print("\n[ Playback finished or stopped ]")
            time.sleep(1) # Pause between tests

        except KeyboardInterrupt:
             print("\n[ Ctrl+C detected, stopping test... ]")
             stop_playback()
        except Exception as e:
            print(f"An error occurred during Test 1: {e}")
            # import traceback
            # traceback.print_exc()
            stop_playback()

        print("\n--- Test 2: Stop Functionality ---")
        try:
            test_text_long = "This is a longer test, designed specifically to check the stop functionality. It includes multiple sentences, which allows the synthesis and playback process to take a noticeable amount of time. We will begin the speech synthesis now, and after waiting for just a few seconds, the stop command will be issued programmatically. We need to observe if the audio output ceases promptly as expected. This final part of the text should ideally not be heard if the stop command works correctly and interrupts the ongoing process effectively."
            print(f"\nSpeaking long text:\n{test_text_long}\n")
            speak_text(test_text_long, voice="alloy")
            print("[ Waiting 4 seconds before calling stop_playback()... ]")
            time.sleep(4)
            print("[ Calling stop_playback()... ]")
            stop_playback()
            print("[ Stop command issued. Waiting 2 seconds... ]")
            time.sleep(2)
            print("[ Test 2 finished ]")

        except KeyboardInterrupt:
             print("\n[ Ctrl+C detected, stopping test... ]")
             stop_playback()
        except Exception as e:
            print(f"An error occurred during Test 2: {e}")
            stop_playback()

        print("\n--- Self-Test Complete ---")

    else:
        print("\nFailed to initialize OpenAI client. Cannot run tests.")
        print("Please ensure:")
        print("  - Dependencies are installed (openai, sounddevice, pydub, numpy, nltk, keyring)")
        print("  - FFmpeg/libav is installed and in PATH.")
        print(f"  - OpenAI API key is stored in keyring (Service: '{KEYRING_SERVICE_NAME_OPENAI}', User: '{KEYRING_USERNAME_OPENAI}')")