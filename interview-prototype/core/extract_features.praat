# Praat Script: extract_features.praat
#
# Description:
#   Extracts a comprehensive set of acoustic features from a given WAV audio file.
#   Outputs features as key=value pairs, one per line, to standard output.
#
# Usage (Command Line):
#   praat --run extract_features.praat /path/to/your/audio.wav
#
# Input:
#   Command line argument 1: Full path to the input WAV file.
#
# Output:
#   feature_name1=value1
#   feature_name2=value2
#   ...
#
# Author: [Your Name/AI Assistant]
# Date: [Current Date]
# Version: 1.1 - Added pause analysis, slope analysis, fixed voice report parsing.

# --- Script Start ---
# Turn off graphics
nocheck noprogress nodraw

# --- Configuration ---
# Get the input file path from command line argument 1
form Get Input File Path
    sentence File_path ""
endform
soundFilePath$ = file_path$
# If run directly without form (e.g., via command line with --run)
if soundFilePath$ == ""
    soundFilePath$ = arguments$(1)
endif

# Pitch analysis settings
pitchFloor = 75
pitchCeiling = 600
timeStepPitch = 0.01  # Default time step for pitch analysis
silenceThreshold = -25.0 ; dB, for pause detection
minPauseDur = 0.15 ; seconds, minimum duration of a pause to be counted
minVoicedSegmentDur = 0.1 ; seconds, minimum duration for reliable pitch/formant stats

# Formant analysis settings (adjust time step, max formant, window length as needed)
timeStepFormants = 0.01
maxNumFormants = 5
maxFormantFreq = 5500 ; Hz (adjust based on expected voice type, e.g., 5000 for male, 5500 for female)
windowLengthFormants = 0.025 ; seconds
preEmphasisFormants = 50 ; Hz

# --- Read Audio File ---
# Clear objects (optional, good practice if running repeatedly)
# Remove all

# Read the sound file
sound = Read from file: soundFilePath$
soundName$ = selected$("Sound")
duration = Get total duration

# Handle potential zero-duration files
if duration <= 0
    printline Error: Sound duration is zero or negative. Cannot process.
    exitScript()
endif

# --- Create Analysis Objects ---
# Intensity
intensity = To Intensity: 100, timeStepPitch, "yes" ; Use same time step as pitch for alignment
intensityMin = Get minimum: 0, 0, "dB"
intensityMax = Get maximum: 0, 0, "dB"
intensityMean = Get mean: 0, 0, "dB"
# Calculate Intensity SD manually if Get standard deviation is not available/reliable
int_num_frames = Get number of frames
int_sum_sq_diff = 0
for i from 1 to int_num_frames
    frame_val = Get value in frame: i
    if frame_val != undefined
        diff = frame_val - intensityMean
        int_sum_sq_diff = int_sum_sq_diff + (diff * diff)
    endif
endfor
intensitySD = 0
if int_num_frames > 1 and int_sum_sq_diff > 0
    intensitySD = sqrt(int_sum_sq_diff / (int_num_frames - 1))
endif
intensityQuant5 = Get quantile: 0, 0, 0.05, "dB"
intensityQuant95 = Get quantile: 0, 0, 0.95, "dB"
intensityMedian = Get quantile: 0, 0, 0.50, "dB" # Use median for 'mode'

# Pitch
pitch = To Pitch: timeStepPitch, pitchFloor, pitchCeiling
# Check if pitch object is created (might fail on silence/noise)
if selected("Pitch") == 0
    # Pitch object failed, set all pitch-related features to 0 or undefined marker
    printline Warning: Pitch object creation failed. Setting pitch features to 0.
    min_pitch = 0
    max_pitch = 0
    mean_pitch = 0
    pitch_sd = 0
    pitchMedian = 0
    pitchQuant5 = 0
    pitchQuant95 = 0
    pitchUvsVRatio = undefined # Special case
    meanPeriod = 0
    percentUnvoiced = 100
    numVoiceBreaks = 0
    PercentBreaks = 0
    jitterLocal = 0
    jitterRap = 0
    shimmerLocalDB = 0
    numRising = 0
    numFall = 0
    MaxRisingSlope = 0
    MaxFallingSlope = 0
    AvgRisingSlope = 0
    AvgFallingSlope = 0
    pitch_obj_available = 0
