# ui/components.py
"""
Shared UI helper functions.
"""
import os
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

def _load_icon(icon_path_base, filename, size=None):
    """Loads an icon using the provided base path."""
    if not icon_path_base or not os.path.isdir(icon_path_base):
        print(f"Icon Load Warning: Invalid base path provided: {icon_path_base}")
        return None 

    try:
        path = os.path.join(icon_path_base, filename)
        if not os.path.exists(path):
            print(f"Icon Load Warning: Icon not found: {path}")
            return None
        return QIcon(path)
    except Exception as e:
        print(f"Error loading icon {filename} from {icon_path_base}: {e}")
        return None