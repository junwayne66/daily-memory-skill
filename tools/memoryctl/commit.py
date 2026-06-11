"""Commit (or fail) a batch: validate outputs, persist loop state incrementally."""

import os

from .config import Workspace
from .fsutil import atomic_write_json, now_iso, read_json
from .state import load_state, mark_processed, save_state
from .validate import validate_vault

# Loops whose body writes vault notes; their commits gate on vault validation.
VALIDATED_LOOPS = ("graph", "attention")


def _batch_path(ws: Workspace, loop: str, batch_id: str) -> str:
    return os.path.join(ws.batch_dir(loop), f"{batch_id}.json")


def load_batch(ws: Workspace, loop: str, batch_id: str) -> dict:
    data = read_json(_batch_path(ws, loop, batch_id))
    if not isinstance(data, dict):
        raise FileNotFoundError(f"batch not found: {loop}/{batch_id}")
    return data


def commit_batch(
    ws: Workspace,
    loop: str,
    batch_id: str,
    force: bool = False,
    skip_validation: bool = False,
) -> dict:
    """Mark every file in the batch as processed using its current content.

    For vault-writing loops, the whole vault is validated first; schema errors
    block the commit unless --force is given. State is saved atomically, so a
    crash between batches never loses completed work.
    """
    batch = load_batch(ws, loop, batch_id)
    if batch.get("status") != "pending":
        raise ValueError(f"batch {batch_id} is not pending (status={batch.get('status')})")

    validation = None
    if loop in VALIDATED_LOOPS and not skip_validation:
        validation = validate_vault(ws)
        if not validation["ok"] and not force:
            return {
                "committed": False,
                "reason": "vault validation failed",
                "validation": validation,
            }

    state = load_state(ws, loop)
    processed: list[str] = []
    missing: list[str] = []
    for entry in batch.get("files", []):
        abspath = ws.path(entry["path"])
        if not os.path.exists(abspath):
            missing.append(entry["path"])
            continue
        mark_processed(ws, state, abspath)
        processed.append(entry["path"])
    save_state(ws, state)

    batch["status"] = "committed"
    batch["committed_at"] = now_iso()
    batch["processed"] = processed
    batch["missing"] = missing
    atomic_write_json(_batch_path(ws, loop, batch_id), batch)

    return {
        "committed": True,
        "loop": loop,
        "batch_id": batch_id,
        "processed": len(processed),
        "missing": missing,
        "validation": validation,
    }


def fail_batch(ws: Workspace, loop: str, batch_id: str, reason: str = "") -> dict:
    """Mark a batch as failed; its files stay unprocessed and will be rescanned."""
    batch = load_batch(ws, loop, batch_id)
    batch["status"] = "failed"
    batch["failed_at"] = now_iso()
    batch["failure_reason"] = reason
    atomic_write_json(_batch_path(ws, loop, batch_id), batch)
    return {"failed": True, "loop": loop, "batch_id": batch_id, "reason": reason}