else
    pitch_obj_available = 1
    # Pitch features (only calculate if object exists)
    min_pitch = Get minimum pitch
    max_pitch = Get maximum pitch
    mean_pitch = Get mean pitch
    pitch_sd = Get standard deviation pitch
    pitchMedian = Get quantile pitch: 0, 0, 0.5, "Hertz" # Use median for 'abs' and 'mode'
    pitchQuant5 = Get quantile pitch: 0, 0, 0.05, "Hertz"
    pitchQuant95 = Get quantile pitch: 0, 0, 0.95, "Hertz"

    # PointProcess for Voice Report
    selectObject: sound, pitch
    pointProc = To PointProcess (periodic, cc)

    # Voice Report Features (Jitter, Shimmer, etc.)
    selectObject: sound, pitch, pointProc
    # Get report - need to parse string output
    voiceReport$ = Voice report: 0, 0, pitchFloor, pitchCeiling, 1.3, 1.6, 0.03, 0.45
    # Default values in case parsing fails
    jitterLocal = 0
    jitterRap = 0
    shimmerLocalDB = 0
    meanPeriod = 0
    percentUnvoiced = 100
    numVoiceBreaks = 0

    if index(voiceReport$, "Jitter (local):") > 0
        line$ = extractLine$(voiceReport$, "Jitter (local):")
        jitterLocal = number(extractWord$(line$, "Jitter (local): "))
    endif
    if index(voiceReport$, "Jitter (rap):") > 0
        line$ = extractLine$(voiceReport$, "Jitter (rap):")
        jitterRap = number(extractWord$(line$, "Jitter (rap): "))
    endif
    if index(voiceReport$, "Shimmer (local, dB):") > 0
        line$ = extractLine$(voiceReport$, "Shimmer (local, dB):")
        shimmerLocalDB = number(extractWord$(line$, "Shimmer (local, dB): "))
    endif
    if index(voiceReport$, "Mean period:") > 0
        line$ = extractLine$(voiceReport$, "Mean period:")
        meanPeriod = number(extractWord$(line$, "Mean period: ")) * 1000 ; Convert s to ms for common representation, but output asks for period (s)
        meanPeriod = number(extractWord$(line$, "Mean period: ")) ; Keep in seconds
    endif
    if index(voiceReport$, "Fraction of locally unvoiced frames:") > 0
        line$ = extractLine$(voiceReport$, "Fraction of locally unvoiced frames:")
        percentUnvoiced = number(extractWord$(line$, "Fraction of locally unvoiced frames: ")) * 100
    endif
    if index(voiceReport$, "Number of voice breaks:") > 0
        line$ = extractLine$(voiceReport$, "Number of voice breaks:")
        numVoiceBreaks = number(extractWord$(line$, "Number of voice breaks: "))
    endif

    # Calculate voiced/unvoiced ratio
    voiced_frames = Get number of frames
    unvoiced_frames = Get number of frames where pitch is undefined
    total_frames_pitch = Get number of frames
    voiced_frames = total_frames_pitch - unvoiced_frames
    pitchUvsVRatio = undefined
    if voiced_frames > 0
      pitchUvsVRatio = unvoiced_frames / voiced_frames
    endif

    # Calculate PercentBreaks (breaks per second of *voiced* time)
    voicedDuration = Get total duration where pitch exists
    PercentBreaks = 0
    if voicedDuration > 0
        PercentBreaks = numVoiceBreaks / voicedDuration
    endif

    # Pitch Slope Analysis
    selectObject: pitch
    numFramesPitch = Get number of frames
    timeStepActual = Get time step
    numRising = 0
    numFall = 0
    MaxRisingSlope = 0
    MaxFallingSlope = 0
    totalRisingSlope = 0
    totalFallingSlope = 0
    countRisingSlope = 0
    countFallingSlope = 0
    lastPitch = undefined
    lastSlopeSign = 0 # 0: undefined/flat, 1: rising, -1: falling

    for i from 1 to numFramesPitch
        currentPitch = Get value in frame: i
        if currentPitch != undefined and lastPitch != undefined
            slope = (currentPitch - lastPitch) / timeStepActual
            currentSlopeSign = 0
            if slope > 0
                currentSlopeSign = 1
                if slope > MaxRisingSlope
                    MaxRisingSlope = slope
                endif
                totalRisingSlope = totalRisingSlope + slope
                countRisingSlope = countRisingSlope + 1
            elsif slope < 0
                currentSlopeSign = -1
                # Use positive value for max falling comparison
                if abs(slope) > abs(MaxFallingSlope)
                    MaxFallingSlope = slope # Keep the negative sign
                endif
                totalFallingSlope = totalFallingSlope + slope
                countFallingSlope = countFallingSlope + 1
            endif

            # Count changes in direction
            if lastSlopeSign != 0 and currentSlopeSign != 0
                if currentSlopeSign == 1 and lastSlopeSign == -1
                    numRising = numRising + 1
                elsif currentSlopeSign == -1 and lastSlopeSign == 1
                    numFall = numFall + 1
                endif
            endif

            if currentSlopeSign != 0
              lastSlopeSign = currentSlopeSign
            endif
        elsif currentPitch == undefined
          lastSlopeSign = 0 # Reset slope if unvoiced frame encountered
        endif

        lastPitch = currentPitch
    endfor

    AvgRisingSlope = 0
    if countRisingSlope > 0
        AvgRisingSlope = totalRisingSlope / countRisingSlope
    endif
    AvgFallingSlope = 0
    if countFallingSlope > 0
        AvgFallingSlope = totalFallingSlope / countFallingSlope
    endif
    # Clean up PointProcess
    selectObject: pointProc
    Remove

