# Schemas And Templates

Use these schemas for the Daily Memory loop pipeline and the knowledge vault. The vault is a folder of plain Markdown notes (Obsidian-compatible): note frontmatter holds structured fields, `[[wikilinks]]` are the graph edges, and the deterministic engine (`tools/memoryctl`) derives indexes from it. Markdown notes are the source of truth; JSON state files are engine-internal.

## Table Of Contents

- Workspace Layout
- Source File
- Vault Note Conventions
- Event Note
- Person Note
- Organization / Project / Topic Notes
- Daily Note
- Bridge Note (Generated)
- Loop State Files
- Batch Work Order
- Edges Index
- Run Manifest
- Owner Report Template

## Workspace Layout

```text
<workdir>/                      # e.g. ~/.openclaw/workspace-daily-memory
  MEMORY.md                     # native long-term bootstrap (compact)
  sources/                      # synced raw evidence (markdown + frontmatter)
    feishu_private_chats/
    feishu_group_chats/
    feishu_docs/
    feishu_materials/
    feishu_calendar/
    feishu_meetings/
    feishu_minutes/
    feishu_tasks_base/
    agent_logs/
    manual/                     # user-pasted supplements
  knowledge/                    # the knowledge vault (Obsidian-compatible)
    Events/
    People/
    Organizations/
    Projects/
    Topics/
    Daily/
    daily-memory-YYYY-MM-DD.md  # generated bridge notes (memoryctl index)
  state/                        # loop engine state (engine-managed)
    classify_state.json
    graph_state.json
    attention_state.json
    batches/<loop>/<batch_id>.json
  index/
    edges.json                  # derived wikilink edges and backlinks
  runs/
    YYYY-MM-DD/run_manifest.yaml
  reports/
    YYYY-MM-DD.md
    YYYY-MM-DD.feishu.md
```

## Source File

Sync loops write one Markdown file per source unit (a chat window, a doc, a calendar day, a meeting) under `sources/<family>/`. Recommended name: `YYYY-MM-DD__<native-id>.md`. Frontmatter preserves provenance; the body is the readable evidence text.

```markdown
---
source_type: feishu_private_message | feishu_group_message | feishu_doc | feishu_material | feishu_calendar | feishu_meeting | feishu_minutes | feishu_task | agent_log | manual
native_id: om_xxx
conversation_id: oc_xxx
conversation_name: Project Chat
sender: Name
timestamp: 2026-06-10T09:30:00+08:00
permission_scope: user_visible | bot_in_group | shared_doc | meeting_participant
source_url: https://...
---

<readable evidence text, speaker turns, doc markdown, agenda entries>
```

The classify loop appends these fields to the same frontmatter:

```yaml
relevance: event | context | skip
relevance_reason: short justification
classified_at: 2026-06-10T22:05:00+08:00
```

- `event`: contains event/task/decision/closure signals; the graph loop must process it.
- `context`: background worth merging into existing notes (no new event).
- `skip`: casual, private, duplicated, or notification-only; the graph loop ignores it.

Never edit the evidence body during classification; only add frontmatter fields.

## Vault Note Conventions

- One note per entity. Folder determines the default type: `Events/`, `People/`, `Organizations/`, `Projects/`, `Topics/`, `Daily/`.
- File names are human-readable titles: `Events/2026-06-10 AI camera positioning.md`, `People/Zhang San.md`. Stable readable names beat opaque ids; renames are allowed because links are by name.
- Relations are `[[wikilinks]]` in frontmatter values or body text. Typed relations go in dedicated frontmatter keys (`owner`, `project`) or labeled body lines.
- Every note carries `type`, `last_updated`, and `source_refs` (workspace-relative source file paths) in frontmatter.
- Merge, never overwrite: when new evidence conflicts with an existing statement, keep both and add a `## Conflicts` entry instead of silently rewriting history.
- Frontmatter must stay flat (scalars and string lists) so the deterministic engine can parse it.

## Event Note

Events are the primary graph nodes. `knowledge/Events/<YYYY-MM-DD> <title>.md`:

