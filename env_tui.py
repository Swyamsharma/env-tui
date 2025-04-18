#!/usr/bin/env python3
import os
import os.path # Added for expanduser
import shlex # For shell quoting
import pyperclip
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
        ("e", "toggle_edit", "Edit Value"), # Add Edit binding
    ]

    CSS_PATH = "env_tui.css"

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
                        yield Button("Save (Copy Cmd)", variant="success", id="edit-save-copy") # Renamed ID
                        yield Button("Save (Update RC)", variant="warning", id="edit-save-rc") # New button
                        yield Button("Cancel", variant="error", id="edit-cancel")
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


    # --- Actions ---
    def action_toggle_edit(self) -> None:
        """Toggle edit mode for the selected variable."""
        if not self.selected_var_details[0]: # No variable selected
             self.notify("Select a variable to edit first.", severity="warning")
             return
        self.edit_mode = not self.edit_mode
    def action_quit(self) -> None:
        """Called when the user presses q or Ctrl+C."""
        self.exit()

    def action_clear_search(self) -> None:
        """Called when the user presses Escape."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self.search_term = "" # Trigger update
        search_input.focus() # Keep focus on input
        self.edit_mode = False # Exit edit mode if clearing search

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

        if button_id == "edit-cancel":
            self.edit_mode = False
            # Restore original value display
            self.selected_var_details = self.selected_var_details
            return # Exit early

        # Common logic for both save buttons
        if button_id in ("edit-save-copy", "edit-save-rc"):
            if not self.editing_var_name:
                self.notify("Error: No variable was being edited.", severity="error")
                self.edit_mode = False
                return

            edit_input = self.query_one("#edit-input", Input)
            new_value = edit_input.value
            var_name = self.editing_var_name

            # 1. Update internal dictionary
            self.all_env_vars[var_name] = new_value

            # 2. Update the reactive variable to refresh display
            self.selected_var_details = (var_name, new_value)

            # 3. Update the table display
            table = self.query_one(DataTable)
            try:
                row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                if row_key and row_key.value == var_name:
                    display_value = (new_value[:70] + '...') if len(new_value) > 73 else new_value
                    table.update_cell_at(table.cursor_coordinate, display_value)
                else:
                    self.update_table() # Fallback
            except Exception:
                self.update_table() # Fallback

            # 4. Construct export command
            quoted_value = shlex.quote(new_value)
            export_cmd = f'export {var_name}={quoted_value}'

            # 5. Perform action specific to the button pressed
            if button_id == "edit-save-copy":
                try:
                    pyperclip.copy(export_cmd)
                    self.notify(
                        f"Updated [b]{var_name}[/b] internally.\n"
                        f"Run in your shell (copied to clipboard):\n"
                        f"[i]{export_cmd}[/i]",
                        title="Variable Updated",
                        timeout=10
                    )
                except Exception as e:
                     self.notify(
                        f"Updated [b]{var_name}[/b] internally.\n"
                        f"Run in your shell:\n"
                        f"[i]{export_cmd}[/i]\n"
                        f"(Copy failed: {e})",
                        title="Variable Updated",
                        timeout=10,
                        severity="warning"
                    )

            elif button_id == "edit-save-rc":
                config_file = self._get_shell_config_file()
                if config_file and os.path.exists(os.path.dirname(config_file)):
                    try:
                        lines = []
                        updated = False
                        # Define the prefix to search for (handle potential whitespace)
                        search_prefix = f"export {var_name}="
                        comment_line = f"# Added by EnvTuiApp"

                        # Read existing file content if it exists
                        if os.path.exists(config_file):
                            with open(config_file, "r") as f:
                                lines = f.readlines()

                        new_lines = []
                        found_line_index = -1

                        # Iterate to find and update the line
                        for i, line in enumerate(lines):
                            stripped_line = line.strip()
                            # Check if the line defines the variable we are editing
                            if stripped_line.startswith(search_prefix):
                                # Replace this line with the new export command
                                new_lines.append(export_cmd + "\n")
                                updated = True
                                found_line_index = i
                                # Check if the previous line was our comment, if so, skip adding it again later
                                if i > 0 and lines[i-1].strip() == comment_line:
                                     # We assume the comment belongs to this line, keep it implicitly
                                     pass # No action needed, the new line replaces the old export
                                # Skip the original line
                                continue
                            # Keep other lines
                            new_lines.append(line)

                        # If the variable was not found, append it with a comment
                        if not updated:
                            # Add a newline before appending if the file is not empty
                            if new_lines and not new_lines[-1].endswith('\n'):
                                new_lines.append("\n")
                            new_lines.append(comment_line + "\n")
                            new_lines.append(export_cmd + "\n")

                        # Write the modified content back to the file
                        with open(config_file, "w") as f:
                            f.writelines(new_lines)

                        # Notify user based on whether it was updated or appended
                        action_desc = "Updated existing export" if updated else "Appended export command"
                        self.notify(
                            f"Updated [b]{var_name}[/b] internally.\n"
                            f"{action_desc} in:\n[i]{config_file}[/i]\n"
                            f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions.",
                            title="Config File Updated",
                            timeout=12
                        )
                    except Exception as e:
                        self.notify(
                            f"Updated [b]{var_name}[/b] internally.\n"
                            f"Failed to write to config file [i]{config_file}[/i]:\n{e}",
                            title="Config Update Error",
                            severity="error",
                            timeout=12
                        )
                elif config_file:
                     self.notify(
                        f"Updated [b]{var_name}[/b] internally.\n"
                        f"Could not find directory for config file:\n[i]{config_file}[/i]",
                        title="Config Update Error",
                        severity="error",
                        timeout=10
                    )
                else:
                    self.notify(
                        f"Updated [b]{var_name}[/b] internally.\n"
                        f"Could not determine shell config file.",
                        title="Config Update Error",
                        severity="error",
                        timeout=10
                    )

            # 6. Exit edit mode (common to both saves)
            self.edit_mode = False

    # Removed duplicated code block that was here

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search input field."""
        if event.input.id == "search-input":
            self.search_term = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submission in the search input field (e.g., Enter)."""
        if event.input.id == "search-input":
            self.query_one(DataTable).focus()
        elif event.input.id == "edit-input":
             # If enter is pressed in edit input, treat it like the primary save (copy cmd)
             save_button = self.query_one("#edit-save-copy", Button)
             self.on_button_pressed(Button.Pressed(save_button))


    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable."""
        row_key = event.row_key
        if row_key is not None:
            var_name = str(row_key.value)
            # Use the potentially updated value from our dictionary
            var_value = self.all_env_vars.get(var_name, "<Not Found>")
            # If we are in edit mode but select a DIFFERENT variable, exit edit mode first
            if self.edit_mode and var_name != self.editing_var_name:
                self.edit_mode = False
            self.selected_var_details = (var_name, var_value)
        else:
             # If selection is cleared (e.g. by filtering), exit edit mode
             if self.edit_mode:
                 self.edit_mode = False
             self.selected_var_details = ("", "")


if __name__ == "__main__":
    app = EnvTuiApp()
    app.run()