endif # End of check for pitch object availability

# Formants (only if sound duration is sufficient)
selectObject: sound
avgVal1, avgVal2, avgVal3 = 0, 0, 0
avgBand1, avgBand2, avgBand3 = 0, 0, 0
f1STD, f2STD, f3STD = 0, 0, 0
formant_obj_available = 0

if duration > windowLengthFormants * 2 ; Need enough duration for formant analysis
    formant = To Formant (burg): timeStepFormants, maxNumFormants, maxFormantFreq, windowLengthFormants, preEmphasisFormants
    if selected("Formant") > 0
        formant_obj_available = 1
        # Calculate means and SDs - requires iterating frames if direct functions aren't robust
        numFramesFormant = Get number of frames
        f1Sum, f2Sum, f3Sum = 0, 0, 0
        b1Sum, b2Sum, b3Sum = 0, 0, 0
        f1SqSum, f2SqSum, f3SqSum = 0, 0, 0
        validFrames = 0
        for i from 1 to numFramesFormant
            # Check if pitch is defined around this time for better formant reliability
            pitchValCheck = Get value at time: Get time from frame number: i, "Hertz", "Linear"
            if pitchValCheck != undefined
                f1 = Get value at time: i * timeStepFormants, 1, "Hertz", "Linear"
                f2 = Get value at time: i * timeStepFormants, 2, "Hertz", "Linear"
                f3 = Get value at time: i * timeStepFormants, 3, "Hertz", "Linear"
                b1 = Get bandwidth at time: i * timeStepFormants, 1, "Hertz", "Linear"
                b2 = Get bandwidth at time: i * timeStepFormants, 2, "Hertz", "Linear"
                b3 = Get bandwidth at time: i * timeStepFormants, 3, "Hertz", "Linear"

                if f1 != undefined and f2 != undefined and f3 != undefined and b1 != undefined and b2 != undefined and b3 != undefined
                    validFrames = validFrames + 1
                    f1Sum = f1Sum + f1
                    f2Sum = f2Sum + f2
                    f3Sum = f3Sum + f3
                    b1Sum = b1Sum + b1
                    b2Sum = b2Sum + b2
                    b3Sum = b3Sum + b3
                    f1SqSum = f1SqSum + f1*f1
                    f2SqSum = f2SqSum + f2*f2
                    f3SqSum = f3SqSum + f3*f3
                endif
            endif
        endfor

        if validFrames > 0
            avgVal1 = f1Sum / validFrames
            avgVal2 = f2Sum / validFrames
            avgVal3 = f3Sum / validFrames
            avgBand1 = b1Sum / validFrames
            avgBand2 = b2Sum / validFrames
            avgBand3 = b3Sum / validFrames
        endif
        if validFrames > 1
             # SD = sqrt( (sum(x^2)/N) - (mean(x))^2 ) * sqrt(N/(N-1)) variance correction
            f1Var = (f1SqSum / validFrames) - (avgVal1 * avgVal1)
            f2Var = (f2SqSum / validFrames) - (avgVal2 * avgVal2)
            f3Var = (f3SqSum / validFrames) - (avgVal3 * avgVal3)
            # Ensure variance is non-negative due to potential float precision issues
            if f1Var < 0 f1Var = 0 endif
            if f2Var < 0 f2Var = 0 endif
            if f3Var < 0 f3Var = 0 endif
            f1STD = sqrt(f1Var * (validFrames / (validFrames - 1)))
            f2STD = sqrt(f2Var * (validFrames / (validFrames - 1)))
            f3STD = sqrt(f3Var * (validFrames / (validFrames - 1)))
        endif
        # Clean up Formant object
        selectObject: formant
        Remove
    else
        printline Warning: Formant object creation failed. Setting formant features to 0.
    endif