```markdown
---
type: event
title: AI camera product positioning discussion
event_type: project | meeting | request | incident | decision_thread | doc_review | delivery | opportunity | follow_up | personal_work
status: open | in_progress | waiting | blocked | done | cancelled | stale | needs_confirmation
owner: "[[People/Zhang San]]"
requester: ""
project: "[[Projects/AI Camera]]"
start_time: 2026-06-10T10:00:00+08:00
due_time: 2026-06-12T18:00:00+08:00
actual_end_time: ""
closure_state: not_started | open_loop | waiting_external | blocked | closed | cancelled | needs_confirmation
next_action: Confirm target customer with Li Si
attention_score: 0.8
attention_reasons:
  - due_soon
  - waiting on interview summary
confidence: 0.85
last_updated: 2026-06-11T22:00:00+08:00
source_refs:
  - sources/feishu_group_chats/2026-06-10__oc_xxx.md
---

# AI camera product positioning discussion

## Objective
Clarify target customer and next demo direction. Success: demo direction agreed by Friday.

## Participants
- [[People/Zhang San]] - owner
- [[People/Li Si]] - collaborator

## Timeline
- 2026-06-10 10:00: kickoff in project chat; Friday deadline set. (sources/feishu_group_chats/2026-06-10__oc_xxx.md)
- 2026-06-11 11:30: interview summary drafted by [[People/Li Si]].

## Decisions
- 2026-06-10: target customer narrowed to retail chains. Decider: [[People/Zhang San]].

## Risks
- Demo hardware may not arrive before Friday.

## Open Loops
- Waiting for final interview summary from [[People/Li Si]].

## Conflicts
- (record contradicting evidence here instead of overwriting)
```

Validation (enforced by `memoryctl validate` and at graph/attention commit):

- `type: event`, valid `status`, non-empty `source_refs`, `confidence` in `[0, 1]` are required.
- `attention_score`, `due_time`, `last_updated` feed the deterministic attention signals.

## Person Note

`knowledge/People/<Name>.md`:

```markdown
---
type: person
title: Zhang San
aliases:
  - zhangsan
open_id: ou_xxx
organization: "[[Organizations/Acme]]"
role_title: Product Lead
relationship_to_user: manager | teammate | stakeholder | customer | vendor | unknown
last_seen: 2026-06-10T16:20:00+08:00
last_updated: 2026-06-11T22:00:00+08:00
source_refs:
  - sources/feishu_group_chats/2026-06-10__oc_xxx.md
---

# Zhang San

## Overview
Product lead for [[Projects/AI Camera]].

## Active Events
- [[Events/2026-06-10 AI camera positioning]] - owner

## Interaction Log
- 2026-06-10: set Friday deadline for demo direction.
```

## Organization / Project / Topic Notes

Same shape with `type: organization | project | topic`. Suggested sections:

- Organization: `## Overview`, `## People`, `## Related Projects`
- Project: `## Background`, `## Goals`, `## Active Events`, `## Key Decisions`, `## Risks`, `## People`
- Topic: `## Overview`, `## Related Projects`, `## Key Facts`, `## Timeline`

## Daily Note

`knowledge/Daily/YYYY-MM-DD.md` is the episodic record written by the graph loop body:

```markdown
---
type: daily
title: Daily 2026-06-10
date: 2026-06-10
last_updated: 2026-06-10T22:10:00+08:00
source_refs:
  - sources/feishu_group_chats/2026-06-10__oc_xxx.md
---

# 2026-06-10

## Observations
- Kickoff for [[Events/2026-06-10 AI camera positioning]]; Friday deadline.

## Graph Delta
- New: [[Events/2026-06-10 AI camera positioning]], [[People/Li Si]]
- Updated: [[Projects/AI Camera]]

## Source Gaps
- Minutes export unavailable for meeting X.
```

## Bridge Note (Generated)

`knowledge/daily-memory-YYYY-MM-DD.md` is generated by `memoryctl index`; do not hand-edit it. It contains top attention events, notes updated that day grouped by folder, search keywords, and pointers to the report and edge index. It is the shallow recall surface for reader agents whose memory search only indexes `knowledge/` root files.

## Loop State Files

