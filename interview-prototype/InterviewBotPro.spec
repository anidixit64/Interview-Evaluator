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
# Removed 'pydub'. Added 'soundfile' and 'cffi'.
hiddenimports = [
    'pkg_resources',
    'keyring.backends.macOS',
    'keyring.backends.fail',
    'google.api_core.bidi',
    'pyaudio',
    'sounddevice',
    # 'pydub',  # REMOVED - Replaced by soundfile for OpenAI TTS decoding
    'soundfile', # ADDED - Used by tts_openai for decoding
    'cffi',      # ADDED - Dependency for soundfile
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
    'numpy',     # Kept - Used by soundfile and tts_openai directly now
    'nltk',      # Kept - Used by tts_openai for sentence splitting
]

# --- Data Files ---
# Collect necessary data files
# Added collection for nltk_data needed by tts_openai
datas = [
    ('icons', 'icons'),
    ('ui/styles.qss', 'ui'),
]
# Use hook utility to collect nltk_data (ensure nltk is installed in the env)
# This finds the 'nltk_data' directory within the nltk package installation
# and copies it into the bundle at the top level ('nltk_data').
# tts_openai.py's NLTK logic should find it there when bundled.
try:
    datas += collect_data_files('nltk_data', include_py_files=True)
    print("INFO: Successfully added nltk_data using collect_data_files.")
except Exception as e:
    print(f"WARNING: Failed to automatically collect nltk_data: {e}")
    print("         Ensure nltk is installed and consider manually adding nltk_data if bundling fails.")
    # Manual fallback example (adjust 'path/to/your/env/lib/.../nltk_data'):
    # datas += [('path/to/your/env/lib/pythonX.Y/site-packages/nltk_data', 'nltk_data')]


# --- Analysis Block (Add hiddenimports, updated datas) ---
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[], # Ensure ffmpeg/ffprobe are NOT added here or via command line
    datas=datas, # Use the updated datas list
    hiddenimports=hiddenimports, # Use the updated hiddenimports list
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --- EXE Object (Keep as generated, likely needed internally) ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InterviewBotPro', # Internal name for the executable inside the .app
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Turn off UPX, it often causes problems
    console=False, # Keep as GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None, # Entitlements go on the BUNDLE/APP, not the inner EXE
)

# --- COLLECT Object (Modify to turn off UPX) ---
coll = COLLECT(
    exe,
    a.binaries,
    a.datas, # Use a.datas here (contains collected nltk_data now)
    strip=False,
    upx=False, # Turn off UPX here too
    upx_exclude=[],
    name='InterviewBotPro', # Name of the folder within Contents/MacOS usually
)

# --- BUNDLE Object (Modify to add icon, identifier, plist, entitlements) ---
app_icon = icon_file_icns if os.path.exists(icon_file_icns) else None
# !!! IMPORTANT: Replace 'com.yourcompany' with your actual reverse domain !!!
bundle_identifier = f'com.yourcompany.{app_name.lower().replace(" ", "")}'
entitlements = entitlements_file_path if os.path.exists(entitlements_file_path) else None

app = BUNDLE(
    coll, # Bundle the collected files/exe
    name=f'{app_name}.app', # Correct name for the .app bundle
    icon=app_icon, # Set the icon path
    bundle_identifier=bundle_identifier, # Set the bundle ID
    info_plist={ # Add the info_plist dictionary
        'NSMicrophoneUsageDescription': 'This app needs access to the microphone for speech-to-text input during the interview.',
        'NSCameraUsageDescription': 'This app needs access to the camera to record video during the interview.',
        'CFBundleName': app_name,
        'CFBundleDisplayName': app_name,
        'CFBundleIdentifier': bundle_identifier, # Use variable
        'CFBundleVersion': '1.0.0', # CHANGE as needed
        'CFBundleShortVersionString': '1.0', # CHANGE as needed
        # !!! IMPORTANT: Replace 'Your Name/Company' !!!
        'NSHumanReadableCopyright': 'Copyright © 2024 Your Name/Company. All rights reserved.'
    },
    entitlements_file=entitlements, # Set the entitlements file path
)