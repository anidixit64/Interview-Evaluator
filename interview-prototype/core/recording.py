# core/recording.py
# Handles audio (STT via SpeechRecognition) and video (OpenCV) recording.

# --- Imports ---
import threading
import time
import os
import speech_recognition as sr
import queue
import cv2
import parselmouth
from parselmouth.praat import call 
import numpy as np
import subprocess
from pathlib import Path # Use pathlib for robust path handling

# --- Configuration ---
# <<< MODIFIED: Point to a user-specific directory inside Documents >>>
_APP_NAME_FOR_DIRS = "InterviewBotPro" # Use a consistent name

# Get the user's Documents directory in a cross-platform way
try:
    # Modern Python approach using pathlib
    _DOCUMENTS_DIR = str(Path.home() / "Documents")
    if not os.path.isdir(_DOCUMENTS_DIR): # Fallback if "Documents" doesn't exist
        _DOCUMENTS_DIR = str(Path.home())
except Exception:
    # Older fallback if Path.home() fails for some reason
    _DOCUMENTS_DIR = os.path.expanduser("~/Documents")
    if not os.path.isdir(_DOCUMENTS_DIR):
        _DOCUMENTS_DIR = os.path.expanduser("~")


# Define the recordings directory inside Documents
RECORDINGS_DIR = os.path.join(_DOCUMENTS_DIR, _APP_NAME_FOR_DIRS, "recordings")

print(f"Recording Handler: Using recordings directory: {RECORDINGS_DIR}")

# -- Praat Configuration --
PRAAT_EXECUTABLE = "praat"
# Try to find the script relative to this file's directory or the executable's directory
# Common structures:
# 1. project/core/recording.py and project/scripts/extract_features.praat
# 2. Packaged app structure where script is bundled.
try:
    # 1. Get the absolute path of this Python file
    current_file = os.path.abspath(__file__)
    print(f"[DEBUG] Current file path: {current_file}")

    # 2. Go up one level to get project root
    project_root = os.path.dirname(os.path.dirname(current_file))
    print(f"[DEBUG] Project root determined as: {project_root}")

    # 3. Build full path to the Praat script
    PRAAT_SCRIPT_PATH = os.path.join(project_root, "scripts", "extract_features.praat")
    print(f"[DEBUG] Full path to Praat script: {PRAAT_SCRIPT_PATH}")

    # 4. Check if file exists at that path
    if not os.path.isfile(PRAAT_SCRIPT_PATH):
        print(f"[DEBUG] File does NOT exist at: {PRAAT_SCRIPT_PATH}")
        PRAAT_SCRIPT_PATH = None
    else:
        print(f"[DEBUG] File FOUND at: {PRAAT_SCRIPT_PATH}")

except Exception as e:
    PRAAT_SCRIPT_PATH = None
    print(f"Recording Handler (Praat) Warning: Error determining Praat script path: {e}. Feature extraction will be skipped.")

# 5. Final flag for enabling/disabling feature extraction
PRAAT_FEATURE_EXTRACTION_ENABLED = PRAAT_SCRIPT_PATH is not None
print(f"[DEBUG] Feature extraction enabled: {PRAAT_FEATURE_EXTRACTION_ENABLED}")
# --- END MODIFICATION ---

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
                    # if frame_count == 0: # Reduce log noise
                    #      print(f"Recording Handler (Video): First frame written to {filename}.")
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


