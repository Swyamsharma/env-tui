# EnvTUI - Environment Variable TUI Viewer

A simple Textual-based Terminal User Interface (TUI) for viewing and interacting with system environment variables on Linux.

## Features

*   **List Variables:** Displays all current environment variables in a scrollable table (Name, Value), sorted alphabetically by name.
*   **Live Filtering:** Filter the list by typing in the search bar. Matches against both variable names and values (case-insensitive).
*   **View Full Value:** Select a variable and press `Enter` to view its complete value in a modal pop-up (useful for long values like `PATH`).
*   **Copy Name:** Select a variable and press `n` to copy its name to the system clipboard.
*   **Copy Value:** Select a variable and press `v` to copy its full value to the system clipboard.
*   **Copy Export Statement:** Select a variable and press `c` to copy a correctly quoted `export VAR_NAME="VALUE"` statement to the system clipboard (uses `shlex.quote` for safety).
*   **Quit:** Exit the application using `q` or `Ctrl+C`.
*   **Clear Search:** Press `Escape` to clear the search input field and reset the filter.

## Requirements

*   Python 3.x
*   `pip` (Python package installer)
*   A clipboard utility recognized by `pyperclip` (e.g., `xclip` or `xsel` on Linux). If copy/paste doesn't work, you might need to install one:
    *   Debian/Ubuntu: `sudo apt-get install xclip`
    *   Arch Linux: `sudo pacman -S xclip`
    *   Fedora: `sudo dnf install xclip`

## Installation & Setup

1.  **Clone the repository (or download the files):**
    ```bash
    # If using git:
    # git clone <repository_url>
    # cd <repository_directory>

    # Or simply ensure env_tui.py, env_tui.css, and requirements.txt are in the same directory.
    ```

2.  **Create and activate a virtual environment (Recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(If you encountered clipboard errors previously, ensure `xclip` or `xsel` is installed as mentioned in Requirements.)*

## Usage

1.  **Activate the virtual environment (if you created one):**
    ```bash
    source .venv/bin/activate
    ```

2.  **Run the application:**
    ```bash
    python3 env_tui.py
    ```

3.  **Navigate and use features:**
    *   Use **Up/Down arrows** or **j/k** to scroll through the list.
    *   Type in the **Search bar** at the top to filter.
    *   Press **Enter** on a selected row to view the full value.
    *   Press **n** to copy the selected variable's name.
    *   Press **v** to copy the selected variable's value.
    *   Press **c** to copy the `export` statement for the selected variable.
    *   Press **Escape** to clear the search bar.
    *   Press **q** or **Ctrl+C** to quit.

## Files

*   `env_tui.py`: The main Python application script using Textual.
*   `env_tui.css`: Basic Textual CSS for styling the application.
*   `requirements.txt`: Lists the required Python packages (`textual`, `pyperclip`).
*   `README.md`: This file.
