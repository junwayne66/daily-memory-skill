"""Per-loop processed-file state with hybrid mtime + hash change detection.

Mirrors rowboat's graph_state.ts:
  - quick check: unchanged mtime means unchanged file, skip hashing
  - verification: if mtime moved, compare content hash; identical hash means
    a false positive (touched but not edited), record new mtime and skip
State files live at state/<loop>_state.json and are written atomically after
every committed batch, so an interrupted run resumes without reprocessing.
"""

import os

from .config import Workspace
from .fsutil import atomic_write_json, content_hash, now_iso, read_json


def load_state(ws: Workspace, loop: str) -> dict:
    state = read_json(ws.state_file(loop), default=None)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("loop", loop)
    state.setdefault("processed", {})
    state.setdefault("last_run", None)
    return state


def save_state(ws: Workspace, state: dict) -> None:
    state["last_run"] = now_iso()
    atomic_write_json(ws.state_file(state["loop"]), state)


def file_entry(path: str) -> dict:
    return {
        "mtime": os.path.getmtime(path),
        "hash": content_hash(path),
        "last_processed": now_iso(),
    }


def has_file_changed(ws: Workspace, state: dict, abspath: str) -> bool:
    """True if the file is new or its content changed since last processing."""
    rel = ws.relpath(abspath)
    entry = state["processed"].get(rel)
    if entry is None:
        return True
    try:
        mtime = os.path.getmtime(abspath)
    except OSError:
        return False  # vanished; nothing to process
    if mtime == entry.get("mtime"):
        return False
    new_hash = content_hash(abspath)
    if new_hash == entry.get("hash"):
        # mtime false positive: refresh mtime in memory so the next scan is cheap.
        entry["mtime"] = mtime
        return False
    return True


def mark_processed(ws: Workspace, state: dict, abspath: str) -> None:
    """Record the file as processed using its CURRENT content.

    The hash is recomputed at commit time (not scan time) because loop bodies
    may legitimately rewrite the input in place, e.g. the classify loop adds
    frontmatter labels to source files.
    """
    rel = ws.relpath(abspath)
    state["processed"][rel] = file_entry(abspath)


def forget(ws: Workspace, state: dict, abspath: str) -> None:
    state["processed"].pop(ws.relpath(abspath), None)


def reset_state(ws: Workspace, loop: str) -> bool:
    """Delete the loop state file. Returns True if a file was removed."""
    path = ws.state_file(loop)
    if os.path.exists(path):
        os.unlink(path)
        return True
    return False
