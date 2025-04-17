# prosodic-trainer/train_mit.py
# Trains a model to predict interview scores from prosodic features.

# --- Imports ---
import os
import re
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
# --- Added for plotting ---
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not found. Install it (`pip install matplotlib`) to generate plots.")
# --- End plotting import ---


# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(SCRIPT_DIR, 'csvs')
PROSODIC_FILE = os.path.join(CSV_DIR, 'prosodic_features.csv')
TURKER_FILE = os.path.join(CSV_DIR, 'turker_scores_full_interview.csv')

TARGET_COLUMN = 'Overall'
PARTICIPANT_ID_PROSODIC_COL = 'participant&question'
PARTICIPANT_ID_TURKER_COL = 'Participant'

N_TOP_FEATURES = 40
TEST_SIZE = 0.2
RANDOM_STATE = 42

MODEL_OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'model_output')
MODEL_FILENAME = 'prosody_model_pipeline.joblib'
FEATURES_FILENAME = 'prosody_model_features.joblib'
PLOT_FILENAME = 'prediction_vs_actual_scatter.png' # Added plot filename

# --- Column Renaming Map (FOCUS ON MAPPING CALCULATED_FEATURES) ---
# Map OLD CSV column names (keys) to NEW standard names (values)
# !! EDIT THIS MAP BASED ON YOUR ACTUAL CSV COLUMN NAMES !!
COLUMN_RENAME_MAP = {
    # Pitch
    'mean_pitch': 'meanF0Hz', 'pitch_sd': 'stdevF0Hz', 'min_pitch': 'minF0Hz',
    'max_pitch': 'maxF0Hz',
    # Jitter/Shimmer/HNR
    'jitter': 'jitterLocal', 'jitterRap': 'jitterRap', 'shimmer': 'shimmerLocal',
    # Intensity
    'intensityMean': 'intensityMean', 'intensitySD': 'intensitySD',
    'intensityMin': 'intensityMin', 'intensityMax': 'intensityMax',
    # Voicing/Duration/Pauses
    'duration': 'duration', 'percentUnvoiced': 'percentUnvoiced',
    'maxDurPause': 'maxDurPause', 'avgDurPause': 'avgDurPause', 'numPause': 'numPauses',
    # Formants/Bandwidths
    'avgVal1': 'meanF1Hz', 'avgVal2': 'meanF2Hz', 'avgVal3': 'meanF3Hz',
    'avgBand1': 'avgBand1', 'avgBand2': 'avgBand2', 'avgBand3': 'avgBand3',
    # --- Mark ALL OTHER CSV columns to be dropped (map to None) ---
    'energy': None, 'power': None, 'pitch_abs': None, 'pitch_quant': None,
    'Time:8': None, 'iDifference': None, 'diffPitchMaxMin': None,
    'diffPitchMaxMean': None, 'diffPitchMaxMode': None, 'intensityQuant': None,
    'diffIntMaxMin': None, 'diffIntMaxMean': None, 'diffIntMaxMode': None,
    'fmean1': None, 'fmean2': None, 'fmean3': None, 'f2meanf1': None,
    'f3meanf1': None, 'f1STD': None, 'f2STD': None, 'f3STD': None,
    'f2STDf1': None, 'f2STDf2': None, 'meanPeriod': None, 'numVoiceBreaks': None,
    'PercentBreaks': None, 'speakRate': None, 'TotDurPause:3': None,
    'iInterval': None, 'MaxRising:3': None, 'MaxFalling:3': None,
    'AvgTotRis:3': None, 'AvgTotFall:3': None, 'numRising': None,
    'numFall': None, 'loudness': None, 'pitchUvsVRatio': None,
    PARTICIPANT_ID_PROSODIC_COL: None, # Drop original ID after use
}

