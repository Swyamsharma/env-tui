# EnvTUI - Environment Variable TUI Manager

A Textual-based Terminal User Interface (TUI) for viewing, filtering, editing, adding, and deleting system environment variables on Linux.

## Features

*   **List Variables:** Displays current environment variables in a scrollable table (Name, Value), sorted alphabetically.
*   **Live Filtering:** Filter the list by typing in the search bar (matches names and values, case-insensitive).
*   **View Details:** Select a variable (using arrow keys or mouse) to see its full name and value in the right-hand pane.
*   **Copy:**
    *   `n`: Copy selected variable's name.
    *   `v`: Copy selected variable's full value.
    *   `c`: Copy a shell `export VAR="VALUE"` command for the selected variable.
*   **Edit Variable (`e`):**
    *   Modify the value of the selected variable.
    *   Choose action:
        *   **Copy Cmd (Session):** Copy the `export` command for the *new* value (session only).
        *   **Update RC (Persistent):** Update/add the `export` command in your shell's configuration file (e.g., `.bashrc`, `.zshrc`). Requires a new shell session to take effect.
        *   **Launch Term (Session):** Launch a new terminal session with the variable updated.
        *   **Cancel:** Discard changes.
*   **Add Variable (`a`):**
    *   Define a new variable name and value.
    *   Choose action (similar to Edit): Copy Cmd, Update RC, Launch Term, Cancel.
*   **Delete Variable (`d`):**
    *   Select a variable and press `d` to initiate deletion.
    *   Confirm action:
        *   **Copy Cmd (Session):** Copy an `unset VAR` command (session only).
        *   **Update RC (Persistent):** Remove the `export` command from your shell's configuration file. Requires a new shell session.
        *   **Launch Term (Session):** Launch a new terminal session with the variable unset.
        *   **Cancel:** Keep the variable.
*   **Quit:** Exit using `q` or `Ctrl+C`.
*   **Clear Search:** Press `Escape` to clear the search input.
*   **Theme Persistence:** Remembers the last used theme (if switched via F1/Header).

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
    *   Use **Up/Down arrows** or mouse click to select variables in the left table. Details appear on the right.
    *   Type in the **Search bar** at the top to filter.
    *   Press **n**, **v**, or **c** to copy name, value, or export command for the selected variable.
    *   Press **e** to edit the selected variable's value.
    *   Press **a** to add a new variable.
    *   Press **d** to delete the selected variable (requires confirmation).
    *   Use the buttons in the Add/Edit/Delete panes or press **Enter** in input fields to proceed/confirm actions.
    *   Press **Escape** to clear the search bar or cancel Add/Edit/Delete modes.
    *   Press **q** or **Ctrl+C** to quit.

## Files

*   `env_tui.py`: Main application logic (Textual App class).
*   `ui.py`: Defines the layout and widgets using Textual Compose API.
*   `shell_utils.py`: Handles shell interactions (RC file updates, command generation, terminal launching).
*   `config.py`: Manages loading/saving application settings (like theme).
*   `env_tui.css`: Basic Textual CSS for styling.
*   `requirements.txt`: Lists required Python packages (`textual`, `pyperclip`).
*   `.gitignore`: Standard Python gitignore file.
*   `README.md`: This file.
