"""End-to-end pipeline over the sample fixtures, simulating the agent loop."""

import json

from conftest import write
from memoryctl.commit import commit_batch
from memoryctl.pipeline import run_pipeline
from memoryctl.validate import validate_vault

DATE = "2026-06-10"

EVENT_NOTE = f"""---
type: event
title: AI camera target customer and demo direction
status: in_progress
event_type: project
owner: "[[People/Zhang San]]"
due_time: 2026-06-12T18:00:00+08:00
last_updated: {DATE}T22:00:00+08:00
confidence: 0.85
source_refs:
  - sources/feishu_group_chats/2026-06-10__oc_demo.md
  - sources/feishu_docs/2026-06-10__doccn_spec.md
---

# AI camera target customer and demo direction

## Objective
Decide target customer and demo direction before Friday.

## Timeline
- {DATE}: [[People/Zhang San]] set the deadline; [[People/Li Si]] owns interviews.
- {DATE}: interview notes suggest retail shelf scenario.
"""

PERSON_NOTE = """---
type: person
title: {name}
last_updated: 2026-06-10T22:00:00+08:00
source_refs:
  - sources/feishu_group_chats/2026-06-10__oc_demo.md
---

# {name}

Active on [[Events/2026-06-10 AI camera positioning]].
"""


def _relevance_for(path: str) -> str:
    if "smalltalk" in path:
        return "skip"
    if "doccn" in path:
        return "context"
    return "event"


def _classify_body(ws, batch):
    for entry in batch["files"]:
        path = ws.path(entry["path"])
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        lines = text.split("\n")
        end = lines.index("---", 1)
        lines[end:end] = [f"relevance: {_relevance_for(path)}", "relevance_reason: test"]
        write(path, "\n".join(lines))


def _graph_body(ws, batch):
    write(ws.path("knowledge/Events/2026-06-10 AI camera positioning.md"), EVENT_NOTE)
    write(ws.path("knowledge/People/Zhang San.md"), PERSON_NOTE.format(name="Zhang San"))
    write(ws.path("knowledge/People/Li Si.md"), PERSON_NOTE.format(name="Li Si"))


def _attention_body(ws, batch):
    for entry in batch["files"]:
        assert "due_soon" in entry["flags"] or "overdue" in entry["flags"] or "stale_open_loop" in entry["flags"]
        path = ws.path(entry["path"])
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        write(path, text.replace("confidence: 0.85", "attention_score: 0.9\nconfidence: 0.85"))


BODIES = {"classify": _classify_body, "graph": _graph_body, "attention": _attention_body}


def test_full_pipeline(ws_with_sources):
    ws = ws_with_sources
    seen_loops = []
    for _ in range(20):
        result = run_pipeline(ws, date=DATE)
        if result["done"]:
            break
        action = result["next_action"]
        seen_loops.append(action["loop"])
        BODIES[action["loop"]](ws, {"files": [
            f for f in _load_batch(ws, action)["files"]
        ]})
        commit = commit_batch(ws, action["loop"], action["batch_id"])
        assert commit["committed"] is True, commit
    else:
        raise AssertionError("pipeline did not drain")

    assert seen_loops == ["classify", "graph", "attention"]

    # Vault is valid, edges exist, bridge note generated.
    assert validate_vault(ws)["ok"] is True
    with open(ws.path("index/edges.json"), "r", encoding="utf-8") as f:
        edges = json.load(f)
    assert edges["edge_count"] > 0
    with open(ws.path(f"knowledge/daily-memory-{DATE}.md"), "r", encoding="utf-8") as f:
        bridge = f.read()
    assert "[[Events/2026-06-10 AI camera positioning]]" in bridge

    # Second invocation with no new input is a no-op.
    rerun = run_pipeline(ws, date=DATE)
    assert rerun["done"] is True
    assert all(s["status"] in ("clean", "executed") for s in rerun["steps"])


def _load_batch(ws, action):
    with open(ws.path(action["batch_file"]), "r", encoding="utf-8") as f:
        return json.load(f)
