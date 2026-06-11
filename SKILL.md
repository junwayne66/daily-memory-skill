---
name: daily-memory-skill
description: Build and run a scheduled personal Daily Memory workflow that reads authorized Feishu/Lark private chats, group chats, shared docs/materials, calendar events, meetings, and Feishu Minutes; turns them into a traceable personal event knowledge graph; tracks event goals, people, start/end/deadline times, progress, results, risks, decisions, and closure state; detects items that need attention; and delivers a daily report to the owner by Feishu doc or private message. Use when the user asks for daily memory, Feishu/Lark work memory, personal knowledge graph, event tracking, meeting/doc/message consolidation, scheduled agent workflows, dynamic subagent orchestration, or OpenClaw/Hermes memory integration.
---

# Daily Memory Skill

Build a scheduled personal memory system. The goal is not a plain daily report; the goal is an evidence-backed, searchable, updateable event knowledge graph that the user's agents can query later.

An event is the central unit of memory. It can be a project milestone, meeting outcome, request, incident, opportunity, document review, decision thread, delivery task, collaboration thread, or follow-up loop.

## Core Rules

- Preserve provenance for every extracted item: source type, source id, source URL or path, sender or speaker, timestamp, and permission boundary.
- Treat raw chat, docs, and meeting transcripts as evidence, not durable memory. Promote only curated events, people, relations, decisions, tasks, risks, and closure facts.
- Send the owner report only when report delivery is configured. Never notify third parties, update task records, or write Feishu/Base state without explicit user confirmation.
- Use the active agent's native memory system first. Add a separate store only for raw evidence, indexes, or project knowledge that is too large for the native memory budget.
- Keep event and task detection strict. Ordinary discussion is not an event unless it includes a goal, stakeholder, decision, request, deliverable, deadline, risk, meeting outcome, progress update, or closure signal.
- Prefer deterministic tooling for ingestion, normalization, ids, diffs, schema validation, and notification payload rendering. Use LLM judgment for classification, extraction, synthesis, and conflict explanation.
- Use dynamic subagents for scheduled harvests. The main task agent is an orchestrator; it creates short-lived atomic workers, coordinates through artifact manifests, and performs final acceptance.
- Avoid duplicate execution. Every run must have a run id, date window, source cursor manifest, content hashes, and per-role artifact status so reruns can resume or skip already-completed work.
- Treat Feishu/Lark auth, channel identity, and memory search as verified preconditions, not assumptions. A run must record the exact identity checks it used, the owner peer it will deliver to, and the post-write search result.

## Stability Guardrails

These guardrails are mandatory for unattended OpenClaw/Hermes runs:

- Start every real harvest with `run_guard`, `lark_auth_verifier`, and `channel_identity_resolver` before any source collector runs.
- Do not start `lark-cli auth login` when `lark-cli config strict-mode` is `off` and `lark-cli auth status` shows a usable user token. Record the status and continue with user-mode reads.
- Discover installed `lark-cli` flags before calling source commands. For example, Feishu Minutes search has been observed to use `--start` and `--end`, not `--start-time` and `--end-time`.
- Prefer bounded retries and chunked fallback over repeated full reruns. If a full calendar/doc/message query times out, split by time range or source partition and mark the run `partial` only after bounded fallback is exhausted.
- For OpenClaw Feishu delivery, resolve the app-local owner peer through OpenClaw directory data immediately before sending. Do not reuse stale `open_id` values from another bot/app.
- For OpenClaw memory sharing, write a root Markdown bridge note under `memory/*.md` in addition to structured graph files, then verify that the reader agent can retrieve it by search.
- If memory indexing reports success but `memory search` returns no result or reports missing index metadata, record a platform defect in the run manifest and owner report instead of claiming searchable memory success.

## Operating Modes

Use one of these modes, inferred from the user request:

