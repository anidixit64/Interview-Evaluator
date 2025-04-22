# core/tts_openai.py
import threading
import time
import io
import numpy as np
import queue
import sys
import os

try:
    import nltk
    _nltk_available = True
    try:
        _is_bundled = hasattr(sys, '_MEIPASS')
        try:
            nltk.data.find('tokenizers/punkt')
        except (LookupError, nltk.downloader.DownloadError):
            if not _is_bundled:
                try:
                    nltk.download('punkt', quiet=True)
                    nltk.data.find('tokenizers/punkt')
                except Exception:
                    _nltk_available = False
            else:
                _nltk_available = False
    except Exception:
        _nltk_available = False
except ImportError:
    nltk = None
    _nltk_available = False

try:
    from openai import OpenAI, APIError, APITimeoutError, RateLimitError, AuthenticationError
    _openai_lib_imported = True
except ImportError:
    OpenAI = None
    APIError = APITimeoutError = RateLimitError = AuthenticationError = Exception
    _openai_lib_imported = False

try:
    import sounddevice as sd
    _sounddevice_available = True
except ImportError:
    sd = None
    _sounddevice_available = False
except Exception:
    sd = None
    _sounddevice_available = False

try:
    import soundfile as sf
    _soundfile_available = True
except ImportError:
    sf = None
    _soundfile_available = False
except Exception:
    sf = None
    _soundfile_available = False

try:
    import keyring
    _keyring_available = True
except ImportError:
    keyring = None
    _keyring_available = False

dependencies_met = (
    _openai_lib_imported
    and _sounddevice_available
    and _soundfile_available
    and _keyring_available
)

sentence_batching_enabled = _nltk_available and dependencies_met

DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"
RESPONSE_FORMAT = "mp3"
EXPECTED_SAMPLE_RATE = 24000
EXPECTED_CHANNELS = 1
EXPECTED_DTYPE = 'float32'
MIN_BATCH_LENGTH_CHARS = 60
KEYRING_SERVICE_NAME_OPENAI = "InterviewBotPro_OpenAI"
KEYRING_USERNAME_OPENAI = "openai_api_key"

_openai_client = None
_client_initialized = False
_api_key_checked = False
is_available = False
_playback_thread = None
_sentence_thread = None
_playback_queue = queue.Queue(maxsize=50)
_stop_event = threading.Event()

def initialize_client():
    global _openai_client, _client_initialized, _api_key_checked, is_available
    if _client_initialized:
        return True
    if not dependencies_met:
        is_available = False
        return False
    if _api_key_checked:
        return _client_initialized
    _api_key_checked = True
    api_key = None
    try:
        api_key = keyring.get_password(KEYRING_SERVICE_NAME_OPENAI, KEYRING_USERNAME_OPENAI)
        if not api_key:
            is_available = False
            return False
    except Exception:
        is_available = False
        return False
    try:
        _openai_client = OpenAI(api_key=api_key)
        _client_initialized = True
        is_available = True
        return True
    except AuthenticationError:
        is_available = False
        _client_initialized = False
        return False
    except APIError:
        is_available = False
        _client_initialized = False
        return False
    except Exception:
        _openai_client = None
        is_available = False
        _client_initialized = False
        return False

def _playback_worker():
    stream = None
    stream_started = False
    block_duration_ms = 150
    blocksize = int(EXPECTED_SAMPLE_RATE * block_duration_ms / 1000)
    samplerate = EXPECTED_SAMPLE_RATE
    channels = EXPECTED_CHANNELS
    dtype = EXPECTED_DTYPE
    try:
        if not sd:
            raise RuntimeError("sounddevice library is not available.")
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            blocksize=blocksize
        )
        stream.start()
        stream_started = True
        while not _stop_event.is_set():
            try:
                pcm_chunk = _playback_queue.get(timeout=0.2)
                if pcm_chunk is None:
                    break
                if isinstance(pcm_chunk, np.ndarray) and pcm_chunk.size > 0:
                    try:
                        stream.write(pcm_chunk)
                    except sd.PortAudioError:
                        _stop_event.set()
                        break
                    except Exception:
                        _stop_event.set()
                        break
                _playback_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                try:
                    _playback_queue.task_done()
                except ValueError:
                    pass
        if stream_started and not stream.stopped and not _stop_event.is_set():
            time.sleep(block_duration_ms / 1000.0 + 0.1)
    except sd.PortAudioError:
        _stop_event.set()
    except Exception:
        _stop_event.set()
    finally:
        if stream is not None and stream_started:
            try:
                if not stream.stopped:
                    stream.abort(ignore_errors=True)
                stream.close(ignore_errors=True)
            except Exception:
                pass

