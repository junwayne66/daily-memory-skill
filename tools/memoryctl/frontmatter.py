"""Tolerant Markdown frontmatter reader.

The engine only ever READS frontmatter (notes are written by the agent or
generated wholesale, never rewritten in place), so a small flat parser is
enough: top-level `key: value` scalars and `key:` + `- item` lists. Unknown
or nested structures are preserved as raw strings and ignored.
"""

import re
from datetime import datetime, timezone

_DELIM = "---"
_KEY_RE = re.compile(r"^([A-Za-z0-9_\-]+):(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s+-\s*(.*)$")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter_text, body). frontmatter_text is None if absent."""
    if not text.startswith(_DELIM + "\n") and text.strip() != _DELIM:
        return None, text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return None, text


def _clean_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_frontmatter(fm_text: str) -> dict:
    """Parse flat key/value and key/list frontmatter into a dict.

    Values are strings; list values are lists of strings. Nested mappings
    are flattened into raw strings of their lines (ignored by the engine).
    """
    data: dict = {}
    current_key: str | None = None
    for line in fm_text.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = _KEY_RE.match(line)
        if m:
            key, rest = m.group(1), m.group(2)
            if rest.strip() == "":
                data[key] = []
                current_key = key
            else:
                data[key] = _clean_scalar(rest)
                current_key = None
            continue
        m = _LIST_ITEM_RE.match(line)
        if m and current_key is not None and isinstance(data.get(current_key), list):
            data[current_key].append(_clean_scalar(m.group(1)))
            continue
        # Nested/unknown structure under the current key: keep raw lines.
        if current_key is not None:
            existing = data.get(current_key)
            if isinstance(existing, list) and existing and not isinstance(existing[0], str):
                continue
            if isinstance(existing, list):
                data[current_key] = "\n".join([*existing, line.strip()]) if existing else line.strip()
            else:
                data[current_key] = f"{existing}\n{line.strip()}" if existing else line.strip()
    return data


def read_note(path: str) -> tuple[dict, str]:
    """Read a Markdown file, returning (frontmatter_dict, body)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        return {}, body
    return parse_frontmatter(fm_text), body


def serialize_frontmatter(data: dict) -> str:
    """Serialize a flat dict back to frontmatter text (used for generated notes)."""
    lines = [_DELIM]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append(_DELIM)
    return "\n".join(lines) + "\n"


def as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_iso_datetime(value):
    """Parse an ISO-8601 timestamp; returns timezone-aware datetime or None."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
