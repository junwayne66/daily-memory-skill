---
name: daily-memory-skill
description: Build and run a scheduled personal Daily Memory pipeline that reads authorized Feishu/Lark private chats, group chats, shared docs/materials, calendar events, meetings, and Feishu Minutes; turns them into a traceable personal knowledge vault (Obsidian-compatible Markdown graph) through small idempotent loops driven by the deterministic memoryctl engine; tracks event goals, people, deadlines, progress, results, risks, decisions, and closure state; detects items that need attention; and delivers a daily report to the owner by Feishu doc or private message. Use when the user asks for daily memory, Feishu/Lark work memory, personal knowledge graph, event tracking, meeting/doc/message consolidation, scheduled agent workflows, or OpenClaw/Hermes memory integration.
---

# Daily Memory Skill

Build a scheduled personal memory system. The goal is not a plain daily report; the goal is an evidence-backed, searchable, updateable knowledge vault that the user's agents can query later.

The system is engineered as a chain of small idempotent loops (rowboat-style loop engineering, see [references/loop-engineering.md](references/loop-engineering.md)). The deterministic engine `tools/memoryctl` owns state, change detection, batching, validation, and indexing; you (the agent) execute the LLM loop bodies. An event is the central unit of memory: a project milestone, meeting outcome, request, incident, decision thread, delivery, or follow-up loop. The vault holds one Markdown note per entity, and `[[wikilinks]]` are the graph edges.

## Core Rules

- Preserve provenance for every extracted item: source type, source id, source URL or path, sender or speaker, timestamp, and permission boundary.
- Treat raw chat, docs, and meeting transcripts as evidence, not durable memory. Promote only curated events, people, organizations, projects, topics, decisions, and closure facts into the vault.
- Send the owner report only when report delivery is configured. Never notify third parties, update task records, or write Feishu/Base state without explicit user confirmation.
- Use the deterministic engine for loop mechanics: never process sources outside a pending batch, never skip `memoryctl commit`, and never call the engine's job (hashing, state, indexing) by hand. Use LLM judgment only inside loop bodies: classification, extraction, note merging, attention scoring, conflict explanation.
- Keep event and task detection strict. Ordinary discussion is not an event unless it includes a goal, stakeholder, decision, request, deliverable, deadline, risk, meeting outcome, progress update, or closure signal.
- Merge, never overwrite. New evidence that contradicts an existing note adds a dated line and a `## Conflicts` entry; old facts are not silently rewritten.
- Avoid duplicate execution. Loop state files and content hashes make reruns cheap: a rerun with no new input is a no-op by construction.
- Treat Feishu/Lark auth, channel identity, and memory search as verified preconditions, not assumptions. A run must record the exact identity checks it used, the owner peer it will deliver to, and the post-write search result.

## Stability Guardrails

These guardrails are mandatory for unattended OpenClaw/Hermes runs:

- Start every real harvest with `run_guard`, `lark_auth_verifier`, and `channel_identity_resolver` before any sync loop runs.
- Do not start `lark-cli auth login` when `lark-cli config strict-mode` is `off` and `lark-cli auth status` shows a usable user token. Record the status and continue with user-mode reads.
- Discover installed `lark-cli` flags before calling source commands. For example, Feishu Minutes search has been observed to use `--start` and `--end`, not `--start-time` and `--end-time`.
- Prefer bounded retries and chunked fallback over repeated full reruns. If a full calendar/doc/message query times out, split by time range or source partition and mark the sync `partial` only after bounded fallback is exhausted.
- For OpenClaw Feishu delivery, resolve the app-local owner peer through OpenClaw directory data immediately before sending. Do not reuse stale `open_id` values from another bot/app.
- For OpenClaw memory sharing, point reader agents at the `knowledge/` vault and verify that the generated bridge note (`knowledge/daily-memory-<date>.md`) is retrievable by search after indexing.
- If memory indexing reports success but `memory search` returns no result or reports missing index metadata, record a platform defect in the run manifest and owner report instead of claiming searchable memory success.

## Operating Modes

Use one of these modes, inferred from the user request:

- **Scheduled daily harvest**: run the sync loops for the configured window, drain the loop pipeline, and deliver an owner report.
- **Manual supplement**: save the pasted note, chat excerpt, document, or meeting summary as a source file under `sources/manual/`, then drain the pipeline; the loops merge it into the right notes.
- **Change watch**: detect changes in event goals, owner, deadline, status, blockers, decisions, or closure state, then surface attention items.
- **Query support**: answer user questions from the vault and bridge notes, not from raw private transcripts unless explicitly needed.

## Workflow

1. Define the run scope: run id, date window, timezone, source accounts, delivery channel, agent platform, and working directory (`--workdir`). Default timezone to `Asia/Shanghai` for Chinese workplace workflows. Run `memoryctl init` on first use and create or resume `runs/<date>/run_manifest.yaml`.
2. Load the native memory adapter ([references/memory-adapters.md](references/memory-adapters.md)) and verify Feishu/Lark auth and owner channel identity ([references/lark-cli-ingestion.md](references/lark-cli-ingestion.md)). Record proofs in the run manifest.
3. Run the **sync loops** per source family (private chats, group chats, docs, materials, calendar, meetings, minutes, tasks/Base), in parallel where the platform supports it ([references/subagent-workflow.md](references/subagent-workflow.md)). Each sync loop writes idempotent Markdown source files under `sources/<family>/` with provenance frontmatter ([references/schemas.md](references/schemas.md)). Record per-family status and gaps.
4. Drain the **loop pipeline** with the engine:

   ```text
   while true:
     result = memoryctl --workdir <workdir> run --steps classify,graph,attention,index --date <date>
     if result.done: break
     process result.next_action's batch following result.next_action.prompt_path
       classify  -> prompts/classify_source.md (label sources with relevance)
       graph     -> prompts/note_creation.md   (create/merge vault notes)
       attention -> prompts/attention.md       (score open events)
     run result.next_action.commit_cmd
   ```

   The deterministic `index` step rebuilds `index/edges.json` and generates the bridge note `knowledge/daily-memory-<date>.md` automatically.
