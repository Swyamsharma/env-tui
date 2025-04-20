import os
import sys
from pathlib import Path

# --- Constants for Config ---
APP_NAME = "env_tui"
CONFIG_DIR_NAME = ".config" # Standard on Linux/macOS, use AppData on Windows
SETTINGS_FILE_NAME = "settings.txt" # File for theme name

def get_config_dir() -> Path:
    """Gets the application's configuration directory path (Linux/macOS)."""
    # Assume Linux/macOS standard: ~/.config/
    config_dir = Path.home() / CONFIG_DIR_NAME / APP_NAME
    # print(f"DEBUG: Config directory: {config_dir}") # Optional Debug
    return config_dir

def get_settings_file_path() -> Path:
    """Gets the full path to the settings configuration file."""
    path = get_config_dir() / SETTINGS_FILE_NAME
    # print(f"DEBUG: Settings file path: {path}") # Optional Debug
    return path

def load_theme_setting() -> str | None:
    """Loads the theme name setting from the config file. Returns None if not found or error."""
    print("DEBUG: load_theme_setting() called")
    settings_file = get_settings_file_path()
    try:
        if settings_file.exists():
            print(f"DEBUG: Settings file exists: {settings_file}")
            # Read the first line, expecting the theme name
            loaded_theme_lines = settings_file.read_text().strip().splitlines()
            if loaded_theme_lines:
                loaded_theme = loaded_theme_lines[0].strip() # Get first line and strip whitespace
                if loaded_theme: # Ensure it's not just whitespace
                    print(f"DEBUG: Read theme name from file: '{loaded_theme}'")
                    return loaded_theme
                else:
                    print("DEBUG: Settings file line is empty. Using default theme.")
            else:
                print("DEBUG: Settings file is empty. Using default theme.")
        else:
            print(f"DEBUG: Settings file does not exist: {settings_file}. Using default theme.")
    except Exception as e:
        print(f"ERROR: Could not load settings from {settings_file}: {e}")
        # Keep default theme if loading fails
    return None # Return None if no theme loaded or error

def save_theme_setting(theme_name: str | None) -> None:
    """Saves the current theme name setting to the config file."""
    print(f"DEBUG: save_theme_setting() called. Theme to save: '{theme_name}'")
    if not theme_name:
        # If the current theme is None or empty, we don't save.
        print("DEBUG: No specific theme name provided (using default/None). Nothing to save.")
        # Optionally, try deleting the file if it exists:
        # settings_file = get_settings_file_path()
        # if settings_file.exists():
        #     try:
        #         settings_file.unlink()
        #         print(f"DEBUG: Deleted settings file as theme was default: {settings_file}")
        #     except Exception as e:
        #         print(f"ERROR: Failed to delete settings file {settings_file}: {e}")
        return # Don't save if it's the default/None

    settings_file = get_settings_file_path()
    try:
        print(f"DEBUG: Ensuring config directory exists: {settings_file.parent}")
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: Writing theme name '{theme_name}' to {settings_file}")
        settings_file.write_text(theme_name) # Write only the theme name
        print(f"DEBUG: Successfully wrote settings to {settings_file}")
    except Exception as e:
        print(f"ERROR: Could not save settings to {settings_file}: {e}")
