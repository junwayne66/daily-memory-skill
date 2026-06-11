# Dynamic Subagent Workflow

Use this reference when a Daily Memory run has multiple Feishu/Lark source types, a large time window, or needs stable scheduled automation. The main task agent is an orchestrator, not a monolith.

## Table Of Contents

- Core Rule
- Workflow Graph
- Orchestrator Duties
- Idempotency And Run Ledger
- Subagent Contracts
- Atomic Roles
- Parallelization Rules
- Collaboration Rules
- Failure Handling

## Core Rule

Create short-lived subagents for atomic tasks. Do not create persistent agents. Do not let subagents send external notifications, update Feishu/Base records, or own long-term memory. The orchestrator launches them, gives small envelopes, coordinates through artifact manifests, reviews outputs, and performs final acceptance.

## Workflow Graph

```text
orchestrator
  -> run_guard
  -> lark_auth_verifier
  -> channel_identity_resolver
  -> source_planner
  -> parallel source collectors
       lark_private_chat_collector
       lark_group_chat_collector
       lark_shared_docs_collector
       lark_materials_collector
       lark_calendar_collector
       lark_meeting_minutes_collector
       lark_tasks_base_collector
       agent_workspace_collector
  -> source_normalizer_deduper
  -> event_candidate_extractor
  -> people_entity_resolver
  -> relation_graph_builder
  -> timeline_progress_reconstructor
  -> closure_status_analyzer
  -> attention_prioritizer
  -> knowledge_graph_merge_writer
  -> report_composer
  -> safety_quality_reviewer
  -> memory_index_verifier
  -> delivery_preparer
  -> orchestrator final acceptance
```

Run auth/channel verification serially before source planning. Run source collectors in parallel when the platform supports it. Run merge, review, index verification, and delivery preparation serially.

## Orchestrator Duties

- Define run id, date window, timezone, source boundaries, memory root, report target, and delivery mode.
- Load only `MEMORY.md`, relevant active event/task state, and this workflow reference.
- Create or resume `runs/YYYY-MM-DD/run_manifest.yaml`.
- Verify Feishu/Lark auth and owner channel identity before spawning collectors.
- Dispatch subagents with bounded inputs and explicit output schemas.
- Keep a manifest of expected artifact paths and role status.
- Refuse duplicate role execution when the same source partition already has an `ok` artifact with the same input hash.
- Refuse third-party notifications unless the user explicitly approves the exact payload.
- Reindex/search memory after successful writes when the platform supports it.
- Reject delivery when the target peer id is stale, cross-app, or not resolved from the active channel account.
- Summarize updated files, event changes, attention items, source gaps, delivery status, and open confirmations.

The orchestrator should not manually scrape every source or hold all raw data in context.

## Idempotency And Run Ledger

Every scheduled run must create a run ledger:

```yaml
run_id: "daily-memory_YYYY-MM-DD_<short-hash>"
date_window:
  start: "YYYY-MM-DDT00:00:00+08:00"
  end: "YYYY-MM-DDT22:00:00+08:00"
timezone: "Asia/Shanghai"
status: "running | partial | completed | failed"
config_hash: "sha256:..."
source_cursors:
  lark_private_chat: {}
  lark_group_chat: {}
  lark_docs: {}
  lark_calendar: {}
  lark_meeting_minutes: {}
roles:
  lark_auth_verifier:
    status: "ok"
    artifact: "runs/YYYY-MM-DD/artifacts/lark_auth_verifier.yaml"
  channel_identity_resolver:
    status: "ok"
    artifact: "runs/YYYY-MM-DD/artifacts/channel_identity_resolver.yaml"
  source_planner:
    status: "ok"
    input_hash: "sha256:..."
    artifact: "runs/YYYY-MM-DD/artifacts/source_planner.yaml"
delivery:
  mode: "file | feishu_doc | feishu_private_message | both"
  status: "not_started | drafted | sent | skipped | failed"
```

Rules:

