# Schemas And Templates

Use these schemas for Daily Memory extraction, graph merging, and report output. Prefer YAML or JSON for state files that need deterministic diffs.

## Table Of Contents

- Directory Layout
- Stable IDs
- Run Manifest
- Source Record
- Event
- People And Relationships
- Task
- Decision
- Risk Or Blocker
- Attention Item
- Graph Edge
- Daily Memory Template
- Owner Report Template

## Directory Layout

```text
daily-memory/
  MEMORY.md
  runs/
    YYYY-MM-DD/
      run_manifest.yaml
      artifacts/
        <role>.yaml
  raw/
    YYYY-MM-DD/
      feishu_private_chats/
      feishu_group_chats/
      feishu_docs/
      feishu_materials/
      feishu_calendar/
      feishu_meetings/
      feishu_minutes/
      agent_logs/
  memory/
    daily-memory-YYYY-MM-DD.md
    historical-backfill-before-YYYY-MM-DD.md
    daily/YYYY-MM-DD.md
    graph/
      events/active_events.yaml
      events/closed_events.yaml
      people/people.yaml
      people/relationships.yaml
      documents/documents.yaml
      edges.yaml
    attention/open_items.yaml
    projects/<project-slug>.md
    tasks/active_tasks.yaml
    tasks/completed_tasks.yaml
    tasks/task_changes.yaml
    decisions/decisions.yaml
    risks/risks.yaml
    glossary/concepts.md
  reports/
    YYYY-MM-DD.md
    YYYY-MM-DD.feishu.md
  index/
    memory.db
    vector_store/
```

## Stable IDs

Use stable ids where possible:

- `source_<type>_<native-id>`
- `bundle_<YYYYMMDD>_<short-hash>`
- `event_<YYYYMMDD>_<short-hash>`
- `person_<slug-or-open-id>`
- `doc_<native-token-or-hash>`
- `task_<YYYYMMDD>_<short-hash>`
- `decision_<YYYYMMDD>_<short-hash>`
- `risk_<YYYYMMDD>_<short-hash>`
- `attention_<YYYYMMDD>_<short-hash>`
- `edge_<from>_<relation>_<to>`
- `project_<slug>`

Hash source text plus timestamp plus native id. Never rely only on sequence numbers.

## Run Manifest

```yaml
run_id: "daily-memory_2026-06-10_ab12cd"
date_window:
  start: "2026-06-10T00:00:00+08:00"
  end: "2026-06-10T22:00:00+08:00"
timezone: "Asia/Shanghai"
status: "running | partial | completed | failed"
config_hash: "sha256:..."
source_cursors: {}
auth:
  lark_cli_version: ""
  strict_mode: "off | bot | user | unknown"
  user_auth_status: "ready | needs_refresh | missing | failed | unknown"
  bot_auth_status: "ready | missing | failed | unknown"
  selected_identity:
    private_chats: "user | bot | skipped"
    group_chats: "user | bot | skipped"
    docs: "user | bot | skipped"
    calendar: "user | bot | skipped"
    minutes: "user | bot | skipped"
  proof_artifact: "runs/2026-06-10/artifacts/lark_auth_verifier.yaml"
channel_identity:
  platform: "openclaw | hermes | codex | generic"
  channel: "feishu"
  account_id: "default"
  owner_peer_id: "ou_xxx"
  stale_peer_ids_rejected: []
role_status:
  lark_auth_verifier:
    status: "ok | partial | skipped | failed"
    artifact: "runs/2026-06-10/artifacts/lark_auth_verifier.yaml"
  channel_identity_resolver:
    status: "ok | partial | skipped | failed"
    artifact: "runs/2026-06-10/artifacts/channel_identity_resolver.yaml"
  lark_private_chat_collector:
    status: "ok | partial | skipped | failed"
    input_hash: "sha256:..."
    artifact: "runs/2026-06-10/artifacts/lark_private_chat_collector.yaml"
    records: 0
    gaps: []
delivery:
  mode: "file | feishu_doc | feishu_private_message | both"
  status: "not_started | drafted | sent | skipped | failed"
  target: null
memory_search:
  bridge_note: "memory/daily-memory-2026-06-10.md"
  indexed_agents: []
  verification_query: ""
  status: "not_started | ok | empty | failed | unsupported"
  defect: null
```

