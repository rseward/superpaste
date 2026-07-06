#!/usr/bin/env python3
"""SuperPaste - A streamlined clipboard palette GUI utility.

Single-click any entry to copy it to the clipboard.
Use the "Manage" button for CRUD operations on entries.
Drag the grip handle (⠿) on the left of any entry to reorder it; the new
order is saved automatically and persists across restarts.
Use --toggle to bring a running instance to the front (bind to a hotkey).
"""

import json
import os
import signal
import socket
import sys

import click


DATA_FILE = os.path.join(os.path.expanduser("~"), ".superpaste.json")
TOGGLE_SOCKET = os.path.join(os.path.expanduser("~"), ".superpaste.sock")
TOGGLE_MAGIC = b"SUPERPASTE_TOGGLE"


def load_entries():
    """Load entries from the JSON data file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_entries(entries):
    """Save entries to the JSON data file."""
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def send_toggle_signal():
    """Send a toggle signal to a running SuperPaste instance via Unix socket."""
    if os.path.exists(TOGGLE_SOCKET):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(TOGGLE_SOCKET)
            s.sendall(TOGGLE_MAGIC)
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            # Stale socket — clean it up
            try:
                os.unlink(TOGGLE_SOCKET)
            except OSError:
                pass
    return False


def start_toggle_listener(app):
    """Start a Unix socket listener that brings the app to front on toggle."""
    import customtkinter as ctk

    # Clean up any stale socket
    if os.path.exists(TOGGLE_SOCKET):
        try:
            os.unlink(TOGGLE_SOCKET)
        except OSError:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(TOGGLE_SOCKET)
    server.listen(1)
    server.setblocking(False)

    def poll_socket():
        try:
            conn, _ = server.accept()
            data = conn.recv(256)
            conn.close()
            if data == TOGGLE_MAGIC:
                app.bring_to_front()
        except (BlockingIOError, OSError):
            pass
        app.after(200, poll_socket)

    app.after(200, poll_socket)
    return server


def launch_gui():
    """Import GUI dependencies and launch the SuperPaste GUI.

    This function defers customtkinter/pyperclip imports so that
    CLI-only usage (list, add, show, etc.) works without a display.
    """
    import customtkinter as ctk
    import pyperclip

    class ManageDialog(ctk.CTkToplevel):
        """Modal dialog for managing (CRUD) entries."""

        def __init__(self, parent, entries, on_save):
            super().__init__(parent)
            self.title("Manage Entries")
            self.geometry("550x500")
            self.transient(parent)
            # Defer grab_set until window is viewable to avoid TclError
            self.after(10, self._grab_focus)

            self.entries = list(entries)  # work on a copy
            self.on_save = on_save
            self.selected_index = None

            self._build_ui()
            self._refresh_list()

            # Close on Escape
            self.bind("<Escape>", lambda e: self.destroy())

        def _grab_focus(self):
            """Deferred grab_set — called after window is viewable."""
            try:
                self.wait_visibility()
                self.grab_set()
                self.focus_force()
            except Exception:
                # Window may have been destroyed before becoming visible
                # (e.g. parent window auto-hid). Just skip the grab.
                pass

        def _build_ui(self):
            # Left: entry list
            left = ctk.CTkFrame(self, width=200)
            left.pack(side="left", fill="y", padx=(10, 5), pady=10)
            left.pack_propagate(False)

            ctk.CTkLabel(left, text="Entries", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 5))

            self.list_frame = ctk.CTkScrollableFrame(left)
            self.list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

            btn_row = ctk.CTkFrame(left, fg_color="transparent")
            btn_row.pack(fill="x", padx=5, pady=(0, 5))

            ctk.CTkButton(btn_row, text="+ Add", command=self._add, width=80).pack(side="left", padx=(0, 3))
            ctk.CTkButton(btn_row, text="- Delete", command=self._delete, width=80, fg_color="#d32f2f", hover_color="#b71c1c").pack(side="left", padx=(3, 0))

            # Right: edit area
            right = ctk.CTkFrame(self)
            right.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

            ctk.CTkLabel(right, text="Name:", anchor="w").pack(fill="x", padx=10, pady=(10, 2))
            self.name_entry = ctk.CTkEntry(right, placeholder_text="Short name")
            self.name_entry.pack(fill="x", padx=10, pady=(0, 10))

            ctk.CTkLabel(right, text="Content:", anchor="w").pack(fill="x", padx=10, pady=(0, 2))
            self.content_box = ctk.CTkTextbox(right, height=200)
            self.content_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            btn_row2 = ctk.CTkFrame(right, fg_color="transparent")
            btn_row2.pack(fill="x", padx=10, pady=(0, 10))
            ctk.CTkButton(btn_row2, text="Save Changes", command=self._save_entry).pack(side="left")
            ctk.CTkButton(btn_row2, text="Done", command=self._done, fg_color="gray").pack(side="right")

        def _refresh_list(self):
            for w in self.list_frame.winfo_children():
                w.destroy()
            for i, entry in enumerate(self.entries):
                name = entry.get("name", f"Entry {i+1}")
                is_selected = self.selected_index == i
                btn = ctk.CTkButton(
                    self.list_frame,
                    text=name,
                    command=lambda idx=i: self._select(idx),
                    anchor="w",
                    fg_color=("#3a7ebf", "#3a7ebf") if is_selected else "transparent",
                    text_color=("white", "white") if is_selected else ("gray10", "gray90"),
                    hover_color=("#4a8ecf", "#4a8ecf"),
                )
                btn.pack(fill="x", pady=1)

        def _select(self, index):
            if 0 <= index < len(self.entries):
                self.selected_index = index
                self.name_entry.delete(0, "end")
                self.name_entry.insert(0, self.entries[index].get("name", ""))
                self.content_box.delete("1.0", "end")
                self.content_box.insert("1.0", self.entries[index].get("content", ""))
                self._refresh_list()

        def _add(self):
            self.entries.append({"name": "New Entry", "content": ""})
            save_entries(self.entries)
            self.selected_index = len(self.entries) - 1
            self._select(self.selected_index)
            self._refresh_list()

        def _delete(self):
            if self.selected_index is not None and 0 <= self.selected_index < len(self.entries):
                del self.entries[self.selected_index]
                save_entries(self.entries)
                self.selected_index = None
                self.name_entry.delete(0, "end")
                self.content_box.delete("1.0", "end")
                self._refresh_list()

        def _save_entry(self):
            if self.selected_index is not None and 0 <= self.selected_index < len(self.entries):
                name = self.name_entry.get().strip() or f"Entry {self.selected_index + 1}"
                content = self.content_box.get("1.0", "end-1c")
                self.entries[self.selected_index]["name"] = name
                self.entries[self.selected_index]["content"] = content
                save_entries(self.entries)
                self._refresh_list()

        def _done(self):
            self.on_save(self.entries)
            self.destroy()

    class SuperPasteApp(ctk.CTk):
        """Main application — streamlined for quick clipboard copying."""

        def __init__(self):
            super().__init__()
            self.title("SuperPaste")
            self.geometry("350x500")
            self.minsize(300, 400)

            ctk.set_appearance_mode("System")
            ctk.set_default_color_theme("blue")

            self.entries = load_entries()
            self.toggle_server = None
            self._auto_hide_id = None

            # Drag-to-reorder state
            self._drag_active = False
            self._drag_index = None
            self._palette_rows = []        # row frames, parallel to visible list
            self._visible_indices = []     # actual entry index for each visible row

            self._build_ui()
            self._refresh_palette()

            # Start toggle listener
            self.toggle_server = start_toggle_listener(self)

            # Handle window close
            self.protocol("WM_DELETE_WINDOW", self._on_close)

            # Global keyboard shortcut: Escape to hide window
            self.bind("<Escape>", lambda e: self._hide_window())

            # Drag-to-reorder: capture motion/release globally so events keep
            # arriving even after palette refresh destroys the original grip.
            self.bind_all("<B1-Motion>", self._drag_motion)
            self.bind_all("<ButtonRelease-1>", self._drag_end)

        def bring_to_front(self):
            """Bring this window to the front (called by toggle signal)."""
            self.after(0, self._bring_to_front_impl)

        def _bring_to_front_impl(self):
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))

        def _hide_window(self):
            self.withdraw()

        def _cancel_auto_hide(self):
            """Cancel any pending auto-hide timer."""
            if self._auto_hide_id is not None:
                self.after_cancel(self._auto_hide_id)
                self._auto_hide_id = None

        def _on_close(self):
            if self.toggle_server:
                self.toggle_server.close()
            if os.path.exists(TOGGLE_SOCKET):
                try:
                    os.unlink(TOGGLE_SOCKET)
                except OSError:
                    pass
            self.destroy()

        def _build_ui(self):
            # Top bar with Manage button
            top_bar = ctk.CTkFrame(self, fg_color="transparent")
            top_bar.pack(fill="x", padx=10, pady=(10, 5))

            ctk.CTkLabel(top_bar, text="SuperPaste", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

            ctk.CTkButton(
                top_bar, text="Manage", width=80, command=self._open_manage, fg_color="gray", hover_color="#555"
            ).pack(side="right")

            # Search/filter
            self.search_var = ctk.StringVar()
            self.search_var.trace_add("write", lambda *_: self._refresh_palette())
            self.search_entry = ctk.CTkEntry(self, placeholder_text="Search...", textvariable=self.search_var)
            self.search_entry.pack(fill="x", padx=10, pady=(0, 5))

            # Main palette — scrollable button list
            self.palette_frame = ctk.CTkScrollableFrame(self)
            self.palette_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

            # Status bar
            self.status_label = ctk.CTkLabel(self, text="Click an entry to copy", anchor="w", text_color="gray")
            self.status_label.pack(fill="x", padx=10, pady=(0, 5))

        def _refresh_palette(self):
            """Refresh the main palette of copy buttons.

            Each entry is rendered as a row: a grip handle on the left
            (drag to reorder) and a copy button on the right. Reordering is
            disabled when a search filter is active (reordering a filtered
            subset is ambiguous and would silently move items the user can't
            see).
            """
            for w in self.palette_frame.winfo_children():
                w.destroy()
            self._palette_rows = []
            self._visible_indices = []

            query = self.search_var.get().lower().strip() if hasattr(self, 'search_var') else ""
            filter_active = bool(query)

            for i, entry in enumerate(self.entries):
                name = entry.get("name", f"Entry {i+1}")
                content = entry.get("content", "")
                # Show a preview snippet
                preview = content[:60].replace("\n", " ") if content else "(empty)"
                if len(content) > 60:
                    preview += "..."

                # Filter by search
                if query and query not in name.lower() and query not in content.lower():
                    continue

                row = ctk.CTkFrame(self.palette_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)

                # Highlight the row currently being dragged.
                is_dragging = (
                    self._drag_active
                    and self._drag_index is not None
                    and i == self._drag_index
                )
                if is_dragging:
                    row.configure(fg_color=("#cfe3ff", "#1e3a5f"))

                # Grip handle — appears draggable. Disabled during search.
                grip = ctk.CTkLabel(
                    row,
                    text="⠿",
                    width=22,
                    anchor="center",
                    text_color=("gray40", "gray60"),
                    cursor="hand2" if not filter_active else "arrow",
                )
                grip.pack(side="left", fill="y", padx=(0, 4))
                if filter_active:
                    grip.configure(text_color=("gray70", "gray70"))
                else:
                    grip.bind("<Button-1>", lambda e, idx=i: self._drag_start(idx, e))

                # Copy button — fills the rest of the row
                btn = ctk.CTkButton(
                    row,
                    text=f"{name}\n{preview}",
                    command=lambda idx=i: self._copy_entry(idx),
                    anchor="w",
                    height=50,
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                    hover_color=("#d0d0d0", "#3a3a3a"),
                )
                btn.pack(side="left", fill="both", expand=True)

                self._palette_rows.append(row)
                self._visible_indices.append(i)

        # ── Drag-to-reorder ───────────────────────────────────────────────

        def _drag_start(self, entry_index, event):
            """Begin a drag operation on a grip handle.

            ``entry_index`` is the index into ``self.entries`` (not the
            visible-row index), so we can swap the right entry even when a
            filter is active. (In practice drag is disabled during filtering,
            so entry_index == visible row index here.)
            """
            self._drag_active = True
            self._drag_index = entry_index
            self._drag_y0 = event.y_root

        def _drag_motion(self, event):
            """Live reorder: swap the dragged entry with its neighbour as the
            pointer crosses row boundaries, and persist the new order."""
            if not self._drag_active or self._drag_index is None:
                return

            y = event.y_root

            # Build a map of row -> (entry_index, y_mid) for visible rows.
            # Use winfo containing scrollable frame for y-coordinate math.
            try:
                self.palette_frame.update_idletasks()
            except Exception:
                return

            # Find the target row under the pointer by Y midpoint comparison.
            target_pos = None
            for row_pos, row in enumerate(self._palette_rows):
                try:
                    y0 = row.winfo_rooty()
                    y1 = y0 + row.winfo_height()
                except Exception:
                    continue
                if y0 <= y <= y1:
                    target_pos = row_pos
                    break
                if y < y0:
                    # Pointer above this row — insert before it
                    target_pos = row_pos
                    break
            if target_pos is None and self._palette_rows:
                target_pos = len(self._palette_rows) - 1

            if target_pos is None:
                return

            # Translate visible-row position back to entry index
            target_entry_idx = self._visible_indices[target_pos]
            current_entry_idx = self._drag_index

            if target_entry_idx == current_entry_idx:
                return

            # Swap entries in the data list, persist, and refresh.
            entries = self.entries
            entries[current_entry_idx], entries[target_entry_idx] = (
                entries[target_entry_idx],
                entries[current_entry_idx],
            )
            self._drag_index = target_entry_idx
            save_entries(entries)
            self._refresh_palette()

        def _drag_end(self, event):
            """Finalize a drag operation."""
            if self._drag_active:
                self._drag_active = False
                self._drag_index = None
                self._refresh_palette()

        def _copy_entry(self, index):
            """Copy the selected entry's content to the clipboard via pyperclip."""
            if 0 <= index < len(self.entries):
                content = self.entries[index].get("content", "")
                name = self.entries[index].get("name", "Unnamed")
                if content:
                    pyperclip.copy(content)
                    self.status_label.configure(text=f"Copied: {name}")
                    # Auto-minimize after copy for quick workflow
                    self._auto_hide_id = self.after(500, self._hide_window)
                else:
                    self.status_label.configure(text=f"'{name}' is empty")

        def _open_manage(self):
            """Open the CRUD management dialog."""
            self._cancel_auto_hide()
            ManageDialog(self, self.entries, self._on_manage_done)

        def _on_manage_done(self, updated_entries):
            """Callback when manage dialog closes with saved changes."""
            self.entries = updated_entries
            self._refresh_palette()

    app = SuperPasteApp()
    app.mainloop()


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
def cli():
    """SuperPaste - Manage your cut-and-paste text entries."""
    pass


