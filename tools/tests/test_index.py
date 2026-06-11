"""Index loop: wikilink edges, backlinks, unresolved targets, bridge note."""

import json

from conftest import write
from memoryctl.index import run_index

PERSON = """---
type: person
title: Zhang San
last_updated: {date}T10:00:00+00:00
source_refs:
  - sources/manual/a.md
---

# Zhang San

Works on [[Events/2026-06-10 Demo]].
"""

EVENT = """---
type: event
title: Demo
status: in_progress
attention_score: 0.9
confidence: 0.8
last_updated: {date}T10:00:00+00:00
source_refs:
  - sources/manual/a.md
---

# Demo

Owner: [[Zhang San]]. Related: [[People/Nobody]].
"""


def _seed(ws, date="2026-06-10"):
    write(ws.path("sources/manual/a.md"), "evidence")
    write(ws.path("knowledge/People/Zhang San.md"), PERSON.format(date=date))
    write(ws.path("knowledge/Events/2026-06-10 Demo.md"), EVENT.format(date=date))


def test_edges_and_backlinks(ws):
    _seed(ws)
    result = run_index(ws, date="2026-06-10")
    with open(ws.path("index/edges.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    resolved = {(e["from"], e["to"]) for e in data["edges"] if e["resolved"]}
    # Folder-qualified link and bare-name link both resolve.
    assert ("People/Zhang San.md", "Events/2026-06-10 Demo.md") in resolved
    assert ("Events/2026-06-10 Demo.md", "People/Zhang San.md") in resolved
    assert "Events/2026-06-10 Demo.md" in data["backlinks"]["People/Zhang San.md"]

    unresolved_targets = {u["target"] for u in data["unresolved"]}
    assert "People/Nobody" in unresolved_targets
    assert result["unresolved_links"] >= 1


def test_bridge_note_contents(ws):
    _seed(ws)
    run_index(ws, date="2026-06-10")
    with open(ws.path("knowledge/daily-memory-2026-06-10.md"), "r", encoding="utf-8") as f:
        text = f.read()

    assert "type: bridge" in text
    assert "[[Events/2026-06-10 Demo]]" in text  # top attention (score 0.9 >= 0.75)
    assert "[[People/Zhang San]]" in text  # updated that day
    assert "Zhang San" in text  # search keywords


def test_bridge_note_excludes_other_dates(ws):
    _seed(ws, date="2026-06-09")
    run_index(ws, date="2026-06-10")
    with open(ws.path("knowledge/daily-memory-2026-06-10.md"), "r", encoding="utf-8") as f:
        text = f.read()
    assert "No vault notes were updated on this date." in text
    # Attention section is date-independent: open events still surface.
    assert "[[Events/2026-06-10 Demo]]" in text


def test_index_is_idempotent(ws):
    _seed(ws)
    run_index(ws, date="2026-06-10")  # first run also creates the bridge note
    second = run_index(ws, date="2026-06-10")
    third = run_index(ws, date="2026-06-10")
    assert second["edges"] == third["edges"]
    assert second["notes"] == third["notes"]
