#!/usr/bin/env python3
import os
import os.path # Added for expanduser
import shlex # For shell quoting
import pyperclip
import subprocess # For launching terminal
import sys # For platform detection
import shutil # For finding executables (shutil.which)
from pathlib import Path # Added for config path handling

from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Label
from textual.widgets._data_table import DuplicateKey
from textual.widgets.option_list import Option # Import Option
from textual.widgets import OptionList # Import OptionList - Though not directly used, good context
# REMOVED: from textual._theme import THEMES as AVAILABLE_THEMES


class EnvTuiApp(App):
    """A Textual app to view and filter environment variables."""

    # --- Constants for Config ---
    APP_NAME = "env_tui"
    CONFIG_DIR_NAME = ".config" # Standard on Linux/macOS, use AppData on Windows
    SETTINGS_FILE_NAME = "settings.txt" # New file for theme name

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("escape", "clear_search", "Clear Search"),
        ("n", "copy_name", "Copy Name"),
        ("v", "copy_value", "Copy Value"),
        ("c", "copy_export", "Copy Export"),
        ("e", "toggle_edit", "Edit Value"),
        ("a", "toggle_add", "Add Variable"), # Add binding
        # F1 for theme switching is usually handled by Header
    ]

    CSS_PATH = "env_tui.css"

    # State for add mode
    add_mode = reactive(False, layout=True)

    # State for edit mode
    edit_mode = reactive(False, layout=True)
    # Store the name of the variable being edited
    editing_var_name = reactive[str | None](None)

    # Reactive variable to store the content for the right pane
    selected_var_details = reactive(("", ""), layout=True)

    search_term = reactive("", layout=True)
    all_env_vars = dict(sorted(os.environ.items()))

    # --- Configuration File Helpers ---

    def _get_config_dir(self) -> Path:
        """Gets the application's configuration directory path."""
        if sys.platform == "win32":
            app_data = os.environ.get("APPDATA")
            base_path = Path(app_data) if app_data else Path.home() / f".{self.APP_NAME}" # Fallback
            config_dir = base_path / self.APP_NAME
        else:
            # Use ~/.config/ on Linux/macOS
            config_dir = Path.home() / self.CONFIG_DIR_NAME / self.APP_NAME
        # print(f"DEBUG: Config directory: {config_dir}") # Optional Debug
        return config_dir

    def _get_settings_file_path(self) -> Path:
        """Gets the full path to the settings configuration file."""
        path = self._get_config_dir() / self.SETTINGS_FILE_NAME
        # print(f"DEBUG: Settings file path: {path}") # Optional Debug
        return path

    def _load_settings(self) -> None:
        """Loads settings (like theme name) from the config file."""
        print("DEBUG: _load_settings() called")
        settings_file = self._get_settings_file_path()
        try:
            if settings_file.exists():
                print(f"DEBUG: Settings file exists: {settings_file}")
                # Read the first line, expecting the theme name
                loaded_theme_lines = settings_file.read_text().strip().splitlines()
                if loaded_theme_lines:
                    loaded_theme = loaded_theme_lines[0].strip() # Get first line and strip whitespace
                    if loaded_theme: # Ensure it's not just whitespace
                        print(f"DEBUG: Read theme name from file: '{loaded_theme}'")
                        # --- MODIFIED: Set theme directly without validation ---
                        print(f"DEBUG: Attempting to set self.theme = '{loaded_theme}'")
                        self.theme = loaded_theme # Set the app's theme attribute
                        # Textual will handle if the theme is invalid later
                    else:
                        print("DEBUG: Settings file line is empty. Using default theme.")
                else:
                    print("DEBUG: Settings file is empty. Using default theme.")
            else:
                print(f"DEBUG: Settings file does not exist: {settings_file}. Using default theme.")
        except Exception as e:
            print(f"ERROR: Could not load settings from {settings_file}: {e}")
            # Keep default theme if loading fails

        # Note: self.theme might be None here if no valid theme was loaded
        print(f"DEBUG: _load_settings() finished. Theme property is now: {self.theme!r}")


    def _save_settings(self) -> None:
        """Saves the current settings (like theme name) to the config file."""
        current_theme = self.theme # Get the currently active theme name
        print(f"DEBUG: _save_settings() called. Current self.theme: '{current_theme}'")
        if not current_theme:
            # If the current theme is None or empty (shouldn't be empty if set),
            # we can either delete the settings file or write nothing/default.
            # Let's just not save an empty/None theme name.
            print("DEBUG: No specific theme set (using default/None). Nothing to save.")
            # Optionally, try deleting the file if it exists:
            # settings_file = self._get_settings_file_path()
            # if settings_file.exists():
            #     try:
            #         settings_file.unlink()
            #         print(f"DEBUG: Deleted settings file as theme was default: {settings_file}")
            #     except Exception as e:
            #         print(f"ERROR: Failed to delete settings file {settings_file}: {e}")
            return # Don't save if it's the default/None

        settings_file = self._get_settings_file_path()
        try:
            print(f"DEBUG: Ensuring config directory exists: {settings_file.parent}")
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            print(f"DEBUG: Writing theme name '{current_theme}' to {settings_file}")
            settings_file.write_text(current_theme) # Write only the theme name
            print(f"DEBUG: Successfully wrote settings to {settings_file}")
        except Exception as e:
            print(f"ERROR: Could not save settings to {settings_file}: {e}")


    # --- App Lifecycle ---

    def __init__(self):
        """Initialize the app and load theme preference."""
        print("DEBUG: EnvTuiApp.__init__() started")
        # Call super first, THEN load settings which might set self.theme
        super().__init__()
        self._load_settings() # Load theme name from file and set self.theme
        print(f"DEBUG: EnvTuiApp.__init__() finished. Initial theme is '{self.theme}'")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        print("DEBUG: on_mount() called")
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Variable Name", "Value")
        # Defer the initial table population
        self.call_later(self.update_table)
        print("DEBUG: on_mount() finished, update_table scheduled")

    def on_unmount(self) -> None:
        """Called when the app is about to unmount (before exit)."""
        print("DEBUG: on_unmount() called")
        self._save_settings() # Save the current theme name
        print("DEBUG: on_unmount() finished after saving settings")
        # No need to call super().on_unmount() unless the base class requires it for cleanup

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        print("DEBUG: compose() called")
        yield Header() # Header provides F1 toggle by default
        yield Input(placeholder="Search variables (name or value)...", id="search-input")
        with Horizontal(id="main-container"): # Use Horizontal layout
            with ScrollableContainer(id="left-pane"):
                yield DataTable(id="env-table")
            with Vertical(id="right-pane"): # Use Vertical for right pane content
                yield Label("Select a variable", id="detail-name")
                # Container for viewing the value
                with ScrollableContainer(id="view-value-container"):
                    yield Static("", id="detail-value", expand=True)
                # Container for editing the value (initially hidden)
                with Vertical(id="edit-value-container", classes="hidden"):
                    yield Label("Editing:", id="edit-label") # Label for clarity
                    yield Input(value="", id="edit-input")
                    with Horizontal(id="edit-buttons"):
                        yield Button("Save (Copy Cmd)", variant="success", id="edit-save-copy")
                        yield Button("Save (Update RC)", variant="warning", id="edit-save-rc")
                        yield Button("Save & Launch Term", variant="primary", id="edit-save-launch") # Renamed Button
                        yield Button("Cancel", variant="error", id="edit-cancel")
                # Container for adding a new variable (initially hidden)
                with Vertical(id="add-value-container", classes="hidden"):
                    yield Label("Add New Variable", id="add-label")
                    yield Input(placeholder="Variable Name", id="add-name-input")
                    yield Input(placeholder="Variable Value", id="add-value-input")
                    with Horizontal(id="add-buttons"):
                         yield Button("Add (Copy Cmd)", variant="success", id="add-save-copy")
                         yield Button("Add (Update RC)", variant="warning", id="add-save-rc")
                         yield Button("Add & Launch Term", variant="primary", id="add-save-launch") # Renamed Button
                         yield Button("Cancel", variant="error", id="add-cancel")
        yield Footer()

    # --- update_table and other methods remain largely the same ---
    # (Ensure no other code relies on the old self.dark saving logic)

    def update_table(self) -> None:
        """Update the DataTable with filtered environment variables."""
        # print("DEBUG: update_table() called") # Optional: uncomment if needed, can be noisy
        try: # Add try/except block for better debugging if needed
            table = self.query_one(DataTable)
            current_cursor_row = table.cursor_row # Remember cursor position
            # Ensure left-pane exists before getting scroll_y
            left_pane = self.query_one("#left-pane", ScrollableContainer)
            current_scroll_y = left_pane.scroll_y

            table.clear(columns=False) # Clear rows before adding new ones

            search = self.search_term.lower()

            added_rows = []
            if not search:
                for name, value in self.all_env_vars.items():
                    display_value = (value[:70] + '...') if len(value) > 73 else value
                    table.add_row(name, display_value, key=name)
                    added_rows.append(name)
            else:
                for name, value in self.all_env_vars.items():
                    if search in name.lower() or search in value.lower():
                        display_value = (value[:70] + '...') if len(value) > 73 else value
                        table.add_row(name, display_value, key=name)
                        added_rows.append(name)

            # Try to restore cursor and scroll position if possible
            if added_rows:
                new_row_count = len(added_rows)
                target_row = min(current_cursor_row, new_row_count - 1)
                if target_row >= 0:
                    try:
                        table.move_cursor(row=target_row, animate=False)
                    except Exception:
                         pass # Ignore cursor move errors
                # Restore scroll position after rows are added
                self.call_later(left_pane.scroll_to, y=current_scroll_y, animate=False)

        except DuplicateKey as e:
            self.notify(f"Internal Error: Duplicate key '{e}' encountered during table update.", severity="error", title="Table Update Error", timeout=10)
            print(f"ERROR: DuplicateKey during update_table: {e}") # Also print to console
        except Exception as e:
            self.notify(f"Internal Error updating table: {e}", severity="error", title="Table Update Error", timeout=10)
            print(f"ERROR: Exception during update_table: {e}") # Also print to console


    # --- Watchers ---
    def watch_search_term(self, old_value: str, new_value: str) -> None:
        """Called when the search_term reactive variable changes."""
        # print("DEBUG: watch_search_term called") # Optional debug
        self.update_table()

    def watch_selected_var_details(self, old_value: tuple[str, str], new_value: tuple[str, str]) -> None:
        """Called when the selected variable details change."""
        # print("DEBUG: watch_selected_var_details called") # Optional debug
        name, value = new_value
        # Use query instead of query_one to avoid errors if widgets aren't ready/visible
        name_labels = self.query("#detail-name")
        value_statics = self.query("#detail-value")

        if name_labels and value_statics:
            name_label = name_labels[0]
            value_static = value_statics[0]
            # Always update the static view first
            if name:
                name_label.update(f"[b]{name}[/b]")
                value_static.update(value)
            else:
                name_label.update("Select a variable")
                value_static.update("")

            # If we are in edit mode AND this is the variable being edited, update Input
            if self.edit_mode and name == self.editing_var_name:
                edit_inputs = self.query("#edit-input")
                if edit_inputs:
                    edit_inputs[0].value = value # Update input field if needed


    def watch_edit_mode(self, old_value: bool, new_value: bool) -> None:
        """Show/hide edit widgets when edit_mode changes."""
        # print("DEBUG: watch_edit_mode called") # Optional debug
        editing = new_value
        # Use query to be safer during state transitions
        view_containers = self.query("#view-value-container")
        edit_containers = self.query("#edit-value-container")

        if not view_containers or not edit_containers:
            return # Widgets not ready yet

        view_container = view_containers[0]
        edit_container = edit_containers[0]

        view_container.set_class(editing, "hidden")
        edit_container.set_class(not editing, "hidden")

        if editing:
            # If entering edit mode, ensure a variable is selected
            name, value = self.selected_var_details
            if name:
                self.editing_var_name = name # Store the name being edited
                edit_inputs = self.query("#edit-input")
                edit_labels = self.query("#edit-label")
                if edit_inputs and edit_labels:
                    edit_input = edit_inputs[0]
                    edit_label = edit_labels[0]
                    edit_label.update(f"Editing: [b]{name}[/b]")
                    edit_input.value = value
                    self.set_timer(0.1, edit_input.focus) # Focus after a short delay
            else:
                # Cannot enter edit mode without selection
                self.notify("Select a variable to edit first.", severity="warning")
                # Schedule revert to avoid potential state conflicts during watcher execution
                self.call_later(setattr, self, "edit_mode", False)
        else:
            # Exiting edit mode
            self.editing_var_name = None


    def watch_add_mode(self, old_value: bool, new_value: bool) -> None:
        """Show/hide add widgets when add_mode changes."""
        # print("DEBUG: watch_add_mode called") # Optional debug
        adding = new_value
        # Use query for safety
        add_containers = self.query("#add-value-container")
        view_containers = self.query("#view-value-container")
        edit_containers = self.query("#edit-value-container")

        if not add_containers or not view_containers or not edit_containers:
            return # Widgets not ready

        add_container = add_containers[0]
        view_container = view_containers[0]
        edit_container = edit_containers[0]

        add_container.set_class(not adding, "hidden")

        if adding:
            # Clear selection display and hide view/edit panes
            # Defer this slightly in case selection watcher is also firing
            self.call_later(setattr, self, "selected_var_details", ("", ""))
            view_container.set_class(True, "hidden")
            edit_container.set_class(True, "hidden")
            # Clear inputs and focus on name input
            add_name_inputs = self.query("#add-name-input")
            add_value_inputs = self.query("#add-value-input")
            if add_name_inputs and add_value_inputs:
                add_name_input = add_name_inputs[0]
                add_value_input = add_value_inputs[0]
                add_name_input.value = ""
                add_value_input.value = ""
                self.set_timer(0.1, add_name_input.focus)
        else:
             # When exiting add mode, potentially show the view container again
             view_container.set_class(False, "hidden") # Show view container by default


    # --- Actions ---
    # (Actions remain the same as the previous version)
    def action_toggle_edit(self) -> None:
        """Toggle edit mode for the selected variable."""
        if self.add_mode: # Exit add mode if active
            self.add_mode = False
        if not self.selected_var_details[0]:
             self.notify("Select a variable to edit first.", severity="warning")
             return
        # Toggle edit mode (watcher will handle showing/hiding)
        self.edit_mode = not self.edit_mode

    def action_toggle_add(self) -> None:
        """Toggle add variable mode."""
        if self.edit_mode: # Exit edit mode if active
            self.edit_mode = False
        # Toggle add mode (watcher will handle showing/hiding)
        self.add_mode = not self.add_mode

    def action_quit(self) -> None:
        """Called when the user presses q or Ctrl+C."""
        print("DEBUG: action_quit called") # Optional debug
        self.exit() # This will trigger on_unmount where saving happens

    def action_clear_search(self) -> None:
        """Called when the user presses Escape."""
        try:
            search_input = self.query_one("#search-input", Input)
            search_input.value = ""
            # self.search_term is updated via on_input_changed
            search_input.focus() # Keep focus on input
            if self.edit_mode:
                self.edit_mode = False # Exit edit mode
            if self.add_mode:
                self.add_mode = False # Exit add mode
        except Exception as e:
            self.notify(f"Error clearing search: {e}", severity="error")


    def action_copy_name(self) -> None:
        """Copy the selected variable name to the clipboard."""
        var_name, _ = self.selected_var_details
        if not var_name:
             self.notify("No variable selected.", title="Copy Name", severity="warning")
             return

        try:
            pyperclip.copy(var_name)
            self.notify(f"Copied name: [b]{var_name}[/b]", title="Copy Name")
        except Exception as e:
            self.notify(f"Failed to copy name: {e}", title="Copy Error", severity="error")

    def action_copy_value(self) -> None:
        """Copy the selected variable's full value to the clipboard."""
        var_name, var_value = self.selected_var_details
        if not var_name:
             self.notify("No variable selected.", title="Copy Value", severity="warning")
             return
        # Ensure we get the potentially updated value from the dictionary
        current_value = self.all_env_vars.get(var_name, var_value) # Fallback just in case

        try:
            pyperclip.copy(current_value)
            display_value = (current_value[:50] + '...') if len(current_value) > 53 else current_value
            self.notify(f"Copied value for [b]{var_name}[/b]:\n{display_value}", title="Copy Value")
        except Exception as e:
            self.notify(f"Failed to copy value: {e}", title="Copy Error", severity="error")

    def action_copy_export(self) -> None:
        """Copy the selected variable as a shell export statement."""
        var_name, var_value = self.selected_var_details
        if not var_name:
             self.notify("No variable selected.", title="Copy Export", severity="warning")
             return
        # Ensure we get the potentially updated value from the dictionary
        current_value = self.all_env_vars.get(var_name, var_value) # Fallback just in case

        try:
            quoted_value = shlex.quote(current_value)
            export_statement = f'export {var_name}={quoted_value}'
            pyperclip.copy(export_statement)
            self.notify(f"Copied export statement for [b]{var_name}[/b]", title="Copy Export")
        except Exception as e:
            self.notify(f"Failed to copy export statement: {e}", title="Copy Error", severity="error")


    # --- Helper Methods ---
    # (_get_shell_config_file and _save_variable remain the same)
    def _get_shell_config_file(self) -> str | None:
        """Try to determine the user's shell configuration file."""
        shell = os.environ.get("SHELL", "")
        config_file = None # Initialize
        if "bash" in shell:
            # Prefer .bashrc, but check existence of .bash_profile as well
            bashrc = Path.home() / ".bashrc"
            bash_profile = Path.home() / ".bash_profile"
            if bashrc.exists():
                config_file = str(bashrc)
            elif bash_profile.exists():
                 config_file = str(bash_profile)
            else:
                 # Default to .bashrc even if not existing yet, we might create it
                 config_file = str(bashrc)

        elif "zsh" in shell:
            # Standard zsh config file
            config_file = "~/.zshrc"
        elif "fish" in shell:
             # Standard fish config file location
             config_file = "~/.config/fish/config.fish"
        else:
             # Fallback or default if shell is unknown
             # Using .profile might be a safer general fallback
             profile = Path.home() / ".profile"
             if profile.exists():
                  config_file = str(profile)
             # else: No clear fallback, return None

        if config_file:
            return os.path.expanduser(config_file) # Expand ~
        return None

    def _save_variable(self, var_name: str, new_value: str, action_button_id: str, is_new: bool = False) -> None:
        """Handles the common logic for saving/adding a variable based on the button pressed."""

        # Determine action type from button ID
        update_rc = action_button_id in ("edit-save-rc", "add-save-rc")
        launch_terminal = action_button_id in ("edit-save-launch", "add-save-launch")

        # 1. Update internal dictionary
        self.all_env_vars[var_name] = new_value
        # Re-sort dictionary after adding
        if is_new:
            self.all_env_vars = dict(sorted(self.all_env_vars.items()))

        # 2. Update the reactive variable to refresh display (if editing)
        #    or clear display (if adding, as add_mode watcher handles hiding)
        if not is_new:
             self.selected_var_details = (var_name, new_value)
        else:
             self.selected_var_details = ("", "")

        # 3. Update the table display
        self.update_table() # Full update is easier for adding/sorting

        # 4. Try to move cursor AFTER update_table finishes (use call_later)
        def move_cursor_post_update():
            try:
                table = self.query_one(DataTable)
                row_index = table.get_row_index(var_name)
                table.move_cursor(row=row_index, animate=True)
                if not is_new:
                    self.selected_var_details = (var_name, new_value)
            except (KeyError, LookupError):
                pass # Key might not be in table if filtering is active, or table is empty
            except Exception as e:
                print(f"Error moving cursor post-update: {e}") # Log other errors
        self.call_later(move_cursor_post_update)

        # 5. Construct export command
        quoted_value = shlex.quote(new_value)
        export_cmd = f'export {var_name}={quoted_value}'
        # windows_set_cmd is no longer needed

        # 6. Perform copy, RC update, or launch terminal action
        action_verb = "Added" if is_new else "Updated"

        if launch_terminal: # Handle Launch Terminal (Linux Only)
            shell_path = os.environ.get("SHELL")
            if not shell_path:
                shell_path = shutil.which("sh") # Basic fallback
            if not shell_path:
                 self.notify("Could not determine SHELL path. Cannot launch terminal.",
                             title="Launch Error", severity="error")
                 return

            terminal_cmd_list = []
            found_terminal = False
            # ==============================================================
            # MODIFIED: Add 'cd / &&' to change directory before exec
            # ==============================================================
            internal_command = f"{export_cmd}; cd ~ && exec \"{shell_path}\" -l"
            # ==============================================================

            try:
                # --- Simplified Linux Terminal Detection ---
                terminals_to_try = [
                    "gnome-terminal", "konsole", "kitty", "alacritty",
                    "terminator", "xfce4-terminal", "lxterminal", "xterm"
                ]

                for term_exe in terminals_to_try:
                    full_path = shutil.which(term_exe)
                    if full_path:
                        # Construct the command list based on common patterns
                        if term_exe in ["gnome-terminal", "terminator", "xfce4-terminal", "lxterminal"]:
                            terminal_cmd_list = [full_path, "--", shell_path, "-c", internal_command]
                        elif term_exe in ["konsole", "alacritty", "xterm"]:
                            terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                        elif term_exe == "kitty":
                            terminal_cmd_list = [full_path, shell_path, "-c", internal_command]
                        else: # Default fallback attempt
                             terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]

                        found_terminal = True
                        print(f"DEBUG: Found terminal: {full_path}. Launch command: {' '.join(terminal_cmd_list)}") # Debug output
                        break # Stop searching

                if not found_terminal:
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Could not find a known terminal emulator.\n"
                        f"(Tried: {', '.join(terminals_to_try)}).\n"
                        f"Please install one or launch manually.",
                        title="Launch Error", severity="warning", timeout=12
                    )
                    return # Don't proceed if no terminal found

                # --- Launch the Terminal ---
                if terminal_cmd_list: # Should always be true if found_terminal is true
                    subprocess.Popen(terminal_cmd_list)
                    term_name = terminal_cmd_list[0]
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Attempting to launch '{term_name}' in '/' with the variable set.",
                        title="Launching Terminal", timeout=12
                    )
                # No else needed here as we return above if not found_terminal

            except FileNotFoundError:
                 # This error means shutil.which found it, but Popen failed
                 term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal"
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Found terminal '{term_name}' but failed to execute it.\n"
                    f"Check path/permissions or try installing another terminal.",
                    title="Launch Execution Error", severity="error", timeout=12
                )
            except Exception as e:
                 # Generic error during Popen or command construction
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Failed to launch new terminal: {e}\n"
                    f"Attempted command: {' '.join(map(shlex.quote, terminal_cmd_list)) if terminal_cmd_list else 'N/A'}",
                    title="Launch Error", severity="error", timeout=15
                )

        elif not update_rc: # Save Copy Cmd
            # --- Simplified for Linux: only export_cmd needed ---
            shell_type = "shell"
            try:
                pyperclip.copy(export_cmd)
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Run in your {shell_type} (copied to clipboard):\n"
                    f"[i]{export_cmd}[/i]",
                    title=f"Variable {action_verb}", timeout=10
                )
            except Exception as e:
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Run in your {shell_type}:\n"
                    f"[i]{export_cmd}[/i]\n"
                    f"(Copy failed: {e})",
                    title=f"Variable {action_verb}", timeout=10, severity="warning"
                )
        else: # Save Update RC (Linux Only)
            # --- No changes needed here, already Linux focused ---
            config_file = self._get_shell_config_file()
            if config_file:
                config_path = Path(config_file) # Use Path object
                config_dir = config_path.parent

                try:
                    # Ensure directory exists or create it
                    config_dir.mkdir(parents=True, exist_ok=True)

                    lines = []
                    updated_existing_rc = False
                    search_prefix = f"export {var_name}=" # Look for existing export
                    comment_line = f"\n# Added/Updated by EnvTuiApp" # Add newline before comment

                    if config_path.exists():
                        lines = config_path.read_text().splitlines()

                    new_lines = []
                    found_in_rc = False
                    i = 0
                    while i < len(lines):
                        line = lines[i]
                        stripped_line = line.strip()
                        if stripped_line.startswith(search_prefix):
                            prev_comment_found = False
                            for j in range(i - 1, -1, -1):
                                prev_line = lines[j].strip()
                                if prev_line == comment_line.strip():
                                    prev_comment_found = True
                                    break
                                elif prev_line:
                                    break
                            if not prev_comment_found:
                                new_lines.append(comment_line)
                            new_lines.append(export_cmd)
                            found_in_rc = True
                            i += 1
                            continue
                        new_lines.append(line)
                        i += 1

                    if not found_in_rc:
                        if new_lines and new_lines[-1]:
                            new_lines.append("")
                        new_lines.append(comment_line.strip())
                        new_lines.append(export_cmd)

                    config_path.write_text("\n".join(new_lines) + "\n")

                    action_desc = "Updated existing export" if found_in_rc else "Appended export command"
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"{action_desc} in:\n[i]{config_file}[/i]\n"
                        f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions.",
                        title="Config File Updated", timeout=12
                    )
                except Exception as e:
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Failed to write to config file [i]{config_file}[/i]:\n{e}",
                        title="Config Update Error", severity="error", timeout=12
                    )
            else: # Could not determine shell config file
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Could not determine shell config file (SHELL={os.environ.get('SHELL', 'Not set')}). Cannot update RC file.",
                    title="Config Update Error", severity="error", timeout=10
                )


    # --- Event Handlers ---
    # (on_button_pressed, on_input_changed, on_input_submitted,
    #  on_data_table_row_selected, on_data_table_row_highlighted remain the same)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks for Save/Cancel."""
        button_id = event.button.id

        # --- Cancel Actions ---
        if button_id == "edit-cancel":
            self.edit_mode = False
            # Re-select the variable to restore display
            current_name, _ = self.selected_var_details # Get potentially stale value
            if current_name:
                 # Trigger watcher with original value from dictionary
                 self.selected_var_details = (current_name, self.all_env_vars.get(current_name, ""))
            return
        if button_id == "add-cancel":
            self.add_mode = False
            # Might want to re-select last selected variable if applicable, or just clear
            # self.selected_var_details = ("", "") # Ensure details pane is cleared
            return

        # --- Edit Save Actions ---
        if button_id in ("edit-save-copy", "edit-save-rc", "edit-save-launch"): # Added launch ID
            if not self.editing_var_name:
                self.notify("Error: No variable was being edited.", severity="error")
                self.edit_mode = False
                return

            edit_inputs = self.query("#edit-input")
            if not edit_inputs: return # Should not happen if button is visible
            edit_input = edit_inputs[0]

            new_value = edit_input.value
            var_name = self.editing_var_name # Use the stored name being edited

            # Perform the update and notification
            self._save_variable(var_name, new_value, button_id, is_new=False)
            self.edit_mode = False # Exit edit mode

        # --- Add Save Actions ---
        elif button_id in ("add-save-copy", "add-save-rc", "add-save-launch"): # Added launch ID
            name_inputs = self.query("#add-name-input")
            value_inputs = self.query("#add-value-input")
            if not name_inputs or not value_inputs: return # Should not happen

            name_input = name_inputs[0]
            value_input = value_inputs[0]

            var_name = name_input.value.strip()
            new_value = value_input.value # Keep original spacing for value

            # Basic validation
            if not var_name:
                self.notify("Variable name cannot be empty.", severity="error", title="Add Error")
                name_input.focus()
                return
            # Simple identifier check (doesn't cover all shell rules but is a good start)
            if not var_name.isidentifier() or var_name[0].isdigit():
                 self.notify(f"Invalid variable name: '{var_name}'.\nMust be letters, digits, underscores (not starting with digit).", severity="error", title="Add Error")
                 name_input.focus()
                 return
            if var_name in self.all_env_vars:
                 self.notify(f"Variable '{var_name}' already exists. Use Edit (e) instead.", severity="warning", title="Add Error")
                 name_input.focus()
                 return

            # Perform the add and notification
            self._save_variable(var_name, new_value, button_id, is_new=True)
            self.add_mode = False # Exit add mode


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search input field."""
        if event.input.id == "search-input":
            self.search_term = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submission in the input fields (e.g., Enter)."""
        try:
            if event.input.id == "search-input":
                # Move focus to the table when submitting search
                table = self.query_one(DataTable)
                if table.row_count > 0:
                    table.focus()
            elif event.input.id == "edit-input":
                # If enter is pressed in edit input, treat it like the first save button (Copy Cmd)
                save_button = self.query_one("#edit-save-copy", Button)
                self.on_button_pressed(Button.Pressed(save_button))
            elif event.input.id == "add-value-input":
                # If enter is pressed in add value input, treat it like the first add button (Copy Cmd)
                save_button = self.query_one("#add-save-copy", Button)
                self.on_button_pressed(Button.Pressed(save_button))
            elif event.input.id == "add-name-input":
                # If enter is pressed in add name input, move focus to value input
                self.query_one("#add-value-input", Input).focus()
        except Exception as e:
            self.notify(f"Error handling input submit: {e}", severity="error")


    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable (mouse click or Enter)."""
        # Exit add/edit mode if a row is selected by the user
        if self.add_mode:
            self.add_mode = False
        if self.edit_mode:
            self.edit_mode = False

        row_key = event.row_key
        if row_key is not None and row_key.value is not None:
            var_name = str(row_key.value)
            var_value = self.all_env_vars.get(var_name, "<Not Found>")
            self.selected_var_details = (var_name, var_value)
        else:
             # This might happen if table is cleared while selection event is processed
             self.selected_var_details = ("", "") # Clear details if selection is lost or invalid

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update details view on highlight (keyboard navigation updates)."""
         # Only update if not in edit or add mode, to avoid flickering
        if not self.edit_mode and not self.add_mode:
            row_key = event.row_key
            if row_key is not None and row_key.value is not None:
                var_name = str(row_key.value)
                var_value = self.all_env_vars.get(var_name, "<Not Found>")
                # Update reactive var directly to trigger watcher
                # Check if it actually changed to prevent redundant updates
                if self.selected_var_details != (var_name, var_value):
                    self.selected_var_details = (var_name, var_value)
            elif self.selected_var_details != ("", ""): # Clear only if needed
                self.selected_var_details = ("", "")


if __name__ == "__main__":
    app = EnvTuiApp()
    app.run()