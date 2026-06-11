"""Filesystem helpers: hashing, atomic writes, file listing."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def content_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def atomic_write_text(path: str, text: str) -> None:
    """Write via temp file + rename so readers never see partial content."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(path: str, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_files(root: str, suffixes=(".md",)) -> list[str]:
    """Recursively list files under root with the given suffixes, sorted."""
    found: list[str] = []
    if not os.path.isdir(root):
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            if suffixes and not any(name.endswith(s) for s in suffixes):
                continue
            found.append(os.path.join(dirpath, name))
    found.sort()
    return found


def short_hash(text: str, length: int = 6) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
