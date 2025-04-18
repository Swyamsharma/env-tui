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
        ("a", "toggle_add", "Add Variable"),
        ("d", "request_delete", "Delete Variable"), # Add delete binding
        # F1 for theme switching is usually handled by Header
    ]

    CSS_PATH = "env_tui.css"

    # State for add mode
    add_mode = reactive(False, layout=True)

    # State for edit mode
    edit_mode = reactive(False, layout=True)
    # State for delete mode
    delete_mode = reactive(False, layout=True)
    # Store the name of the variable being edited or deleted
    editing_var_name = reactive[str | None](None)
    deleting_var_name = reactive[str | None](None) # Added for delete confirmation

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
                        yield Button("Copy Cmd (Session)", variant="success", id="edit-save-copy")
                        yield Button("Update RC (Persistent)", variant="warning", id="edit-save-rc")
                        yield Button("Launch Term (Session)", variant="primary", id="edit-save-launch")
                        yield Button("Cancel", variant="error", id="edit-cancel")
                # Container for adding a new variable (initially hidden)
                with Vertical(id="add-value-container", classes="hidden"):
                    yield Label("Add New Variable", id="add-label")
                    yield Input(placeholder="Variable Name", id="add-name-input")
                    yield Input(placeholder="Variable Value", id="add-value-input")
                    with Horizontal(id="add-buttons"):
                         yield Button("Copy Cmd (Session)", variant="success", id="add-save-copy")
                         yield Button("Update RC (Persistent)", variant="warning", id="add-save-rc")
                         yield Button("Launch Term (Session)", variant="primary", id="add-save-launch")
                         yield Button("Cancel", variant="error", id="add-cancel")
                # Container for confirming deletion (initially hidden)
                with Vertical(id="delete-confirm-container", classes="hidden"):
                    yield Label("Confirm Delete:", id="delete-label")
                    with Horizontal(id="delete-buttons"):
                        yield Button("Copy Cmd (Session)", variant="success", id="delete-confirm-copy")
                        yield Button("Update RC (Persistent)", variant="warning", id="delete-confirm-rc")
                        yield Button("Launch Term (Session)", variant="primary", id="delete-confirm-launch")
                        yield Button("Cancel", variant="error", id="delete-cancel")
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
                    # Use the value from the internal dict for consistency
                    edit_input.value = self.all_env_vars.get(name, "")
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
             # Only show view if not entering delete mode immediately after
             if not self.delete_mode:
                 view_container.set_class(False, "hidden") # Show view container by default

    def watch_delete_mode(self, old_value: bool, new_value: bool) -> None:
        """Show/hide delete confirmation widgets when delete_mode changes."""
        # print("DEBUG: watch_delete_mode called") # Optional debug
        deleting = new_value
        # Use query for safety
        delete_containers = self.query("#delete-confirm-container")
        view_containers = self.query("#view-value-container")
        edit_containers = self.query("#edit-value-container")
        add_containers = self.query("#add-value-container")

        if not delete_containers or not view_containers or not edit_containers or not add_containers:
            return # Widgets not ready

        delete_container = delete_containers[0]
        view_container = view_containers[0]
        edit_container = edit_containers[0]
        add_container = add_containers[0]

        delete_container.set_class(not deleting, "hidden")

        if deleting:
            # Hide other panes
            view_container.set_class(True, "hidden")
            edit_container.set_class(True, "hidden")
            add_container.set_class(True, "hidden")

            # Update label
            delete_labels = self.query("#delete-label")
            if delete_labels and self.deleting_var_name:
                delete_labels[0].update(f"Delete [b]{self.deleting_var_name}[/b]? This action has consequences.")
                # Optionally focus the cancel button by default
                self.set_timer(0.1, lambda: self.query_one("#delete-cancel", Button).focus())
        else:
            # Exiting delete mode
            self.deleting_var_name = None
            # Show the view container again by default, unless edit/add mode is active
            if not self.edit_mode and not self.add_mode:
                view_container.set_class(False, "hidden")


    # --- Actions ---
    def action_toggle_edit(self) -> None:
        """Toggle edit mode for the selected variable."""
        if self.add_mode: # Exit add mode if active
            self.add_mode = False
        if self.delete_mode: # Exit delete mode if active
            self.delete_mode = False
        if not self.selected_var_details[0]:
             self.notify("Select a variable to edit first.", severity="warning")
             return
        # Toggle edit mode (watcher will handle showing/hiding)
        self.edit_mode = not self.edit_mode

    def action_toggle_add(self) -> None:
        """Toggle add variable mode."""
        if self.edit_mode: # Exit edit mode if active
            self.edit_mode = False
        if self.delete_mode: # Exit delete mode if active
            self.delete_mode = False
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
            if self.delete_mode:
                self.delete_mode = False # Exit delete mode
        except Exception as e:
            self.notify(f"Error clearing search: {e}", severity="error")

    def action_request_delete(self) -> None:
        """Enter delete confirmation mode for the selected variable."""
        if self.edit_mode: # Exit edit mode if active
            self.edit_mode = False
        if self.add_mode: # Exit add mode if active
            self.add_mode = False

        var_name, _ = self.selected_var_details
        if not var_name:
            self.notify("Select a variable to delete first.", severity="warning")
            return

        # Enter delete mode (watcher will handle showing/hiding)
        self.deleting_var_name = var_name # Store the name to be deleted
        self.delete_mode = True


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

    def _delete_variable(self, var_name: str, action_button_id: str) -> None:
        """Handles the common logic for deleting a variable based on the button pressed."""
        # Check if variable exists *before* trying to delete
        # We use the current TUI state for this check, even if we don't modify it later
        # Note: If update_rc is false, self.all_env_vars won't be modified,
        # but we still need the original value for checks/actions.
        if var_name not in self.all_env_vars:
            self.notify(f"Variable '{var_name}' not found for deletion.", severity="error")
            return

        # Determine action type from button ID
        update_rc = action_button_id == "delete-confirm-rc"
        launch_terminal = action_button_id == "delete-confirm-launch"
        copy_cmd_only = not update_rc and not launch_terminal # If it's not RC or Launch, it's Copy

        tui_updated = False # Flag to track if internal state changed

        # 1. Remove from internal dictionary ONLY if updating RC
        if update_rc:
            # We know var_name exists from the check above
            del self.all_env_vars[var_name]
            tui_updated = True
            # No need to re-sort, just remove

        # 2. Clear the reactive variable to refresh display ONLY if updating RC
        #    If not updating RC, we keep the selection active.
        if update_rc:
            self.selected_var_details = ("", "")

        # 3. Update the table display ONLY if updating RC
        if update_rc:
            self.update_table() # Full update to remove the row

        # 4. Construct unset command (always needed for actions)
        unset_cmd = f'unset {var_name}' # No quoting needed for unset

        # 5. Perform copy, RC update, or launch terminal action
        action_verb = "Deleted" if tui_updated else "Prepared delete action for"

        if launch_terminal: # Handle Launch Terminal (Linux Only)
            # --- Terminal Launch Logic ---
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
            # MODIFIED: Use unset command and change directory before exec (Removed -l)
            # ==============================================================
            internal_command = f"{unset_cmd}; cd ~ && exec \"{shell_path}\""
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
                if terminal_cmd_list:
                    subprocess.Popen(terminal_cmd_list)
                    term_name = terminal_cmd_list[0]
                    # Modify notification based on whether TUI was updated
                    tui_msg = "internally and TUI updated." if tui_updated else "internally (TUI not updated)."
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Attempting to launch '{term_name}' in '~' with the variable unset.",
                        title="Launching Terminal (Session)", timeout=12
                    )

            except FileNotFoundError:
                tui_msg = "internally (TUI not updated)." # TUI definitely not updated if launch failed
                term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal" # Fixed indentation
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Found terminal '{term_name}' but failed to execute it.\n"
                    f"Check path/permissions or try installing another terminal.",
                    title="Launch Execution Error", severity="error", timeout=12
                )
            except Exception as e:
                 tui_msg = "internally (TUI not updated)." # TUI definitely not updated if launch failed
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Failed to launch new terminal: {e}\n"
                    f"Attempted command: {' '.join(map(shlex.quote, terminal_cmd_list)) if terminal_cmd_list else 'N/A'}",
                    title="Launch Error", severity="error", timeout=15
                )

        elif copy_cmd_only: # Delete Copy Cmd
            shell_type = "shell"
            tui_msg = "internally (TUI not updated)."
            try:
                pyperclip.copy(unset_cmd)
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Run in your {shell_type} (copied to clipboard):\n"
                    f"[i]{unset_cmd}[/i]",
                    title=f"Unset Command Copied (Session)", timeout=10
                )
            except Exception as e:
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Run in your {shell_type}:\n"
                    f"[i]{unset_cmd}[/i]\n"
                    f"(Copy failed: {e})",
                    title=f"Unset Command Copy Failed", timeout=10, severity="warning"
                )
        elif update_rc: # Delete Update RC (Linux Only) - This case must be last now
            config_file = self._get_shell_config_file()
            if config_file:
                config_path = Path(config_file)
                config_dir = config_path.parent

                try:
                    # Ensure directory exists
                    config_dir.mkdir(parents=True, exist_ok=True)

                    tui_msg = "internally and TUI updated." # TUI is updated in this branch
                    if not config_path.exists():
                        self.notify(
                            f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                            f"Config file [i]{config_file}[/i] does not exist. Cannot remove variable.",
                            title="Config Update Info", severity="info", timeout=10
                        )
                        return # Nothing to remove if file doesn't exist

                    lines = config_path.read_text().splitlines()
                    new_lines = []
                    found_and_removed = False
                    search_prefix = f"export {var_name}="
                    comment_prefix = f"# Added/Updated by EnvTuiApp" # Comment to potentially remove

                    i = 0
                    while i < len(lines):
                        line = lines[i]
                        stripped_line = line.strip()

                        # Check if the current line is the export command we want to remove
                        if stripped_line.startswith(search_prefix):
                            # Check if the *previous* line was the EnvTuiApp comment
                            if i > 0 and lines[i-1].strip() == comment_prefix:
                                # If the previous line in new_lines is the comment, remove it
                                if new_lines and new_lines[-1].strip() == comment_prefix:
                                    new_lines.pop()
                                    # Potentially remove preceding blank line if it exists now
                                    if new_lines and not new_lines[-1].strip():
                                        new_lines.pop()

                            found_and_removed = True
                            i += 1 # Skip this line (don't add it to new_lines)
                            continue # Move to the next line in the original list

                        # Check if the current line is an `unset` command for this var (less likely)
                        # You might want to remove `unset VAR` lines added by previous versions/logic
                        # if stripped_line == f"unset {var_name}":
                        #     # Similar logic to remove preceding comment if desired
                        #     found_and_removed = True # Mark as handled
                        #     i += 1
                        #     continue

                        # Otherwise, keep the line
                        new_lines.append(line)
                        i += 1


                    if found_and_removed:
                        # Write the modified content back
                        config_path.write_text("\n".join(new_lines) + "\n")
                        self.notify(
                            f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                            f"Removed export command from:\n[i]{config_file}[/i]\n"
                            f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions.",
                            title="Config File Updated (Persistent)", timeout=12
                        )
                    else:
                        # Variable wasn't found in the RC file
                        self.notify(
                            f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                            f"Variable export not found in [i]{config_file}[/i]. No changes made to file.",
                            title="Config Update Info", severity="info", timeout=10
                        )

                except Exception as e:
                    # If RC update fails, TUI state is still changed, reflect that
                    tui_msg = "internally and TUI updated, but"
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Failed to update config file [i]{config_file}[/i]:\n{e}",
                        title="Config Update Error", severity="error", timeout=12
                    )
            else: # Could not determine shell config file
                # If RC update fails, TUI state is still changed, reflect that
                tui_msg = "internally and TUI updated, but"
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Could not determine shell config file (SHELL={os.environ.get('SHELL', 'Not set')}). Cannot update RC file.",
                    title="Config Update Error", severity="error", timeout=10
                )


    # (_get_shell_config_file remains the same)
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
        copy_cmd_only = not update_rc and not launch_terminal

        tui_updated = False # Flag to track if internal state changed

        # 1. Update internal dictionary ONLY if updating RC
        if update_rc:
            self.all_env_vars[var_name] = new_value
            tui_updated = True
            # Re-sort dictionary after adding if it was a new variable
            if is_new:
                self.all_env_vars = dict(sorted(self.all_env_vars.items()))

        # 2. Update the reactive variable to refresh display ONLY if updating RC
        if update_rc:
            if not is_new:
                 # If editing, update the details pane
                 self.selected_var_details = (var_name, new_value)
            else:
                 # If adding, clear the details pane (add mode watcher handles hiding)
                 self.selected_var_details = ("", "")
        # If not updating RC, keep the current selection active

        # 3. Update the table display ONLY if updating RC
        if update_rc:
            self.update_table() # Full update is easier for adding/sorting

        # 4. Try to move cursor AFTER update_table finishes ONLY if updating RC
        if update_rc:
            def move_cursor_post_update():
                try:
                    table = self.query_one(DataTable)
                    row_index = table.get_row_index(var_name)
                    table.move_cursor(row=row_index, animate=True)
                    # Re-select after moving cursor if editing via RC update
                    if not is_new:
                        self.selected_var_details = (var_name, new_value)
                except (KeyError, LookupError):
                    pass # Key might not be in table if filtering is active, or table is empty
                except Exception as e:
                    print(f"Error moving cursor post-update: {e}") # Log other errors
            self.call_later(move_cursor_post_update)

        # 5. Construct export command (always needed)
        quoted_value = shlex.quote(new_value)
        export_cmd = f'export {var_name}={quoted_value}'
        # windows_set_cmd is no longer needed

        # 6. Perform copy, RC update, or launch terminal action
        add_or_update = "Added" if is_new else "Updated"
        action_verb = add_or_update if tui_updated else f"Prepared {add_or_update.lower()} action for"


        if launch_terminal: # Handle Launch Terminal (Linux Only)
            # --- Terminal Launch Logic ---
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
            # MODIFIED: Add 'cd ~ &&' to change directory before exec (Removed -l)
            # ==============================================================
            internal_command = f"{export_cmd}; cd ~ && exec \"{shell_path}\""
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
                    # Notification if terminal not found (TUI state unchanged)
                    tui_msg = "internally (TUI not updated)."
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
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
                    # Modify notification based on whether TUI was updated
                    tui_msg = "internally and TUI updated." if tui_updated else "internally (TUI not updated)."
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Attempting to launch '{term_name}' in '~' with the variable set.",
                        title="Launching Terminal (Session)", timeout=12
                    )
                # No else needed here as we return above if not found_terminal

            except FileNotFoundError:
                tui_msg = "internally (TUI not updated)." # TUI definitely not updated if launch failed
                term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal"
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Found terminal '{term_name}' but failed to execute it.\n"
                    f"Check path/permissions or try installing another terminal.",
                    title="Launch Execution Error", severity="error", timeout=12
                )
            except Exception as e:
                 tui_msg = "internally (TUI not updated)." # TUI definitely not updated if launch failed
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Failed to launch new terminal: {e}\n"
                    f"Attempted command: {' '.join(map(shlex.quote, terminal_cmd_list)) if terminal_cmd_list else 'N/A'}",
                    title="Launch Error", severity="error", timeout=15
                )

        elif copy_cmd_only: # Save Copy Cmd
            # --- Simplified for Linux: only export_cmd needed ---
            shell_type = "shell"
            tui_msg = "internally (TUI not updated)."
            try:
                pyperclip.copy(export_cmd)
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Run in your {shell_type} (copied to clipboard):\n"
                    f"[i]{export_cmd}[/i]",
                    title=f"Export Command Copied (Session)", timeout=10
                )
            except Exception as e:
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Run in your {shell_type}:\n"
                    f"[i]{export_cmd}[/i]\n"
                    f"(Copy failed: {e})",
                    title=f"Export Command Copy Failed", timeout=10, severity="warning"
                )
        elif update_rc: # Save Update RC (Linux Only) - Must be last case
            # --- RC Update Logic ---
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
                            # Check if the *previous* line was the EnvTuiApp comment
                            prev_comment_found = False
                            for j in range(i - 1, -1, -1):
                                prev_line = lines[j].strip()
                                if prev_line == comment_line.strip():
                                    prev_comment_found = True
                                    break
                                elif prev_line: # Stop if we hit non-empty, non-comment line
                                    break
                            # Add comment if not found immediately before
                            if not prev_comment_found:
                                new_lines.append(comment_line.strip()) # Add comment without leading newline if inserting
                            new_lines.append(export_cmd) # Add the updated export command
                            found_in_rc = True
                            updated_existing_rc = True # Mark that we updated an existing line
                            i += 1 # Skip the old line
                            continue # Continue to next line
                        new_lines.append(line)
                        i += 1

                    if not found_in_rc:
                        # Append if not found
                        if new_lines and new_lines[-1]: # Add blank line if needed
                            new_lines.append("")
                        new_lines.append(comment_line.strip())
                        new_lines.append(export_cmd)

                    config_path.write_text("\n".join(new_lines) + "\n")

                    action_desc = "Updated existing export" if updated_existing_rc else "Appended export command"
                    tui_msg = "internally and TUI updated." # TUI is updated in this branch
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"{action_desc} in:\n[i]{config_file}[/i]\n"
                        f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions.",
                        title="Config File Updated (Persistent)", timeout=12
                    )
                except Exception as e:
                    # If RC update fails, TUI state is still changed, reflect that
                    tui_msg = "internally and TUI updated, but"
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Failed to write to config file [i]{config_file}[/i]:\n{e}",
                        title="Config Update Error", severity="error", timeout=12
                    )
            else: # Could not determine shell config file
                # If RC update fails, TUI state is still changed, reflect that
                tui_msg = "internally and TUI updated, but"
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
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
            # Re-select the variable to restore display (using potentially stale value is ok here)
            current_name, _ = self.selected_var_details
            if current_name:
                 # Trigger watcher with original value from dictionary
                 original_value = self.all_env_vars.get(current_name, "")
                 self.selected_var_details = (current_name, original_value)
            return
        if button_id == "add-cancel":
            self.add_mode = False
            # Might want to re-select last selected variable if applicable, or just clear
            # self.selected_var_details = ("", "") # Ensure details pane is cleared
            return
        if button_id == "delete-cancel":
            self.delete_mode = False
            # Re-select the variable that was targeted for deletion to restore display
            if self.deleting_var_name:
                 # Trigger watcher with original value from dictionary
                 original_value = self.all_env_vars.get(self.deleting_var_name, "")
                 self.selected_var_details = (self.deleting_var_name, original_value)
            return

        # --- Edit Save Actions ---
        if button_id in ("edit-save-copy", "edit-save-rc", "edit-save-launch"):
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

            # Exit edit mode regardless of which button was pressed
            self.edit_mode = False

            # If the action didn't update the RC file (and thus didn't update the TUI state),
            # re-select the variable to ensure the display reverts to the original value.
            if button_id != "edit-save-rc":
                original_value = self.all_env_vars.get(var_name, "") # Get original value
                self.selected_var_details = (var_name, original_value)


        # --- Add Save Actions ---
        elif button_id in ("add-save-copy", "add-save-rc", "add-save-launch"):
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
            # Check against current TUI state for existence before adding via RC
            if button_id == "add-save-rc" and var_name in self.all_env_vars:
                 self.notify(f"Variable '{var_name}' already exists in TUI. Use Edit (e) instead.", severity="warning", title="Add Error")
                 name_input.focus()
                 return
            # Note: We don't prevent adding via Copy/Launch if it exists, as those are session-specific

            # Perform the add and notification
            self._save_variable(var_name, new_value, button_id, is_new=True)

            # Exit add mode regardless of which button was pressed
            self.add_mode = False


        # --- Delete Confirm Actions ---
        elif button_id in ("delete-confirm-copy", "delete-confirm-rc", "delete-confirm-launch"):
            if not self.deleting_var_name:
                self.notify("Error: No variable was targeted for deletion.", severity="error")
                self.delete_mode = False
                return

            var_name = self.deleting_var_name # Use the stored name

            # Perform the deletion and notification
            self._delete_variable(var_name, button_id)

            # Exit delete mode regardless of which button was pressed
            self.delete_mode = False

            # If the action didn't update the RC file (and thus didn't update the TUI state),
            # re-select the variable to ensure it remains visible.
            if button_id != "delete-confirm-rc":
                 original_value = self.all_env_vars.get(var_name, "") # Get original value
                 self.selected_var_details = (var_name, original_value)


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
        # Exit add/edit/delete mode if a row is selected by the user
        if self.add_mode:
            self.add_mode = False
        if self.edit_mode:
            self.edit_mode = False
        if self.delete_mode:
            self.delete_mode = False

        row_key = event.row_key
        if row_key is not None and row_key.value is not None:
            var_name = str(row_key.value)
            # Use value from internal dict for consistency
            var_value = self.all_env_vars.get(var_name, "<Not Found>")
            self.selected_var_details = (var_name, var_value)
        else:
             # This might happen if table is cleared while selection event is processed
             self.selected_var_details = ("", "") # Clear details if selection is lost or invalid

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update details view on highlight (keyboard navigation updates)."""
         # Only update if not in edit, add, or delete mode, to avoid flickering
        if not self.edit_mode and not self.add_mode and not self.delete_mode:
            row_key = event.row_key
            if row_key is not None and row_key.value is not None:
                var_name = str(row_key.value)
                # Use value from internal dict for consistency
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