def extract_features(audio_path):
    """
    Extracts acoustic features using the Parselmouth library (Praat wrapper).

    Args:
        audio_path (str): Path to the WAV audio file.

    Returns:
        dict: A dictionary containing the extracted features, or None if extraction fails.
              Keys match the praat script output names where possible.
    """
    print(f"Recording Handler (Parselmouth): Extracting features from '{os.path.basename(audio_path)}'...")
    features = {}
    try:
        snd = parselmouth.Sound(audio_path)
        duration = snd.get_total_duration()
        features['duration'] = duration

        if duration <= 0:
            print("Recording Handler (Parselmouth) Warning: Audio duration is zero or negative.")
            return None # Cannot process zero duration

        # --- Intensity ---
        try:
            intensity = snd.to_intensity(minimum_pitch=75.0) # Use a reasonable minimum pitch
            features['intensityMean'] = call(intensity, "Get mean", 0, 0, "energy") # dB or energy? Energy is more standard.
            # Calculate SD manually from values array for reliability
            intensity_values = intensity.values[0] # Get the numpy array of intensity values
            intensity_values_finite = intensity_values[np.isfinite(intensity_values)] # Filter out potential NaNs/Infs
            if len(intensity_values_finite) > 1:
                 features['intensitySD'] = np.std(intensity_values_finite, ddof=1)
            else:
                 features['intensitySD'] = 0.0
            features['intensityMin'] = call(intensity, "Get minimum", 0, 0, "Parabolic")
            features['intensityMax'] = call(intensity, "Get maximum", 0, 0, "Parabolic")
            # Quantiles might need manual numpy calculation if 'call' is problematic
            try:
                 features['intensityQuant5'] = np.percentile(intensity_values_finite, 5) if len(intensity_values_finite) > 0 else 0
                 features['intensityQuant95'] = np.percentile(intensity_values_finite, 95) if len(intensity_values_finite) > 0 else 0
                 features['intensityMedian'] = np.median(intensity_values_finite) if len(intensity_values_finite) > 0 else 0
            except IndexError: # Handle empty array after filtering
                 features['intensityQuant5'] = 0; features['intensityQuant95'] = 0; features['intensityMedian'] = 0

        except parselmouth.PraatError as e:
            print(f"Recording Handler (Parselmouth) Warning: Intensity analysis failed: {e}")
            # Assign default 0s
            features.update({k: 0 for k in ['intensityMean', 'intensitySD', 'intensityMin', 'intensityMax', 'intensityQuant5', 'intensityQuant95', 'intensityMedian']})


        # --- Pitch ---
        pitch = None
        mean_pitch = 0 # Initialize defaults needed later
        voiced_dur = 0
        unvoiced_dur = 0
        total_pitch_dur = 0
        try:
            print("--> Attempting snd.to_pitch...") # DEBUG
            pitch = snd.to_pitch(time_step=None, pitch_floor=75.0, pitch_ceiling=600.0)
            print(f"--> Pitch object created: {pitch}") # DEBUG

            # Get basic stats directly
            raw_mean_pitch = call(pitch, "Get mean", 0, 0, "Hertz")
            print(f"--> Raw result from call(pitch, 'Get mean', ...): {raw_mean_pitch} (Type: {type(raw_mean_pitch)})") # DEBUG
            mean_pitch = 0
            if raw_mean_pitch is not None and np.isfinite(raw_mean_pitch): mean_pitch = raw_mean_pitch

            # Update features dictionary *immediately* after calculation
            features['mean_pitch'] = mean_pitch
            # Get other basic stats and update features dict immediately if valid
            min_p = call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic"); features['min_pitch'] = min_p if min_p is not None and np.isfinite(min_p) else 0
            max_p = call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic"); features['max_pitch'] = max_p if max_p is not None and np.isfinite(max_p) else 0
            sd_p = call(pitch, "Get standard deviation", 0, 0, "Hertz"); features['pitch_sd'] = sd_p if sd_p is not None and np.isfinite(sd_p) else 0
            med_p = call(pitch, "Get quantile", 0, 0, 0.5, "Hertz"); features['pitchMedian'] = med_p if med_p is not None and np.isfinite(med_p) else 0
            q5_p = call(pitch, "Get quantile", 0, 0, 0.05, "Hertz"); features['pitchQuant5'] = q5_p if q5_p is not None and np.isfinite(q5_p) else 0
            q95_p = call(pitch, "Get quantile", 0, 0, 0.95, "Hertz"); features['pitchQuant95'] = q95_p if q95_p is not None and np.isfinite(q95_p) else 0

            if mean_pitch > 0:
                 features['meanPeriod'] = 1.0 / mean_pitch

                 num_frames = pitch.get_number_of_frames()
                 time_step_pitch = pitch.time_step
                 total_pitch_dur = 0
                 voiced_frames = 0
                 unvoiced_frames = 0
                 voiced_dur = 0
                 unvoiced_dur = 0

                 if num_frames > 0 and time_step_pitch > 0:
                     total_pitch_dur = num_frames * time_step_pitch
                     pitch_values = pitch.selected_array['frequency']
                     print(f"--> Pitch frequency values (first 20): {pitch_values[:20]}") # DEBUG
                     voiced_mask = (pitch_values > 0) & (~np.isnan(pitch_values))
                     voiced_frames = np.sum(voiced_mask)
                     unvoiced_frames = num_frames - voiced_frames
                     print(f"--> Voiced frames: {voiced_frames}, Unvoiced frames: {unvoiced_frames}") # DEBUG

                     voiced_dur = voiced_frames * time_step_pitch
                     unvoiced_dur = unvoiced_frames * time_step_pitch

                     features['percentUnvoiced'] = (unvoiced_dur / total_pitch_dur * 100) if total_pitch_dur > 0 else 100
                     features['pitchUvsVRatio'] = (unvoiced_dur / voiced_dur) if voiced_dur > 0 else -1
                 else:
                     print("--> Pitch object has 0 frames or 0 time step.") # DEBUG
                     features['percentUnvoiced'] = 100
                     features['pitchUvsVRatio'] = -1
                     voiced_dur = 0

                 # --- PointProcess, Jitter, Shimmer, Breaks (only if voiced frames exist) ---
                 if voiced_dur > 0:
                     print("--> Attempting PointProcess/Jitter/Shimmer/Breaks...") # DEBUG
                     try:
                         point_process = call([snd, pitch], "To PointProcess (periodic, cc)", 75.0, 600.0)
                         jit_loc = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
                         jit_rap = call(point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3)
                         shim_db = call(point_process, "Get shimmer (local, dB)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
                         n_breaks = call(pitch, "Count number of voice breaks", 0.02, 0.1, 0.02) # Use call for breaks

                         if jit_loc is not None and np.isfinite(jit_loc): features['jitterLocal'] = jit_loc
                         if jit_rap is not None and np.isfinite(jit_rap): features['jitterRap'] = jit_rap
                         if shim_db is not None and np.isfinite(shim_db): features['shimmerLocalDB'] = shim_db
                         if n_breaks is not None and np.isfinite(n_breaks): features['numVoiceBreaks'] = n_breaks
                         features['percentBreaks'] = (features['numVoiceBreaks'] / duration) if duration > 0 else 0
                         print("--> Jitter/Shimmer/Breaks successful.") # DEBUG
                     except parselmouth.PraatError as e_pp_breaks:
                          print(f"Recording Handler (Parselmouth) Info: Could not get PointProcess/jitter/shimmer/break stats: {e_pp_breaks}. Using defaults.")
                 else:
                     print("--> No voiced frames found. Skipping Jitter, Shimmer, Breaks.")

                 # --- Slope Features (only if voiced frames exist) ---
                 if voiced_dur > 0 and num_frames > 1 and time_step_pitch > 0:
                     print("--> Attempting Slope calculation...") # DEBUG
                     # ... (slope calculation logic as before) ...
                     # Make sure to update features dict here: features['numRising'] = numRising etc.
                     numRising = 0; numFall = 0
                     maxRisingSlope = 0.0; maxFallingSlope = 0.0
                     totalRisingSlope = 0.0; totalFallingSlope = 0.0
                     numRisingSlope = 0; numFallingSlope = 0
                     last_pitch_val = pitch_values[0] if pitch_values[0] > 0 else np.nan
                     for i in range(1, num_frames):
                         current_pitch_val = pitch_values[i] if pitch_values[i] > 0 else np.nan
                         if not np.isnan(last_pitch_val) and not np.isnan(current_pitch_val):
                            slope = (current_pitch_val - last_pitch_val) / time_step_pitch
                            if slope > 0:
                                prevSlope = 0; # ... (prevSlope logic) ...
                                if prevSlope <= 0: numRising += 1
                                totalRisingSlope += slope
                                numRisingSlope += 1
                                if slope > maxRisingSlope: maxRisingSlope = slope
                            elif slope < 0:
                                prevSlope = 0; # ... (prevSlope logic) ...
                                if prevSlope >= 0: numFall += 1
                                totalFallingSlope += slope
                                numFallingSlope += 1
                                if slope < maxFallingSlope: maxFallingSlope = slope
                         last_pitch_val = current_pitch_val
                     # --- UPDATE features dictionary ---
                     features['numRising'] = numRising
                     features['numFall'] = numFall
                     features['maxRisingSlope'] = maxRisingSlope
                     features['maxFallingSlope'] = maxFallingSlope
                     features['avgRisingSlope'] = (totalRisingSlope / numRisingSlope) if numRisingSlope > 0 else 0
                     features['avgFallingSlope'] = (totalFallingSlope / numFallingSlope) if numFallingSlope > 0 else 0
                     print("--> Slope calculation successful.") # DEBUG
                 else:
                     print("--> No voiced frames/insufficient frames found. Skipping Slope analysis.")

            elif mean_pitch == 0:
                 print("--> Mean pitch is 0. Detailed voicing/jitter/shimmer/slope analysis skipped.")


        except parselmouth.PraatError as e:
            print(f"Recording Handler (Parselmouth) Warning: Initial Pitch analysis failed: {e}")
            # This except block should now only catch failures in to_pitch or the basic Get commands
            # Defaults were already set at the beginning.


        # --- Formant Features ---
        formant = None
        avgVal1=0; avgVal2=0; avgVal3=0; f1STD=0; f2STD=0; f3STD=0; avgBand1=0; avgBand2=0; avgBand3=0
        try:
            formant = snd.to_formant_burg(time_step=0.01, max_number_of_formants=5.0, maximum_formant=5500.0, window_length=0.025, pre_emphasis_from=50.0)
            num_formant_frames = formant.get_number_of_frames()
            valid_frames = 0
            f1_sum=0; f2_sum=0; f3_sum=0; b1_sum=0; b2_sum=0; b3_sum=0
            f1_sq_sum=0; f2_sq_sum=0; f3_sq_sum=0

            # Get pitch values again if pitch object exists, for checking voicing
            pitch_values_for_formant = None
            if pitch:
                 # Ensure times align - may need interpolation if time steps differ
                 # For simplicity here, we'll just check the nearest pitch frame time
                 pitch_times = pitch.xs()
                 pitch_values_for_formant = pitch.selected_array['frequency']

            for i in range(num_formant_frames):
                formant_time = formant.get_time_from_frame_number(i + 1) # Frame numbers are 1-based
                is_voiced = True # Assume voiced if no pitch info

                if pitch_values_for_formant is not None:
                    # Find nearest pitch frame index
                    try:
                        pitch_frame_index = (np.abs(pitch_times - formant_time)).argmin()
                        pitch_val_check = pitch_values_for_formant[pitch_frame_index]
                        if pitch_val_check == 0 or np.isnan(pitch_val_check): # Check for Praat's 0 or numpy's NaN
                            is_voiced = False
                    except IndexError:
                        is_voiced = False # Error finding frame

                if is_voiced:
                    f1 = formant.get_value_at_time(formant_number=1, time=formant_time)
                    f2 = formant.get_value_at_time(formant_number=2, time=formant_time)
                    f3 = formant.get_value_at_time(formant_number=3, time=formant_time)
                    b1 = formant.get_bandwidth_at_time(formant_number=1, time=formant_time)
                    b2 = formant.get_bandwidth_at_time(formant_number=2, time=formant_time)
                    b3 = formant.get_bandwidth_at_time(formant_number=3, time=formant_time)

                    # Check if all formant values are valid numbers
                    formant_vals = [f1, f2, f3, b1, b2, b3]
                    if all(v is not None and np.isfinite(v) for v in formant_vals):
                        valid_frames += 1
                        f1_sum += f1; f2_sum += f2; f3_sum += f3
                        b1_sum += b1; b2_sum += b2; b3_sum += b3
                        f1_sq_sum += f1*f1; f2_sq_sum += f2*f2; f3_sq_sum += f3*f3

            if valid_frames > 0:
                avgVal1 = f1_sum / valid_frames; avgVal2 = f2_sum / valid_frames; avgVal3 = f3_sum / valid_frames
                avgBand1 = b1_sum / valid_frames; avgBand2 = b2_sum / valid_frames; avgBand3 = b3_sum / valid_frames
            if valid_frames > 1:
                f1Var = (f1_sq_sum / valid_frames) - (avgVal1**2); f1Var = max(0, f1Var)
                f2Var = (f2_sq_sum / valid_frames) - (avgVal2**2); f2Var = max(0, f2Var)
                f3Var = (f3_sq_sum / valid_frames) - (avgVal3**2); f3Var = max(0, f3Var)
                f1STD = np.sqrt(f1Var * valid_frames / (valid_frames - 1))
                f2STD = np.sqrt(f2Var * valid_frames / (valid_frames - 1))
                f3STD = np.sqrt(f3Var * valid_frames / (valid_frames - 1))

            features['formant1Mean'] = avgVal1
            features['formant2Mean'] = avgVal2
            features['formant3Mean'] = avgVal3
            features['formant1SD'] = f1STD
            features['formant2SD'] = f2STD
            features['formant3SD'] = f3STD
            features['formant1Bandwidth'] = avgBand1
            features['formant2Bandwidth'] = avgBand2
            features['formant3Bandwidth'] = avgBand3

        except parselmouth.PraatError as e:
            print(f"Recording Handler (Parselmouth) Warning: Formant analysis failed: {e}")
            # Assign default 0s to formant features
            formant_keys = ['formant1Mean', 'formant2Mean', 'formant3Mean', 'formant1SD', 'formant2SD',
                            'formant3SD', 'formant1Bandwidth', 'formant2Bandwidth', 'formant3Bandwidth']
            features.update({k: 0 for k in formant_keys})


        print(f"Recording Handler (Parselmouth): Successfully extracted {len(features)} features.")
        return features

    except parselmouth.PraatError as e:
        # Catch errors during initial sound loading or major failures
        print(f"Recording Handler (Parselmouth) Error: Failed to process audio file '{audio_path}': {e}")
        return None
    except FileNotFoundError:
         print(f"Recording Handler (Parselmouth) Error: Audio file not found at '{audio_path}'.")
         return None
    except Exception as e:
        # Catch any other unexpected Python errors
        print(f"Recording Handler (Parselmouth) Error: Unexpected error during feature extraction for '{audio_path}': {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        return None



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
    extracted_audio_features = None

    try:
        # Ensure user-specific directory exists before recording
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
                         stt_result_queue.put(f"STT_Warning: Mic Adjust Failed") # Simplified message
                         _recognizer.energy_threshold = initial_threshold
                         _ambient_noise_adjusted = True # Prevent retries
        # else: # Reduce log noise
            # print(f"Recording Handler (STT): Using pre-calibrated fixed energy threshold: {_recognizer.energy_threshold:.2f}")
        # --- End Adjustment ---

        # --- Initialize Video Recording ---
        try:
            video_filename = f"{topic_idx}.{follow_up_idx}{VIDEO_EXTENSION}"
            video_filepath = os.path.join(RECORDINGS_DIR, video_filename) # Use absolute path
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

            # Retry logic for VideoWriter opening (can sometimes fail intermittently)
            if not video_writer.isOpened():
                 print(f"Recording Handler (Video): Initial VideoWriter open failed for {video_filepath}. Retrying...")
                 time.sleep(0.5) # Brief pause before retry
                 video_writer = cv2.VideoWriter(video_filepath, fourcc, fps_for_writer, (frame_width, frame_height))
                 if not video_writer.isOpened():
                      raise IOError(f"Could not open VideoWriter for file after retry: {video_filepath}")
                 else:
                      print(f"Recording Handler (Video): VideoWriter succeeded on retry.")
                      # No need to reopen camera if it was opened successfully before

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
            # Clean up resources if init failed partially
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
                    # Listen with timeout and phrase limit
                    audio = _recognizer.listen(source, timeout=5, phrase_time_limit=30)
                    print("Recording Handler (STT): Audio captured.")

                except sr.WaitTimeoutError:
                    print("Recording Handler (STT): No speech detected within timeout.")
                    stt_result_queue.put("STT_Error: No speech detected.")
                except Exception as listen_e:
                     print(f"Recording Handler (STT): Error during listening phase: {listen_e}")
                     stt_result_queue.put(f"STT_Error: Listening Failed") # Simplified

                # Save audio file if captured
                if audio:
                    try:
                        audio_filename = f"{topic_idx}.{follow_up_idx}.wav"
                        audio_filepath = os.path.join(RECORDINGS_DIR, audio_filename) # Use absolute path
                        print(f"Recording Handler (STT): Saving audio to {audio_filepath}...")
                        wav_data = audio.get_wav_data()
                        with open(audio_filepath, "wb") as f:
                            f.write(wav_data)
                        print(f"Recording Handler (STT): Audio saved successfully.")

                        if PRAAT_FEATURE_EXTRACTION_ENABLED and audio_filepath:
                             try:
                                 # Make sure the file handle is closed before Praat tries to access it
                                 extracted_audio_features = extract_features(audio_filepath)
                                 if extracted_audio_features:
                                     print(f"Recording Handler (Praat): Extracted Features for {audio_filename}:")
                                     # You can format this output better if needed
                                     for key, val in extracted_audio_features.items():
                                         print(f"  - {key}: {val:.4f}")
                                     # TODO: Decide what to do with features (save to file, queue, database?)
                                     # Example: Put on queue (requires modifying queue consumer)
                                     # stt_result_queue.put({"type": "features", "topic": topic_idx, "follow_up": follow_up_idx, "data": extracted_audio_features})
                                 else:
                                     print(f"Recording Handler (Praat): No features were extracted for {audio_filename}.")

                             except FileNotFoundError:
                                 print(f"Recording Handler (Praat) Error: Cannot run feature extraction. Praat executable or script not found. Disabling for this session.")
                                 # Optionally disable future attempts if this is critical
                                 # global PRAAT_FEATURE_EXTRACTION_ENABLED
                                 # PRAAT_FEATURE_EXTRACTION_ENABLED = False
                             except RuntimeError as praat_err:
                                 # Catch errors from Praat script execution/parsing
                                 print(f"Recording Handler (Praat) Error: Failed to extract features for {audio_filename}: {praat_err}")
                             except Exception as feat_err:
                                 # Catch any other unexpected errors during feature extraction
                                 print(f"Recording Handler (Praat) Error: Unexpected error during feature extraction for {audio_filename}: {feat_err}")
                        elif not PRAAT_FEATURE_EXTRACTION_ENABLED:
                            print("Recording Handler (Praat): Feature extraction is disabled (script not found or configured).")
                    except Exception as save_err:
                        print(f"Recording Handler (STT) Warning: Failed to save audio file {audio_filename}: {save_err}")

                # Recognize audio if captured
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
                        stt_result_queue.put(f"STT_Error: API/Network Error") # Simplified
                    except Exception as recog_e:
                        print(f"Recording Handler (STT): Unknown error during recognition: {recog_e}")
                        stt_result_queue.put(f"STT_Error: Recognition Failed") # Simplified

        except OSError as e:
             # Specific check for device unavailable error
             if "Invalid input device" in str(e) or "No Default Input Device Available" in str(e):
                 print(f"Recording Handler (STT) Error: Microphone device error: {e}")
                 stt_result_queue.put(f"STT_Error: Microphone Device Unavailable")
             else:
                 print(f"Recording Handler (STT) Error: Microphone OS Error: {e}")
                 stt_result_queue.put(f"STT_Error: Microphone Access Failed")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get_pyaudio'" in str(e):
                 print("Recording Handler (STT) Error: PyAudio not found or failed to initialize.")
                 stt_result_queue.put(f"STT_Error: PyAudio Missing/Failed")
            else:
                 print(f"Recording Handler (STT) Error: Attribute Error during setup: {e}")
                 stt_result_queue.put(f"STT_Error: Setup Attribute Error")
        except Exception as setup_e:
            print(f"Recording Handler (STT) Error: Failed to setup microphone: {setup_e}")
            stt_result_queue.put(f"STT_Error: Mic Setup Failed")
        # --- End Audio Recording and STT ---

        audio_processing_done = True

    except OSError as e:
        print(f"Recording Handler Error: Could not create recordings directory '{RECORDINGS_DIR}': {e}")
        stt_result_queue.put(f"STT_Error: Setup Failed - Cannot create directory.")
        video_recording_started = False # Ensure video flag is off
        # Clean up video resources if directory creation failed after video init attempt
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()
    except Exception as main_err:
        print(f"Recording Handler Error: Unexpected error in recognition thread: {main_err}")
        stt_result_queue.put(f"STT_Error: Unexpected Thread Error")
        # Ensure video resources are cleaned up on unexpected error
        if video_thread is not None and video_thread.is_alive():
            stop_video_event.set()
        video_recording_started = False # Ensure video flag is off
        if video_writer is not None and video_writer.isOpened(): video_writer.release()
        if video_capture is not None and video_capture.isOpened(): video_capture.release()

    finally:
        # --- GUARANTEED CLEANUP: Video Finalization ---
        print(f"Recording Handler: Entering FINALLY block for {topic_idx}.{follow_up_idx}. Audio done: {audio_processing_done}")
        thread_was_joined_cleanly = False

        if video_recording_started and stop_video_event and not stop_video_event.is_set():
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

        # Ensure VideoWriter is released AFTER attempting to join the thread
        if video_writer is not None:
            if video_writer.isOpened():
                print("Recording Handler (Video): Releasing VideoWriter...")
                try:
                    video_writer.release()
                    print("Recording Handler (Video): VideoWriter released.")
                    # Log if release happened after timeout
                    if video_recording_started and not thread_was_joined_cleanly:
                         print("Recording Handler (Video) Warning: VideoWriter released after thread join timeout/failure. File may be incomplete or corrupted.")
                except Exception as vw_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoWriter: {vw_rel_err}")
            # else: print("Recording Handler (Video): VideoWriter was not open or already released.") # Optional log

        # Ensure VideoCapture is released
        if video_capture is not None:
            if video_capture.isOpened():
                print("Recording Handler (Video): Releasing VideoCapture...")
                try:
                    video_capture.release()
                    print("Recording Handler (Video): VideoCapture released.")
                except Exception as vc_rel_err:
                     print(f"Recording Handler (Video) Error releasing VideoCapture: {vc_rel_err}")
            # else: print("Recording Handler (Video): VideoCapture was not open or already released.") # Optional log

        print(f"Recording Handler: Recognition thread FINALLY block finished for {topic_idx}.{follow_up_idx}.")
        # --- End GUARANTEED CLEANUP ---


def start_speech_recognition(topic_idx, follow_up_idx):
    """
    Starts the speech recognition AND video recording process in a separate thread.
    Performs initial ambient noise check/adjustment if not already done.
    Results/status will be put onto stt_result_queue.
    Clears the queue before starting.
    """
    # Clear queue safely
    while not stt_result_queue.empty():
        try: stt_result_queue.get_nowait()
        except queue.Empty: break
        except Exception as e: print(f"Recording Handler (STT): Error clearing queue: {e}")

    print(f"Recording Handler: Starting recognition & video thread for {topic_idx}.{follow_up_idx}...")
    stt_thread = threading.Thread(target=_recognize_speech_thread, args=(topic_idx, follow_up_idx), daemon=True)
    stt_thread.start()

# --- End Recording Functions ---