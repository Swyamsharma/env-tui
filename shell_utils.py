import os
import shlex
import re # Added for parsing RC file
import shutil
import subprocess
from pathlib import Path
import pyperclip # For copy actions

# Type hinting for callback functions
from typing import Callable, Dict, Tuple, Set # Added Set

NotifyCallable = Callable[[str], None] # Simplified type for notify callback

def get_shell_config_file() -> str | None:
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

def get_user_defined_vars_from_rc() -> Set[str]:
    """
    Attempts to parse the user's shell config file to find 'export VAR=' lines.
    Returns a set of variable names found.
    """
    config_file = get_shell_config_file()
    user_vars = set()
    if config_file and Path(config_file).exists():
        try:
            content = Path(config_file).read_text()
            # Regex to find lines starting with optional whitespace, 'export', whitespace,
            # then capture the variable name (alphanumeric + underscore, not starting with digit),
            # followed by '='. Handles potential spaces around '='.
            # Example matches: export VAR=..., export VAR = ..., export   VAR=...
            # It does NOT match commented lines like # export VAR=...
            export_pattern = re.compile(r"^\s*export\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
            for line in content.splitlines():
                match = export_pattern.match(line)
                if match:
                    user_vars.add(match.group(1))
        except Exception as e:
            # Log or notify about the error if needed, but don't crash
            print(f"Warning: Could not read or parse {config_file}: {e}")
            # Optionally notify the user via the notify callback if available/appropriate
            pass # Silently ignore for now
    return user_vars

def save_variable(
    var_name: str,
    new_value: str,
    action_button_id: str,
    is_new: bool,
    all_env_vars: Dict[str, str], # Pass current env vars state
    notify: NotifyCallable # Pass notify function
) -> Tuple[bool, Dict[str, str]]: # Return TUI update status and potentially modified env vars
    """Handles the common logic for saving/adding a variable based on the button pressed."""

    # Determine action type from button ID
    update_rc = action_button_id in ("edit-save-rc", "add-save-rc")
    launch_terminal = action_button_id in ("edit-save-launch", "add-save-launch")
    copy_cmd_only = not update_rc and not launch_terminal

    tui_updated = False # Flag to track if internal state changed
    current_env_vars = all_env_vars.copy() # Work on a copy

    # 1. Update internal dictionary ONLY if updating RC
    if update_rc:
        current_env_vars[var_name] = new_value
        tui_updated = True
        # Re-sort dictionary after adding if it was a new variable
        if is_new:
            current_env_vars = dict(sorted(current_env_vars.items()))

    # Steps 2, 3, 4 (updating reactive vars, table, cursor) are handled in the App class

    # 5. Construct export command (always needed)
    quoted_value = shlex.quote(new_value)
    export_cmd = f'export {var_name}={quoted_value}'

    # 6. Perform copy, RC update, or launch terminal action
    add_or_update = "Added" if is_new else "Updated"
    action_verb = add_or_update if tui_updated else f"Prepared {add_or_update.lower()} action for"

    if launch_terminal: # Handle Launch Terminal (Linux Only)
        shell_path = os.environ.get("SHELL")
        if not shell_path:
            shell_path = shutil.which("sh") # Basic fallback
        if not shell_path:
             notify(f"Could not determine SHELL path. Cannot launch terminal. Title: Launch Error Severity: error")
             return tui_updated, all_env_vars # Return original state

        terminal_cmd_list = []
        found_terminal = False
        internal_command = f"{export_cmd}; cd ~ && exec \"{shell_path}\""

        try:
            terminals_to_try = [
                "gnome-terminal", "konsole", "kitty", "alacritty",
                "terminator", "xfce4-terminal", "lxterminal", "xterm"
            ]
            for term_exe in terminals_to_try:
                full_path = shutil.which(term_exe)
                if full_path:
                    if term_exe in ["gnome-terminal", "terminator", "xfce4-terminal", "lxterminal"]:
                        terminal_cmd_list = [full_path, "--", shell_path, "-c", internal_command]
                    elif term_exe in ["konsole", "alacritty", "xterm"]:
                        terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                    elif term_exe == "kitty":
                        terminal_cmd_list = [full_path, shell_path, "-c", internal_command]
                    else:
                         terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                    found_terminal = True
                    print(f"DEBUG: Found terminal: {full_path}. Launch command: {' '.join(terminal_cmd_list)}")
                    break

            if not found_terminal:
                tui_msg = "internally (TUI not updated)."
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Could not find a known terminal emulator.\n"
                    f"(Tried: {', '.join(terminals_to_try)}).\n"
                    f"Please install one or launch manually. Title: Launch Error Severity: warning Timeout: 12"
                )
                return tui_updated, all_env_vars # Return original state

            if terminal_cmd_list:
                subprocess.Popen(terminal_cmd_list)
                term_name = terminal_cmd_list[0]
                tui_msg = "internally and TUI updated." if tui_updated else "internally (TUI not updated)."
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Attempting to launch '{term_name}' in '~' with the variable set. Title: Launching Terminal (Session) Timeout: 12"
                )

        except FileNotFoundError:
            tui_msg = "internally (TUI not updated)."
            term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal"
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Found terminal '{term_name}' but failed to execute it.\n"
                f"Check path/permissions or try installing another terminal. Title: Launch Execution Error Severity: error Timeout: 12"
            )
        except Exception as e:
             tui_msg = "internally (TUI not updated)."
             notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Failed to launch new terminal: {e}\n"
                f"Attempted command: {' '.join(map(shlex.quote, terminal_cmd_list)) if terminal_cmd_list else 'N/A'}. Title: Launch Error Severity: error Timeout: 15"
            )

    elif copy_cmd_only: # Save Copy Cmd
        shell_type = "shell"
        tui_msg = "internally (TUI not updated)."
        try:
            pyperclip.copy(export_cmd)
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Run in your {shell_type} (copied to clipboard):\n"
                f"[i]{export_cmd}[/i]. Title: Export Command Copied (Session) Timeout: 10"
            )
        except Exception as e:
             notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Run in your {shell_type}:\n"
                f"[i]{export_cmd}[/i]\n"
                f"(Copy failed: {e}). Title: Export Command Copy Failed Timeout: 10 Severity: warning"
            )
    elif update_rc: # Save Update RC (Linux Only)
        config_file = get_shell_config_file()
        if config_file:
            config_path = Path(config_file)
            config_dir = config_path.parent
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                lines = []
                updated_existing_rc = False
                search_prefix = f"export {var_name}="
                comment_line = f"\n# Added/Updated by EnvTuiApp"

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
                            new_lines.append(comment_line.strip())
                        new_lines.append(export_cmd)
                        found_in_rc = True
                        updated_existing_rc = True
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
                action_desc = "Updated existing export" if updated_existing_rc else "Appended export command"
                tui_msg = "internally and TUI updated."
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"{action_desc} in:\n[i]{config_file}[/i]\n"
                    f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions. Title: Config File Updated (Persistent) Timeout: 12"
                )
            except Exception as e:
                tui_msg = "internally and TUI updated, but"
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Failed to write to config file [i]{config_file}[/i]:\n{e}. Title: Config Update Error Severity: error Timeout: 12"
                )
        else:
            tui_msg = "internally and TUI updated, but"
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Could not determine shell config file (SHELL={os.environ.get('SHELL', 'Not set')}). Cannot update RC file. Title: Config Update Error Severity: error Timeout: 10"
            )

    # Return whether the TUI state was updated and the potentially modified env vars
    return tui_updated, current_env_vars if tui_updated else all_env_vars


