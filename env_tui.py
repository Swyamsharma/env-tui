#!/usr/bin/env python3
import os
import os.path # Added for expanduser
import shlex # For shell quoting
import pyperclip
import subprocess # For launching terminal
import sys # For platform detection
import shutil # For finding executables (shutil.which)
from pathlib import Path # Added for config path handling
import tempfile # For creating temporary files

# Local imports
import config # Import the new config module
import shell_utils # Import the new shell utils module
from shell_utils import get_user_defined_vars_from_rc # Import the new function
import ui # Import the new ui module

from textual.app import App, ComposeResult
# Container imports moved to ui.py
from textual.containers import ScrollableContainer # Keep ScrollableContainer for left-pane access
from textual.reactive import reactive
# Specific widget imports (Header, Footer, Label) moved to ui.py
from textual.widgets import DataTable, Input, Button, Static, TextArea # Add Static here, TextArea
from textual.widgets._data_table import DuplicateKey
from textual.binding import Binding # Import Binding
from textual import events # Import events for on_key
# OptionList/Option imports likely not needed here anymore if not used directly
# REMOVED: from textual._theme import THEMES as AVAILABLE_THEMES
from typing import Dict, Tuple, Set # Added Set for type hint


class EnvTuiApp(App):
    """A Textual app to view and filter environment variables."""

    # --- Constants for Config ---
    # Moved to config.py

    BINDINGS = [
        Binding("q", "quit", "Quit"), # Use Binding class
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "clear_search", "Clear Search"),
        Binding("n", "copy_name", "Copy Name"),
        Binding("v", "copy_value", "Copy Value"),
        Binding("c", "copy_export", "Copy Export"),
        Binding("e", "toggle_edit", "Edit Value"),
        Binding("a", "toggle_add", "Add Variable"),
        Binding("d", "request_delete", "Delete Variable"),
        # Removed: Binding("right", "cycle_filter", "Cycle Filter", show=False),
        # F1 for theme switching is usually handled by Header
    ]

    CSS_PATH = "env_tui.css"

    # --- Filter State ---
    FILTER_STATES = ["all", "user", "system"]
    filter_state = reactive("all", layout=True) # "all", "user", "system"

    # State for add mode
    add_mode = reactive(False, layout=True)

    # State for edit mode
    edit_mode = reactive(False, layout=True)
    # State for delete mode
    delete_mode = reactive(False, layout=True)
    # Store the name of the variable being edited or deleted
    editing_var_name = reactive[str | None](None)
    deleting_var_name = reactive[str | None](None) # Added for delete confirmation
    deleting_var_source = reactive[str | None](None) # Added to store source during delete

    # Reactive variable to store the content for the right pane
    selected_var_details = reactive(("", ""), layout=True)
    # Track if selected var is 'user' or 'system' or None
    selected_var_source = reactive[str | None](None, layout=True)

    search_term = reactive("", layout=True)
    # Split environment variables
    user_env_vars: Dict[str, str] = reactive({}) # Vars likely defined by user in RC
    system_env_vars: Dict[str, str] = reactive({}) # Other vars (system/inherited)
    # Keep a combined view for easy lookup in some cases (like copy value)
    _all_env_vars_combined: Dict[str, str] = {}
    _is_updating_table = False # Flag to prevent concurrent updates

    # --- Configuration File Helpers ---
    # Moved to config.py

    # --- App Lifecycle ---

    def __init__(self):
        """Initialize the app and load theme preference."""
        print("DEBUG: EnvTuiApp.__init__() started")
        # Call super first
        super().__init__()

        # Load theme name from config file and set self.theme
        loaded_theme = config.load_theme_setting()
        if loaded_theme:
            self.theme = loaded_theme

        # --- Populate User and System Vars ---
        print("DEBUG: Populating user and system env vars...")
        user_var_names = get_user_defined_vars_from_rc()
        print(f"DEBUG: Found {len(user_var_names)} vars in RC file: {user_var_names}")
        all_os_vars = dict(os.environ.items())
        self._all_env_vars_combined = all_os_vars # Store the combined view

        user_vars_dict = {}
        system_vars_dict = {}

        for name, value in all_os_vars.items():
            if name in user_var_names:
                user_vars_dict[name] = value
            else:
                system_vars_dict[name] = value

        # Sort and assign to reactive attributes
        self.user_env_vars = dict(sorted(user_vars_dict.items()))
        self.system_env_vars = dict(sorted(system_vars_dict.items()))
        print(f"DEBUG: Populated {len(self.user_env_vars)} user vars and {len(self.system_env_vars)} system vars.")
        # --- End Populate ---

        # Dictionary to store changes (add/edit/delete) intended for the parent shell
        self.session_changes: Dict[str, str | None] = {}

        print(f"DEBUG: EnvTuiApp.__init__() finished. Initial theme is '{self.theme}'")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        print("DEBUG: on_mount() called")
        # Configure Combined Table
        table = self.query_one("#combined-env-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        # Add columns including the new "Type" column
        table.add_columns("Name", "Value", "Type")
        table.fixed_columns = 1 # Keep Name column fixed if desired

        # Defer the initial table population
        self.call_later(self.update_table)
        print("DEBUG: on_mount() finished, update_table scheduled")

    def on_unmount(self) -> None:
        """Called when the app is about to unmount (before exit)."""
        print("DEBUG: on_unmount() called")
        config.save_theme_setting(self.theme) # Save the current theme name using config module

        # --- Write session changes to temporary file ---
        export_file_path = Path(tempfile.gettempdir()) / "env_tui_exports.sh"
        try:
            if self.session_changes:
                print(f"DEBUG: Writing {len(self.session_changes)} changes to {export_file_path}")
                with open(export_file_path, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write("# Temporary file generated by EnvTuiApp to apply changes to the parent shell.\n")
                    f.write("# Source this file after the TUI exits: source env_tui_exports.sh\n\n")
                    for var_name, value in self.session_changes.items():
                        if value is None: # Deletion marker
                            f.write(f"unset {shlex.quote(var_name)}\n")
                            print(f"  - Unset: {var_name}")
                        else: # Addition or modification
                            f.write(f"export {shlex.quote(var_name)}={shlex.quote(value)}\n")
                            print(f"  - Export: {var_name}={value}")
                # Make the script executable (optional, but good practice)
                os.chmod(export_file_path, 0o755)
            else:
                # If no changes, ensure the file doesn't exist or is empty
                if export_file_path.exists():
                    print(f"DEBUG: No session changes, removing existing {export_file_path}")
                    export_file_path.unlink()
                else:
                    print("DEBUG: No session changes to write.")

        except Exception as e:
            print(f"ERROR: Failed to write session changes to {export_file_path}: {e}")
            # Optionally notify the user in the TUI if possible, though it's exiting
            # self.notify(f"Error writing export file: {e}", severity="error", timeout=10)

        print("DEBUG: on_unmount() finished after saving settings and writing exports.")
        # No need to call super().on_unmount() unless the base class requires it for cleanup

    def compose(self) -> ComposeResult:
        """Create child widgets by calling the function in the ui module."""
        # Delegate the actual composition to the ui module
        yield from ui.compose_app()

    # --- update_table and other methods remain largely the same ---
    # (Ensure no other code relies on the old self.dark saving logic)

    def update_table(self) -> None:
        """Update the combined DataTable with filtered environment variables."""
        if self._is_updating_table:
            # print("DEBUG: update_table() called while already updating. Skipping.") # Optional debug
            # If an update is already running, skip this one.
            # The latest state change will likely trigger another update anyway.
            return

        self._is_updating_table = True
        # print(f"DEBUG: update_table() started with filter: {self.filter_state}") # Debug
        try:
            table = self.query_one("#combined-env-table", DataTable)
            left_pane = self.query_one("#left-pane", ScrollableContainer)

            # Store cursor/scroll state
            current_cursor_row = table.cursor_row
            current_scroll_y = left_pane.scroll_y
            # Store the key of the currently selected row to try and restore selection
            selected_key = None
            # Check if cursor row is valid before trying to get the key
            if 0 <= current_cursor_row < table.row_count:
                try:
                    selected_key = table.get_row_at(current_cursor_row)[0]
                except IndexError: # Catch potential errors if row_count is inconsistent
                    selected_key = None

            table.clear(columns=False)

            search = self.search_term.lower()
            added_rows_keys = []
            # No longer need added_keys_this_update with the combined approach for 'all'

            # Populate based on filter state
            if self.filter_state == "user":
                for name, value in self.user_env_vars.items():
                    if not search or search in name.lower() or search in value.lower():
                        display_value = (value[:70] + '...') if len(value) > 73 else value
                        table.add_row(name, display_value, "User", key=name)
                        added_rows_keys.append(name)
            elif self.filter_state == "system":
                for name, value in self.system_env_vars.items():
                    # Ensure we don't show system vars that are overridden by user vars
                    # (This check might be redundant if _all_env_vars_combined is kept up-to-date,
                    # but better safe than sorry, though system_env_vars *shouldn't* contain user vars)
                    if name not in self.user_env_vars:
                         if not search or search in name.lower() or search in value.lower():
                            display_value = (value[:70] + '...') if len(value) > 73 else value
                            table.add_row(name, display_value, "System", key=name)
                            added_rows_keys.append(name)
            elif self.filter_state == "all":
                # Combine system and user vars (user takes precedence), then sort
                combined_vars = {**self.system_env_vars, **self.user_env_vars}
                sorted_combined = sorted(combined_vars.items())

                for name, value in sorted_combined:
                    if not search or search in name.lower() or search in value.lower():
                        display_value = (value[:70] + '...') if len(value) > 73 else value
                        # Determine type based on presence in the original user_env_vars dict
                        var_type = "User" if name in self.user_env_vars else "System"
                        table.add_row(name, display_value, var_type, key=name)
                        added_rows_keys.append(name)

            # --- Restore Cursor/Scroll ---
            target_row_index = -1
            if selected_key in added_rows_keys:
                try:
                    # Find the new index of the previously selected key
                    target_row_index = table.get_row_index(selected_key)
                except KeyError:
                    target_row_index = -1 # Key not found (shouldn't happen if in added_rows_keys)

            if target_row_index != -1:
                 # Restore cursor to the previously selected row
                 table.move_cursor(row=target_row_index, animate=False)
            elif added_rows_keys:
                 # If previous selection is gone, try to restore to roughly the same position,
                 # ensuring the target index is valid for the *new* table size.
                 if added_rows_keys: # Only attempt if there are rows
                     target_row_index = min(current_cursor_row, len(added_rows_keys) - 1)
                     if target_row_index >= 0:
                         table.move_cursor(row=target_row_index, animate=False)

            # Restore scroll position after rows are added
            self.call_later(left_pane.scroll_to, y=current_scroll_y, animate=False)
            # --- End Restore ---

        except DuplicateKey as e:
            # This might happen if a var exists in both user and system somehow? Should be handled by init logic.
            self.notify(f"Internal Error: Duplicate key '{e}' encountered during table update.", severity="error", title="Table Update Error", timeout=10)
            print(f"ERROR: DuplicateKey during update_table: {e}")
        except Exception as e:
            self.notify(f"Internal Error updating table: {e}", severity="error", title="Table Update Error", timeout=10)
            print(f"ERROR: Exception during update_table: {e}") # Also print to console
        finally:
            # print("DEBUG: update_table() finished.") # Optional debug
            self._is_updating_table = False # Ensure flag is reset


    # --- Watchers ---
    def watch_search_term(self, old_value: str, new_value: str) -> None:
        """Called when the search_term reactive variable changes."""
        self.update_table()

    def watch_filter_state(self, old_state: str, new_state: str) -> None:
        """Update the filter status label when the filter state changes."""
        # print(f"DEBUG: watch_filter_state: {old_state} -> {new_state}") # Debug
        try:
            filter_label = self.query_one("#filter-status-label", Static)
            # Format the display string
            display_text = f"<{new_state.replace('_', ' ')}>"
            filter_label.update(display_text)
            # Also trigger table update when filter changes
            self.update_table()
        except Exception as e:
            print(f"ERROR: Could not update filter status label: {e}")


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
                edit_text_areas = self.query("#edit-input") # Now it's a TextArea
                if edit_text_areas:
                    # Use .text for TextArea
                    edit_text_areas[0].text = value # Update text area content if needed


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
                edit_text_areas = self.query("#edit-input") # Now it's a TextArea
                edit_labels = self.query("#edit-label")
                if edit_text_areas and edit_labels:
                    edit_text_area = edit_text_areas[0]
                    edit_label = edit_labels[0]
                    edit_label.update(f"Editing: [b]{name}[/b]")
                    # Use the value from the combined dict for consistency
                    # Use .text for TextArea
                    edit_text_area.text = self._all_env_vars_combined.get(name, "")
                    # Focus the TextArea
                    self.set_timer(0.1, edit_text_area.focus) # Focus after a short delay
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
         self.deleting_var_source = None # Clear the stored source
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

        # Store the name and source of the variable to be deleted
        self.deleting_var_name = var_name
        self.deleting_var_source = self.selected_var_source # Store the source now
        # Enter delete mode (watcher will handle showing/hiding)
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
        # Use the combined dictionary to get the most current value
        current_value = self._all_env_vars_combined.get(var_name, var_value) # Fallback just in case

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
        # Use the combined dictionary to get the most current value
        current_value = self._all_env_vars_combined.get(var_name, var_value) # Fallback just in case

        try:
            quoted_value = shlex.quote(current_value)
            export_statement = f'export {var_name}={quoted_value}'
            pyperclip.copy(export_statement)
            self.notify(f"Copied export statement for [b]{var_name}[/b]", title="Copy Export")
        except Exception as e:
            self.notify(f"Failed to copy export statement: {e}", title="Copy Error", severity="error")


    # Removed action_cycle_filter as it's handled by on_key now


    # --- Helper Methods ---
    # _delete_variable, _get_shell_config_file, _save_variable moved to shell_utils.py

    def _notify_wrapper(self, message: str) -> None:
        """Wraps self.notify to match the expected signature for shell_utils."""
        # Basic parsing of potential title/severity/timeout from the message string
        # This is a simple approach; a more robust way would be to pass a dict or object
        title = "Notification"
        severity = "information"
        timeout = 4.0 # Default timeout

        parts = message.split(" Title: ")
        if len(parts) > 1:
            message = parts[0]
            details = parts[1].split(" Severity: ")
            if len(details) > 1:
                title = details[0]
                severity_timeout = details[1].split(" Timeout: ")
                if len(severity_timeout) > 1:
                    severity = severity_timeout[0].lower()
                    try:
                        timeout = float(severity_timeout[1])
                    except ValueError:
                        pass # Keep default timeout if parsing fails
                else:
                    severity = severity_timeout[0].lower()
            else:
                title = details[0] # Only title was provided

        self.notify(message, title=title, severity=severity, timeout=timeout)


    # --- Event Handlers ---

    def on_key(self, event: events.Key) -> None:
        """Handle key presses, specifically left/right arrows for filter cycling."""
        # print(f"DEBUG: Key pressed: {event.key}, Focused: {self.focused}") # Debug
        if event.key in ("right", "left"):
            try:
                table = self.query_one("#combined-env-table", DataTable)
                # Check if the DataTable itself is the focused widget
                if self.focused is table:
                    current_index = self.FILTER_STATES.index(self.filter_state)
                    if event.key == "right":
                        # print("DEBUG: Right arrow pressed while table focused. Cycling filter forward.") # Debug
                        next_index = (current_index + 1) % len(self.FILTER_STATES)
                        self.filter_state = self.FILTER_STATES[next_index]
                    elif event.key == "left":
                        # print("DEBUG: Left arrow pressed while table focused. Cycling filter backward.") # Debug
                        prev_index = (current_index - 1 + len(self.FILTER_STATES)) % len(self.FILTER_STATES) # Ensure positive index
                        self.filter_state = self.FILTER_STATES[prev_index]

                    # Prevent the default DataTable horizontal scroll/navigation
                    event.prevent_default()
            except Exception as e:
                # Log if there's an error finding the table or cycling state
                print(f"ERROR: Exception during on_key filter cycle: {e}")


    # (on_input_changed, on_input_submitted,
    #  on_data_table_row_selected, on_data_table_row_highlighted remain the same)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks for Save/Cancel/Actions."""
        button_id = event.button.id

        # --- Cancel Actions ---
        if button_id == "edit-cancel":
            self.edit_mode = False
            # Re-select the variable to restore display (using potentially stale value is ok here)
            current_name, _ = self.selected_var_details
            if current_name:
                 # Trigger watcher with original value from combined dictionary
                 original_value = self._all_env_vars_combined.get(current_name, "")
                 self.selected_var_details = (current_name, original_value)
                 # Also clear source as we are cancelling edit
                 self.selected_var_source = None
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
                # Trigger watcher with original value from combined dictionary
                original_value = self._all_env_vars_combined.get(self.deleting_var_name, "")
                self.selected_var_details = (self.deleting_var_name, original_value)
                # Restore the source as well
                self.selected_var_source = self.deleting_var_source # Use the stored source
                self.deleting_var_source = None # Clear stored source after cancel
                return

        # --- Edit Save Actions ---
        if button_id in ("edit-save-copy", "edit-save-rc"):
            if not self.editing_var_name:
                self.notify("Error: No variable was being edited.", severity="error")
                self.edit_mode = False
                return

            edit_text_areas = self.query("#edit-input") # Now it's a TextArea
            if not edit_text_areas: return # Should not happen if button is visible
            edit_text_area = edit_text_areas[0]

            # Use .text for TextArea
            new_value = edit_text_area.text
            var_name = self.editing_var_name # Use the stored name being edited

            # Determine if RC update is requested and if it's allowed
            update_rc_requested = button_id == "edit-save-rc"
            if update_rc_requested and self.selected_var_source != "user":
                self.notify("Cannot update RC file for system/inherited variables.", severity="error", title="Edit Error")
                self.edit_mode = False
                # Re-select to restore display
                original_value = self._all_env_vars_combined.get(var_name, "")
                self.selected_var_details = (var_name, original_value)
                return

            # Pass the correct dictionary to shell_utils if updating RC
            vars_to_pass = self.user_env_vars if update_rc_requested else self._all_env_vars_combined

            # Perform the update using shell_utils
            tui_updated, updated_user_vars = shell_utils.save_variable(
                var_name, new_value, button_id, is_new=False,
                all_env_vars=vars_to_pass, notify=self._notify_wrapper
            )

            # Exit edit mode regardless of which button was pressed
            self.edit_mode = False

            # Update internal state ONLY if the RC file was modified (tui_updated is True)
            if tui_updated:
                # Record change for session export if RC was updated
                if update_rc_requested:
                    self.session_changes[var_name] = new_value
                    print(f"DEBUG: Recorded session change (edit): {var_name}={new_value}")

                self.user_env_vars = updated_user_vars # Update user vars
                # Rebuild combined dictionary
                self._all_env_vars_combined = {**self.system_env_vars, **self.user_env_vars}
                # Update reactive details and table
                self.selected_var_details = (var_name, new_value) # Show new value
                self.selected_var_source = "user" # It's now definitely a user var
                self.update_table()
                # Try to move cursor in the combined table after update
                def move_cursor_post_update():
                    try:
                        table = self.query_one("#combined-env-table", DataTable)
                        row_index = table.get_row_index(var_name)
                        table.move_cursor(row=row_index, animate=True)
                        # Re-select after moving cursor to ensure focus and details are correct
                        self.selected_var_details = (var_name, new_value)
                        self.selected_var_source = "User" # It's now definitely a user var
                    except (KeyError, LookupError): pass
                    except Exception as e: print(f"Error moving cursor post-update: {e}")
                self.call_later(move_cursor_post_update)
            else:
                # If the action didn't update the RC file (e.g., Copy Cmd, Launch Term),
                # re-select the variable to ensure the display reverts to the original value.
                # Use the combined dict as it wasn't modified.
                original_value = self._all_env_vars_combined.get(var_name, "")
                self.selected_var_details = (var_name, original_value)
                # Keep the original source

        # --- Edit External Action ---
        elif button_id == "edit-external":
            if not self.editing_var_name:
                self.notify("Error: No variable is being edited.", severity="error")
                return

            edit_text_areas = self.query("#edit-input")
            if not edit_text_areas: return # Should not happen

            edit_text_area = edit_text_areas[0]
            current_value = edit_text_area.text
            var_name = self.editing_var_name

            # Find editor
            editor = os.environ.get('EDITOR')
            if not editor:
                # Try common fallbacks
                for fallback in ['vim', 'nano', 'emacs', 'vi']: # Add more if needed
                    if shutil.which(fallback):
                        editor = fallback
                        break
            if not editor:
                self.notify("Could not find a suitable text editor.\nSet the EDITOR environment variable.", severity="error", title="Edit Error")
                return

            try:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".envtui", delete=False) as tmp_file:
                    tmp_file.write(current_value)
                    tmp_file_path = tmp_file.name
                    # Ensure data is written before editor opens
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())

                # Suspend the TUI and run the editor
                self.notify(f"Opening '{var_name}' in {editor}...", title="External Edit")
                with self.suspend_process():
                    print(f"\n--- EnvTui Suspended ---")
                    print(f"Editing variable '{var_name}' in {editor}.")
                    print(f"Temporary file: {tmp_file_path}")
                    print(f"Save and close the editor when finished.")
                    print(f"------------------------")
                    try:
                        # Use subprocess.run to wait for completion
                        process = subprocess.run([editor, tmp_file_path], check=False) # check=False to handle editor errors gracefully
                        if process.returncode != 0:
                             print(f"\n--- Editor exited with code {process.returncode} ---")
                        else:
                             print(f"\n--- Editor closed ---")
                    except Exception as e:
                        print(f"\n--- Error launching editor: {e} ---")
                        # Notify user within TUI after resuming
                        self.call_later(self.notify, f"Error launching editor {editor}: {e}", severity="error", title="Edit Error")


                # Resume TUI automatically happens after 'with' block

                # Read the content back from the temp file
                try:
                    with open(tmp_file_path, 'r') as tmp_file:
                        updated_value = tmp_file.read()

                    # Update the TextArea content
                    edit_text_area.text = updated_value
                    edit_text_area.focus() # Focus back on the text area
                    self.notify(f"Value updated from external editor.", title="External Edit")

                except Exception as e:
                    self.notify(f"Error reading back from temp file: {e}", severity="error", title="Edit Error")
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(tmp_file_path)
                    except OSError:
                        pass # Ignore if already deleted or other error

            except Exception as e:
                self.notify(f"Error during external edit process: {e}", severity="error", title="Edit Error")


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
            # Check against combined state for existence before adding
            if var_name in self._all_env_vars_combined:
                 # Check if it's a system var we might be overriding display for
                 if var_name in self.system_env_vars and button_id == "add-save-rc":
                     self.notify(f"Warning: '{var_name}' exists as a system variable.\nAdding to RC will override it in new shells.", severity="warning", title="Add Variable")
                 elif button_id == "add-save-rc": # Already exists as a user var
                     self.notify(f"Variable '{var_name}' already exists as a user variable. Use Edit (e) instead.", severity="warning", title="Add Error")
                     name_input.focus()
                     return
                 # Allow adding via Copy/Launch even if it exists (session-specific)

            # Note: shell_utils doesn't prevent adding via Copy/Launch if it exists, as those are session-specific

            # Adding always targets the user vars if RC is updated
            update_rc_requested = button_id == "add-save-rc"
            vars_to_pass = self.user_env_vars if update_rc_requested else self._all_env_vars_combined

            # Perform the add using shell_utils
            tui_updated, updated_user_vars = shell_utils.save_variable(
                var_name, new_value, button_id, is_new=True,
                all_env_vars=vars_to_pass, notify=self._notify_wrapper
            )

            # Exit add mode regardless of which button was pressed
            self.add_mode = False

            # Update internal state ONLY if the RC file was modified (tui_updated is True)
            if tui_updated:
                # Record change for session export if RC was updated
                if update_rc_requested:
                    self.session_changes[var_name] = new_value
                    print(f"DEBUG: Recorded session change (add): {var_name}={new_value}")

                self.user_env_vars = updated_user_vars # Update user vars
                 # Rebuild combined dictionary
                self._all_env_vars_combined = {**self.system_env_vars, **self.user_env_vars}
                # Clear details pane and update table
                self.selected_var_details = ("", "")
                self.selected_var_source = None
                self.update_table()
                 # Try to move cursor in combined table after update
                def move_cursor_post_update():
                    try:
                        table = self.query_one("#combined-env-table", DataTable)
                        row_index = table.get_row_index(var_name)
                        table.move_cursor(row=row_index, animate=True)
                        # Select the newly added var after moving cursor
                        self.selected_var_details = (var_name, new_value)
                        self.selected_var_source = "User" # Added vars are always user vars
                    except (KeyError, LookupError): pass
                    except Exception as e: print(f"Error moving cursor post-update: {e}")
                self.call_later(move_cursor_post_update)
            # No else needed - if TUI wasn't updated (Copy/Launch), state remains the same


        # --- Delete Confirm Actions ---
        elif button_id in ("delete-confirm-copy", "delete-confirm-rc", "delete-confirm-launch"):
            if not self.deleting_var_name:
                self.notify("Error: No variable was targeted for deletion.", severity="error")
                self.delete_mode = False
                return

            var_name = self.deleting_var_name # Use the stored name

            # Determine if RC update is requested and if it's allowed
            update_rc_requested = button_id == "delete-confirm-rc"
            # Use the stored source from when delete was initiated
            if update_rc_requested and self.deleting_var_source != "User": # Check against stored source ("User")
                self.notify("Cannot remove system/inherited variables from RC file.", severity="error", title="Delete Error")
                self.delete_mode = False
                # Re-select to restore display using the stored source
                original_value = self._all_env_vars_combined.get(var_name, "")
                self.selected_var_details = (var_name, original_value)
                self.selected_var_source = self.deleting_var_source # Restore source display
                self.deleting_var_source = None # Clear stored source
                return

            # Pass the correct dictionary to shell_utils if updating RC
            vars_to_pass = self.user_env_vars if update_rc_requested else self._all_env_vars_combined

            # Perform the deletion using shell_utils
            tui_updated, updated_user_vars = shell_utils.delete_variable(
                var_name, button_id,
                all_env_vars=vars_to_pass, notify=self._notify_wrapper
            )

            # Exit delete mode regardless of which button was pressed
            self.delete_mode = False

            # Update internal state ONLY if the RC file was modified (tui_updated is True)
            if tui_updated:
                # Record change for session export if RC was updated
                if update_rc_requested:
                    self.session_changes[var_name] = None # Use None as deletion marker
                    print(f"DEBUG: Recorded session change (delete): {var_name}")

                self.user_env_vars = updated_user_vars # Update user vars
                # Rebuild combined dictionary
                self._all_env_vars_combined = {**self.system_env_vars, **self.user_env_vars}
                # Clear details pane and update table
                self.selected_var_details = ("", "")
                self.selected_var_source = None
                self.update_table()
            else:
                # If the action didn't update the RC file (e.g., Copy Cmd, Launch Term),
                # re-select the variable to ensure it remains visible (if it still exists in combined).
                original_value = self._all_env_vars_combined.get(var_name)
                if original_value is not None:
                    # Determine original source again for re-selection
                    # We need to check the *current* state before potential deletion
                    original_source = "User" if var_name in self.user_env_vars else "System"
                    self.selected_var_details = (var_name, original_value)
                    self.selected_var_source = original_source
                else:
                    self.selected_var_details = ("", "") # Clear if it somehow disappeared
                    self.selected_var_source = None


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search input field."""
        if event.input.id == "search-input":
            self.search_term = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submission in the input fields (e.g., Enter)."""
        try:
            if event.input.id == "search-input":
                # Move focus to the combined table if it has rows
                table = self.query_one("#combined-env-table", DataTable)
                if table.row_count > 0:
                    table.focus()
            # Removed Enter handling for edit-input (TextArea handles Enter differently)
            # elif event.input.id == "edit-input":
            #     # If enter is pressed in edit input, treat it like the first save button (Copy Cmd)
            #     save_button = self.query_one("#edit-save-copy", Button)
            #     self.on_button_pressed(Button.Pressed(save_button))
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
        """Handle row selection in the combined DataTable (mouse click or Enter)."""
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
            # Get full row data to extract the type
            try:
                row_data = event.control.get_row(row_key) # ["Name", "Value", "Type"]
                var_type = row_data[2] if len(row_data) > 2 else None # Get type from 3rd column
            except KeyError:
                var_type = None # Should not happen if row_key is valid

            # Use value from combined dict for consistency (especially for full value)
            var_value = self._all_env_vars_combined.get(var_name, "<Not Found>")
            self.selected_var_details = (var_name, var_value)
            self.selected_var_source = str(var_type) if var_type else None # Set the source ("User" or "System")
        else:
             # This might happen if table is cleared while selection event is processed
             self.selected_var_details = ("", "") # Clear details if selection is lost or invalid
             self.selected_var_source = None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update details view on highlight in the combined table (keyboard navigation updates)."""
         # Only update if not in edit, add, or delete mode, to avoid flickering
        if not self.edit_mode and not self.add_mode and not self.delete_mode:
            row_key = event.row_key
            if row_key is not None and row_key.value is not None:
                var_name = str(row_key.value)
                # Get full row data to extract the type
                try:
                    row_data = event.control.get_row(row_key) # ["Name", "Value", "Type"]
                    var_type = row_data[2] if len(row_data) > 2 else None # Get type from 3rd column
                except KeyError:
                    var_type = None # Should not happen if row_key is valid

                # Use value from combined dict for consistency
                var_value = self._all_env_vars_combined.get(var_name, "<Not Found>")
                source = str(var_type) if var_type else None

                # Update reactive var directly to trigger watcher
                # Check if it actually changed to prevent redundant updates
                if self.selected_var_details != (var_name, var_value) or self.selected_var_source != source:
                    self.selected_var_details = (var_name, var_value)
                    self.selected_var_source = source # Set the source ("User" or "System")
            elif self.selected_var_details != ("", ""): # Clear only if needed
                self.selected_var_details = ("", "")
                self.selected_var_source = None


if __name__ == "__main__":
    app = EnvTuiApp()
    app.run()
