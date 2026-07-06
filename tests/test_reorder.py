"""Tests for the reorder CLI command and persistence of entry ordering.

These tests exercise the data layer (load/save + the `reorder` CLI command)
without requiring a display or tkinter — the GUI drag-to-reorder handler uses
the same save_entries() function, so persistence is verified here.
"""
import json
import os
import subprocess
import sys

import click.testing

# Import the module under test
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import superpaste  # noqa: E402


def _setup_temp_data(tmp_path, entries):
    """Point superpaste.DATA_FILE at a temp file and write entries to it."""
    data_file = tmp_path / ".superpaste.json"
    superpaste.DATA_FILE = str(data_file)
    with open(data_file, "w") as f:
        json.dump(entries, f)
    return data_file


def test_reorder_moves_entry_and_persists(tmp_path):
    entries = [
        {"name": "A", "content": "alpha"},
        {"name": "B", "content": "beta"},
        {"name": "C", "content": "gamma"},
    ]
    data_file = _setup_temp_data(tmp_path, entries)

    runner = click.testing.CliRunner()
    result = runner.invoke(superpaste.cli, ["reorder", "1", "3"])
    assert result.exit_code == 0, result.output
    assert "Moved entry 'A'" in result.output

    # Verify persisted order
    with open(data_file) as f:
        saved = json.load(f)
    assert [e["name"] for e in saved] == ["B", "C", "A"]


def test_reorder_persists_across_reload(tmp_path):
    """Order written by reorder is what load_entries() reads back."""
    entries = [
        {"name": "X", "content": "1"},
        {"name": "Y", "content": "2"},
        {"name": "Z", "content": "3"},
        {"name": "W", "content": "4"},
    ]
    _setup_temp_data(tmp_path, entries)

    runner = click.testing.CliRunner()
    runner.invoke(superpaste.cli, ["reorder", "4", "1"])  # W -> position 1

    reloaded = superpaste.load_entries()
    assert [e["name"] for e in reloaded] == ["W", "X", "Y", "Z"]


def test_reorder_same_position_noop(tmp_path):
    entries = [
        {"name": "A", "content": "a"},
        {"name": "B", "content": "b"},
    ]
    data_file = _setup_temp_data(tmp_path, entries)

    runner = click.testing.CliRunner()
    result = runner.invoke(superpaste.cli, ["reorder", "1", "1"])
    assert result.exit_code == 0

    with open(data_file) as f:
        saved = json.load(f)
    assert [e["name"] for e in saved] == ["A", "B"]


def test_reorder_invalid_index_errors(tmp_path):
    entries = [{"name": "Only", "content": "one"}]
    _setup_temp_data(tmp_path, entries)

    runner = click.testing.CliRunner()
    result = runner.invoke(superpaste.cli, ["reorder", "1", "2"])
    assert result.exit_code != 0
    assert "Invalid indices" in result.output


def test_drag_swap_logic_mirrors_cli(tmp_path):
    """The GUI _drag_motion handler swaps two adjacent entries; verify that
    a sequence of adjacent swaps produces the same result as a reorder CLI
    call moving an item across the same span."""
    entries = [
        {"name": "A", "content": "a"},
        {"name": "B", "content": "b"},
        {"name": "C", "content": "c"},
        {"name": "D", "content": "d"},
    ]
    # GUI path: simulate swapping entry 0 (A) rightward three times
    gui_entries = [dict(e) for e in entries]
    # swap A (idx 0) with idx 1, then idx 2, then idx 3
    for target in (1, 2, 3):
        current = gui_entries.index(next(e for e in gui_entries if e["name"] == "A"))
        gui_entries[current], gui_entries[target] = gui_entries[target], gui_entries[current]
    assert [e["name"] for e in gui_entries] == ["B", "C", "D", "A"]

    # CLI path: reorder 1 -> 4 should yield the same final order
    _setup_temp_data(tmp_path, entries)
    runner = click.testing.CliRunner()
    runner.invoke(superpaste.cli, ["reorder", "1", "4"])
    cli_entries = superpaste.load_entries()
    assert [e["name"] for e in cli_entries] == ["B", "C", "D", "A"]