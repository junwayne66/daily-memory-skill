"""Index loop (deterministic): rebuild wikilink edges and the daily bridge note.

The vault Markdown is the source of truth; this loop derives:
  - index/edges.json: every [[wikilink]] edge, backlinks, unresolved targets
  - knowledge/daily-memory-<date>.md: a compact generated bridge note that
    reader agents can retrieve through shallow memory search
"""

import os
from datetime import datetime, timezone

from .config import OPEN_EVENT_STATUSES, Workspace
from .frontmatter import as_float, read_note, serialize_frontmatter
from .fsutil import atomic_write_json, atomic_write_text, list_files, now_iso

BRIDGE_PREFIX = "daily-memory-"
DEFAULT_ATTENTION_THRESHOLD = 0.75


def _vault_rel(ws: Workspace, path: str) -> str:
    return os.path.relpath(path, ws.knowledge).replace(os.sep, "/")


def build_edges(ws: Workspace) -> dict:
    """Scan every vault note and derive the edge/backlink index."""
    from .validate import build_note_index, extract_wikilinks, resolve_wikilink

    note_index = build_note_index(ws)
    edges: list[dict] = []
    unresolved: list[dict] = []
    backlinks: dict[str, list[str]] = {}
    notes = list_files(ws.knowledge)

    for path in notes:
        rel = _vault_rel(ws, path)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for target in extract_wikilinks(text):
            resolved = resolve_wikilink(target, note_index)
            edge = {"from": rel, "target": target, "to": resolved, "resolved": resolved is not None}
            edges.append(edge)
            if resolved is None:
                unresolved.append({"from": rel, "target": target})
            else:
                backlinks.setdefault(resolved, [])
                if rel not in backlinks[resolved]:
                    backlinks[resolved].append(rel)

    data = {
        "generated_at": now_iso(),
        "note_count": len(notes),
        "edge_count": len(edges),
        "edges": edges,
        "backlinks": backlinks,
        "unresolved": unresolved,
    }
    atomic_write_json(os.path.join(ws.index, "edges.json"), data)
    return data


def _notes_updated_on(ws: Workspace, date: str) -> list[tuple[str, dict]]:
    """Vault notes whose frontmatter last_updated (or file mtime) falls on date."""
    updated = []
    for path in list_files(ws.knowledge):
        if os.path.basename(path).startswith(BRIDGE_PREFIX):
            continue
        fm, _ = read_note(path)
        stamp = str(fm.get("last_updated", ""))
        if not stamp:
            stamp = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
        if stamp[:10] == date:
            updated.append((_vault_rel(ws, path), fm))
    return updated


def _open_attention_events(ws: Workspace, threshold: float) -> list[tuple[str, dict]]:
    events = []
    for path in list_files(os.path.join(ws.knowledge, "Events")):
        fm, _ = read_note(path)
        status = str(fm.get("status", "")).strip().lower()
        if status not in OPEN_EVENT_STATUSES:
            continue
        if as_float(fm.get("attention_score"), 0.0) >= threshold:
            events.append((_vault_rel(ws, path), fm))
    events.sort(key=lambda item: -as_float(item[1].get("attention_score"), 0.0))
    return events


def _link(vault_rel: str) -> str:
    return f"[[{os.path.splitext(vault_rel)[0]}]]"


def write_bridge_note(
    ws: Workspace,
    date: str,
    attention_threshold: float = DEFAULT_ATTENTION_THRESHOLD,
) -> dict:
    """Generate knowledge/daily-memory-<date>.md deterministically."""
    updated = _notes_updated_on(ws, date)
    attention = _open_attention_events(ws, attention_threshold)
    report_rel = f"reports/{date}.md"
    report_exists = os.path.exists(ws.path(report_rel))

    by_folder: dict[str, list[str]] = {}
    keywords: list[str] = []
    for rel, fm in updated:
        folder = rel.split("/")[0] if "/" in rel else "(root)"
        by_folder.setdefault(folder, []).append(rel)
        title = str(fm.get("title", "")) or os.path.splitext(os.path.basename(rel))[0]
        if title not in keywords:
            keywords.append(title)

    fm = {
        "type": "bridge",
        "title": f"Daily Memory {date}",
        "date": date,
        "generated_by": "memoryctl index",
        "last_updated": now_iso(),
        "notes_updated": [rel for rel, _ in updated],
    }
    lines = [serialize_frontmatter(fm)]
    lines.append(f"# Daily Memory - {date}\n")
    lines.append("Generated bridge note. The vault notes are the source of truth.\n")

    lines.append("## Top Attention\n")
    if attention:
        for rel, note_fm in attention:
            score = note_fm.get("attention_score", "?")
            status = note_fm.get("status", "?")
            due = note_fm.get("due_time", "")
            extra = f", due {due}" if due else ""
            lines.append(f"- {_link(rel)} (score {score}, {status}{extra})")
    else:
        lines.append("- No open events above the attention threshold.")
    lines.append("")

    lines.append("## Notes Updated Today\n")
    if updated:
        for folder in sorted(by_folder):
            lines.append(f"### {folder}\n")
            for rel in by_folder[folder]:
                lines.append(f"- {_link(rel)}")
            lines.append("")
    else:
        lines.append("- No vault notes were updated on this date.\n")

    lines.append("## Search Keywords\n")
    lines.append(", ".join(keywords) if keywords else "(none)")
    lines.append("")

    lines.append("## Pointers\n")
    lines.append(f"- Owner report: {report_rel}" + ("" if report_exists else " (not generated yet)"))
    lines.append("- Edge index: index/edges.json")
    lines.append("- Vault root: knowledge/")
    lines.append("")

    bridge_rel = f"knowledge/{BRIDGE_PREFIX}{date}.md"
    atomic_write_text(ws.path(bridge_rel), "\n".join(lines))
    return {
        "bridge_note": bridge_rel,
        "notes_updated": len(updated),
        "attention_items": len(attention),
    }


def run_index(ws: Workspace, date: str | None = None, attention_threshold: float = DEFAULT_ATTENTION_THRESHOLD) -> dict:
    """Run the full deterministic index loop."""
    ws.ensure_layout()
    date = date or datetime.now(timezone.utc).date().isoformat()
    edges = build_edges(ws)
    bridge = write_bridge_note(ws, date, attention_threshold)
    return {
        "loop": "index",
        "date": date,
        "notes": edges["note_count"],
        "edges": edges["edge_count"],
        "unresolved_links": len(edges["unresolved"]),
        **bridge,
    }
