# SuperPaste

A small GUI utility for managing a clipboard palette. Single-click any entry to copy it to your system clipboard — quick and simple.

## Features

- **Click-to-copy** — Click any entry in the palette to copy its content to the clipboard and auto-hide the window
- **Search/filter** — Type in the search bar to quickly find entries by name or content
- **Manage modal** — Click "Manage" to add, edit, or delete entries (CRUD operations)
- **`--toggle` hotkey support** — Bring a running instance to the front with `superpaste toggle`, perfect for binding to a desktop hotkey
- **CLI commands** — Add, list, show, copy, and delete entries from the command line
- **Persistent storage** — Entries saved to `~/.superpaste.json`

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
make venv    # Create virtual environment
make deps    # Install dependencies
```

## Usage

### GUI

```bash
make run
# or
uv run superpaste.py
# or
uv run superpaste.py gui
```

### Toggle (hotkey activation)

```bash
superpaste toggle       # Brings running instance to front
superpaste --toggle     # Same thing, shorthand
```

Bind `superpaste toggle` to a desktop hotkey (e.g. `Ctrl+Alt+V`) for quick access.

### CLI

```bash
superpaste add "Name" "Content text"    # Add an entry
superpaste list                         # List all entries
superpaste show 1                       # Show entry details (1-based index)
superpaste copy 1                       # Copy entry content to clipboard
superpaste delete 1                     # Delete an entry
```

## Tech Stack

- **GUI**: [customtkinter](https://github.com/TomSchimansky/CustomTkinter)
- **CLI**: [click](https://click.palletsprojects.com/)
- **Clipboard**: [pyperclip](https://github.com/asweigart/pyperclip)
- **Package management**: [uv](https://docs.astral.sh/uv/)

## Makefile Targets

| Target | Description |
|--------|-------------|
| `venv` | Create uv virtual environment |
| `deps` | Install dependencies (`uv sync`) |
| `run`  | Launch the GUI (`uv run superpaste.py`) |