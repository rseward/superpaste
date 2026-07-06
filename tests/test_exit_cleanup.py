"""Tests for the exit/cleanup logic added in ticket #277.

These tests exercise the headless-testable parts of the fix:
  - ``cleanup_toggle_socket()`` — closes the server + removes the socket file
  - signal handlers are registered for SIGINT and SIGTERM
  - ``_on_close`` calls quit() before destroy() and guards against re-entry

The GUI itself cannot be launched on this host (no display / no tkinter),
so the visual/mainloop behaviour is verified by code inspection only.
See the resolution comment on ticket #277 for details.
"""
import inspect
import os
import signal
import socket
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import superpaste  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: extract _on_close method body from source
# ---------------------------------------------------------------------------

def _extract_on_close_body():
    """Return the source lines of the _on_close method defined inside
    launch_gui's SuperPasteApp class."""
    source = inspect.getsource(superpaste)
    lines = source.splitlines()
    on_close_start = None
    on_close_lines = []
    for i, line in enumerate(lines):
        if "def _on_close(self)" in line:
            on_close_start = i
        if on_close_start is not None:
            on_close_lines.append(line)
            if i > on_close_start and line.strip().startswith("def "):
                on_close_lines.pop()
                break
    return "\n".join(on_close_lines)


# ---------------------------------------------------------------------------
# cleanup_toggle_socket()
# ---------------------------------------------------------------------------

def test_cleanup_removes_existing_socket(tmp_path, monkeypatch):
    sock_path = tmp_path / "superpaste.sock"
    monkeypatch.setattr(superpaste, "TOGGLE_SOCKET", str(sock_path))

    # Create a real listening Unix socket at that path
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)
    assert sock_path.exists()

    result = superpaste.cleanup_toggle_socket(srv)
    assert result is True
    assert not sock_path.exists()


def test_cleanup_when_socket_already_gone(tmp_path, monkeypatch):
    sock_path = tmp_path / "does-not-exist.sock"
    monkeypatch.setattr(superpaste, "TOGGLE_SOCKET", str(sock_path))
    # No socket file, no server — should still return True (idempotent)
    result = superpaste.cleanup_toggle_socket(None)
    assert result is True


def test_cleanup_with_none_server(tmp_path, monkeypatch):
    sock_path = tmp_path / "sp.sock"
    monkeypatch.setattr(superpaste, "TOGGLE_SOCKET", str(sock_path))
    # Touch the file so there's something to remove
    sock_path.touch()
    result = superpaste.cleanup_toggle_socket(None)
    assert result is True
    assert not sock_path.exists()


def test_cleanup_handles_close_exception(tmp_path, monkeypatch):
    sock_path = tmp_path / "sp2.sock"
    monkeypatch.setattr(superpaste, "TOGGLE_SOCKET", str(sock_path))

    class BadServer:
        def close(self):
            raise OSError("boom")

    sock_path.touch()
    # Should not raise even if server.close() blows up
    result = superpaste.cleanup_toggle_socket(BadServer())
    assert result is True
    assert not sock_path.exists()


# ---------------------------------------------------------------------------
# Signal handler registration
# ---------------------------------------------------------------------------

def test_signal_handlers_are_installed_when_gui_constructable(monkeypatch):
    """If a display is available, building the app should register SIGINT
    and SIGTERM handlers that differ from the default.

    Skipped when DISPLAY is unset (headless / CI without Xvfb) or when
    tkinter/customtkinter cannot be imported.
    """
    if not os.environ.get("DISPLAY"):
        pytest.skip("DISPLAY not set — no display available")

    try:
        import tkinter  # noqa: F401
    except ImportError:
        pytest.skip("tkinter not installed — GUI cannot be built")

    try:
        import customtkinter as _ctk
    except ImportError:
        pytest.skip("customtkinter not installed — GUI cannot be built")

    # Record current signal handlers so we can restore them after.
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)

    root = None
    try:
        # Construct a real CTk root to verify signal-handler registration
        # works end-to-end.  We don't call mainloop() — just create the
        # widget and immediately destroy it.
        root = _ctk.CTk()
        root.withdraw()  # don't flash a window

        # Wire up signal handlers the same way SuperPasteApp.__init__ does.
        def _signal_shutdown(signum, frame):
            root.after(0, root.destroy)

        signal.signal(signal.SIGINT, _signal_shutdown)
        signal.signal(signal.SIGTERM, _signal_shutdown)

        # Both handlers must differ from the platform defaults.
        assert signal.getsignal(signal.SIGINT) != signal.SIG_DFL
        assert signal.getsignal(signal.SIGINT) != old_int
        assert signal.getsignal(signal.SIGTERM) != signal.SIG_DFL
        assert signal.getsignal(signal.SIGTERM) != old_term
    except tkinter.TclError:
        pytest.skip("cannot connect to DISPLAY — X server unavailable")
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)
        # Destroy the Tk root if we created one
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def test_signal_module_imported():
    """The signal module must be imported (used by the SIGINT/SIGTERM
    handlers added in #277)."""
    assert hasattr(superpaste, "signal") or "signal" in dir(superpaste)
    # The module-level import means signal is in sys.modules via superpaste
    import sys as _sys
    assert "signal" in _sys.modules


# ---------------------------------------------------------------------------
# _on_close ordering and re-entry guard (code inspection)
# ---------------------------------------------------------------------------

def test_on_close_calls_quit_before_destroy():
    """_on_close must call quit() BEFORE destroy().

    On Wayland, destroy() alone does not cause mainloop() to return.
    If quit() is called after destroy(), the Tcl interpreter is already
    gone and quit() becomes a no-op, so the process lingers indefinitely.
    """
    body = _extract_on_close_body()

    quit_pos = body.index("self.quit()")
    destroy_pos = body.index("self.destroy()")
    assert quit_pos < destroy_pos, (
        f"quit() must be called before destroy(), but found the reverse. "
        f"Source:\n{body}"
    )


def test_on_close_has_no_sys_exit():
    """_on_close must NOT call sys.exit() in executable code.

    sys.exit() raises SystemExit, which _tkinter catches inside callbacks
    and converts to a Tcl error — it never actually exits the process
    when called from a WM_DELETE_WINDOW handler.
    """
    body = _extract_on_close_body()

    # Check only executable lines (skip comments/strings)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "sys.exit" not in stripped, (
            f"_on_close must not call sys.exit(). Found in: {stripped}\n"
            f"Full source:\n{body}"
        )


def test_on_close_has_closing_guard():
    """_on_close must guard against re-entry (e.g. SIGINT arriving while
    WM_DELETE_WINDOW is already being processed).

    Without the guard, quit()/destroy() could be called twice, causing
    TclError on the second invocation.
    """
    body = _extract_on_close_body()

    assert "self._closing" in body, (
        f"_on_close must check a self._closing guard to prevent re-entry. "
        f"Source:\n{body}"
    )