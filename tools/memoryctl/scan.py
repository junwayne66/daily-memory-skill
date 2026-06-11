"""Scan a loop's inputs and emit the next bounded batch of work.

A batch is a JSON work order under state/batches/<loop>/. The host agent
processes the listed files following the referenced prompt, writes outputs,
then calls `memoryctl commit`. If a pending batch already exists for the
loop, scan returns it again instead of creating a new one, which makes the
loop resumable after an interruption.
"""

import os
from datetime import datetime, timezone

from . import attention as attention_signals
from .config import (
    DEFAULT_BATCH_SIZE,
    LOOPS,
    RELEVANCE_CONTEXT,
    RELEVANCE_EVENT,
    SKILL_ROOT,
    Workspace,
)
from .frontmatter import read_note
from .fsutil import atomic_write_json, list_files, now_iso, read_json, short_hash
from .state import has_file_changed, load_state


def pending_batches(ws: Workspace, loop: str) -> list[dict]:
    batch_dir = ws.batch_dir(loop)
    batches = []
    if not os.path.isdir(batch_dir):
        return batches
    for name in sorted(os.listdir(batch_dir)):
        if not name.endswith(".json"):
            continue
        data = read_json(os.path.join(batch_dir, name))
        if isinstance(data, dict) and data.get("status") == "pending":
            batches.append(data)
    return batches


def _classify_eligible(ws: Workspace, state: dict) -> list[dict]:
    """Sources that are new/changed since the last classification."""
    eligible = []
    for path in list_files(ws.sources):
        if has_file_changed(ws, state, path):
            eligible.append({"path": ws.relpath(path)})
    return eligible


def _graph_eligible(ws: Workspace, state: dict) -> list[dict]:
    """Classified, work-relevant sources that the graph loop has not merged yet."""
    eligible = []
    for path in list_files(ws.sources):
        if not has_file_changed(ws, state, path):
            continue
        fm, _ = read_note(path)
        relevance = fm.get("relevance")
        if relevance not in (RELEVANCE_EVENT, RELEVANCE_CONTEXT):
            continue  # unclassified or skip: not graph work
        eligible.append({"path": ws.relpath(path), "relevance": relevance})
    return eligible


def _attention_eligible(ws: Workspace, state: dict) -> list[dict]:
    """Open events that changed, are due soon, or have gone stale."""
    eligible = []
    today = datetime.now(timezone.utc).date().isoformat()
    events_dir = os.path.join(ws.knowledge, "Events")
    for path in list_files(events_dir):
        signals = attention_signals.event_signals(path)
        if signals is None:
            continue  # closed/cancelled events need no attention pass
        changed = has_file_changed(ws, state, path)
        flagged = bool(signals["flags"])
        if not changed and flagged:
            # Re-surface persistent flags at most once per day.
            entry = state["processed"].get(ws.relpath(path), {})
            last = str(entry.get("last_processed", ""))
            if last.startswith(today):
                flagged = False
        if changed or flagged:
            eligible.append({"path": ws.relpath(path), **signals})
    return eligible


_ELIGIBLE = {
    "classify": _classify_eligible,
    "graph": _graph_eligible,
    "attention": _attention_eligible,
}


def eligible_files(ws: Workspace, loop: str) -> list[dict]:
    spec = LOOPS[loop]
    if spec.kind != "llm":
        raise ValueError(f"loop '{loop}' is deterministic; it has no scan phase")
    state = load_state(ws, loop)
    pending = set()
    for batch in pending_batches(ws, loop):
        pending.update(f["path"] for f in batch.get("files", []))
    return [f for f in _ELIGIBLE[loop](ws, state) if f["path"] not in pending]


def scan(ws: Workspace, loop: str, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Return the next batch for the loop (resumed or freshly created).

    Result: {"batch": <batch dict or None>, "resumed": bool, "remaining": int}
    """
    spec = LOOPS[loop]
    ws.ensure_layout()

    existing = pending_batches(ws, loop)
    remaining = len(eligible_files(ws, loop))
    if existing:
        return {"batch": existing[0], "resumed": True, "remaining": remaining}

    candidates = _ELIGIBLE[loop](ws, load_state(ws, loop))
    if not candidates:
        return {"batch": None, "resumed": False, "remaining": 0}

    take = candidates[:batch_size]
    batch_id = "{}_{}_{}".format(
        loop,
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
        short_hash("\n".join(f["path"] for f in take)),
    )
    batch = {
        "batch_id": batch_id,
        "loop": loop,
        "status": "pending",
        "created_at": now_iso(),
        "prompt": spec.prompt,
        "prompt_path": os.path.join(SKILL_ROOT, spec.prompt) if spec.prompt else None,
        "workdir": ws.root,
        "files": take,
        "remaining_after_batch": len(candidates) - len(take),
    }
    atomic_write_json(os.path.join(ws.batch_dir(loop), f"{batch_id}.json"), batch)
    return {"batch": batch, "resumed": False, "remaining": len(candidates) - len(take)}