else
    printline Warning: Sound duration too short for formant analysis. Setting formant features to 0.
endif


# Pause Analysis (using Intensity object)
selectObject: intensity
numFramesIntensity = Get number of frames
timeStepIntensity = Get time step

inPause = 0
numPause = 0
currentPauseStartFrame = 0
totalPauseDur = 0
maxDurPause = 0
pauseDurations = Create Table with column names: "pauses", 0, "duration"

for i from 1 to numFramesIntensity
    intensityVal = Get value in frame: i
    isSilent = 0
    if intensityVal != undefined and intensityVal < silenceThreshold
        isSilent = 1
    endif

    if isSilent == 1 and inPause == 0
        # Start of a potential pause
        inPause = 1
        currentPauseStartFrame = i
    elsif isSilent == 0 and inPause == 1
        # End of a pause
        pauseEndFrame = i - 1
        if pauseEndFrame >= currentPauseStartFrame
            pauseDurFrames = pauseEndFrame - currentPauseStartFrame + 1
            pauseDurSec = pauseDurFrames * timeStepIntensity
            if pauseDurSec >= minPauseDur
                numPause = numPause + 1
                totalPauseDur = totalPauseDur + pauseDurSec
                if pauseDurSec > maxDurPause
                    maxDurPause = pauseDurSec
                endif
                # Add to table for calculating average later
                Append row
                row = Get number of rows
                Set numeric value: row, "duration", pauseDurSec
            endif
        endif
        inPause = 0
    endif
endfor

# Check if file ends during a pause
if inPause == 1
    pauseEndFrame = numFramesIntensity
    if pauseEndFrame >= currentPauseStartFrame
         pauseDurFrames = pauseEndFrame - currentPauseStartFrame + 1
         pauseDurSec = pauseDurFrames * timeStepIntensity
         if pauseDurSec >= minPauseDur
            numPause = numPause + 1
            totalPauseDur = totalPauseDur + pauseDurSec
            if pauseDurSec > maxDurPause
                maxDurPause = pauseDurSec
            endif
            Append row
            row = Get number of rows
            Set numeric value: row, "duration", pauseDurSec
         endif
    endif
endif

avgDurPause = 0
if numPause > 0
    # Calculate average from the table
    selectObject: pauseDurations
    avgDurPause = Get mean: "duration"
endif

# Clean up pause table
selectObject: pauseDurations
Remove


# --- Calculate Derived Features ---
# Use median pitch for pitch_abs and pitch_mode proxy
pitch_abs = pitchMedian ? pitchMedian : 0
diffPitchMaxMin = (max_pitch - min_pitch) ? (max_pitch - min_pitch) : 0
diffPitchMaxMean = (max_pitch - mean_pitch) ? (max_pitch - mean_pitch) : 0
diffPitchMaxMode = (max_pitch - pitchMedian) ? (max_pitch - pitchMedian) : 0 # Using Median as Mode

diffIntMaxMin = (intensityMax - intensityMin) ? (intensityMax - intensityMin) : 0
diffIntMaxMean = (intensityMax - intensityMean) ? (intensityMax - intensityMean) : 0
diffIntMaxMode = (intensityMax - intensityMedian) ? (intensityMax - intensityMedian) : 0 # Using Median as Mode

