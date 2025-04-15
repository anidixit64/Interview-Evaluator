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

# Load the audio
sound = Read from file: soundFilePath$
selectObject: sound
soundName$ = selected$("Sound")
duration = Get total duration

# --- Intensity ---
# Ensure sound is selected before creating Intensity
selectObject: sound
intensity = To Intensity: 75, 0, "yes"
intensityName$ = selected$("Intensity")
intensityMean = Get mean: 0, 0, "energy"
intensitySD = Get standard deviation: 0, 0
intensityMin = Get minimum: 0, 0, "Parabolic"
intensityMax = Get maximum: 0, 0, "Parabolic"
intensityQuant5 = Get quantile: 0, 0, 0.05
intensityQuant95 = Get quantile: 0, 0, 0.95
intensityMedian = Get quantile: 0, 0, 0.5

# --- Pitch ---
# <<< FIX: Select the original Sound object BEFORE To Pitch: >>>
selectObject: sound
# <<< END FIX >>>
pitch = To Pitch: 0.0, 75, 15
# Check if pitch object creation failed (e.g., on pure silence)
pitch_obj_available = 1
if selected("Pitch") == 0
    printline Warning: Pitch object creation failed. Setting pitch features to 0.
    pitch_obj_available = 0
    mean_pitch = 0
    min_pitch = 0
    max_pitch = 0
    pitch_sd = 0
    pitchMedian = 0
    pitchQuant5 = 0
    pitchQuant95 = 0
    pitchUvsVRatio = undefined
    meanPeriod = 0
    percentUnvoiced = 100 
    numVoiceBreaks = 0
    PercentBreaks = 0
    jitterLocal = 0
    jitterRap = 0
    shimmerLocalDB = 0
    # Also zero out slope features if no pitch
    numRising = 0
    numFall = 0
    MaxRisingSlope = 0
    MaxFallingSlope = 0
    AvgRisingSlope = 0
    AvgFallingSlope = 0
