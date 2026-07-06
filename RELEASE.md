# Release Notes

## v0.1.1

- **Drag-to-reorder entries in the palette**: Grab the grip handle (⠿) on any entry and drag it to a new position. The new order is saved automatically and persists across restarts. Reordering is paused while a search filter is active.
- **New `reorder` CLI command**: Move entries from the terminal with `superpaste reorder FROM TO` (1-based indices), mirroring the GUI drag behaviour — handy for scripting and automation.

## v0.1.0

- **GUI clipboard palette**: Browse and copy saved text entries with a single click, with search/filter support.
- **Toggle signal**: Bring a running instance to the front via Unix socket — bind `superpaste toggle` to a hotkey.
- **Full CLI**: Manage entries from the terminal with `add`, `list`, `copy`, `delete`, `show`, and `config` commands.
- **Auto-hide**: Window automatically minimizes after copying for a quick, distraction-free workflow.
- **Persistent storage**: Entries saved to `~/.superpaste.json`.
