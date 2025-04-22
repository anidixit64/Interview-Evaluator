# core/tts.py
import sys
import os
import importlib
import subprocess

SUPPORTED_PROVIDERS = ["gtts", "openai"]
DEFAULT_PROVIDER = "gtts"

tts_providers = {}
potentially_available_providers = []

print("TTS Facade: Loading providers...")
for provider_name in SUPPORTED_PROVIDERS:
    try:
        module_name = f"core.tts_{provider_name}"
        provider_module = importlib.import_module(module_name)
        if getattr(provider_module, 'dependencies_met', False):
            tts_providers[provider_name] = provider_module
            potentially_available_providers.append(provider_name)
            print(f"TTS Facade: Provider '{provider_name}' loaded (dependencies met).")
        else:
            print(f"TTS Facade: Provider '{provider_name}' unavailable (missing dependencies).")
            if provider_name in tts_providers:
                 del tts_providers[provider_name]
    except ImportError as e:
        print(f"TTS Facade: Could not import provider module '{module_name}': {e}")
    except Exception as e:
        print(f"TTS Facade: Error loading provider '{provider_name}': {e}")

_current_provider_name = None

def get_runtime_available_providers():
    runtime_available = []
    for name in potentially_available_providers:
        provider_module = tts_providers.get(name)
        if not provider_module: continue
        if name == 'gtts':
             if getattr(provider_module, 'is_available', False):
                 runtime_available.append(name)
        elif name == 'openai':
             if getattr(provider_module, 'is_available', False) and getattr(provider_module, '_client_initialized', False):
                 runtime_available.append(name)
    return runtime_available

def set_provider(provider_name):
    global _current_provider_name
    if provider_name in potentially_available_providers:
        provider_module = tts_providers.get(provider_name)
        if not provider_module: return False
        if provider_name == "openai":
             if not getattr(provider_module, '_client_initialized', False):
                 print(f"TTS Facade: Initializing '{provider_name}'...")
                 if not provider_module.initialize_client():
                     print(f"TTS Facade Warning: Failed to initialize '{provider_name}'.")
                     _current_provider_name = None
                     return False
        _current_provider_name = provider_name
        print(f"TTS Facade: Active provider set to '{_current_provider_name}'.")
        return True
    elif provider_name in SUPPORTED_PROVIDERS:
         print(f"TTS Facade Error: Provider '{provider_name}' supported but dependencies not met.")
         return False
    else:
        print(f"TTS Facade Error: Unknown provider '{provider_name}'.")
        return False

def get_current_provider():
    return _current_provider_name

def get_potentially_available_providers():
    return potentially_available_providers

def get_next_provider(current_name):
    potential_list = get_potentially_available_providers()
    if not potential_list: return None
    if current_name not in potential_list: return potential_list[0]
    try:
        current_index = potential_list.index(current_name)
        next_index = (current_index + 1) % len(potential_list)
        return potential_list[next_index]
    except Exception: return potential_list[0]

def speak_text(text_to_speak, **kwargs):
    global _current_provider_name
    runtime_available = get_runtime_available_providers()
    if not _current_provider_name or _current_provider_name not in runtime_available:
        print(f"TTS Facade: Current provider '{_current_provider_name}' invalid/unavailable at runtime.")
        new_provider_set = False
        if DEFAULT_PROVIDER in potentially_available_providers:
            print(f"TTS Facade: Trying default provider '{DEFAULT_PROVIDER}'.")
            if set_provider(DEFAULT_PROVIDER):
                 if _current_provider_name in get_runtime_available_providers():
                     new_provider_set = True
                 else:
                      _current_provider_name = None
        potential_list = get_potentially_available_providers()
        if not new_provider_set and potential_list:
             print(f"TTS Facade: Trying first potential provider '{potential_list[0]}'.")
             if set_provider(potential_list[0]):
                 if _current_provider_name in get_runtime_available_providers():
                     new_provider_set = True
                 else:
                      _current_provider_name = None
        if not _current_provider_name:
            fallback_say(text_to_speak, "No TTS provider is available or could be initialized.")
            return
    if _current_provider_name in tts_providers:
        provider_module = tts_providers[_current_provider_name]
        try:
            if _current_provider_name not in get_runtime_available_providers():
                 raise RuntimeError(f"Provider '{_current_provider_name}' became unavailable before speech call.")
            if hasattr(provider_module, 'stop_playback'):
                provider_module.stop_playback()
            provider_module.speak_text(text_to_speak, **kwargs)
        except AttributeError:
            fallback_say(text_to_speak, f"Provider '{_current_provider_name}' misconfigured (no speak_text/stop_playback).")
        except Exception as e:
            print(f"TTS Facade Error calling '{_current_provider_name}': {e}")
            fallback_say(text_to_speak, f"Error during speech with '{_current_provider_name}'.")
    else:
        fallback_say(text_to_speak, f"Selected provider '{_current_provider_name}' not loaded.")

def fallback_say(text, reason):
    print(f"TTS Facade: {reason}"); print("TTS Facade: Attempting system 'say' command fallback...")
    try:
        cmd = None
        if sys.platform == 'darwin': cmd = ['say', text]
        elif sys.platform == 'win32': print("TTS Facade: System 'say' fallback not directly supported on Windows."); return
        elif 'linux' in sys.platform:
            import shutil
            if shutil.which('spd-say'): cmd = ['spd-say', '--wait', text]
            elif shutil.which('espeak'): cmd = ['espeak', text]
            else: print("TTS Facade: No Linux TTS command found (spd-say, espeak)."); return
        if cmd: subprocess.run(cmd, check=True, timeout=30, capture_output=True); print("TTS Facade: System 'say' command executed.")
    except FileNotFoundError: print(f"TTS Facade Error: System TTS command not found.")
    except subprocess.TimeoutExpired: print("TTS Facade Error: System 'say' command timed out.")
    except Exception as say_e: print(f"TTS Facade Error: System 'say' command failed: {say_e}")

initial_provider = DEFAULT_PROVIDER if DEFAULT_PROVIDER in potentially_available_providers else (potentially_available_providers[0] if potentially_available_providers else None)
if initial_provider:
    print(f"TTS Facade: Setting initial provider to '{initial_provider}' (initialization may be deferred)...")
    _current_provider_name = initial_provider
else:
    print("TTS Facade Warning: No TTS providers potentially available on startup.")
    _current_provider_name = None