5. Compose the owner report `reports/<date>.md` from the vault: top attention events, graph delta (from the bridge note and daily note), decisions, risks, closed loops, source gaps, and loop statistics from `memoryctl status`.
6. Record loop statistics, validation results, and delivery state in the run manifest. Run the quality and safety checks in [references/safety-quality.md](references/safety-quality.md).
7. Reindex and verify reader-agent search when supported. Record the exact query and result status.
8. Deliver the owner report by configured mode: Feishu document, private Feishu/Lark message, both, or file-only. Third-party notifications stay confirmation-gated.

## Loop Pipeline

Defined in [references/loop-engineering.md](references/loop-engineering.md). Summary:

| Loop | Kind | Input | Output |
| --- | --- | --- | --- |
| sync (per family) | agent + lark-cli | Feishu/Lark APIs | `sources/<family>/*.md` |
| classify | LLM body | new/changed sources | `relevance` frontmatter |
| graph | LLM body | relevant sources | `knowledge/` vault notes |
| attention | LLM body | open/flagged event notes | attention fields |
| index | deterministic | vault | `index/edges.json`, bridge note |

Every loop is incremental (mtime+hash change detection), batched (default 25 files), and resumable (state persisted per committed batch). An interrupted run loses at most one in-flight batch. Use `memoryctl status` for progress and `memoryctl reset` to force reprocessing.

## Event-Relevance Rules

Promote content into the vault only when it matches at least one strong signal (full rules in [prompts/classify_source.md](prompts/classify_source.md)):

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

Each change must include old state, new evidence, impact, confidence, suggested action, and whether user confirmation or stakeholder notification is recommended. The engine pre-computes objective signals (`overdue`, `due_soon`, `stale_open_loop`, `blocked`, `missing_owner`) into attention batches; the attention loop body turns them into scores and recommended actions.

## Memory Write Policy

Write memory into these layers:

- **Raw evidence**: source snapshots under `sources/<family>/` with provenance frontmatter. Keep out of bootstrap memory.
- **Run ledger**: `runs/YYYY-MM-DD/run_manifest.yaml` with auth proofs, sync status, loop statistics, and delivery status. Loop state itself lives in engine-managed `state/*.json`.
- **Knowledge vault**: entity notes under `knowledge/` (Events, People, Organizations, Projects, Topics) plus the episodic daily note `knowledge/Daily/YYYY-MM-DD.md`. This is the source of truth and the reader-agent search surface.
- **Bridge note**: `knowledge/daily-memory-YYYY-MM-DD.md`, generated deterministically by `memoryctl index`. Do not hand-write it.
- **Derived index**: `index/edges.json`, rebuilt by the index loop; never edit it manually.
- **Procedural memory**: only promote recurring workflow rules, user preferences, or tool lessons into native long-term memory (`MEMORY.md`) after confidence is high.

When native memory is small, write a short pointer instead of full detail, for example: "Daily Memory for 2026-06-10 updated project X; details in <path>."

## Output Contract

Return a concise result with:

- Loop statistics: sources synced, classified (event/context/skip), notes created/updated/merged, batches committed, pending work remaining (`memoryctl status`).
- Vault changes: new events, updated events, closed events, and merged duplicates, with `[[wikilinks]]`.
- Attention items requiring user focus, ordered by urgency and impact.
- Event goals, people, timeline, progress, results, and closure gaps.
- Risks, blockers, decisions, open questions, and follow-up suggestions.
- Daily report delivery status and target; bridge note path and memory-search verification result.
- Confirmation prompts for third-party Feishu/Lark notifications or task writes.
- Any ingestion gaps, permission failures, validation errors, or low-confidence extractions.

## Reference Files

- [references/loop-engineering.md](references/loop-engineering.md): loop skeleton, batch protocol, state files, resume/rebuild, sync conventions, quality gates.
- [tools/README.md](tools/README.md): memoryctl engine commands and behavior.
- [prompts/classify_source.md](prompts/classify_source.md), [prompts/note_creation.md](prompts/note_creation.md), [prompts/attention.md](prompts/attention.md): LLM loop body instructions.
- [references/schemas.md](references/schemas.md): workspace layout, source files, vault note schemas, batch work orders, run manifest, and report templates.
- [references/subagent-workflow.md](references/subagent-workflow.md): subagent roles for parallel sync loops and run preconditions.
- [references/lark-cli-ingestion.md](references/lark-cli-ingestion.md): Feishu/Lark source collection, auth, permissions, command discovery, and safe notification patterns.
- [references/memory-adapters.md](references/memory-adapters.md): OpenClaw, Hermes Agent, Codex, and generic memory integration guidance.
- [references/safety-quality.md](references/safety-quality.md): provenance, privacy, prompt-injection, conflict, confidence, and notification gates.
- [references/agent-installation.md](references/agent-installation.md): agent-facing runbook for automated OpenClaw/Hermes installation, config patching, cron setup, validation, and rollback.
- [references/openclaw-auto-install.md](references/openclaw-auto-install.md): OpenClaw-specific automated install, Feishu channel binding, cron, memory indexing, and E2E validation.
- [references/hermes-auto-install.md](references/hermes-auto-install.md): Hermes-specific automated install, native memory pointer policy, and scheduling.