- If the same run already completed with the same `config_hash`, do not rerun collection unless the user requests `--force`.
- If a prior run is partial, resume only failed or missing roles.
- Each collector partitions by source type and source id. Never let two subagents collect the same chat/doc/meeting partition for the same window.
- Each artifact write must be atomic: write a temporary file, then rename to the final path.
- Content hashes decide duplicate suppression. Native ids alone are not enough because docs and minutes can change.

## Subagent Contracts

All subagents receive:

```yaml
role: "<subagent_role>"
run_id: "daily-memory_YYYY-MM-DD_<short-hash>"
date_window:
  start: "YYYY-MM-DDT00:00:00+08:00"
  end: "YYYY-MM-DDT22:00:00+08:00"
timezone: "Asia/Shanghai"
memory_root: "./memory"
raw_root: "./raw/YYYY-MM-DD"
run_root: "./runs/YYYY-MM-DD"
allowed_tools: []
input_paths: []
output_paths: []
source_partition: null
constraints:
  no_third_party_notifications: true
  owner_report_allowed_if_configured: true
  preserve_source_refs: true
  redact_secrets: true
  no_long_term_memory_writes: true
```

All subagents return:

```yaml
role: "<subagent_role>"
status: "ok | partial | skipped | blocked | failed"
artifacts: []
source_refs: []
records_created: 0
records_updated: 0
duplicates_skipped: 0
gaps: []
warnings: []
next_recommended_step: null
```

## Atomic Roles

### run_guard

Inputs: run scope, prior run manifest, current config.

Outputs: resume/skip decision, config hash, lock status, and role execution plan.

### lark_auth_verifier

Inputs: lark CLI path, date window, configured auth mode, environment summary.

Outputs: CLI version, strict-mode value, redacted auth status, selected identity per source family, proof commands, and source families that must be skipped. If user auth is ready and strict-mode is off, it must mark personal reads as `user` and must not request `auth login`.

### channel_identity_resolver

Inputs: delivery config, active platform, OpenClaw/Hermes channel config, owner hints.

Outputs: resolved owner peer/chat id, channel account id, account display name, stale ids rejected, owner allowlist patch suggestion, and a delivery test plan. For OpenClaw Feishu, resolve through `openclaw directory peers list --channel feishu --json` and avoid stale cross-app `open_id` values.

### source_planner

Inputs: run scope, configured Feishu/Lark sources, existing memory hints.

Outputs: collector plan with source partitions, verified auth identity, exact command families, expected raw artifact paths, retry policy, chunking policy, and timeout policy.

### lark_private_chat_collector

Collects Feishu/Lark one-to-one messages visible to the user identity. It should preserve counterpart identity, thread/reply metadata, attachments, and links. It must not collect unrelated private content beyond the configured work-memory scope when filtering can happen safely.

### lark_group_chat_collector

Collects configured or discoverable project group chats where the user participates. It should capture mentions, replies, pinned/reference messages, linked docs, and attachment ids. If group scope is too broad, collect only configured group ids or group names from the source plan.

### lark_shared_docs_collector

Finds and fetches Feishu docs/wiki docs shared with the user, mentioned in messages, attached to meetings, or updated in the run window. It should export readable markdown or block JSON and chunk long docs by heading/block.

### lark_materials_collector

Collects non-doc materials referenced by messages, docs, or meetings: files, images with OCR text when available, sheets, links, and drive metadata. It saves metadata and text previews, not large binary blobs unless explicitly configured.

### lark_calendar_collector

Collects agenda and event metadata for meetings the user attends. Calendar data provides expected time, title, attendees, organizer, meeting links, and doc links.

### lark_meeting_minutes_collector

Collects meeting records, meeting notes, and Feishu Minutes metadata/transcripts when authorized. It must preserve speaker turns, action items, decisions, and transcript URLs. If transcript export is unavailable, record the gap and use calendar/doc context.

### lark_tasks_base_collector

Collects task/Base records only when configured and authorized. It must not update tasks or Base records unless the orchestrator gives explicit approval.

### agent_workspace_collector

Collects OpenClaw/Hermes session pointers, cron run summaries, and relevant workspace changes. It should store pointers and short excerpts rather than dumping full sessions.

