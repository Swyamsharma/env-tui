from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Label, Rule # Added Rule

def compose_app() -> ComposeResult:
    """Create child widgets for the app."""
    print("DEBUG: compose_app() called") # Changed from compose()
    yield Header() # Header provides F1 toggle by default
    yield Input(placeholder="Search variables (name or value)...", id="search-input")
    with Horizontal(id="main-container"): # Use Horizontal layout
        with ScrollableContainer(id="left-pane"):
            # Combined Environment Variables Table
            yield DataTable(id="combined-env-table") # Single table for all variables
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
