# core/tts_openai.py
# Implements TTS using OpenAI's API, batched by sentence/length for lower perceived latency.
# Combines sentences into batches meeting a minimum length before API calls.
# USES: soundfile for decoding (removes ffmpeg dependency).
# REQUIRES: sounddevice, soundfile, numpy, nltk, openai, keyring.
# Ensure required non-Python libraries for soundfile (like libsndfile with mp3 support) are available if needed.

import threading
import time
import io
import numpy as np # Explicit numpy import
import queue
import sys
import os # Ensure os is imported
# Removed shutil import as ffmpeg path finding is removed

# --- NLTK Import for Sentence Splitting ---
try:
    import nltk
    _nltk_available = True # Assume available initially
    # --- MODIFIED NLTK data check/download ---
    try:
        # Check if running bundled first
        _is_bundled = hasattr(sys, '_MEIPASS')

        try:
             # Always try finding first, works if already downloaded or bundled correctly
             nltk.data.find('tokenizers/punkt')
             print("TTS_OpenAI INFO: NLTK 'punkt' model found.")
        except (LookupError, nltk.downloader.DownloadError):
             # Only attempt download if NOT bundled
             if not _is_bundled:
                 print("TTS_OpenAI INFO: NLTK 'punkt' model not found. Attempting download...")
                 try:
                    nltk.download('punkt', quiet=True) # Download silently if possible
                    nltk.data.find('tokenizers/punkt') # Verify download
                    print("TTS_OpenAI INFO: NLTK 'punkt' model downloaded successfully.")
                 except Exception as download_err:
                     print(f"TTS_OpenAI ERROR: Failed to download NLTK 'punkt' model: {download_err}")
                     print("                 Sentence splitting will likely fail. Please run 'python -m nltk.downloader punkt' manually.")
                     _nltk_available = False # Mark as unavailable if download fails
             else:
                 # Is bundled but data not found where expected
                 print("TTS_OpenAI ERROR: Running bundled, but NLTK 'punkt' model not found.")
                 print("                 Ensure 'nltk_data' was correctly included by PyInstaller (e.g., using --collect-data nltk_data).")
                 _nltk_available = False # Mark as unavailable

    except Exception as e:
         # Catch errors during the find/download process itself
         print(f"TTS_OpenAI ERROR: Unexpected error during NLTK 'punkt' setup: {e}")
         _nltk_available = False
    # --- END MODIFIED ---

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

# --- Playback/Decoding Imports (Using sounddevice and soundfile) ---
try:
    import sounddevice as sd
    _sounddevice_available = True
    print(f"TTS_OpenAI: sounddevice loaded. Default output device: {sd.query_devices(kind='output')}") # Log default device
except ImportError:
    print("TTS_OpenAI Error: sounddevice library not found. Run: pip install sounddevice")
    sd = None
    _sounddevice_available = False
except Exception as sd_err:
     print(f"TTS_OpenAI Error: Failed to import/init sounddevice: {sd_err}")
     sd = None
     _sounddevice_available = False

try:
    import soundfile as sf
    _soundfile_available = True
    print("TTS_OpenAI: soundfile loaded for audio decoding.")
    # Optional: Log available formats if debugging codec issues
    # try:
    #     print(f"TTS_OpenAI: soundfile available formats: {sf.available_formats()}")
    # except Exception: pass # Ignore errors during format listing
except ImportError:
    print("TTS_OpenAI Error: soundfile library not found. Run: pip install soundfile")
    sf = None
    _soundfile_available = False
except Exception as sf_err: # Catch other potential errors during import
    print(f"TTS_OpenAI Error: Failed to import/init soundfile: {sf_err}")
    sf = None
    _soundfile_available = False

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
    and _soundfile_available   # <--- Use soundfile flag
    and _keyring_available
    # NLTK is optional for the core functionality but required for sentence batching
)
# Feature flag based on NLTK availability
sentence_batching_enabled = _nltk_available and dependencies_met # Also depend on core deps

