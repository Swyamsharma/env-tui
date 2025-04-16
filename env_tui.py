#!/usr/bin/env python3
import os
import shlex # For shell quoting
import pyperclip
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal # Added Horizontal
from textual.reactive import reactive
# Removed ModalScreen import as it's no longer used
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
        # Removed modal-related bindings if any were here
    ]

    CSS_PATH = "env_tui.css"

    # Reactive variable to store the content for the right pane
    selected_var_details = reactive(("", ""), layout=True)

    search_term = reactive("", layout=True)
    all_env_vars = dict(sorted(os.environ.items()))

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Input(placeholder="Search variables (name or value)...", id="search-input")
        with Horizontal(id="main-container"): # Use Horizontal layout
            with ScrollableContainer(id="left-pane"): # Left pane for the table
                yield DataTable(id="env-table")
            with ScrollableContainer(id="right-pane"): # Right pane for details
                yield Label("Select a variable", id="detail-name")
                yield Static("", id="detail-value", expand=True) # Static to display value
        yield Footer()

    # --- App Lifecycle --- (Removed ValueDetailScreen class)

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

        if name:
            name_label.update(f"[b]{name}[/b]")
            value_static.update(value)
        else:
            # Reset if no variable is selected (e.g., after clearing search)
            name_label.update("Select a variable")
            value_static.update("")


    # --- Actions ---
    def action_quit(self) -> None:
        """Called when the user presses q or Ctrl+C."""
        self.exit()

    def action_clear_search(self) -> None:
        """Called when the user presses Escape."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self.search_term = "" # Trigger update
        search_input.focus() # Keep focus on input

    def action_copy_name(self) -> None:
        """Copy the selected variable name to the clipboard."""
        table = self.query_one(DataTable)
        if table.cursor_row < 0: # No row selected
             self.notify("No variable selected.", title="Copy Name", severity="warning")
             return

        # Get the data for the row at the cursor
        try:
            # get_row_at returns a list of cell contents for the row
            row_data = table.get_row_at(table.cursor_row)
            if not row_data: # Check if row_data is empty
                 self.notify("Could not get data for selected row.", title="Copy Name", severity="error")
                 return
            # The variable name is the first item in the row data
            var_name = str(row_data[0])
        except IndexError:
             self.notify("Could not get selected variable name (Index Error).", title="Copy Name", severity="error")
             return

        # Proceed if var_name was successfully retrieved
        if var_name:
            try:
                pyperclip.copy(var_name)
                self.notify(f"Copied name: [b]{var_name}[/b]", title="Copy Name")
            except Exception as e:
                self.notify(f"Failed to copy name: {e}", title="Copy Error", severity="error")
        else:
             self.notify("Could not get selected variable name.", title="Copy Name", severity="error")

    def action_copy_value(self) -> None:
        """Copy the selected variable's full value to the clipboard."""
        table = self.query_one(DataTable)
        if table.cursor_row < 0: # No row selected
             self.notify("No variable selected.", title="Copy Value", severity="warning")
             return

        # Get the variable name from the selected row
        try:
            row_data = table.get_row_at(table.cursor_row)
            if not row_data:
                 self.notify("Could not get data for selected row.", title="Copy Value", severity="error")
                 return
            var_name = str(row_data[0])
        except IndexError:
             self.notify("Could not get selected variable name (Index Error).", title="Copy Value", severity="error")
             return

        # Get the full value from our stored dictionary
        var_value = self.all_env_vars.get(var_name)

        if var_name and var_value is not None:
            try:
                pyperclip.copy(var_value)
                # Display truncated value in notification for brevity
                display_value = (var_value[:50] + '...') if len(var_value) > 53 else var_value
                self.notify(f"Copied value for [b]{var_name}[/b]:\n{display_value}", title="Copy Value")
            except Exception as e:
                self.notify(f"Failed to copy value: {e}", title="Copy Error", severity="error")
        else:
             self.notify(f"Could not find value for {var_name}.", title="Copy Value", severity="error")

    def action_copy_export(self) -> None:
        """Copy the selected variable as a shell export statement."""
        table = self.query_one(DataTable)
        if table.cursor_row < 0: # No row selected
             self.notify("No variable selected.", title="Copy Export", severity="warning")
             return

        # Get the variable name from the selected row
        try:
            row_data = table.get_row_at(table.cursor_row)
            if not row_data:
                 self.notify("Could not get data for selected row.", title="Copy Export", severity="error")
                 return
            var_name = str(row_data[0])
        except IndexError:
             self.notify("Could not get selected variable name (Index Error).", title="Copy Export", severity="error")
             return

        # Get the full value from our stored dictionary
        var_value = self.all_env_vars.get(var_name)

        if var_name and var_value is not None:
            try:
                # Safely quote the value for shell usage
                quoted_value = shlex.quote(var_value)
                export_statement = f'export {var_name}={quoted_value}'
                pyperclip.copy(export_statement)
                self.notify(f"Copied export statement for [b]{var_name}[/b]", title="Copy Export")
            except Exception as e:
                self.notify(f"Failed to copy export statement: {e}", title="Copy Error", severity="error")
        else:
             self.notify(f"Could not find value for {var_name}.", title="Copy Export", severity="error")


    # --- Event Handlers ---
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search input field."""
        if event.input.id == "search-input":
            self.search_term = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submission in the search input field (e.g., Enter)."""
        if event.input.id == "search-input":
            # Move focus to the table when Enter is pressed in search
            self.query_one(DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable."""
        # When a row is selected, update the reactive variable for the right pane
        row_key = event.row_key
        if row_key is not None:
            var_name = str(row_key.value)
            var_value = self.all_env_vars.get(var_name, "<Not Found>")
            self.selected_var_details = (var_name, var_value) # Update reactive var
        else:
             self.selected_var_details = ("", "") # Clear details if no row key


if __name__ == "__main__":
    app = EnvTuiApp()
    app.run()