def _synthesize_batch(batch_text, voice, model):
    if not batch_text or not _openai_client or not _client_initialized:
        return None
    if not sf:
        return None
    clean_batch_text = batch_text.strip()
    if not clean_batch_text:
        return None
    pcm_data = None
    try:
        response = _openai_client.audio.speech.create(
            model=model, voice=voice, input=clean_batch_text, response_format=RESPONSE_FORMAT
        )
        audio_bytes = response.content
        if not audio_bytes:
            return None
        audio_stream = io.BytesIO(audio_bytes)
        try:
            data, samplerate = sf.read(audio_stream, dtype=None, always_2d=False)
        except sf.SoundFileError:
            return None
        except Exception:
            return None
        if samplerate != EXPECTED_SAMPLE_RATE:
            return None
        current_channels = 1 if data.ndim == 1 else data.shape[1]
        if current_channels != EXPECTED_CHANNELS:
            if EXPECTED_CHANNELS == 1 and current_channels > 1:
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                data = data.mean(axis=1)
            else:
                return None
        if data.dtype != np.dtype(EXPECTED_DTYPE):
            try:
                if np.issubdtype(data.dtype, np.floating) and EXPECTED_DTYPE == 'float32':
                    data = data.astype(np.float32)
                elif np.issubdtype(data.dtype, np.integer) and EXPECTED_DTYPE == 'float32':
                    max_val = np.iinfo(data.dtype).max
                    data = data.astype(np.float32) / max_val
                elif np.issubdtype(data.dtype, np.floating) and EXPECTED_DTYPE == 'int16':
                    data = np.clip(data, -1.0, 1.0)
                    max_val = np.iinfo(np.int16).max
                    data = (data * max_val).astype(np.int16)
                else:
                    data = data.astype(EXPECTED_DTYPE)
            except Exception:
                return None
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        pcm_data = data
    except RateLimitError:
        _stop_event.set()
        pcm_data = None
    except AuthenticationError:
        _stop_event.set()
        pcm_data = None
    except (APIError, APITimeoutError):
        pcm_data = None
    except Exception:
        pcm_data = None
    return pcm_data

