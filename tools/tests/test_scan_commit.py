"""Batch protocol: scan/commit/fail, resume, eligibility, validation gate."""

import json
import os

from conftest import write
from memoryctl.commit import commit_batch, fail_batch
from memoryctl.scan import scan
from memoryctl.state import has_file_changed, load_state

EVENT_NOTE = """---
type: event
title: Demo event
status: open
confidence: 0.8
last_updated: 2026-06-10T10:00:00+00:00
source_refs:
  - sources/manual/a.md
---

# Demo event
"""


def _classify(ws, path, relevance):
    """Simulate the classify loop body: append relevance frontmatter."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("---\n\n", f"relevance: {relevance}\n---\n\n", 1)
    write(path, text)


def test_scan_respects_batch_size(ws):
    for i in range(5):
        write(ws.path(f"sources/manual/{i}.md"), f"---\nsource_type: manual\n---\n\nnote {i}")
    result = scan(ws, "classify", batch_size=2)
    assert len(result["batch"]["files"]) == 2
    assert result["remaining"] == 3


def test_scan_resumes_pending_batch(ws):
    write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    first = scan(ws, "classify")
    second = scan(ws, "classify")
    assert second["resumed"] is True
    assert second["batch"]["batch_id"] == first["batch"]["batch_id"]


def test_pending_files_never_double_issued(ws):
    write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    write(ws.path("sources/manual/b.md"), "---\nsource_type: manual\n---\n\nB")
    first = scan(ws, "classify", batch_size=1)
    pending_paths = {f["path"] for f in first["batch"]["files"]}
    # A second scan resumes the same batch; its files do not leak elsewhere.
    second = scan(ws, "classify", batch_size=1)
    assert {f["path"] for f in second["batch"]["files"]} == pending_paths


def test_commit_records_post_edit_hash(ws):
    """The classify body rewrites sources; commit must hash the edited file."""
    path = write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    batch = scan(ws, "classify")["batch"]
    _classify(ws, path, "event")
    result = commit_batch(ws, "classify", batch["batch_id"])
    assert result["committed"] is True

    state = load_state(ws, "classify")
    assert has_file_changed(ws, state, path) is False  # post-edit content recorded
    assert scan(ws, "classify")["batch"] is None


def test_failed_batch_is_rescanned(ws):
    write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    batch = scan(ws, "classify")["batch"]
    fail_batch(ws, "classify", batch["batch_id"], reason="body crashed")
    again = scan(ws, "classify")
    assert again["batch"] is not None
    assert again["batch"]["batch_id"] != batch["batch_id"]
    assert again["resumed"] is False


def test_graph_eligibility_requires_relevance(ws):
    relevant = write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    skipped = write(ws.path("sources/manual/b.md"), "---\nsource_type: manual\n---\n\nB")
    unclassified = write(ws.path("sources/manual/c.md"), "---\nsource_type: manual\n---\n\nC")
    _classify(ws, relevant, "event")
    _classify(ws, skipped, "skip")

    batch = scan(ws, "graph")["batch"]
    paths = {f["path"] for f in batch["files"]}
    assert ws.relpath(relevant) in paths
    assert ws.relpath(skipped) not in paths
    assert ws.relpath(unclassified) not in paths


def test_graph_commit_blocked_by_invalid_vault(ws):
    path = write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    _classify(ws, path, "event")
    batch = scan(ws, "graph")["batch"]

    # Loop body writes an invalid note (missing status/confidence/source_refs).
    write(ws.path("knowledge/Events/Broken.md"), "---\ntype: event\n---\n\n# Broken\n")
    result = commit_batch(ws, "graph", batch["batch_id"])
    assert result["committed"] is False
    assert result["validation"]["ok"] is False

    # Repair and commit again.
    write(ws.path("knowledge/Events/Broken.md"), EVENT_NOTE)
    result = commit_batch(ws, "graph", batch["batch_id"])
    assert result["committed"] is True


def test_interrupt_recovery_keeps_committed_batches(ws):
    """Crash between batches loses at most the in-flight batch."""
    for i in range(4):
        write(ws.path(f"sources/manual/{i}.md"), f"---\nsource_type: manual\n---\n\nnote {i}")

    first = scan(ws, "classify", batch_size=2)["batch"]
    for entry in first["files"]:
        _classify(ws, ws.path(entry["path"]), "context")
    commit_batch(ws, "classify", first["batch_id"])

    second = scan(ws, "classify", batch_size=2)["batch"]
    assert {f["path"] for f in second["files"]}.isdisjoint({f["path"] for f in first["files"]})

    # "Crash" here: simply rescan as a fresh engine invocation.
    resumed = scan(ws, "classify", batch_size=2)
    assert resumed["resumed"] is True
    assert resumed["batch"]["batch_id"] == second["batch_id"]

    state = load_state(ws, "classify")
    assert len(state["processed"]) == 2  # first batch survived the interruption


def test_batch_work_order_is_valid_json(ws):
    write(ws.path("sources/manual/a.md"), "---\nsource_type: manual\n---\n\nA")
    batch = scan(ws, "classify")["batch"]
    raw = ws.path("state/batches/classify", f"{batch['batch_id']}.json")
    with open(raw, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "pending"
    assert data["prompt"] == "prompts/classify_source.md"
    assert os.path.isabs(data["prompt_path"])
