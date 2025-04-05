# ui/components.py
"""
Shared UI helper functions.
"""
import os
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize # Keep QSize if _load_icon uses it, otherwise remove

# Helper function
def _load_icon(icon_path_base, filename, size=None): # Receives resolved base path
    """Loads an icon using the provided base path."""
    # Ensure the base path is valid
    if not icon_path_base or not os.path.isdir(icon_path_base):
        print(f"Icon Load Warning: Invalid base path provided: {icon_path_base}")
        # Optionally return a default placeholder icon or None
        # return QIcon("path/to/placeholder.png")
        return None # Return None if base path is invalid

    try:
        # Use the provided base path directly
        path = os.path.join(icon_path_base, filename)
        if not os.path.exists(path):
            print(f"Icon Load Warning: Icon not found: {path}")
            return None
        # Return the QIcon object; size is set on the widget later
        return QIcon(path)
    except Exception as e:
        print(f"Error loading icon {filename} from {icon_path_base}: {e}")
        return None