`state/<loop>_state.json` (engine-managed, mirrors rowboat's `knowledge_graph_state.json`):

```json
{
  "loop": "graph",
  "processed": {
    "sources/feishu_group_chats/2026-06-10__oc_xxx.md": {
      "mtime": 1765432100.0,
      "hash": "sha256:a3f5e9d2...",
      "last_processed": "2026-06-10T22:05:00+00:00"
    }
  },
  "last_run": "2026-06-10T22:05:00+00:00"
}
```

## Batch Work Order

`state/batches/<loop>/<batch_id>.json` is the contract between the engine and the LLM loop body:

```json
{
  "batch_id": "graph_20260610T220500_ab12cd",
  "loop": "graph",
  "status": "pending | committed | failed",
  "created_at": "2026-06-10T22:05:00+00:00",
  "prompt": "prompts/note_creation.md",
  "prompt_path": "/abs/path/to/skill/prompts/note_creation.md",
  "workdir": "/abs/path/to/workdir",
  "files": [
    {"path": "sources/feishu_group_chats/2026-06-10__oc_xxx.md", "relevance": "event"}
  ],
  "remaining_after_batch": 12
}
```

Attention batches additionally carry deterministic signals per file: `status`, `flags` (`overdue`, `due_soon`, `stale_open_loop`, `blocked`, `waiting_external`, `needs_confirmation`, `missing_owner`), `days_to_due`, `days_since_update`.

## Edges Index

`index/edges.json` is derived from vault wikilinks by `memoryctl index`:

```json
{
  "generated_at": "2026-06-10T22:10:00+00:00",
  "note_count": 42,
  "edge_count": 120,
  "edges": [
    {"from": "Events/2026-06-10 AI camera positioning.md", "target": "People/Zhang San", "to": "People/Zhang San.md", "resolved": true}
  ],
  "backlinks": {"People/Zhang San.md": ["Events/2026-06-10 AI camera positioning.md"]},
  "unresolved": [{"from": "Daily/2026-06-10.md", "target": "People/Unknown"}]
}
```

## Run Manifest

One manifest per scheduled run records preconditions, sync results, loop statistics, and delivery state. `runs/YYYY-MM-DD/run_manifest.yaml`:

```yaml
run_id: "daily-memory_2026-06-10_ab12cd"
date_window:
  start: "2026-06-10T00:00:00+08:00"
  end: "2026-06-10T22:00:00+08:00"
timezone: "Asia/Shanghai"
status: "running | partial | completed | failed"
config_hash: "sha256:..."
auth:
  lark_cli_version: ""
  strict_mode: "off | bot | user | unknown"
  user_auth_status: "ready | needs_refresh | missing | failed | unknown"
  selected_identity:
    private_chats: "user | bot | skipped"
    group_chats: "user | bot | skipped"
    docs: "user | bot | skipped"
    calendar: "user | bot | skipped"
    minutes: "user | bot | skipped"
channel_identity:
  platform: "openclaw | hermes | codex | generic"
  owner_peer_id: "ou_xxx"
sync:
  feishu_private_chats: {status: "ok | partial | skipped | failed", files_written: 0, gaps: []}
  feishu_group_chats: {status: "ok", files_written: 0, gaps: []}
  feishu_docs: {status: "ok", files_written: 0, gaps: []}
  feishu_calendar: {status: "ok", files_written: 0, gaps: []}
  feishu_minutes: {status: "ok", files_written: 0, gaps: []}
loops:
  classify: {batches: 0, files_processed: 0, pending_after: 0}
  graph: {batches: 0, files_processed: 0, pending_after: 0, validation_errors: 0}
  attention: {batches: 0, files_processed: 0, pending_after: 0}
  index: {notes: 0, edges: 0, unresolved_links: 0, bridge_note: "knowledge/daily-memory-2026-06-10.md"}
delivery:
  mode: "file | feishu_doc | feishu_private_message | both"
  status: "not_started | drafted | sent | skipped | failed"
  target: null
memory_search:
  bridge_note: "knowledge/daily-memory-2026-06-10.md"
  verification_query: ""
  status: "not_started | ok | empty | failed | unsupported"
  defect: null
```

## Owner Report Template

`reports/YYYY-MM-DD.md`, composed by the agent from the vault after the loops finish:

```markdown
# Daily Memory Report - YYYY-MM-DD

## 需要你关注

1. <attention item>: why it matters, recommended action, due time, people.

## 今日事件图谱更新

| Event | Status | Goal | Progress/Result | People | Closure |
| --- | --- | --- | --- | --- | --- |

## 新增事件

## 推进中的事件

## 已闭环事件

## 风险与阻塞

## 关键决策

## 明日建议

## 数据缺口

## 附录

- Sources synced / classified / merged:
- Loop statistics (from `memoryctl status`):
- Low-confidence items:
- Report delivery:
```
