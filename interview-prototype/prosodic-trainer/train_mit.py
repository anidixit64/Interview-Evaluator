import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import re

PROSODIC_FILE = './csvs/prosodic_features.csv'
TURKER_FILE = './csvs/turker_scores_full_interview.csv'
TARGET_COLUMN = 'Overall'
PARTICIPANT_ID_PROSODIC = 'participant&question'
PARTICIPANT_ID_TURKER = 'Participant'
N_TOP_FEATURES = 10
TEST_SIZE = 0.2
RANDOM_STATE = 30
LOUDNESS_COLUMN = 'loudness'

def extract_participant_id(participant_question):
    if pd.isna(participant_question):
        return None
    match = re.match(r'([P]{1,2}\d+)Q\d+', str(participant_question), re.IGNORECASE)
    if match:
        participant_id = match.group(1).upper()
        if participant_id.startswith('PP'):
            try:
                numeric_part = int(participant_id[2:])  # extract number after "PP"
                new_id = 'P' + str(numeric_part + 89)  # Add 89
                return new_id
            except ValueError:
                print(f"Warning: Could not convert numeric part of '{participant_id}' to integer.")
                return None
        else:
            return participant_id
    print(f"Warning: Could not extract Participant ID from '{participant_question}'")
    return None

df_prosodic = pd.read_csv(PROSODIC_FILE, sep=',', header=0)
if df_prosodic.columns[0].startswith(('Unnamed:', ' ')):
    df_prosodic = df_prosodic.iloc[:, 1:]

df_turker = pd.read_csv(TURKER_FILE, sep=',', header=0)
if df_turker.columns[0].startswith(('Unnamed:', ' ')):
    df_turker = df_turker.iloc[:, 1:]

# preprocess prosodic data
df_prosodic['Participant_ID'] = df_prosodic[PARTICIPANT_ID_PROSODIC].apply(extract_participant_id)
df_prosodic.dropna(subset=['Participant_ID'], inplace=True)
df_prosodic['Participant_ID'] = df_prosodic['Participant_ID'].astype(str)

numeric_cols = df_prosodic.select_dtypes(include=np.number).columns.tolist()
feature_columns = [col for col in numeric_cols if col != LOUDNESS_COLUMN]  # exclude loudness
if 'Participant_ID' in feature_columns:
    feature_columns.remove('Participant_ID')

for col in feature_columns:
    df_prosodic[col] = pd.to_numeric(df_prosodic[col], errors='coerce')

df_prosodic_avg = df_prosodic.groupby('Participant_ID')[feature_columns].mean().reset_index()

# preprocess Turker data
df_turker_aggr = df_turker[df_turker['Worker'] == 'AGGR'].copy()
# apply the same transformation to Turker data participant IDs
df_turker_aggr[PARTICIPANT_ID_TURKER] = df_turker_aggr[PARTICIPANT_ID_TURKER].apply(lambda x: extract_participant_id(f"{x}Q1") if pd.notna(x) else None)
df_turker_aggr.dropna(subset=[PARTICIPANT_ID_TURKER], inplace=True)
df_turker_aggr['Participant_ID'] = df_turker_aggr[PARTICIPANT_ID_TURKER].str.upper().astype(str)
df_turker_aggr = df_turker_aggr[['Participant_ID', TARGET_COLUMN]]
df_turker_aggr[TARGET_COLUMN] = pd.to_numeric(df_turker_aggr[TARGET_COLUMN], errors='coerce')

# merge prosodic and Turker data
df_merged = pd.merge(df_prosodic_avg, df_turker_aggr, on='Participant_ID', how='inner')
df_merged.dropna(subset=feature_columns + [TARGET_COLUMN], inplace=True)
# prep data for modeling
X = df_merged[feature_columns]
y = df_merged[TARGET_COLUMN]

# imputation and scaling
temp_pipeline = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])
X_temp_scaled = temp_pipeline.fit_transform(X)

# feature selection
rf_selector = RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1)
rf_selector.fit(X_temp_scaled, y)

importances = rf_selector.feature_importances_
feature_importance_df = pd.DataFrame({'Feature': feature_columns, 'Importance': importances})
feature_importance_df = feature_importance_df.sort_values(by='Importance', ascending=False)
top_features = feature_importance_df.head(N_TOP_FEATURES)['Feature'].tolist()

print("\nTop Features:")
print(feature_importance_df.head(N_TOP_FEATURES))

X_top = X[top_features]

# split data
X_train, X_test, y_train, y_test = train_test_split(
    X_top, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
)

# model pipeline
pipeline = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler()),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1))
])
pipeline.fit(X_train, y_train)

y_pred = pipeline.predict(X_test)

# evaluate
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.4f}")
print(f"MSE: {mse:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R²: {r2:.4f}")

predictions_df = pd.DataFrame({'Actual': y_test.values, 'Predicted': y_pred}, index=y_test.index)
print("\nSample Predictions vs Actual:")
print(predictions_df.head(10))