else
    # Pitch object exists, proceed with calculations
    pitchName$ = selected$("Pitch")
    mean_pitch = Get mean: 0, 0, "Hertz"
    min_pitch = Get minimum: 0, 0, "Hertz", "Parabolic"
    max_pitch = Get maximum: 0, 0, "Hertz", "Parabolic"
    pitch_sd = Get standard deviation: 0, 0, "Hertz"
    pitchQuant5 = Get quantile: 0, 0, 0.05, "Hertz"
    pitchQuant95 = Get quantile: 0, 0, 0.95, "Hertz"
    pitchMedian = Get quantile: 0, 0, 0.5, "Hertz"
    selectObject: pitch
    numberOfFrames = Get number of frames
    voicedFrames = 0
    unvoicedFrames = 0

    if mean_pitch > 0
        meanPeriod = 1 / mean_pitch
    endif

    selectObject: pitch
    numberOfFrames = Get number of frames
    voicedFrames = 0
    unvoicedFrames = 0
    if numberOfFrames > 0
        for frame from 1 to numberOfFrames
            # Get value in frame returns undefined for unvoiced frames
            frequency = Get value in frame: frame, "Hertz"
            if frequency == undefined
                unvoicedFrames = unvoicedFrames + 1
            else
                voicedFrames = voicedFrames + 1
            endif
        endfor

        if voicedFrames > 0
            pitchUvsVRatio = unvoicedFrames / voicedFrames
        else
            # Handle case where entire file is unvoiced according to Pitch object
            pitchUvsVRatio = undefined # Or a large number if preferred
        endif
    else
        # Handle case where Pitch object has zero frames (shouldn't happen if created)
        pitchUvsVRatio = undefined
    endif


    # --- Voicing features (require Sound and Pitch selected) ---
    # <<< FIX: Select BOTH Sound and Pitch for PointProcess >>>
    selectObject: sound, pitch
    # <<< END FIX >>>
    pointProcess = To PointProcess (periodic, cc): 75, 500
    pointProcessName$ = selected$("PointProcess")
    # Jitter/Shimmer operate on the PointProcess implicitly
    jitterLocal = Get jitter (local): 0, 0, 0.0001, 0.02, 1.3
    jitterRap = Get jitter (rap): 0, 0, 0.0001, 0.02, 1.3
    shimmerLocalDB = Get shimmer (local, dB): 0, 0, 0.0001, 0.02, 1.3, 1.6

    # --- Voiced/unvoiced and voice breaks (require Pitch selected) ---
    # <<< FIX: Select Pitch object >>>
    selectObject: pitch
    # <<< END FIX >>>
    totalDurationPitchContext = Get total duration
    unvoicedDur = Get total duration of unvoiced intervals
    percentUnvoiced = 0
    if totalDurationPitchContext > 0
      percentUnvoiced = (unvoicedDur / totalDurationPitchContext) * 100
    else
      percentUnvoiced = 100 # Assume fully unvoiced if pitch duration is zero
    endif

    numVoiceBreaks = Count number of voice breaks: 0.02, 0.1, 0.02
    PercentBreaks = 0
    # Use overall sound duration for breaks/sec calculation
    if duration > 0
      PercentBreaks = numVoiceBreaks / duration
    endif

    # --- Slope Features (require Pitch selected) ---
    # <<< FIX: Ensure Pitch object is still selected >>>
    selectObject: pitch
    # <<< END FIX >>>
    numRising = 0
    numFall = 0
    MaxRisingSlope = 0 # Initialize to 0, not -1000
    MaxFallingSlope = 0 # Initialize to 0, not 1000
    TotalRisingSlope = 0
    TotalFallingSlope = 0
    NumRisingSlope = 0
    NumFallingSlope = 0

    totalFrames = Get number of frames
    timeStepSlope = Get time step # Get actual time step
    # Check if enough frames for slope calculation
    if totalFrames > 1
        for i from 2 to totalFrames
            # Use Get value in frame for robustness
            p1 = Get value in frame: i - 1
            p2 = Get value in frame: i
            # Only calculate slope if both points are voiced
            if p1 != undefined and p2 != undefined
                # t1 = Get time from frame number: i - 1
                # t2 = Get time from frame number: i
                # slope = (p2 - p1) / (t2 - t1)
                slope = (p2 - p1) / timeStepSlope
                if slope > 0
                    # Check if it's the start of a new rising segment
                    p0 = undefined
                    if i > 2
                       p0 = Get value in frame: i - 2
                    endif
                    # Count rise only if previous was non-rising or undefined
                    if p0 == undefined or (p1 - p0) / timeStepSlope <= 0
                       numRising = numRising + 1
                    endif

                    TotalRisingSlope = TotalRisingSlope + slope
                    NumRisingSlope = NumRisingSlope + 1
                    if slope > MaxRisingSlope
                        MaxRisingSlope = slope
                    endif
                elsif slope < 0
                    # Check if it's the start of a new falling segment
                    p0 = undefined
                    if i > 2
                       p0 = Get value in frame: i - 2
                    endif
                     # Count fall only if previous was non-falling or undefined
                    if p0 == undefined or (p1 - p0) / timeStepSlope >= 0
                       numFall = numFall + 1
                    endif

                    TotalFallingSlope = TotalFallingSlope + slope
                    NumFallingSlope = NumFallingSlope + 1
                    # Compare absolute values for MaxFallingSlope, store negative
                    if slope < MaxFallingSlope # Since MaxFallingSlope starts at 0, first negative slope is smaller
                        MaxFallingSlope = slope
                    endif
                endif
            endif
        endfor

        AvgRisingSlope = 0
        if NumRisingSlope > 0
            AvgRisingSlope = TotalRisingSlope / NumRisingSlope
        endif
        AvgFallingSlope = 0
        if NumFallingSlope > 0
            AvgFallingSlope = TotalFallingSlope / NumFallingSlope
        endif
    endif # End check for totalFrames > 1 for slope
endif # End check for pitch_obj_available

# --- Formant Features ---
# <<< FIX: Select Sound object BEFORE To Formant >>>
selectObject: sound
# <<< END FIX >>>
formant = To Formant (burg): 0, 5, 5500, 0.025, 50
formant_obj_available = 0
avgVal1, avgVal2, avgVal3 = 0, 0, 0
f1STD, f2STD, f3STD = 0, 0, 0
avgBand1, avgBand2, avgBand3 = 0, 0, 0