# Adjust map based on actual CSV header presence
def adjust_map_for_csv(df_columns, rename_map):
    """ Creates final map, marking unmapped CSV columns for dropping. """
    adjusted_map = {}
    all_map_keys = list(rename_map.keys())
    for col in df_columns:
        if col not in all_map_keys: adjusted_map[col] = None # Drop unmapped
    for key, value in rename_map.items():
        if key in df_columns: adjusted_map[key] = value # Keep existing map if key exists
    return adjusted_map

# --- Create output directory ---
os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_OUTPUT_DIR, MODEL_FILENAME)
FEATURES_PATH = os.path.join(MODEL_OUTPUT_DIR, FEATURES_FILENAME)
PLOT_PATH = os.path.join(MODEL_OUTPUT_DIR, PLOT_FILENAME) # Added plot path

# --- Helper Function: Extract Participant ID ---
def extract_participant_id(participant_question):
    """Extracts PXXX style ID. Converts PPXXX -> P(XXX+89)."""
    if pd.isna(participant_question): return None
    match = re.match(r'(P{1,2})(\d+)(?:Q\d+)?', str(participant_question), re.IGNORECASE)
    if match:
        prefix, num_str = match.group(1).upper(), match.group(2)
        try: num = int(num_str); return f'P{num + 89}' if prefix == 'PP' else f'P{num}'
        except ValueError: pass
    match_simple = re.match(r'(P)(\d+)', str(participant_question), re.IGNORECASE)
    if match_simple:
        try: return f'P{int(match_simple.group(2))}'
        except ValueError: pass
    print(f"Warning: Could not extract ID from '{participant_question}'")
    return None

# --- Data Loading Function ---
def load_dataframe(file_path, id_col_name):
    """Loads CSV, checks ID column, handles unnamed index."""
    print(f"Loading data from: {file_path}")
    try:
        df = pd.read_csv(file_path)
        print(f"  - Loaded shape: {df.shape}")
        if df.columns[0].startswith('Unnamed:'): df = df.iloc[:, 1:]; print(f"  - Shape after drop unnamed: {df.shape}")
        if id_col_name not in df.columns: print(f"Error: ID col '{id_col_name}' not found."); sys.exit(1)
        return df
    except FileNotFoundError: print(f"Error: File not found: {file_path}"); sys.exit(1)
    except Exception as e: print(f"Error loading {file_path}: {e}"); sys.exit(1)

# --- Plotting Function ---
def plot_predictions(y_test, y_pred, save_path):
    """Generates and saves a scatter plot of actual vs predicted values."""
    if not MATPLOTLIB_AVAILABLE:
        print("Plotting skipped: matplotlib not available.")
        return

    plt.figure(figsize=(8, 8))
    plt.scatter(y_test, y_pred, alpha=0.6, edgecolors='k', s=50)
    plt.title('Predicted vs. Actual Overall Scores (Test Set)')
    plt.xlabel('Actual Overall Score')
    plt.ylabel('Predicted Overall Score')

    # Add ideal prediction line (y=x)
    min_val = min(y_test.min(), y_pred.min()) - 0.5 # Add buffer
    max_val = max(y_test.max(), y_pred.max()) + 0.5 # Add buffer
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Ideal Prediction (y=x)')

    plt.xlim(min_val, max_val)
    plt.ylim(min_val, max_val)
    plt.gca().set_aspect('equal', adjustable='box') # Ensure square plot with 45-deg line
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    try:
        plt.savefig(save_path)
        print(f"\nScatter plot saved to: {save_path}")
    except Exception as e:
        print(f"\nError saving scatter plot: {e}")
    # plt.show() # Uncomment to display plot interactively
    plt.close() # Close plot figure to free memory