def _sentence_batch_worker(full_text, voice, model):
    global _playback_queue
    first_batch_queued = False
    start_time = time.time()
    sentence_batches = []
    use_nltk = sentence_batching_enabled and _nltk_available and nltk
    if use_nltk:
        try:
            sentences = nltk.sent_tokenize(full_text)
            current_batch = ""
            for idx, sentence in enumerate(sentences):
                cleaned_sentence = sentence.strip()
                if not cleaned_sentence:
                    continue
                next_chunk = (" " + cleaned_sentence) if current_batch else cleaned_sentence
                if len(current_batch) + len(next_chunk) <= MIN_BATCH_LENGTH_CHARS or not current_batch:
                    current_batch += next_chunk
                else:
                    if len(current_batch) >= MIN_BATCH_LENGTH_CHARS:
                        sentence_batches.append(current_batch)
                        current_batch = cleaned_sentence
                    else:
                        current_batch += next_chunk
                if idx == len(sentences) - 1 and current_batch:
                    sentence_batches.append(current_batch)
                    current_batch = ""
        except Exception:
            sentence_batches = [full_text.strip()]
    else:
        full_text_stripped = full_text.strip()
        if full_text_stripped:
            sentence_batches = [full_text_stripped]
    sentence_batches = [batch for batch in sentence_batches if batch]
    if not sentence_batches:
        try:
            _playback_queue.put(None, block=False)
        except queue.Full:
            pass
        return
    total_batches = len(sentence_batches)
    processed_count = 0
    for i, batch in enumerate(sentence_batches):
        if _stop_event.is_set():
            break
        pcm_data = _synthesize_batch(batch, voice, model)
        if _stop_event.is_set():
            break
        if pcm_data is not None and pcm_data.size > 0:
            try:
                put_start_time = time.time()
                while not _stop_event.is_set():
                    try:
                        _playback_queue.put(pcm_data, timeout=0.2)
                        processed_count += 1
                        if not first_batch_queued:
                            first_batch_queued = True
                        break
                    except queue.Full:
                        if time.time() - put_start_time > 5.0:
                            _stop_event.set()
                            break
                        time.sleep(0.1)
                        continue
                if _stop_event.is_set():
                    break
            except Exception:
                _stop_event.set()
                break
        elif pcm_data is None and not _stop_event.is_set():
            continue
    if not _stop_event.is_set():
        try:
            _playback_queue.put(None, timeout=1.0)
        except queue.Full:
            if not _stop_event.is_set():
                _stop_event.set()
    else:
        try:
            _playback_queue.put(None, block=False)
        except queue.Full:
            pass

def _start_threads(text_to_speak, voice, model):
    global _playback_thread, _sentence_thread
    if not is_available or not _openai_client or not _client_initialized:
        return False
    _stop_event.clear()
    while not _playback_queue.empty():
        try:
            item = _playback_queue.get_nowait()
            _playback_queue.task_done()
            del item
        except queue.Empty:
            break
        except ValueError:
            pass
        except Exception:
            pass
    _playback_thread = threading.Thread(target=_playback_worker, daemon=True)
    _playback_thread.start()
    time.sleep(0.05)
    if not _playback_thread.is_alive():
        _stop_event.set()
        return False
    _sentence_thread = threading.Thread(
        target=_sentence_batch_worker,
        args=(text_to_speak, voice, model),
        daemon=True
    )
    _sentence_thread.start()
    time.sleep(0.05)
    if not _sentence_thread.is_alive():
        _stop_event.set()
        try:
            _playback_queue.put(None, block=False)
        except queue.Full:
            pass
        if _playback_thread.is_alive():
            _playback_thread.join(timeout=0.5)
        return False
    return True

def stop_playback():
    global _playback_thread, _sentence_thread
    if not _stop_event.is_set():
        _stop_event.set()
    try:
        _playback_queue.put(None, block=False, timeout=0.1)
    except queue.Full:
        pass
    current_sentence_thread = _sentence_thread
    if current_sentence_thread and current_sentence_thread.is_alive():
        current_sentence_thread.join(timeout=0.5)
    current_playback_thread = _playback_thread
    if current_playback_thread and current_playback_thread.is_alive():
        current_playback_thread.join(timeout=0.5)
    if _sentence_thread == current_sentence_thread:
        _sentence_thread = None
    if _playback_thread == current_playback_thread:
        _playback_thread = None
    cleared_count = 0
    while not _playback_queue.empty():
        try:
            item = _playback_queue.get_nowait()
            _playback_queue.task_done()
            del item
            cleared_count += 1
        except queue.Empty:
            break
        except ValueError:
            pass
        except Exception:
            break

def speak_text(text_to_speak, voice=DEFAULT_VOICE, model=DEFAULT_MODEL, **kwargs):
    if not _client_initialized:
        if not initialize_client():
            return
    if not is_available:
        return
    if not text_to_speak:
        return
    if sentence_batching_enabled and not _nltk_available:
        pass
    stop_playback()
    if not _start_threads(text_to_speak, voice, model):
        stop_playback()
        return