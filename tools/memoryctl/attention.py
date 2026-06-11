"""Deterministic attention signals for open event notes.

The engine pre-computes objective signals (due soon, stale, blocked, missing
owner) so the attention loop body starts from facts instead of re-deriving
them. Judgment about urgency wording and recommended actions stays with the
LLM loop body.
"""

from datetime import datetime, timezone

from .config import DUE_SOON_DAYS, OPEN_EVENT_STATUSES, STALE_OPEN_LOOP_DAYS
from .frontmatter import parse_iso_datetime, read_note


def event_signals(path: str) -> dict | None:
    """Compute signals for one event note. Returns None for closed events."""
    fm, _ = read_note(path)
    status = str(fm.get("status", "open")).strip().lower()
    if status not in OPEN_EVENT_STATUSES:
        return None

    now = datetime.now(timezone.utc)
    flags: list[str] = []

    days_to_due = None
    due = parse_iso_datetime(fm.get("due_time"))
    if due is not None:
        days_to_due = round((due - now).total_seconds() / 86400, 2)
        if days_to_due < 0:
            flags.append("overdue")
        elif days_to_due <= DUE_SOON_DAYS:
            flags.append("due_soon")

    days_since_update = None
    updated = parse_iso_datetime(fm.get("last_updated"))
    if updated is not None:
        days_since_update = round((now - updated).total_seconds() / 86400, 2)
        if days_since_update > STALE_OPEN_LOOP_DAYS:
            flags.append("stale_open_loop")

    if status == "blocked":
        flags.append("blocked")
    if status == "waiting":
        flags.append("waiting_external")
    if status == "needs_confirmation":
        flags.append("needs_confirmation")
    if not str(fm.get("owner", "")).strip():
        flags.append("missing_owner")

    return {
        "status": status,
        "flags": flags,
        "days_to_due": days_to_due,
        "days_since_update": days_since_update,
        "attention_score": fm.get("attention_score"),
    }
