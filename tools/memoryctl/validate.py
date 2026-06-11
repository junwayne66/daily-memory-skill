"""Vault validation: note schema, provenance, and wikilink resolution.

Errors block a commit; warnings are reported but do not block. The rules are
intentionally minimal so the vault stays Obsidian-compatible and human-editable.
"""

import os
import re

from .config import Workspace
from .frontmatter import as_float, read_note
from .fsutil import list_files

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")

NOTE_TYPES = {
    "event",
    "person",
    "organization",
    "project",
    "topic",
    "daily",
    "bridge",
}

FOLDER_TYPE = {
    "Events": "event",
    "People": "person",
    "Organizations": "organization",
    "Projects": "project",
    "Topics": "topic",
    "Daily": "daily",
}

EVENT_STATUSES = {
    "open",
    "in_progress",
    "waiting",
    "blocked",
    "done",
    "cancelled",
    "stale",
    "needs_confirmation",
}


def extract_wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def build_note_index(ws: Workspace) -> dict[str, list[str]]:
    """Map note basename (without .md) and vault-relative path to note paths."""
    index: dict[str, list[str]] = {}
    for path in list_files(ws.knowledge):
        rel = os.path.relpath(path, ws.knowledge).replace(os.sep, "/")
        stem = os.path.splitext(os.path.basename(path))[0]
        index.setdefault(stem, []).append(rel)
        index.setdefault(os.path.splitext(rel)[0], []).append(rel)
    return index


def resolve_wikilink(target: str, note_index: dict[str, list[str]]) -> str | None:
    """Resolve an Obsidian-style link target to a vault-relative note path."""
    hits = note_index.get(target.strip())
    return hits[0] if hits else None


def validate_note(ws: Workspace, path: str, note_index: dict) -> tuple[list[str], list[str]]:
    rel = ws.relpath(path)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        fm, body = read_note(path)
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{rel}: unreadable note ({exc})"], []

    note_type = str(fm.get("type", "")).strip().lower()
    vault_rel = os.path.relpath(path, ws.knowledge).replace(os.sep, "/")
    folder = vault_rel.split("/")[0] if "/" in vault_rel else ""

    if not fm:
        errors.append(f"{rel}: missing frontmatter")
        return errors, warnings
    if not note_type:
        errors.append(f"{rel}: missing 'type' in frontmatter")
    elif note_type not in NOTE_TYPES:
        errors.append(f"{rel}: unknown type '{note_type}'")
    expected = FOLDER_TYPE.get(folder)
    if expected and note_type and note_type not in (expected, "bridge"):
        warnings.append(f"{rel}: type '{note_type}' but stored under {folder}/")

    if note_type == "event":
        status = str(fm.get("status", "")).strip().lower()
        if not status:
            errors.append(f"{rel}: event note missing 'status'")
        elif status not in EVENT_STATUSES:
            errors.append(f"{rel}: invalid event status '{status}'")
        refs = fm.get("source_refs")
        if not refs or not isinstance(refs, list):
            errors.append(f"{rel}: event note missing non-empty 'source_refs'")
        else:
            for ref in refs:
                ref_path = ws.path(str(ref))
                if not os.path.exists(ref_path):
                    warnings.append(f"{rel}: source_ref not found: {ref}")
        if "confidence" not in fm:
            errors.append(f"{rel}: event note missing 'confidence'")
        elif not 0.0 <= as_float(fm.get("confidence"), -1.0) <= 1.0:
            errors.append(f"{rel}: confidence must be a number in [0, 1]")
    elif note_type in ("person", "organization", "project", "topic"):
        if not fm.get("source_refs"):
            warnings.append(f"{rel}: no source_refs (provenance recommended)")

    for target in extract_wikilinks((body or "")):
        if resolve_wikilink(target, note_index) is None:
            warnings.append(f"{rel}: unresolved wikilink [[{target}]]")

    return errors, warnings


def validate_vault(ws: Workspace, paths: list[str] | None = None) -> dict:
    """Validate the given notes (or the whole vault). Returns errors/warnings."""
    note_index = build_note_index(ws)
    targets = [ws.path(p) for p in paths] if paths else list_files(ws.knowledge)
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for path in targets:
        if not os.path.exists(path):
            all_errors.append(f"{ws.relpath(path)}: file does not exist")
            continue
        errors, warnings = validate_note(ws, path, note_index)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
    return {
        "checked": len(targets),
        "errors": all_errors,
        "warnings": all_warnings,
        "ok": not all_errors,
    }