# --- Main Training Logic ---
if __name__ == "__main__":
    # Load DataFrames
    df_prosodic = load_dataframe(PROSODIC_FILE, PARTICIPANT_ID_PROSODIC_COL)
    df_turker = load_dataframe(TURKER_FILE, PARTICIPANT_ID_TURKER_COL)

    # --- Preprocessing Prosodic Data ---
    print("Preprocessing prosodic data...")
    ADJUSTED_MAP = adjust_map_for_csv(df_prosodic.columns, COLUMN_RENAME_MAP)
    COLS_TO_DROP = [k for k, v in ADJUSTED_MAP.items() if v is None]
    COLUMN_RENAME_MAP_FILTERED = {k: v for k, v in ADJUSTED_MAP.items() if v is not None and k != v}

    # 1: Extract Participant ID
    print(f"  - Extracting Participant ID from '{PARTICIPANT_ID_PROSODIC_COL}'...")
    df_prosodic['Participant_ID'] = df_prosodic[PARTICIPANT_ID_PROSODIC_COL].apply(extract_participant_id)
    initial_rows = len(df_prosodic); df_prosodic = df_prosodic.dropna(subset=['Participant_ID'])
    dropped_rows = initial_rows - len(df_prosodic)
    if dropped_rows > 0: print(f"  - Dropped {dropped_rows} rows: failed ID extraction.")
    df_prosodic['Participant_ID'] = df_prosodic['Participant_ID'].astype(str)

    # 2: Drop columns
    cols_to_drop_present = [c for c in COLS_TO_DROP if c in df_prosodic.columns]
    if cols_to_drop_present:
        print(f"  - Dropping {len(cols_to_drop_present)} columns (incl. non-mapped & original ID)...")
        df_prosodic = df_prosodic.drop(columns=cols_to_drop_present)
    else: print(f"  - No columns found to drop.")

    # 3: Apply Renaming
    rename_map_applicable = {k: v for k, v in COLUMN_RENAME_MAP_FILTERED.items() if k in df_prosodic.columns}
    if rename_map_applicable:
        print(f"  - Applying {len(rename_map_applicable)} column renames...")
        df_prosodic = df_prosodic.rename(columns=rename_map_applicable)
    else: print("  - No columns needed renaming.")

    # Identify numeric features from the *remaining* columns
    numeric_cols = df_prosodic.select_dtypes(include=np.number).columns.tolist()
    feature_columns = [col for col in numeric_cols if col != 'Participant_ID']
    print(f"  - Identified {len(feature_columns)} potential numeric features for aggregation.")
    if not feature_columns: print("Error: No numeric features left."); sys.exit(1)

    # Coerce features to numeric, aggregate
    for col in feature_columns:
        df_prosodic[col] = pd.to_numeric(df_prosodic[col], errors='coerce')
        if df_prosodic[col].isnull().all(): print(f"  - Warning: '{col}' all NaN after coercion. Excluding."); feature_columns.remove(col)
    print(f"  - Aggregating {len(feature_columns)} features by Participant_ID...")
    df_prosodic_avg = df_prosodic.groupby('Participant_ID')[feature_columns].mean().reset_index()
    print(f"  - Aggregated prosodic shape: {df_prosodic_avg.shape}")

    # --- Preprocessing Turker Data ---
    print("Preprocessing Turker data...")
    df_turker_aggr = df_turker[df_turker['Worker'] == 'AGGR'].copy()
    if df_turker_aggr.empty: print("Error: No 'AGGR' worker data."); sys.exit(1)
    df_turker_aggr['Participant_ID_Extracted'] = df_turker_aggr[PARTICIPANT_ID_TURKER_COL].apply(lambda x: extract_participant_id(f"{x}Q1") if pd.notna(x) else None)
    df_turker_aggr = df_turker_aggr.dropna(subset=['Participant_ID_Extracted'])
    df_turker_aggr['Participant_ID'] = df_turker_aggr['Participant_ID_Extracted'].astype(str)
    df_turker_aggr = df_turker_aggr[['Participant_ID', TARGET_COLUMN]]
    df_turker_aggr[TARGET_COLUMN] = pd.to_numeric(df_turker_aggr[TARGET_COLUMN], errors='coerce')
    df_turker_aggr = df_turker_aggr.dropna(subset=[TARGET_COLUMN])
    print(f"  - Turker preprocessing complete. Shape: {df_turker_aggr.shape}")

    # --- Merging Data ---
    print("Merging prosodic and Turker data...")
    df_merged = pd.merge(df_prosodic_avg, df_turker_aggr, on='Participant_ID', how='inner')
    print(f"  - Initial merged shape: {df_merged.shape}")
    final_feature_columns = list(df_prosodic_avg.columns.drop('Participant_ID'))
    df_merged = df_merged.dropna(subset=final_feature_columns + [TARGET_COLUMN])
    print(f"  - Shape after dropping NaNs: {df_merged.shape}")
    if df_merged.empty: print("Error: Merged dataframe empty."); sys.exit(1)

    # --- Prepare Data for Modeling ---
    X = df_merged[final_feature_columns]
    y = df_merged[TARGET_COLUMN]
    print(f"Data prepared. X shape: {X.shape}, y shape: {y.shape}")

    # --- Feature Selection ---
    print("Performing feature selection...")
    temp_pipeline = Pipeline([('imputer', SimpleImputer(strategy='median')), ('scaler', StandardScaler())])
    try: X_temp_scaled = temp_pipeline.fit_transform(X)
    except Exception as e: print(f"Error during scaling/imputation: {e}"); sys.exit(1)
    rf_selector = RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1)
    rf_selector.fit(X_temp_scaled, y)
    importances = rf_selector.feature_importances_
    feature_importance_df = pd.DataFrame({'Feature': final_feature_columns, 'Importance': importances})
    feature_importance_df = feature_importance_df.sort_values(by='Importance', ascending=False)
    if N_TOP_FEATURES >= len(final_feature_columns): actual_top_n = len(final_feature_columns)
    else: actual_top_n = N_TOP_FEATURES
    top_features = feature_importance_df.head(actual_top_n)['Feature'].tolist()
    print(f"\nTop {actual_top_n} Features Selected (based on available CSV data):")
    print(feature_importance_df.head(actual_top_n).to_string())

    # --- Prepare Final Data & Split ---
    X_top = X[top_features]
    print(f"\nSplitting data (Test size: {TEST_SIZE})...")
    X_train, X_test, y_train, y_test = train_test_split(X_top, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    print(f"  - Train shape: {X_train.shape}, Test shape: {X_test.shape}")

    # --- Model Training Pipeline ---
    print("Training the final model pipeline...")
    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1))
    ])
    pipeline.fit(X_train, y_train)
    print("Model training complete.")

    # --- Save the Model and Updated Features List ---
    print(f"Saving trained pipeline to: {MODEL_PATH}")
    try: joblib.dump(pipeline, MODEL_PATH); print("  - Pipeline saved successfully.")
    except Exception as e: print(f"Error saving pipeline: {e}")
    print(f"Saving list of {len(top_features)} features used by model to: {FEATURES_PATH}")
    try: joblib.dump(top_features, FEATURES_PATH); print("  - Feature list saved successfully.")
    except Exception as e: print(f"Error saving feature list: {e}")

    # --- Evaluation ---
    print("\nEvaluating model on test set...")
    y_pred = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred); mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse); r2 = r2_score(y_test, y_pred)
    print("\nModel Evaluation Metrics:")
    print(f"  - MAE:  {mae:.4f}"); print(f"  - MSE:  {mse:.4f}")
    print(f"  - RMSE: {rmse:.4f}"); print(f"  - R²:   {r2:.4f}")
    predictions_df = pd.DataFrame({'Actual': y_test.values, 'Predicted': y_pred}, index=y_test.index)
    print("\nSample Predictions vs Actual:"); print(predictions_df.head(10).to_string())

    # --- Generate and Save Plot ---
    print("\nGenerating prediction scatter plot...")
    plot_predictions(y_test, y_pred, PLOT_PATH) # Call the plotting function

    print("\n--- Training Script Finished ---")