## Source Record

```yaml
id: "source_feishu_message_om_xxx"
type: "feishu_private_message | feishu_group_message | feishu_doc | feishu_material | feishu_calendar | feishu_meeting | feishu_minutes | agent_log"
source_url: "https://..."
native_id: "om_xxx"
conversation_id: "oc_xxx"
conversation_name: "Project Chat"
sender_or_speaker:
  id: "ou_xxx"
  name: "Name"
timestamp: "2026-06-10T09:30:00+08:00"
permission_scope: "user_visible | bot_in_group | shared_doc | meeting_participant"
content_path: "raw/2026-06-10/feishu_group_chats/om_xxx.json"
content_hash: "sha256:..."
parent_refs: []
attachment_refs: []
trusted: true
prompt_injection_flags: []
notes: []
```

## Event

Events are the primary graph nodes. A task can belong to an event, but not every event is a task.

```yaml
id: "event_20260610_ab12cd"
title: "AI camera product positioning discussion"
event_type: "project | meeting | request | incident | decision_thread | doc_review | delivery | opportunity | follow_up | personal_work"
status: "open | in_progress | waiting | blocked | done | cancelled | stale | needs_confirmation"
objective:
  summary: "Clarify target customer and next demo direction."
  success_criteria: []
owner: "person_ou_xxx"
requester: null
participants:
  - person_id: "person_ou_xxx"
    role: "owner | collaborator | reviewer | approver | requester | stakeholder | observer"
start_time: "2026-06-10T10:00:00+08:00"
due_time: null
actual_end_time: null
project_id: "project_ai-camera-product"
related_docs: []
related_meetings: []
related_tasks: []
related_decisions: []
related_risks: []
progress:
  - time: "2026-06-10T11:30:00+08:00"
    summary: "..."
    result: "..."
    source_refs: []
outcomes:
  current_result: null
  deliverables: []
  accepted_by: null
closure:
  state: "not_started | open_loop | waiting_external | blocked | closed | cancelled | needs_confirmation"
  closure_evidence_refs: []
  missing_for_closure: []
  next_action: null
attention:
  score: 0.0
  reasons: []
source_refs: []
confidence: 0.0
created_at: "2026-06-10T22:00:00+08:00"
last_updated: "2026-06-10T22:00:00+08:00"
```

## People And Relationships

```yaml
id: "person_ou_xxx"
name: "Name"
aliases: []
open_id: "ou_xxx"
email: null
organization: null
role_title: null
relationship_to_user: "manager | teammate | stakeholder | customer | vendor | unknown"
active_events: []
source_refs: []
confidence: 0.0
last_seen: "2026-06-10T16:20:00+08:00"
```

```yaml
id: "relationship_20260610_ab12cd"
from_person_id: "person_ou_xxx"
to_person_id: "person_ou_yyy"
relation_type: "reports_to | collaborates_with | requested_from | approves | reviews | depends_on | mentioned_with"
event_id: "event_20260610_ab12cd"
source_refs: []
confidence: 0.0
```

## Task

```yaml
id: "task_20260610_xxxx"
event_id: "event_20260610_ab12cd"
project_id: "project_openclaw-agent-platform"
title: "Configure Feishu multi-user session isolation"
description: "..."
owner: "person_ou_xxx"
collaborators: []
requester: null
status: "todo | in_progress | waiting | blocked | done | cancelled"
priority: "low | medium | high | urgent"
due_time: null
next_milestone: null
dependencies: []
risks: []
source_refs: []
confidence: 0.0
last_updated: "2026-06-10T22:00:00+08:00"
```