if selected("Formant") > 0
    formant_obj_available = 1
    formantName$ = selected$("Formant")
    numFramesFormant = Get number of frames
    validFrames = 0
    f1Sum, f2Sum, f3Sum = 0, 0, 0
    f1SqSum, f2SqSum, f3SqSum = 0, 0, 0
    b1Sum, b2Sum, b3Sum = 0, 0, 0

    for i from 1 to numFramesFormant
        time = Get time from frame number: i
        f1 = Get value at time: 1, time, "Hertz", "Linear"
        f2 = Get value at time: 2, time, "Hertz", "Linear"
        f3 = Get value at time: 3, time, "Hertz", "Linear"
        b1 = Get bandwidth at time: 1, time, "Hertz"
        b2 = Get bandwidth at time: 2, time, "Hertz"
        b3 = Get bandwidth at time: 3, time, "Hertz"
        if f1 != undefined and f2 != undefined and f3 != undefined and b1 != undefined and b2 != undefined and b3 != undefined
            validFrames = validFrames + 1
            f1Sum = f1Sum + f1
            f2Sum = f2Sum + f2
            f3Sum = f3Sum + f3
            f1SqSum = f1SqSum + (f1 * f1)
            f2SqSum = f2SqSum + (f2 * f2)
            f3SqSum = f3SqSum + (f3 * f3)
            b1Sum = b1Sum + b1
            b2Sum = b2Sum + b2
            b3Sum = b3Sum + b3
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
        # Calculate variance carefully to avoid negative results due to precision
        f1Var = (f1SqSum / validFrames) - (avgVal1 * avgVal1)
        f2Var = (f2SqSum / validFrames) - (avgVal2 * avgVal2)
        f3Var = (f3SqSum / validFrames) - (avgVal3 * avgVal3)
        if f1Var < 0 f1Var = 0 endif
        if f2Var < 0 f2Var = 0 endif
        if f3Var < 0 f3Var = 0 endif
        # Apply Bessel's correction sqrt(Var * N / (N-1))
        f1STD = sqrt(f1Var * (validFrames / (validFrames - 1)))
        f2STD = sqrt(f2Var * (validFrames / (validFrames - 1)))
        f3STD = sqrt(f3Var * (validFrames / (validFrames - 1)))
    endif
else
    printline Warning: Formant object creation failed. Setting formant features to 0.
endif

# --- Print Final Output ---
# Use '?' operator for potentially undefined values from pitch/formant sections
printline duration='duration:6'
printline intensityMean='intensityMean:6'
printline intensitySD='intensitySD:6'
printline intensityMin='intensityMin:6'
printline intensityMax='intensityMax:6'
printline intensityQuant5='intensityQuant5:6'
printline intensityQuant95='intensityQuant95:6'
printline intensityMedian='intensityMedian:6'
printline mean_pitch='mean_pitch?0:6'
printline min_pitch='min_pitch?0:6'
printline max_pitch='max_pitch?0:6'
printline pitch_sd='pitch_sd?0:6'
printline pitchMedian='pitchMedian?0:6'
printline pitchQuant5='pitchQuant5?0:6'
printline pitchQuant95='pitchQuant95?0:6'
printline pitchUvsVRatio='pitchUvsVRatio?-1:6'
printline meanPeriod='meanPeriod?0:6'
printline percentUnvoiced='percentUnvoiced?100:6'
printline numVoiceBreaks='numVoiceBreaks?0:0'
printline PercentBreaks='PercentBreaks?0:6'
printline jitterLocal='jitterLocal?0:6'
printline jitterRap='jitterRap?0:6'
printline shimmerLocalDB='shimmerLocalDB?0:6'
printline numRising='numRising?0:0'
printline numFall='numFall?0:0'
printline MaxRisingSlope='MaxRisingSlope?0:6'
printline MaxFallingSlope='MaxFallingSlope?0:6'
printline AvgRisingSlope='AvgRisingSlope?0:6'
printline AvgFallingSlope='AvgFallingSlope?0:6'
printline formant1Mean='avgVal1?0:6'
printline formant2Mean='avgVal2?0:6'
printline formant3Mean='avgVal3?0:6'
printline formant1SD='f1STD?0:6'
printline formant2SD='f2STD?0:6'
printline formant3SD='f3STD?0:6'
printline formant1Bandwidth='avgBand1?0:6'
printline formant2Bandwidth='avgBand2?0:6'
printline formant3Bandwidth='avgBand3?0:6'

# --- Cleanup ---
# Remove objects carefully, checking if they were created
if formant_obj_available == 1
    selectObject: formantName$
    Remove
endif
if pitch_obj_available == 1
    selectObject: pitchName$, pointProcessName$
    Remove
endif
# Remove intensity and original sound last
selectObject: intensityName$, soundName$
Remove

# --- Script End ---