@cli.command()
@click.option("--debug", is_flag=True, help="Enable debug mode with console output")
def gui(debug):
    """Launch the SuperPaste GUI."""
    launch_gui()


@cli.command()
def toggle():
    """Bring a running SuperPaste instance to the front.

    If SuperPaste is already running, this brings it to focus.
    If not running, launches a new instance.

    Bind this to a hotkey for quick access, e.g.:
      Linux:   xdotool or window manager hotkey → superpaste toggle
      Example: superpaste toggle
    """
    if send_toggle_signal():
        click.echo("SuperPaste is now active (brought to front).")
    else:
        click.echo("No running SuperPaste found. Starting new instance...")
        # Launch in background and send toggle shortly after
        import subprocess
        subprocess.Popen([sys.executable, "-m", "superpaste", "gui"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        # Give it a moment to start and create the socket, then toggle
        import time
        for _ in range(10):
            time.sleep(0.3)
            if send_toggle_signal():
                click.echo("SuperPaste launched and brought to front.")
                return
        click.echo("SuperPaste started but toggle signal could not be sent.")


@cli.command()
@click.argument("name")
@click.argument("content")
def add(name, content):
    """Add a new entry from the command line."""
    entries = load_entries()
    entries.append({"name": name, "content": content})
    save_entries(entries)
    click.echo(f"Added entry '{name}'")


@cli.command(name="list")
def list_entries():
    """List all entries."""
    entries = load_entries()
    if not entries:
        click.echo("No entries found.")
        return
    for i, entry in enumerate(entries):
        click.echo(f"  [{i+1}] {entry.get('name', 'Unnamed')}")


@cli.command()
@click.argument("index", type=int)
def copy(index):
    """Copy an entry's content to the system clipboard (1-based index)."""
    import pyperclip
    entries = load_entries()
    if 1 <= index <= len(entries):
        content = entries[index - 1].get("content", "")
        pyperclip.copy(content)
        click.echo(f"Copied '{entries[index - 1].get('name', 'Unnamed')}' to clipboard")
    else:
        click.echo(f"Invalid index. Use 1-{len(entries)}.", err=True)
        sys.exit(1)


@cli.command()
@click.argument("index", type=int)
def delete(index):
    """Delete an entry by index (1-based)."""
    entries = load_entries()
    if 1 <= index <= len(entries):
        name = entries[index - 1].get("name", "Unnamed")
        del entries[index - 1]
        save_entries(entries)
        click.echo(f"Deleted entry '{name}'")
    else:
        click.echo(f"Invalid index. Use 1-{len(entries)}.", err=True)
        sys.exit(1)


@cli.command()
def config():
    """Print the location of the config file and exit."""
    click.echo(DATA_FILE)


@cli.command()
@click.argument("from_index", type=int)
@click.argument("to_index", type=int)
def reorder(from_index, to_index):
    """Move an entry from position FROM_INDEX to TO_INDEX (both 1-based).

    The entry at FROM_INDEX is removed and inserted at TO_INDEX, shifting
    the entries in between. The new order is saved to the data file and
    persists across restarts. This mirrors the drag-to-reorder feature in
    the GUI and is useful for scripting/automation.
    """
    entries = load_entries()
    n = len(entries)
    if not (1 <= from_index <= n) or not (1 <= to_index <= n):
        click.echo(f"Invalid indices. Use 1-{n}.", err=True)
        sys.exit(1)
    # Remove then insert (1-based -> 0-based, insert index is to-1 after removal)
    item = entries.pop(from_index - 1)
    entries.insert(to_index - 1, item)
    save_entries(entries)
    click.echo(f"Moved entry '{item.get('name', 'Unnamed')}' from {from_index} to {to_index}.")


@cli.command()
@click.argument("index", type=int)
def show(index):
    """Show an entry's details (1-based index)."""
    entries = load_entries()
    if 1 <= index <= len(entries):
        entry = entries[index - 1]
        click.echo(f"Name: {entry.get('name', 'Unnamed')}")
        click.echo(f"Content:\n{entry.get('content', '')}")
    else:
        click.echo(f"Invalid index. Use 1-{len(entries)}.", err=True)
        sys.exit(1)


def main():
    """Entry point - default to GUI if no subcommand given."""
    if len(sys.argv) == 1:
        launch_gui()
    else:
        # Support --toggle as a top-level flag (shorthand for 'toggle' subcommand)
        if "--toggle" in sys.argv:
            sys.argv = [sys.argv[0], "toggle"]
        cli()


if __name__ == "__main__":
    main()