- **Scheduled daily harvest**: collect the configured Feishu/Lark window, update the personal event graph, and deliver an owner report.
- **Manual supplement**: merge a pasted note, chat excerpt, document, or meeting summary into the right event and graph nodes.
- **Change watch**: detect changes in event goals, owner, deadline, status, blockers, decisions, or closure state, then surface attention items.
- **Query support**: answer user questions from curated memory and source-backed graph records, not from raw private transcripts unless explicitly needed.

## Workflow

1. Define the run scope: run id, date window, timezone, source accounts, chats, docs, calendar, meetings, delivery channel, agent platform, and memory root. Default timezone to `Asia/Shanghai` for Chinese workplace workflows.
2. Load the native memory adapter. For OpenClaw, Hermes, Codex, and generic agents, read [references/memory-adapters.md](references/memory-adapters.md).
3. Verify Feishu/Lark auth and owner channel identity. For Feishu/Lark, read [references/lark-cli-ingestion.md](references/lark-cli-ingestion.md), run strict-mode/auth checks, and use command discovery instead of assuming flags.
4. Plan idempotent source collection with bounded retry, partitioning, and fallback policies.
5. Spawn dynamic subagents according to [references/subagent-workflow.md](references/subagent-workflow.md). Collect private chats, group chats, docs/materials, calendar events, meetings, and minutes in parallel when possible.
6. Normalize evidence into source records. Preserve ids, timestamps, author/speaker names, source URLs, permission scope, raw paths, and content hashes.
7. Deduplicate across sources. Link the same document shared in chat, calendar, and meeting minutes into one source bundle.
8. Extract event candidates, people, organizations, documents, decisions, tasks, risks, blockers, and relationships using [references/schemas.md](references/schemas.md).
9. Reconstruct event timelines: objective, start time, deadline, progress updates, results, closure state, open loops, and next action.
10. Merge with existing memory. Update graph files, active events, people relationships, decisions, and attention queues through append-or-diff behavior. Do not silently overwrite old facts.
11. Score attention items: deadline risk, blocked work, missing owner, unresolved decision, stakeholder dependency, stale open loop, conflict, or high-value opportunity.
12. Run the quality and safety checks in [references/safety-quality.md](references/safety-quality.md).
13. Write outputs: raw evidence, run manifest, daily note, root memory bridge note, event graph updates, attention queue, and report draft.
14. Reindex and verify reader-agent search when supported. Record the exact query and result status.
15. Deliver the owner report by configured mode: Feishu document, private Feishu/Lark message, both, or file-only. Third-party notifications stay confirmation-gated.

## Dynamic Subagent Workflow

For daily harvests and other multi-source runs, follow [references/subagent-workflow.md](references/subagent-workflow.md). The orchestrator must split work into atomic, temporary subagents:

- Source collectors run in parallel by source family and source partition.
- Auth and channel identity verifiers run before collectors.
- Normalizers transform raw source outputs into source records and deduplicated bundles.
- Event extractors identify events, goals, people, relations, tasks, decisions, risks, and documents.
- Timeline and closure analyzers reconstruct progress and loop state.
- Attention prioritizers decide what the user should notice.
- Merge writers update curated graph, root bridge notes, and memory files serially.
- Report composers produce a user-facing daily report.
- Reviewers audit provenance, privacy, conflicts, idempotency, and delivery gates.
- Memory index verifiers prove that the target reader agent can retrieve the new memory or record the defect.

Subagents are not persistent agents and must not own long-term memory. They receive a small task envelope, write/read bounded artifacts, return structured outputs, and terminate.

## Event-Relevance Rules

Promote content into the event graph only when it matches at least one strong signal:

- Mentions a project, requirement, customer, product, architecture, system, document, delivery, meeting, stakeholder, risk, opportunity, or collaboration.
- Contains a goal, request, decision, action, deliverable, expected result, deadline, milestone, dependency, status, blocker, owner, or next step.
- Appears in a shared work doc, meeting minutes transcript, project group chat, direct work request, task/Base record, code review, commit, PR, issue, or agent work session.
- Changes an existing event's objective, related people, timeline, progress, result, risk, or closure state.