# --- Configuration ---
DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"
RESPONSE_FORMAT = "mp3" # OpenAI supports: mp3, opus, aac, flac. Ensure soundfile/libsndfile supports it.
EXPECTED_SAMPLE_RATE = 24000 # OpenAI TTS standard rate
EXPECTED_CHANNELS = 1       # OpenAI TTS is mono
EXPECTED_DTYPE = 'float32'  # sounddevice often prefers float32, soundfile reads to float easily.
                            # Keep consistent with _playback_worker stream dtype.

# --- Minimum characters per batch sent to API ---
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
    if not dependencies_met: # Core dependencies check (uses updated flags)
        print("TTS_OpenAI: Core dependencies not met (check openai, sounddevice, soundfile, keyring).")
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
        # Optional: Test call (consider cost/rate limits)
        # try: _openai_client.models.list()
        # except Exception as test_err: print(f"TTS_OpenAI Warning: API test call failed: {test_err}")

        _client_initialized = True
        is_available = True # Mark as available *after* successful init
        print("TTS_OpenAI: Client initialized successfully.")
        if sentence_batching_enabled:
             print("TTS_OpenAI: NLTK available, sentence batching enabled.")
        else:
             print("TTS_OpenAI: NLTK unavailable or disabled, sentence batching disabled.")
        return True
    except AuthenticationError:
        print(f"TTS_OpenAI Error: Client init failed - AuthenticationError (Invalid API Key?).")
        is_available = False
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
    block_duration_ms = 150
    blocksize = int(EXPECTED_SAMPLE_RATE * block_duration_ms / 1000)
    samplerate = EXPECTED_SAMPLE_RATE
    channels = EXPECTED_CHANNELS
    dtype = EXPECTED_DTYPE # Uses the global config (e.g., 'float32')

    print(f"Playback thread: Starting...") # Log start

    try:
        if not sd:
             raise RuntimeError("sounddevice library is not available.")
        print(f"Playback thread: Attempting to open OutputStream (Samplerate: {samplerate}, Channels: {channels}, Dtype: {dtype}, Blocksize: {blocksize})")
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype, # Ensure this matches EXPECTED_DTYPE
            blocksize=blocksize
        )
        print("Playback thread: OutputStream object created.")
        stream.start()
        stream_started = True
        print("Playback thread: OutputStream started successfully.")

        while not _stop_event.is_set():
            try:
                # Get data (numpy array) from queue
                # print("Playback thread: Waiting for item from queue...") # Less verbose log
                pcm_chunk = _playback_queue.get(timeout=0.2) # Shorter timeout ok
                # print("Playback thread: Got item from queue.") # Less verbose log

                if pcm_chunk is None: # Sentinel value indicates end of all sentences
                    print("Playback thread: Received None (end signal). Exiting loop.")
                    break # Exit loop

                if isinstance(pcm_chunk, np.ndarray) and pcm_chunk.size > 0:
                    # print(f"Playback thread: Writing chunk shape {pcm_chunk.shape}, dtype {pcm_chunk.dtype}") # Less verbose
                    try:
                        stream.write(pcm_chunk)
                        # print("Playback thread: Write successful.") # Less verbose
                    except sd.PortAudioError as pae_write:
                        print(f"Playback thread ERROR writing to stream: {pae_write}")
                        _stop_event.set() # Stop processing on write error
                        break
                    except Exception as write_err:
                         print(f"Playback thread UNEXPECTED ERROR writing to stream: {write_err}")
                         _stop_event.set()
                         break
                elif pcm_chunk is not None: # Log if we got something weird
                     print(f"Playback thread: Warning - received unexpected non-empty item of type {type(pcm_chunk)}. Skipping.")

                _playback_queue.task_done()

            except queue.Empty:
                # Queue empty, just loop again to check stop event or wait for data
                continue
            except Exception as e:
                print(f"Playback thread: Error during queue get or task_done: {e}")
                try: _playback_queue.task_done() # Try to mark done anyway
                except ValueError: pass # Ignore if already done

        print("Playback thread: Playback loop finished.")
        if stream_started and not stream.stopped and not _stop_event.is_set():
            print("Playback thread: Waiting for buffer to clear...")
            time.sleep(block_duration_ms / 1000.0 + 0.1) # Wait for stream to finish

    except sd.PortAudioError as pae:
         print(f"Playback thread ERROR initializing/starting stream: {pae}")
         _stop_event.set() # Signal stop if stream init fails
    except Exception as e:
        print(f"Playback thread UNEXPECTED ERROR initializing or running stream: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors
        _stop_event.set() # Signal stop on unexpected error
    finally:
        if stream is not None and stream_started:
            print("Playback thread: Attempting to stop and close stream...")
            try:
                if not stream.stopped:
                    stream.abort(ignore_errors=True) # Use abort for quicker stop
                    print("Playback thread: Stream aborted.")
                stream.close(ignore_errors=True)
                print("Playback thread: Stream closed.")
            except Exception as close_e:
                print(f"Playback thread: Error closing stream: {close_e}")
        else:
            print("Playback thread: Stream was not started or already None.")
        print("Playback thread: Exiting finally block.")


# --- Batch Synthesis (Using soundfile) ---
def _synthesize_batch(batch_text, voice, model):
    """Synthesizes a text batch and returns the decoded numpy array."""
    print(f"Synth Batch: Processing text: '{batch_text[:60]}...'") # Log entry
    if not batch_text or not _openai_client or not _client_initialized:
        print("Synth Batch ERROR: Client not ready or no text.")
        return None
    if not sf: # Check soundfile dependency
        print("Synth Batch ERROR: soundfile library not available for decoding.")
        return None

    clean_batch_text = batch_text.strip()
    if not clean_batch_text: return None

    pcm_data = None
    try:
        print("Synth Batch: Requesting speech from OpenAI API...")
        response = _openai_client.audio.speech.create(
            model=model, voice=voice, input=clean_batch_text, response_format=RESPONSE_FORMAT
        )
        audio_bytes = response.content
        print(f"Synth Batch: Received {len(audio_bytes)} bytes from API.")

        if not audio_bytes:
            print("Synth Batch ERROR: Received empty audio data from API.")
            return None

        # --- Use soundfile for decoding ---
        print(f"Synth Batch: Decoding audio data using soundfile (expected format: {RESPONSE_FORMAT})...")
        audio_stream = io.BytesIO(audio_bytes)
        try:
            # Read directly into a NumPy array. dtype=None lets soundfile choose.
            # always_2d=False aims for 1D array for mono (matching OpenAI)
            data, samplerate = sf.read(audio_stream, dtype=None, always_2d=False)
            print(f"Synth Batch: Decoded successfully. Samplerate: {samplerate}, Shape: {data.shape}, Dtype: {data.dtype}")

        except sf.SoundFileError as sfe:
            # This often means the format isn't supported by libsndfile (e.g., MP3 codec missing)
            print(f"Synth Batch ERROR: soundfile could not decode audio: {sfe}")
            print(f"                 Ensure libsndfile used by soundfile supports '{RESPONSE_FORMAT}'.")
            # Consider logging sf.available_formats() here when debugging codec issues
            # print(f"DEBUG: soundfile available formats: {sf.available_formats()}")
            return None
        except Exception as decode_err:
             print(f"Synth Batch ERROR: Unexpected error during soundfile decoding: {decode_err}")
             import traceback
             traceback.print_exc()
             return None
        # --- End soundfile decoding ---


        # --- Ensure correct audio format for sounddevice ---
        # 1. Check Sample Rate
        if samplerate != EXPECTED_SAMPLE_RATE:
             # This is critical. Resampling is needed if they don't match.
             print(f"Synth Batch ERROR: Sample rate mismatch! Decoded: {samplerate}, Expected: {EXPECTED_SAMPLE_RATE}.")
             print("                 Resampling not implemented. Cannot proceed.")
             # If you NEED resampling, add `scipy` or `librosa` dependency and code here.
             # Example (requires scipy):
             # from scipy.signal import resample
             # num_samples = int(len(data) * EXPECTED_SAMPLE_RATE / samplerate)
             # data = resample(data, num_samples)
             # samplerate = EXPECTED_SAMPLE_RATE # Update samplerate after resampling
             # print(f"Synth Batch: Resampled to {samplerate} Hz. New shape: {data.shape}")
             return None # Fail if rates don't match and no resampling

        # 2. Check Channels
        current_channels = 1 if data.ndim == 1 else data.shape[1]
        if current_channels != EXPECTED_CHANNELS:
             print(f"Synth Batch WARNING: Channel mismatch! Decoded: {current_channels}, Expected: {EXPECTED_CHANNELS}.")
             if EXPECTED_CHANNELS == 1 and current_channels > 1:
                 print("Synth Batch: Converting to mono by averaging channels.")
                 # Ensure data is 2D for mean calculation if needed (shouldn't be if always_2d=False worked)
                 if data.ndim == 1: data = data.reshape(-1, 1) # Should not happen with >1 channels
                 data = data.mean(axis=1) # Average across channels
                 print(f"Synth Batch: Converted to mono. New shape: {data.shape}")
             else:
                 # Add other conversions if necessary (e.g., mono to stereo by duplicating channel)
                 print(f"Synth Batch ERROR: Cannot handle channel conversion from {current_channels} to {EXPECTED_CHANNELS}.")
                 return None

        # 3. Check and Convert Data Type (dtype)
        if data.dtype != np.dtype(EXPECTED_DTYPE): # Compare actual numpy dtypes
            print(f"Synth Batch: Converting dtype from {data.dtype} to {EXPECTED_DTYPE}")
            try:
                # Common case: soundfile reads float64, we want float32
                if np.issubdtype(data.dtype, np.floating) and EXPECTED_DTYPE == 'float32':
                    data = data.astype(np.float32)
                # Case: soundfile reads int16, we want float32
                elif np.issubdtype(data.dtype, np.integer) and EXPECTED_DTYPE == 'float32':
                    max_val = np.iinfo(data.dtype).max
                    data = data.astype(np.float32) / max_val
                # Case: soundfile reads float, we want int16 (less common need with sounddevice)
                elif np.issubdtype(data.dtype, np.floating) and EXPECTED_DTYPE == 'int16':
                    data = np.clip(data, -1.0, 1.0) # Clip to avoid wrap-around
                    max_val = np.iinfo(np.int16).max
                    data = (data * max_val).astype(np.int16)
                # Add other specific conversions if needed
                else:
                    print(f"Synth Batch WARNING: Attempting direct dtype cast from {data.dtype} to {EXPECTED_DTYPE}. Might be lossy/incorrect scale.")
                    data = data.astype(EXPECTED_DTYPE)
            except Exception as cast_err:
                print(f"Synth Batch ERROR: Failed to convert dtype: {cast_err}")
                return None
        # --- End Format Conversion ---

        # Ensure the final array is contiguous for sounddevice (sometimes needed after manipulations)
        if not data.flags['C_CONTIGUOUS']:
            print("Synth Batch: Making array C-contiguous.")
            data = np.ascontiguousarray(data)

        pcm_data = data # Assign final processed data
        print(f"Synth Batch: Final numpy array. Shape: {pcm_data.shape}, Dtype: {pcm_data.dtype}")

    except RateLimitError:
         print(f"Synth Batch ERROR: OpenAI API Rate limit exceeded.")
         _stop_event.set(); pcm_data = None
    except AuthenticationError:
         print(f"Synth Batch ERROR: OpenAI API AuthenticationError (API Key Issue?).")
         _stop_event.set(); pcm_data = None
    except (APIError, APITimeoutError) as api_err:
         print(f"Synth Batch ERROR: OpenAI API Error: {type(api_err).__name__}: {api_err}"); pcm_data = None
    except Exception as e:
        print(f"Synth Batch UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc() # Print full traceback
        pcm_data = None

    print(f"Synth Batch: Finished processing. Returning {'data' if pcm_data is not None else 'None'}.")
    return pcm_data


# --- Sentence Batching Worker ---
def _sentence_batch_worker(full_text, voice, model):
    """Splits text, batches, synthesizes, and queues audio chunks."""
    global _playback_queue
    print("Sentence Worker: Starting.") # Log entry
    first_batch_queued = False
    start_time = time.time()
    sentence_batches = []

    # Only use NLTK if it's available AND sentence batching is enabled
    use_nltk = sentence_batching_enabled and _nltk_available and nltk

    if use_nltk:
        try:
            print("Sentence Worker: Tokenizing sentences using NLTK...")
            sentences = nltk.sent_tokenize(full_text)
            print(f"Sentence Worker: Found {len(sentences)} sentences.")
            current_batch = ""
            for idx, sentence in enumerate(sentences):
                cleaned_sentence = sentence.strip()
                if not cleaned_sentence: continue
                next_chunk = (" " + cleaned_sentence) if current_batch else cleaned_sentence
                if len(current_batch) + len(next_chunk) <= MIN_BATCH_LENGTH_CHARS or not current_batch:
                    current_batch += next_chunk
                else:
                    # Add current batch if it meets criteria, then start new one
                    if len(current_batch) >= MIN_BATCH_LENGTH_CHARS:
                       sentence_batches.append(current_batch)
                       print(f"Sentence Worker: Created batch {len(sentence_batches)}: '{current_batch[:60]}...' (Len: {len(current_batch)})")
                       current_batch = cleaned_sentence # Start new batch with current sentence
                    else: # Current batch too short, append sentence anyway
                         current_batch += next_chunk

                # Always add the last batch regardless of length
                if idx == len(sentences) - 1 and current_batch:
                    sentence_batches.append(current_batch)
                    print(f"Sentence Worker: Created final batch {len(sentence_batches)}: '{current_batch[:60]}...' (Len: {len(current_batch)})")
                    current_batch = "" # Clear just in case

        except Exception as e:
            print(f"Sentence Worker: Error during NLTK processing/batching: {e}. Falling back.")
            sentence_batches = [full_text.strip()] # Fallback
    else:
        print("Sentence Worker: NLTK/batching disabled or unavailable. Using full text.")
        full_text_stripped = full_text.strip()
        if full_text_stripped: # Avoid adding empty string
             sentence_batches = [full_text_stripped]

    sentence_batches = [batch for batch in sentence_batches if batch] # Clean empty batches

    if not sentence_batches:
         print("Sentence Worker: No text batches to process.")
         try: _playback_queue.put(None, block=False) # Signal end immediately
         except queue.Full: pass
         print("Sentence Worker: Exiting early.")
         return

    total_batches = len(sentence_batches)
    print(f"Sentence Worker: Processing {total_batches} batches...")
    processed_count = 0

    for i, batch in enumerate(sentence_batches):
        if _stop_event.is_set(): print(f"Sentence Worker: Stop event detected before processing batch {i+1}. Halting."); break
        print(f"Sentence Worker: Synthesizing batch {i+1}/{total_batches}...")
        pcm_data = _synthesize_batch(batch, voice, model)

        if _stop_event.is_set(): print(f"Sentence Worker: Stop event detected after synthesizing batch {i+1}. Halting."); break

        if pcm_data is not None and pcm_data.size > 0:
            print(f"Sentence Worker: Batch {i+1} synthesized ({pcm_data.size} samples). Attempting to queue...")
            try:
                put_start_time = time.time()
                while not _stop_event.is_set():
                    try:
                         _playback_queue.put(pcm_data, timeout=0.2) # Put with timeout
                         print(f"Sentence Worker: Batch {i+1} queued successfully.")
                         processed_count += 1
                         if not first_batch_queued:
                             first_batch_latency = time.time() - start_time
                             print(f"Sentence Worker: First batch queued (Latency: {first_batch_latency:.2f}s)")
                             first_batch_queued = True
                         break # Exit inner queue-wait loop once successfully put
                    except queue.Full:
                        # Queue is full, wait briefly and check stop event
                        if time.time() - put_start_time > 5.0: # Timeout waiting for queue
                             print("Sentence Worker ERROR: Timeout waiting for playback queue space.")
                             _stop_event.set()
                             break # Break inner loop on timeout
                        time.sleep(0.1)
                        continue # Go back to check stop event and try putting again

                if _stop_event.is_set(): print("Sentence Worker: Stop event detected while waiting for queue."); break # Exit outer batch loop

            except Exception as q_err:
                 print(f"Sentence Worker ERROR putting data onto queue: {q_err}")
                 _stop_event.set(); break # Exit outer batch loop
        elif pcm_data is None and not _stop_event.is_set(): # Only log failure if not stopping
             print(f"Sentence Worker: Failed to get audio for batch {i+1}. Skipping.")
             # Consider stopping if synthesis repeatedly fails? For now, continue.
             # _stop_event.set(); break

    # Signal end of playback ONLY if stop wasn't requested during processing
    if not _stop_event.is_set():
        print(f"Sentence Worker: Finished processing {processed_count}/{total_batches} batches. Signaling end...")
        try:
            _playback_queue.put(None, timeout=1.0) # Signal end
            print("Sentence Worker: End signal queued.")
        except queue.Full:
             print("Sentence Worker WARNING: Queue full when trying to signal end.")
             # Force stop if we can't even queue the end signal
             if not _stop_event.is_set():
                 print("Sentence Worker: Setting stop event due to inability to queue end signal.")
                 _stop_event.set()
    else:
         print("Sentence Worker: Stop was requested during processing. Attempting to queue end signal (non-blocking)...")
         try: _playback_queue.put(None, block=False)
         except queue.Full: pass # Ignore if full, stop event should handle it

    print("Sentence Worker: Exiting.")


# --- Thread Management ---
def _start_threads(text_to_speak, voice, model):
    """Starts the playback and sentence processing threads."""
    global _playback_thread, _sentence_thread

    if not is_available or not _openai_client or not _client_initialized:
        print("TTS_OpenAI Error: Cannot start threads, client not ready or unavailable.")
        return False

    _stop_event.clear() # Reset stop event for the new operation

    # Clear the queue before starting new threads
    print("TTS_OpenAI: Clearing playback queue before start...")
    while not _playback_queue.empty():
        try:
             item = _playback_queue.get_nowait()
             _playback_queue.task_done()
             del item # Help GC
        except queue.Empty: break
        except ValueError: pass # task_done called too many times
        except Exception as e: print(f"TTS_OpenAI: Error clearing queue: {e}")


    # Start playback worker
    print("TTS_OpenAI: Starting playback thread...")
    _playback_thread = threading.Thread(target=_playback_worker, daemon=True)
    _playback_thread.start()
    time.sleep(0.05) # Brief pause to allow thread startup
    if not _playback_thread.is_alive():
        print("TTS_OpenAI Error: Playback thread failed to start.")
        _stop_event.set() # Ensure stop is signaled
        return False

    # Start sentence processing worker
    print("TTS_OpenAI: Starting sentence processing thread...")
    _sentence_thread = threading.Thread(
        target=_sentence_batch_worker,
        args=(text_to_speak, voice, model),
        daemon=True
    )
    _sentence_thread.start()
    time.sleep(0.05) # Brief pause
    if not _sentence_thread.is_alive():
        print("TTS_OpenAI Error: Sentence processing thread failed to start.")
        # Stop playback thread if sentence thread failed
        _stop_event.set()
        try: _playback_queue.put(None, block=False) # Try to signal playback thread end
        except queue.Full: pass
        if _playback_thread.is_alive():
            _playback_thread.join(timeout=0.5) # Short join timeout
        return False

    print("TTS_OpenAI: Playback and Sentence Processing threads started successfully.")
    return True

def stop_playback():
    """Stops ongoing TTS playback and sentence processing."""
    global _playback_thread, _sentence_thread

    if not _stop_event.is_set():
        print("TTS_OpenAI: Signaling stop event...")
        _stop_event.set()
    # else: # Avoid spamming logs if called multiple times
    #     pass

    # Try to wake up playback thread if it's waiting on queue get()
    # print("TTS_OpenAI: Attempting to queue None to potentially stop playback worker...")
    try:
        _playback_queue.put(None, block=False, timeout=0.1) # Non-blocking put of end signal with small timeout
    except queue.Full:
        # print("TTS_OpenAI: Playback queue full while trying to send stop signal.")
        pass # Ignore if full, stop event should handle it
    except Exception as qe:
        print(f"TTS_OpenAI: Error queueing stop signal: {qe}")


    # Wait for threads to finish, capturing current thread references
    current_sentence_thread = _sentence_thread
    if current_sentence_thread and current_sentence_thread.is_alive():
        # print("TTS_OpenAI: Waiting for sentence thread to stop...")
        current_sentence_thread.join(timeout=0.5) # Shorter timeout OK
        if current_sentence_thread.is_alive():
            print("TTS_OpenAI: Warning - Sentence thread join timed out.")
        # else: print("TTS_OpenAI: Sentence thread stopped.")

    current_playback_thread = _playback_thread
    if current_playback_thread and current_playback_thread.is_alive():
        # print("TTS_OpenAI: Waiting for playback thread to stop...")
        current_playback_thread.join(timeout=0.5) # Shorter timeout OK
        if current_playback_thread.is_alive():
             print("TTS_OpenAI: Warning - Playback thread join timed out.")
        # else: print("TTS_OpenAI: Playback thread stopped.")

    # Clear thread references only if they are the ones we waited for
    if _sentence_thread == current_sentence_thread: _sentence_thread = None
    if _playback_thread == current_playback_thread: _playback_thread = None

    # Clear the queue after threads have likely stopped or timed out
    # print("TTS_OpenAI: Clearing playback queue after stop...")
    cleared_count = 0
    while not _playback_queue.empty():
        try:
            item = _playback_queue.get_nowait()
            _playback_queue.task_done()
            del item # Help GC
            cleared_count += 1
        except queue.Empty: break
        except ValueError: pass # task_done called too many times
        except Exception as e:
             print(f"TTS_OpenAI: Error clearing queue item during stop: {e}")
             break # Stop trying to clear if errors occur
    # print(f"TTS_OpenAI: Cleared {cleared_count} items from queue.")
    # print("TTS_OpenAI: Stop sequence complete.")


# --- Main `speak_text` function ---
def speak_text(text_to_speak, voice=DEFAULT_VOICE, model=DEFAULT_MODEL, **kwargs):
    """
    Public function: Speaks text using OpenAI TTS, batched by sentence/length.
    Uses soundfile for decoding. Stops previous playback before starting new.
    Returns immediately after starting threads.
    """

    print(f"TTS_OpenAI: speak_text called with text: '{text_to_speak[:60]}...'")
    # --- Initial Checks ---
    if not _client_initialized:
        print("TTS_OpenAI: First use, attempting initialization...")
        if not initialize_client():
            print("TTS_OpenAI Error: Initialization failed. Cannot speak.")
            return

    # Check availability *after* attempting init (covers dependencies & init status)
    if not is_available:
        print("TTS_OpenAI Error: Not available (check dependencies/API key/init status). Cannot speak.")
        return

    if not text_to_speak:
        print("TTS_OpenAI: No text provided.")
        return
    # sd and sf checks are covered by is_available check now

    # Check NLTK only if batching is supposed to be enabled
    if sentence_batching_enabled and not _nltk_available:
         print("TTS_OpenAI Warning: NLTK library imported but unusable. Sentence batching disabled.")

    # --- Stop Previous Activity ---
    # print("TTS_OpenAI: Stopping previous activity (if any)...") # Less verbose
    stop_playback() # Use the function to handle stopping/cleanup

    # --- Start New Playback ---
    print("TTS_OpenAI: Starting new sentence-batched playback...")

    if not _start_threads(text_to_speak, voice, model):
         print("TTS_OpenAI Error: Failed to start processing threads.")
         # Ensure stop is signaled and cleanup attempted if threads failed
         stop_playback() # Attempt cleanup again
         return

    print("TTS_OpenAI: speak_text call finished (processing runs in background).")