# Formant differences
f2meanf1 = (avgVal2 - avgVal1) ? (avgVal2 - avgVal1) : 0
f3meanf1 = (avgVal3 - avgVal1) ? (avgVal3 - avgVal1) : 0

# Speak Rate Proxy (Voiced Ratio)
# Use percentUnvoiced calculated earlier
speakRate = (100 - (percentUnvoiced ? percentUnvoiced : 100)) / 100 # Proportion voiced

# --- Output ---
# Use 'printline' for each feature=value pair
# Use '?' operator to handle potential undefined values gracefully, outputting 0 instead.
# Specify precision using :<number> (e.g., :6 for 6 decimal places)

printline duration='duration:6'
printline energy='intensityMean:6' # Using mean intensity as proxy for energy/power
printline power='intensityMean:6' # Using mean intensity as proxy for energy/power
printline min_pitch='min_pitch:6'
printline max_pitch='max_pitch:6'
printline mean_pitch='mean_pitch:6'
printline pitch_sd='pitch_sd:6'
printline pitch_abs='pitch_abs:6' # Using Median
printline pitch_quant_5='pitchQuant5:6'
printline pitch_quant_95='pitchQuant95:6'
printline pitchUvsVRatio='pitchUvsVRatio:6' # Ratio unvoiced/voiced frames

printline diffPitchMaxMin='diffPitchMaxMin:6'
printline diffPitchMaxMean='diffPitchMaxMean:6'
printline diffPitchMaxMode='diffPitchMaxMode:6' # Using Median as Mode

printline intensityMin='intensityMin:6'
printline intensityMax='intensityMax:6'
printline intensityMean='intensityMean:6'
printline intensitySD='intensitySD:6'
printline intensityQuant_5='intensityQuant5:6'
printline intensityQuant_95='intensityQuant95:6'

printline diffIntMaxMin='diffIntMaxMin:6'
printline diffIntMaxMean='diffIntMaxMean:6'
printline diffIntMaxMode='diffIntMaxMode:6' # Using Median as Mode

printline avgVal1='avgVal1:6'
printline avgVal2='avgVal2:6'
printline avgVal3='avgVal3:6'
printline avgBand1='avgBand1:6'
printline avgBand2='avgBand2:6'
printline avgBand3='avgBand3:6'

# fmean assumed same as avgVal
printline fmean1='avgVal1:6'
printline fmean2='avgVal2:6'
printline fmean3='avgVal3:6'

printline f2meanf1='f2meanf1:6'
printline f3meanf1='f3meanf1:6'

printline f1STD='f1STD:6'
printline f2STD='f2STD:6'
printline f3STD='f3STD:6'

# Jitter/Shimmer etc. from Voice Report
printline jitter='jitterLocal:6' # Jitter (local)
printline shimmer='shimmerLocalDB:6' # Shimmer (local, dB)
printline jitterRap='jitterRap:6' # Jitter (rap)
printline meanPeriod='meanPeriod:6' # Mean period (seconds)
printline percentUnvoiced='percentUnvoiced:6'
printline numVoiceBreaks='numVoiceBreaks:0' # Integer
printline PercentBreaks='PercentBreaks:6' # Breaks per sec of voiced time

printline speakRate='speakRate:6' # Proxy: Proportion of voiced frames

# Pause features
printline numPause='numPause:0' # Integer
printline maxDurPause='maxDurPause:6'
printline avgDurPause='avgDurPause:6'
printline TotDurPause='totalPauseDur:6' # Total duration of detected pauses

# Pitch slope features
printline MaxRisingSlope='MaxRisingSlope:6' # Max slope (Hz/s)
printline MaxFallingSlope='MaxFallingSlope:6' # Max falling slope (Hz/s, negative)
printline AvgRisingSlope='AvgRisingSlope:6' # Average rising slope (Hz/s)
printline AvgFallingSlope='AvgFallingSlope:6' # Average falling slope (Hz/s, negative)
printline numRising='numRising:0' # Number of rising contours
printline numFall='numFall:0' # Number of falling contours

# --- Cleanup ---
# Select all objects created and remove them
selectObject: sound, intensity
if pitch_obj_available == 1
    selectObject: pitch
endif
# Formant object removed earlier if created
Remove

# --- Script End ---