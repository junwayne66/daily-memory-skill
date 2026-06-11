"""Change detection: hybrid mtime + hash, persistence, reset."""

import os

from conftest import write
from memoryctl.state import (
    has_file_changed,
    load_state,
    mark_processed,
    reset_state,
    save_state,
)


def test_new_file_is_changed(ws):
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    assert has_file_changed(ws, state, path) is True


def test_processed_file_is_unchanged(ws):
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    mark_processed(ws, state, path)
    assert has_file_changed(ws, state, path) is False


def test_mtime_only_change_is_skipped(ws):
    """Touching a file without editing it must not re-queue it (hash check)."""
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    mark_processed(ws, state, path)
    os.utime(path, (os.path.getmtime(path) + 100, os.path.getmtime(path) + 100))
    assert has_file_changed(ws, state, path) is False


def test_content_change_is_detected(ws):
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    mark_processed(ws, state, path)
    write(path, "hello world")
    os.utime(path, (os.path.getmtime(path) + 100, os.path.getmtime(path) + 100))
    assert has_file_changed(ws, state, path) is True


def test_state_round_trip(ws):
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    mark_processed(ws, state, path)
    save_state(ws, state)

    reloaded = load_state(ws, "classify")
    assert has_file_changed(ws, reloaded, path) is False
    assert reloaded["last_run"] is not None


def test_reset_state(ws):
    path = write(ws.path("sources/manual/a.md"), "hello")
    state = load_state(ws, "classify")
    mark_processed(ws, state, path)
    save_state(ws, state)

    assert reset_state(ws, "classify") is True
    fresh = load_state(ws, "classify")
    assert has_file_changed(ws, fresh, path) is True
    assert reset_state(ws, "classify") is False