## Task Or Event Change

```yaml
id: "change_20260610_xxxx"
target_type: "event | task | decision | risk"
target_id: "event_20260610_ab12cd"
change_type: "new_event | event_goal_changed | event_people_changed | event_deadline_changed | event_progress_updated | event_result_updated | event_closure_changed | new_task | owner_changed | deadline_changed | status_changed | blocked | unblocked | completed | cancelled | decision_conflict"
old_state: null
new_state: {}
evidence_refs: []
impact: "..."
suggested_action: "..."
requires_user_confirmation: true
suggest_notify_people: []
suggested_notification: "..."
confidence: 0.0
detected_at: "2026-06-10T22:00:00+08:00"
```

## Decision

```yaml
id: "decision_20260610_xxxx"
event_id: "event_20260610_ab12cd"
title: "..."
decision: "..."
decider: null
participants: []
decision_time: "2026-06-10T10:00:00+08:00"
impact: "..."
follow_up_actions: []
source_refs: []
confidence: 0.0
supersedes: []
conflicts_with: []
```

## Risk Or Blocker

```yaml
id: "risk_20260610_xxxx"
event_id: "event_20260610_ab12cd"
project_id: "project_x"
description: "..."
risk_level: "low | medium | high"
status: "open | mitigated | accepted | closed"
affected_tasks: []
trigger_source_refs: []
suggested_action: "..."
owner: null
confidence: 0.0
```

## Attention Item

```yaml
id: "attention_20260610_xxxx"
event_id: "event_20260610_ab12cd"
title: "..."
attention_type: "deadline_risk | blocked | waiting_external | missing_owner | unresolved_decision | stale_open_loop | conflict | opportunity | user_confirmation"
urgency: "low | medium | high | urgent"
impact: "low | medium | high"
reason: "..."
recommended_action: "..."
due_time: null
related_people: []
source_refs: []
confidence: 0.0
status: "open | acknowledged | resolved | dismissed"
```

## Graph Edge

```yaml
id: "edge_event_20260610_ab12cd_mentions_doc_xxx"
from:
  type: "event"
  id: "event_20260610_ab12cd"
relation: "mentions | owns | requests | attends | decides | blocks | depends_on | updates | closes | supersedes | conflicts_with"
to:
  type: "document"
  id: "doc_xxx"
source_refs: []
confidence: 0.0
```

## Daily Memory Template

```markdown
# Daily Memory - YYYY-MM-DD

## Overview

- New events:
- Updated events:
- Closed events:
- Key people:
- Documents/materials:
- Meetings/minutes:
- Attention items:
- Source gaps:

## Event Graph Delta

### Event: <title>

- Event ID:
- Type:
- Status:
- Objective:
- Owner/requester:
- Related people:
- Start:
- Due:
- Progress:
- Result:
- Closure state:
- Source evidence:
- Confidence:

## Attention Queue

- [ ] <attention item> — urgency, reason, recommended action, source refs

## Decisions

## Risks And Blockers

## Open Confirmations

- [ ] ...

## Tomorrow Suggestions

- Prioritize:
- Follow up:
- Confirm:
- Archive:
```

## Owner Report Template

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

- Source count:
- Low-confidence items:
- Report delivery:
```

## Project Memory Template

```markdown
# Project: <name>

## Background

## Goals

## Current Events

| Event | Owner | Status | Next milestone | Risk |
| --- | --- | --- | --- | --- |

## Current Tasks

| Task | Owner | Status | Next milestone | Risk |
| --- | --- | --- | --- | --- |

## Key Decisions

| Date | Decision | Reason | Impact | Source |
| --- | --- | --- | --- | --- |

## Risks

## People

| Person | Role | Relationship | Notes |
| --- | --- | --- | --- |

## Source Index
```