Exclude content that is only casual, private, emotional, duplicated, notification-only, or outside the permission boundary for the current run.

## Attention And Change Types

Detect and report these event/task changes:

- `new_event`
- `event_goal_changed`
- `event_people_changed`
- `event_start_changed`
- `event_deadline_changed`
- `event_progress_updated`
- `event_result_updated`
- `event_closure_changed`
- `new_task`
- `task_content_changed`
- `owner_changed`
- `deadline_changed`
- `priority_changed`
- `status_changed`
- `dependency_changed`
- `blocked`
- `unblocked`
- `cancelled`
- `completed`
- `scope_expanded`
- `scope_reduced`
- `decision_conflict`
- `needs_user_attention`

Each change must include old state, new evidence, impact, confidence, suggested action, and whether user confirmation or stakeholder notification is recommended.

## Memory Write Policy

Write memory into these layers:

- **Raw evidence**: source snapshots, transcripts, message exports, and document markdown. Keep out of bootstrap memory.
- **Run ledger**: `runs/YYYY-MM-DD/run_manifest.yaml` with run id, source cursors, role statuses, artifact hashes, and delivery status.
- **Episodic daily memory**: `memory/daily/YYYY-MM-DD.md` or the native agent's daily note path. Include source-backed daily observations and graph deltas.
- **Event knowledge graph**: event, person, organization, document, decision, task, risk, and relationship records. Keep these compact, merged, and searchable.
- **Reader bridge note**: a compact Markdown file directly under `memory/*.md` when the target agent only indexes shallow Markdown paths. It should link to graph files and contain the report title, date window, event ids, top attention items, and search terms.
- **Procedural memory**: only promote recurring workflow rules, user preferences, or tool lessons into native long-term memory after confidence is high.

When native memory is small, write a short pointer instead of full detail, for example: "Daily Memory for 2026-06-10 updated project X; details in <path>."

## Output Contract

Return a concise result with:

- Files or native memories created or updated.
- Daily report delivery status and target.
- Event graph changes: new events, updated events, closed events, and merged duplicates.
- Attention items requiring user focus, ordered by urgency and impact.
- Event goals, people, timeline, progress, results, and closure gaps.
- Risks, blockers, decisions, open questions, and follow-up suggestions.
- Confirmation prompts for third-party Feishu/Lark notifications or task writes.
- Any ingestion gaps, permission failures, or low-confidence extractions.

## Reference Files

- [references/agent-installation.md](references/agent-installation.md): agent-facing runbook for automated OpenClaw/Hermes installation, config patching, cron setup, validation, and rollback.
- [references/openclaw-auto-install.md](references/openclaw-auto-install.md): OpenClaw-specific automated install, Feishu channel binding, raw delivery mode, cron, memory indexing, and E2E validation.
- [references/hermes-auto-install.md](references/hermes-auto-install.md): Hermes-specific automated install, native memory pointer policy, scheduling, and subagent-role emulation when native subagents are unavailable.
- [references/lark-cli-ingestion.md](references/lark-cli-ingestion.md): Feishu/Lark source collection, auth, permissions, command discovery, and safe notification patterns.
- [references/memory-adapters.md](references/memory-adapters.md): OpenClaw, Hermes Agent, Codex, and generic memory integration guidance.
- [references/subagent-workflow.md](references/subagent-workflow.md): dynamic subagent roles, parallelization plan, handoff envelopes, and workflow gates.
- [references/schemas.md](references/schemas.md): directory layout, source records, event graph schemas, ids, attention queues, and report templates.
- [references/safety-quality.md](references/safety-quality.md): provenance, privacy, prompt-injection, conflict, confidence, and notification gates.