def delete_variable(
    var_name: str,
    action_button_id: str,
    all_env_vars: Dict[str, str], # Pass current env vars state
    notify: NotifyCallable # Pass notify function
) -> Tuple[bool, Dict[str, str]]: # Return TUI update status and potentially modified env vars
    """Handles the common logic for deleting a variable based on the button pressed."""
    if var_name not in all_env_vars:
        notify(f"Variable '{var_name}' not found for deletion. Severity: error")
        return False, all_env_vars # No change

    # Determine action type from button ID
    update_rc = action_button_id == "delete-confirm-rc"
    launch_terminal = action_button_id == "delete-confirm-launch"
    copy_cmd_only = not update_rc and not launch_terminal

    tui_updated = False # Flag to track if internal state changed
    current_env_vars = all_env_vars.copy() # Work on a copy

    # 1. Remove from internal dictionary ONLY if updating RC
    if update_rc:
        del current_env_vars[var_name]
        tui_updated = True

    # Steps 2, 3 (updating reactive vars, table) are handled in the App class

    # 4. Construct unset command (always needed for actions)
    unset_cmd = f'unset {var_name}'

    # 5. Perform copy, RC update, or launch terminal action
    action_verb = "Deleted" if tui_updated else "Prepared delete action for"

    if launch_terminal: # Handle Launch Terminal (Linux Only)
        shell_path = os.environ.get("SHELL")
        if not shell_path:
            shell_path = shutil.which("sh")
        if not shell_path:
             notify(f"Could not determine SHELL path. Cannot launch terminal. Title: Launch Error Severity: error")
             return tui_updated, all_env_vars # Return original state if TUI not updated

        terminal_cmd_list = []
        found_terminal = False
        internal_command = f"{unset_cmd}; cd ~ && exec \"{shell_path}\""

        try:
            terminals_to_try = [
                "gnome-terminal", "konsole", "kitty", "alacritty",
                "terminator", "xfce4-terminal", "lxterminal", "xterm"
            ]
            for term_exe in terminals_to_try:
                full_path = shutil.which(term_exe)
                if full_path:
                    if term_exe in ["gnome-terminal", "terminator", "xfce4-terminal", "lxterminal"]:
                        terminal_cmd_list = [full_path, "--", shell_path, "-c", internal_command]
                    elif term_exe in ["konsole", "alacritty", "xterm"]:
                        terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                    elif term_exe == "kitty":
                        terminal_cmd_list = [full_path, shell_path, "-c", internal_command]
                    else:
                         terminal_cmd_list = [full_path, "-e", shell_path, "-c", internal_command]
                    found_terminal = True
                    print(f"DEBUG: Found terminal: {full_path}. Launch command: {' '.join(terminal_cmd_list)}")
                    break

            if not found_terminal:
                tui_msg = "internally (TUI not updated)." # TUI not updated in this branch
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Could not find a known terminal emulator.\n"
                    f"(Tried: {', '.join(terminals_to_try)}).\n"
                    f"Please install one or launch manually. Title: Launch Error Severity: warning Timeout: 12"
                )
                return tui_updated, all_env_vars # Return original state

            if terminal_cmd_list:
                subprocess.Popen(terminal_cmd_list)
                term_name = terminal_cmd_list[0]
                tui_msg = "internally and TUI updated." if tui_updated else "internally (TUI not updated)."
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Attempting to launch '{term_name}' in '~' with the variable unset. Title: Launching Terminal (Session) Timeout: 12"
                )

        except FileNotFoundError:
            tui_msg = "internally (TUI not updated)."
            term_name = terminal_cmd_list[0] if terminal_cmd_list else "the specified terminal"
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Found terminal '{term_name}' but failed to execute it.\n"
                f"Check path/permissions or try installing another terminal. Title: Launch Execution Error Severity: error Timeout: 12"
            )
        except Exception as e:
             tui_msg = "internally (TUI not updated)."
             notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Failed to launch new terminal: {e}\n"
                f"Attempted command: {' '.join(map(shlex.quote, terminal_cmd_list)) if terminal_cmd_list else 'N/A'}. Title: Launch Error Severity: error Timeout: 15"
            )

    elif copy_cmd_only: # Delete Copy Cmd
        shell_type = "shell"
        tui_msg = "internally (TUI not updated)."
        try:
            pyperclip.copy(unset_cmd)
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Run in your {shell_type} (copied to clipboard):\n"
                f"[i]{unset_cmd}[/i]. Title: Unset Command Copied (Session) Timeout: 10"
            )
        except Exception as e:
             notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Run in your {shell_type}:\n"
                f"[i]{unset_cmd}[/i]\n"
                f"(Copy failed: {e}). Title: Unset Command Copy Failed Timeout: 10 Severity: warning"
            )
    elif update_rc: # Delete Update RC (Linux Only)
        config_file = get_shell_config_file()
        if config_file:
            config_path = Path(config_file)
            config_dir = config_path.parent
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                tui_msg = "internally and TUI updated." # TUI is updated in this branch
                if not config_path.exists():
                    notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Config file [i]{config_file}[/i] does not exist. Cannot remove variable. Title: Config Update Info Severity: info Timeout: 10"
                    )
                    return tui_updated, current_env_vars # Return updated state

                lines = config_path.read_text().splitlines()
                new_lines = []
                found_and_removed = False
                search_prefix = f"export {var_name}="
                comment_prefix = f"# Added/Updated by EnvTuiApp"

                i = 0
                while i < len(lines):
                    line = lines[i]
                    stripped_line = line.strip()
                    if stripped_line.startswith(search_prefix):
                        if i > 0 and lines[i-1].strip() == comment_prefix:
                            if new_lines and new_lines[-1].strip() == comment_prefix:
                                new_lines.pop()
                                if new_lines and not new_lines[-1].strip():
                                    new_lines.pop()
                        found_and_removed = True
                        i += 1
                        continue
                    new_lines.append(line)
                    i += 1

                if found_and_removed:
                    config_path.write_text("\n".join(new_lines) + "\n")
                    notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Removed export command from:\n[i]{config_file}[/i]\n"
                        f"[b]Note:[/b] This change will only apply to [u]new[/u] shell sessions. Title: Config File Updated (Persistent) Timeout: 12"
                    )
                else:
                    notify(
                        f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                        f"Variable export not found in [i]{config_file}[/i]. No changes made to file. Title: Config Update Info Severity: info Timeout: 10"
                    )

            except Exception as e:
                tui_msg = "internally and TUI updated, but"
                notify(
                    f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                    f"Failed to update config file [i]{config_file}[/i]:\n{e}. Title: Config Update Error Severity: error Timeout: 12"
                )
        else:
            tui_msg = "internally and TUI updated, but"
            notify(
                f"{action_verb} [b]{var_name}[/b] {tui_msg}\n"
                f"Could not determine shell config file (SHELL={os.environ.get('SHELL', 'Not set')}). Cannot update RC file. Title: Config Update Error Severity: error Timeout: 10"
            )

    # Return whether the TUI state was updated and the potentially modified env vars
    return tui_updated, current_env_vars if tui_updated else all_env_vars