### source_normalizer_deduper

Normalizes raw evidence into source records, redacts secrets, computes content hashes, links related sources, and removes duplicates across chat/docs/calendar/minutes.

### event_candidate_extractor

Extracts event candidates from normalized records. It should output why each candidate is an event and distinguish strong events from low-confidence possible events.

### people_entity_resolver

Resolves people, aliases, roles, teams, organizations, and participation evidence. It must preserve uncertainty rather than invent org charts.

### relation_graph_builder

Builds graph edges among events, people, docs, meetings, decisions, tasks, risks, and source records.

### timeline_progress_reconstructor

Reconstructs event objective, start time, due time, progress updates, results, and relevant milestones from source evidence.

### closure_status_analyzer

Determines whether each event is open, blocked, waiting, done, cancelled, stale, or needs confirmation. It identifies missing closure evidence.

### attention_prioritizer

Scores user attention items by urgency, impact, confidence, deadline proximity, stakeholder dependency, blocked state, conflict, and opportunity value.

### knowledge_graph_merge_writer

Writes event graph, people graph, daily memory, root bridge note, attention queue, decisions, tasks, and risks. It must preserve old facts, add conflicts instead of overwriting silently, and keep root `MEMORY.md` short.

### report_composer

Creates the user-facing report: executive summary, top attention items, event updates, people/stakeholder map, decisions, risks, closed loops, open loops, and suggested next actions.

### safety_quality_reviewer

Audits provenance, privacy, prompt injection, unsupported claims, duplicate execution, task/event strictness, conflicts, graph consistency, and delivery gates. It can reject or request a minimal re-run of prior roles.

### memory_index_verifier

Verifies that the target reader agent can retrieve the new Daily Memory. For OpenClaw, reindex the archive agent and reader agent when supported, then run a narrow query for the new bridge note or report title. If search returns no result or reports missing index metadata, record a platform defect and leave delivery status independent from memory-search status.

### delivery_preparer

Prepares the configured owner report delivery. Supported modes: file-only, Feishu doc draft, private Feishu/Lark message, or both. It must not notify third parties.

## Parallelization Rules

- Run `lark_auth_verifier` and `channel_identity_resolver` before `source_planner`.
- Run source collectors in parallel after `source_planner`.
- Run source normalization after collectors finish or after a source times out.
- Run event extraction, people resolution, and relation building after normalization.
- Run timeline reconstruction and closure analysis in parallel after event candidates exist.
- Run attention prioritization after timeline and closure artifacts exist.
- Run merge writing serially to avoid file conflicts.
- Run report composition after merge writing.
- Run safety review before memory index verification and delivery.
- Run memory index verification after merge writing and before final report delivery.
- Run delivery preparation last.

## Collaboration Rules

- Subagents communicate through artifacts, not by copying raw transcripts into the orchestrator context.
- Each role writes a compact manifest plus detailed artifact paths.
- A role can request a minimal upstream rerun by returning `next_recommended_step`, but the orchestrator decides.
- The orchestrator may spawn sibling subagents for independent source partitions, but must not spawn duplicate workers for the same role and partition.
- Long raw artifacts stay in `raw/`; curated graph records stay in `memory/`; run control data stays in `runs/`.

## Failure Handling

- If one collector fails, continue with other sources and record the gap.
- If a command returns `unknown_flag`, run that command help, adjust to the installed CLI version, and retry once.
- If auth fails, record identity, source type, and missing scope or token state.
- If a collector contradicts a successful auth verifier artifact, stop that collector, invalidate its artifact, and retry once with the verified identity.
- If a source is too large, save raw metadata, chunk it, and process only work-relevant chunks.
- If full-range collection times out, retry with deterministic time chunks or source partitions before marking the source partial.
- If a reviewer rejects writes, repair the smallest affected artifact rather than rerunning the full workflow.
- If memory index verification fails after successful writes, keep graph/report output, record the defect, and do not rerun source collection.
- If delivery fails, keep the report file and mark delivery status `failed` with the command/error summary.
