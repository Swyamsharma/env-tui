#!/usr/bin/env python3
import os
import os.path # Added for expanduser
import shlex # For shell quoting
import pyperclip
import subprocess # For launching terminal
import sys # For platform detection
import shutil # For finding executables (shutil.which)
# Removed duplicate shlex import
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Label

class EnvTuiApp(App):
    """A Textual app to view and filter environment variables."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("escape", "clear_search", "Clear Search"),
        ("n", "copy_name", "Copy Name"),
        ("v", "copy_value", "Copy Value"),
        ("c", "copy_export", "Copy Export"),
        ("e", "toggle_edit", "Edit Value"),
        ("a", "toggle_add", "Add Variable"), # Add binding
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

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
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
                # Corrected indentation for this block
                with Vertical(id="edit-value-container", classes="hidden"):
                    yield Label("Editing:", id="edit-label") # Label for clarity
                    # Corrected indentation for Input and Horizontal block below
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

    # --- App Lifecycle ---

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Variable Name", "Value")

    def update_table(self) -> None:
        """Update the DataTable with filtered environment variables."""
        table = self.query_one(DataTable)
        table.clear(columns=False)

        search = self.search_term.lower()

        if not search:
            for name, value in self.all_env_vars.items():
                display_value = (value[:70] + '...') if len(value) > 73 else value
                table.add_row(name, display_value, key=name)
        else:
            for name, value in self.all_env_vars.items():
                if search in name.lower() or search in value.lower():
                    display_value = (value[:70] + '...') if len(value) > 73 else value
                    table.add_row(name, display_value, key=name)

    # --- Watchers ---
    def watch_search_term(self, old_value: str, new_value: str) -> None:
        """Called when the search_term reactive variable changes."""
        self.update_table()

    def watch_selected_var_details(self, old_value: tuple[str, str], new_value: tuple[str, str]) -> None:
        """Called when the selected variable details change."""
        name, value = new_value
        name_label = self.query_one("#detail-name", Label)
        value_static = self.query_one("#detail-value", Static)

        # Always update the static view first
        if name:
            name_label.update(f"[b]{name}[/b]")
            value_static.update(value)
        else:
            name_label.update("Select a variable")
            value_static.update("")

        # If we are in edit mode AND this is the variable being edited, update Input
        if self.edit_mode and name == self.editing_var_name:
            edit_input = self.query_one("#edit-input", Input)
            edit_input.value = value # Update input field if needed

    def watch_edit_mode(self, old_value: bool, new_value: bool) -> None:
        """Show/hide edit widgets when edit_mode changes."""
        editing = new_value
        view_container = self.query_one("#view-value-container")
        edit_container = self.query_one("#edit-value-container")

        view_container.set_class(editing, "hidden")
        edit_container.set_class(not editing, "hidden")

        if editing:
            # If entering edit mode, ensure a variable is selected
            name, value = self.selected_var_details
            if name:
                self.editing_var_name = name # Store the name being edited
                edit_input = self.query_one("#edit-input", Input)
                edit_label = self.query_one("#edit-label", Label)
                edit_label.update(f"Editing: [b]{name}[/b]")
                edit_input.value = value
                self.set_timer(0.1, edit_input.focus) # Focus after a short delay
            else:
                # Cannot enter edit mode without selection
                self.notify("Select a variable to edit first.", severity="warning")
                self.edit_mode = False # Revert
        else:
            # Exiting edit mode
            self.editing_var_name = None
            # Optionally move focus back to table or keep it where it is
            # self.query_one(DataTable).focus()

    def watch_add_mode(self, old_value: bool, new_value: bool) -> None:
        """Show/hide add widgets when add_mode changes."""
        adding = new_value
        add_container = self.query_one("#add-value-container")
        # Hide other potentially active containers
        view_container = self.query_one("#view-value-container")
        edit_container = self.query_one("#edit-value-container")

        add_container.set_class(not adding, "hidden")

        if adding:
            # Clear selection display and hide view/edit panes
            self.selected_var_details = ("", "") # Clear selection display
            view_container.set_class(True, "hidden")
            edit_container.set_class(True, "hidden")
            # Clear inputs and focus on name input
            self.query_one("#add-name-input", Input).value = ""
            self.query_one("#add-value-input", Input).value = ""
            self.set_timer(0.1, self.query_one("#add-name-input", Input).focus)
        else:
             # When exiting add mode, potentially show the view container again
             # if a variable was selected before entering add mode,
             # but clearing selection is simpler for now.
             view_container.set_class(False, "hidden") # Show view container by default


    # --- Actions ---
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
        self.exit()

    def action_clear_search(self) -> None:
        """Called when the user presses Escape."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self.search_term = "" # Trigger update
        search_input.focus() # Keep focus on input
        self.edit_mode = False # Exit edit mode
        self.add_mode = False # Exit add mode

    def action_copy_name(self) -> None:
        """Copy the selected variable name to the clipboard."""
        # Use the reactive variable for the selected name
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
        # Use the reactive variable for the selected name/value
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
        # Use the reactive variable for the selected name/value
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
    def _get_shell_config_file(self) -> str | None:
        """Try to determine the user's shell configuration file."""
        shell = os.environ.get("SHELL", "")
        if "bash" in shell:
            config_file = "~/.bashrc"
        elif "zsh" in shell:
            config_file = "~/.zshrc"
        # Add other shells here if needed (e.g., fish, ksh)
        # elif "fish" in shell:
        #     config_file = "~/.config/fish/config.fish" # Example
        else:
             # Fallback or default if shell is unknown
             # Using .profile might be a safer general fallback, but less common for exports
             config_file = "~/.profile" # Or return None if no sensible default

        if config_file:
            return os.path.expanduser(config_file)
        return None

    # --- Event Handlers ---
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks for Save/Cancel."""
        button_id = event.button.id

        # --- Cancel Actions ---
        if button_id == "edit-cancel":
            self.edit_mode = False
            # Restore original value display (watcher should handle this)
            # self.selected_var_details = self.selected_var_details
            return
        if button_id == "add-cancel":
            self.add_mode = False
            return

        # --- Edit Save Actions ---
        if button_id in ("edit-save-copy", "edit-save-rc", "edit-save-launch"): # Added launch ID
            if not self.editing_var_name:
                self.notify("Error: No variable was being edited.", severity="error")
                self.edit_mode = False
                return

            edit_input = self.query_one("#edit-input", Input)
            new_value = edit_input.value
            var_name = self.editing_var_name # Use the stored name being edited

            # Perform the update and notification
            # Pass button_id to _save_variable to determine action
            self._save_variable(var_name, new_value, button_id, is_new=False)
            self.edit_mode = False # Exit edit mode

        # --- Add Save Actions ---
        elif button_id in ("add-save-copy", "add-save-rc", "add-save-launch"): # Added launch ID
            name_input = self.query_one("#add-name-input", Input)
            value_input = self.query_one("#add-value-input", Input)
            var_name = name_input.value.strip()
            new_value = value_input.value # Keep original spacing for value

            # Basic validation
            if not var_name:
                self.notify("Variable name cannot be empty.", severity="error", title="Add Error")
                name_input.focus()
                return
            if not var_name.isidentifier(): # Check if valid shell identifier
                 self.notify(f"Invalid variable name: '{var_name}'.\nMust be letters, digits, underscores (not starting with digit).", severity="error", title="Add Error")
                 name_input.focus()
                 return
            if var_name in self.all_env_vars:
                 self.notify(f"Variable '{var_name}' already exists. Use Edit (e) instead.", severity="warning", title="Add Error")
                 name_input.focus()
                 return

            # Perform the add and notification
            # Pass button_id to _save_variable to determine action
            self._save_variable(var_name, new_value, button_id, is_new=True)
            self.add_mode = False # Exit add mode


    def _save_variable(self, var_name: str, new_value: str, action_button_id: str, is_new: bool = False) -> None:
        """Handles the common logic for saving/adding a variable based on the button pressed."""

        # Determine action type from button ID
        update_rc = action_button_id in ("edit-save-rc", "add-save-rc")
        launch_terminal = action_button_id in ("edit-save-launch", "add-save-launch") # Renamed variable

        # 1. Update internal dictionary
        self.all_env_vars[var_name] = new_value
        # Re-sort dictionary after adding
        if is_new:
            self.all_env_vars = dict(sorted(self.all_env_vars.items()))


        # 2. Update the reactive variable to refresh display (if editing)
        #    or clear display (if adding, as add_mode watcher handles hiding)
        if not is_new:
            self.selected_var_details = (var_name, new_value)

        # 3. Update the table display
        self.update_table() # Full update is easier for adding/sorting
        # Try to move cursor to the added/edited row
        table = self.query_one(DataTable)
        try:
            # Find the row index by key
            row_index = table.get_row_index(var_name)
            table.move_cursor(row=row_index, animate=True)
        except KeyError:
            pass # Key might not be in table if filtering is active

        # 4. Construct export command
        quoted_value = shlex.quote(new_value)
        export_cmd = f'export {var_name}={quoted_value}'

        # 5. Perform copy, RC update, or launch terminal action
        action_verb = "Added" if is_new else "Updated"

        if launch_terminal: # Handle Launch Terminal
            shell_path = os.environ.get("SHELL", "/bin/bash") # Default to bash for safety
            # Command to execute inside the new terminal: export the var, then exec the shell
            # Using 'exec' replaces the intermediate shell, making the new shell the main process
            internal_command = f"{export_cmd}; exec {shell_path} -l"

            terminal_cmd_list = []
            found_terminal = False
            try:
                if sys.platform.startswith("linux"): # More robust check for Linux
                    # List of terminals to try, in preferred order, with their execution args
                    # Format: (terminal_executable, [args_before_command], [args_after_command])
                    # The command itself will be placed between args_before and args_after
                    # List of terminals to try, with execution flags.
                    # Most use '-e' or '--' followed by the command/shell.
                    # Some might need specific shell invocation.
                    terminals_to_try = [
                        "gnome-terminal",
                        "konsole",
                        "kitty",
                        "alacritty",
                        "terminator",
                        "xterm",
                    ]

                    for term_exe in terminals_to_try:
                        full_path = shutil.which(term_exe)
                        if full_path:
                            # Construct the command list to launch the terminal
                            # and have it execute the user's shell with our internal command.
                            if term_exe in ["gnome-terminal", "terminator"]:
                                # These often use '--' to separate terminal args from the command
                                terminal_cmd_list = [full_path, "--", shell_path, "-c", internal_command]
                            elif term_exe in ["konsole", "alacritty", "xterm"]:
                                # These often use '-e'
                                terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                            elif term_exe == "kitty":
                                # Kitty executes the command directly, so we tell it to run the shell
                                terminal_cmd_list = [full_path, shell_path, "-c", internal_command]
                            else:
                                # Default fallback attempt using -e (might work for others)
                                terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]

                            found_terminal = True
                            break # Stop searching once a terminal is found

                    if not found_terminal:
                        self.notify(
                            f"{action_verb} [b]{var_name}[/b] internally.\n"
                            f"Could not find a supported terminal emulator "
                            f"(tried gnome-terminal, konsole, kitty, alacritty, terminator, xterm).\n"
                            f"Please install one or launch manually.",
                            title="Launch Error",
                            severity="warning",
                            timeout=12
                        )
                        return # Don't proceed if no terminal found

                elif sys.platform == "darwin": # macOS
                    # Use 'open -a Terminal' - might need adjustment based on default term
                    # Using -n ensures a new window instance
                    terminal_cmd_list = ["open", "-n", "-a", "Terminal", "--args", shell_path, "-c", internal_command]
                elif sys.platform == "win32":
                    # Windows: Use 'start cmd /k' to set var and keep window open
                    # Windows uses 'set' instead of 'export'
                    win_set_cmd = f'set {var_name}={new_value}' # No shlex.quote needed for basic set
                    # Launch a new cmd prompt that sets the variable and stays open
                    terminal_cmd_list = ["start", "cmd", "/k", win_set_cmd]
                    internal_command = win_set_cmd # For notification

                if terminal_cmd_list:
                    # Only proceed if we constructed a command list (either Linux found one or other OS)
                    subprocess.Popen(terminal_cmd_list)
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Attempting to launch '{terminal_cmd_list[0]}' with the variable exported.",
                        # f"Full command: [i]{' '.join(map(shlex.quote, terminal_cmd_list))}[/i]", # More accurate quoting if needed
                        title="Launching Terminal",
                        timeout=12
                    )
                else:
                     self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Unsupported OS ({sys.platform}) for launching terminal automatically.",
                        title="Launch Error",
                        severity="warning",
                        timeout=10
                    )

            except FileNotFoundError:
                 # Specific error if the found terminal executable isn't actually runnable
                 # (shutil.which might find it, but permissions etc. could be wrong)
                 term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal"
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Found terminal '{term_name}' but failed to execute it.\n"
                    f"Check permissions or try installing another terminal.",
                    title="Launch Execution Error",
                    severity="error",
                    timeout=12
                )
            except Exception as e:
                 # Generic error
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Failed to launch new terminal: {e}\n"
                    f"Command attempted: {' '.join(terminal_cmd_list)}",
                    title="Launch Error",
                    severity="error",
                    timeout=12
                )

        elif not update_rc: # Save Copy Cmd (original export command)
            try:
                pyperclip.copy(export_cmd)
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Run in your shell (copied to clipboard):\n"
                    f"[i]{export_cmd}[/i]",
                    title=f"Variable {action_verb}",
                    timeout=10
                )
            except Exception as e:
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Run in your shell:\n"
                    f"[i]{export_cmd}[/i]\n"
                    f"(Copy failed: {e})",
                    title=f"Variable {action_verb}",
                    timeout=10,
                    severity="warning"
                )
        else: # Save Update RC
            config_file = self._get_shell_config_file()
            if config_file and os.path.exists(os.path.dirname(config_file)):
                try:
                    lines = []
                    updated_existing_rc = False
                    search_prefix = f"export {var_name}="
                    comment_line = f"# Added by EnvTuiApp"

                    if os.path.exists(config_file):
                        with open(config_file, "r") as f:
                            lines = f.readlines()

                    new_lines = []
                    # Iterate to find and update the line
                    for i, line in enumerate(lines):
                        stripped_line = line.strip()
                        if stripped_line.startswith(search_prefix):
                            new_lines.append(export_cmd + "\n") # Replace
                            updated_existing_rc = True
                            # Skip original line
                            continue
                        new_lines.append(line) # Keep other lines

                    # If the variable was not found, append it
                    if not updated_existing_rc:
                        if new_lines and not new_lines[-1].endswith('\n'):
                            new_lines.append("\n")
                        new_lines.append(comment_line + "\n")
                        new_lines.append(export_cmd + "\n")

                    # Write the modified content back
                    with open(config_file, "w") as f:
                        f.writelines(new_lines)

                    action_desc = "Updated existing export" if updated_existing_rc else "Appended export command"
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"{action_desc} in:\n[i]{config_file}[/i]\n"
                        f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions.",
                        title="Config File Updated",
                        timeout=12
                    )
                except Exception as e:
                    self.notify(
                        f"{action_verb} [b]{var_name}[/b] internally.\n"
                        f"Failed to write to config file [i]{config_file}[/i]:\n{e}",
                        title="Config Update Error",
                        severity="error",
                        timeout=12
                    )
            elif config_file:
                 self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Could not find directory for config file:\n[i]{config_file}[/i]",
                    title="Config Update Error",
                    severity="error",
                    timeout=10
                )
            else:
                self.notify(
                    f"{action_verb} [b]{var_name}[/b] internally.\n"
                    f"Could not determine shell config file.",
                    title="Config Update Error",
                    severity="error",
                    timeout=10
                )


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search input field."""
        if event.input.id == "search-input":
            self.search_term = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submission in the search input field (e.g., Enter)."""
        if event.input.id == "search-input":
            self.query_one(DataTable).focus()
        elif event.input.id == "edit-input":
             # If enter is pressed in edit input, treat it like edit-save-copy
             save_button = self.query_one("#edit-save-copy", Button)
             self.on_button_pressed(Button.Pressed(save_button))
        elif event.input.id == "add-value-input":
             # If enter is pressed in add value input, treat it like add-save-copy
             save_button = self.query_one("#add-save-copy", Button)
             self.on_button_pressed(Button.Pressed(save_button))
        # No special action needed for Enter in add-name-input, user should tab or click


    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable."""
        row_key = event.row_key
        # Exit add/edit mode if a row is selected
        if self.add_mode:
            self.add_mode = False
        if self.edit_mode:
            self.edit_mode = False

        row_key = event.row_key
        if row_key is not None:
            var_name = str(row_key.value)
            var_value = self.all_env_vars.get(var_name, "<Not Found>")
            self.selected_var_details = (var_name, var_value)
        else:
             self.selected_var_details = ("", "") # Clear details if selection is lost


if __name__ == "__main__":
    app = EnvTuiApp()
    app.run()
