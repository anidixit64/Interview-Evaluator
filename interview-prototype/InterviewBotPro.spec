# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files # Import hook utility

# --- Configuration (Define these at the top for clarity) ---
app_name = 'InterviewBotPro'
# macOS Specific
icon_file_icns = 'icons/app_icon.icns' # Path to your macOS .icns file
entitlements_file_path = 'entitlements.plist' # Path to your macOS entitlements file

# --- Hidden Imports ---
# Added specific sklearn submodules needed for unpickling the model pipeline.
hiddenimports = [
    'pkg_resources',
    'keyring.backends.macOS',
    'keyring.backends.fail',
    'google.api_core.bidi',
    'pyaudio',
    'sounddevice',
    'soundfile',
    'cffi',
    'openai',
    'google.generativeai',
    'PyQt6.sip',
    'core.tts_gtts',
    'core.tts_openai',
    'appdirs',
    'pathlib',
    'playsound',
    'gtts',
    'speech_recognition',
    'PyPDF2',
    'cv2',
    'numpy',
    'nltk',
    'pandas',
    'scipy',
    'sklearn',              # Keep top-level just in case
    # --- Added for loading the scikit-learn pipeline ---
    'sklearn.pipeline',
    'sklearn.ensemble',
    'sklearn.preprocessing',
    'sklearn.impute',
    'sklearn.metrics',      # Often needed indirectly or for checks
    'sklearn.model_selection', # Often needed indirectly
    'sklearn.utils._typedefs', # Sometimes needed internally by sklearn
    'sklearn.utils._openmp_helpers', # Sometimes needed
    'sklearn.neighbors._typedefs', # Add related typedefs
    'sklearn.neighbors._quad_tree', # Add potential compiled extensions
    'sklearn.tree', # Base for RandomForest
    'sklearn.tree._utils', # Utilities for tree
    # --- End added sklearn ---
    'joblib',
    'parselmouth',
    '_portaudio',
]

# --- Data Files ---
# Collect necessary data files
datas = [
    ('icons', 'icons'),
    ('ui/styles.qss', 'ui'),
    # Include model files
    ('core/model_output/prosody_model_features.joblib', 'core/model_output'),
    ('core/model_output/prosody_model_pipeline.joblib', 'core/model_output'),
]

# Collect nltk_data
try:
    datas += collect_data_files('nltk_data', include_py_files=True)
    print("INFO: Successfully added nltk_data using collect_data_files.")
except Exception as e:
    print(f"WARNING: Failed to automatically collect nltk_data: {e}")
    print("         Ensure nltk is installed and consider manually adding nltk_data if bundling fails.")

# Collect parselmouth data files
try:
    datas += collect_data_files('parselmouth', include_py_files=False)
    print("INFO: Successfully added parselmouth data files using collect_data_files.")
except Exception as e:
    print(f"WARNING: Failed to automatically collect parselmouth data files: {e}")
    print("         Ensure parselmouth is installed. The app might fail to run Praat.")


# --- Analysis Block (No change needed here) ---
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --- EXE Object (No change needed here) ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InterviewBotPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# --- COLLECT Object (No change needed here) ---
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='InterviewBotPro',
)

# --- BUNDLE Object (No change needed here) ---
app_icon = icon_file_icns if os.path.exists(icon_file_icns) else None
bundle_identifier = f'com.yourcompany.{app_name.lower().replace(" ", "")}' # Replace com.yourcompany
entitlements = entitlements_file_path if os.path.exists(entitlements_file_path) else None

app = BUNDLE(
    coll,
    name=f'{app_name}.app',
    icon=app_icon,
    bundle_identifier=bundle_identifier,
    info_plist={
        'NSMicrophoneUsageDescription': 'This app needs access to the microphone for speech-to-text input during the interview.',
        'NSCameraUsageDescription': 'This app needs access to the camera to record video during the interview.',
        'CFBundleName': app_name,
        'CFBundleDisplayName': app_name,
        'CFBundleIdentifier': bundle_identifier,
        'CFBundleVersion': '1.0.0', # CHANGE as needed
        'CFBundleShortVersionString': '1.0', # CHANGE as needed
        'NSHumanReadableCopyright': 'Copyright © 2025 Ethan Justice. All rights reserved.' # Replace
    },
    entitlements_file=entitlements,
)