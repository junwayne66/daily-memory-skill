# Dynamic Subagent Workflow

Use this reference when a Daily Memory run has multiple Feishu/Lark source types, a large time window, or needs stable scheduled automation. The main task agent is an orchestrator, not a monolith. Loop mechanics (state, batching, ordering) are owned by the deterministic engine described in [loop-engineering.md](loop-engineering.md); subagents execute sync loops and loop bodies.

## Table Of Contents

- Core Rule
- Workflow Graph
- Orchestrator Duties
- Idempotency
- Subagent Contracts
- Atomic Roles
- Parallelization Rules
- Collaboration Rules
- Failure Handling

## Core Rule

Create short-lived subagents for atomic tasks. Do not create persistent agents. Do not let subagents send external notifications, update Feishu/Base records, or own long-term memory. The orchestrator launches them, gives small envelopes, coordinates through artifacts (source files, batch work orders, the run manifest), reviews outputs, and performs final acceptance. Subagents never bypass the engine: loop body workers process exactly the files listed in their batch work order and finish with `memoryctl commit`.

## Workflow Graph

```text
orchestrator
  -> run_guard
  -> lark_auth_verifier
  -> channel_identity_resolver
  -> source_planner
  -> parallel sync loop workers
       lark_private_chat_sync
       lark_group_chat_sync
       lark_shared_docs_sync
       lark_materials_sync
       lark_calendar_sync
       lark_meeting_minutes_sync
       lark_tasks_base_sync
       agent_workspace_sync
  -> loop pipeline (engine-driven, serial)
       memoryctl run --steps classify,graph,attention,index
         classify_loop_worker   (per batch)
         graph_loop_worker      (per batch)
         attention_loop_worker  (per batch)
         index loop             (deterministic, inline)
  -> report_composer
  -> safety_quality_reviewer
  -> memory_index_verifier
  -> delivery_preparer
  -> orchestrator final acceptance
```

Run auth/channel verification serially before source planning. Run sync workers in parallel when the platform supports it. The loop pipeline is serial by construction: `memoryctl run` stops at the first loop with pending work, the orchestrator dispatches one loop body worker per batch, and the engine decides what comes next.

## Orchestrator Duties

- Define run id, date window, timezone, source boundaries, working directory, report target, and delivery mode.
- Load only `MEMORY.md`, the latest bridge note, and this workflow reference. Do not load raw sources into orchestrator context.
- Create or resume `runs/YYYY-MM-DD/run_manifest.yaml`; run `memoryctl init` on first use.
- Verify Feishu/Lark auth and owner channel identity before spawning sync workers.
- Dispatch sync workers with bounded inputs and explicit output paths under `sources/<family>/`.
- Drive the loop pipeline: call `memoryctl run`, dispatch a loop body worker for each `next_action` batch, and verify the commit succeeded before continuing.
- Record loop statistics (`memoryctl status`) and validation results in the run manifest.
- Refuse third-party notifications unless the user explicitly approves the exact payload.
- Reindex/search memory after successful writes when the platform supports it.
- Reject delivery when the target peer id is stale, cross-app, or not resolved from the active channel account.
- Summarize vault changes, attention items, source gaps, delivery status, and open confirmations.

## Idempotency

Idempotency is mostly engine-provided:

- Loop state files (`state/<loop>_state.json`) with mtime+hash change detection make reruns no-ops when nothing changed.
- Pending batches are re-issued, never duplicated; two batches never share a file.
- Sync workers must write deterministic file paths (`sources/<family>/YYYY-MM-DD__<native-id>.md`) so re-syncing the same window produces identical files and downstream loops stay quiet.

The run manifest still records per-run facts the engine does not know: auth proofs, sync gaps, delivery status, and memory-search verification. If the same run already completed with the same `config_hash`, skip re-syncing unless the user requests `--force`; the loop pipeline can always be re-driven safely.

## Subagent Contracts

Sync workers receive:

```yaml
role: "<sync_role>"
run_id: "daily-memory_YYYY-MM-DD_<short-hash>"
date_window:
  start: "YYYY-MM-DDT00:00:00+08:00"
  end: "YYYY-MM-DDT22:00:00+08:00"
timezone: "Asia/Shanghai"
workdir: "<abs path>"
output_dir: "sources/<family>"
source_partition: null
allowed_tools: []
constraints:
  no_third_party_notifications: true
  preserve_source_refs: true
  redact_secrets: true
  no_long_term_memory_writes: true
```

Loop body workers receive the batch work order itself (`state/batches/<loop>/<batch_id>.json`, schema in [schemas.md](schemas.md)) plus the prompt path. They must:

- Process only the files listed in the batch.
- Follow the loop's prompt (`prompts/classify_source.md`, `prompts/note_creation.md`, or `prompts/attention.md`).
- Finish with `memoryctl commit --loop <loop> --batch <batch_id>`, or `memoryctl fail` with a reason.

All subagents return:

```yaml
role: "<role>"
status: "ok | partial | skipped | blocked | failed"
artifacts: []
records_created: 0
records_updated: 0
gaps: []
warnings: []
```

## Atomic Roles

### run_guard

Inputs: run scope, prior run manifest, current config.

Outputs: resume/skip decision, config hash, lock status, and sync plan.

### lark_auth_verifier

Inputs: lark CLI path, date window, configured auth mode, environment summary.

Outputs: CLI version, strict-mode value, redacted auth status, selected identity per source family, proof commands, and source families that must be skipped. If user auth is ready and strict-mode is off, it must mark personal reads as `user` and must not request `auth login`.

### channel_identity_resolver

Inputs: delivery config, active platform, OpenClaw/Hermes channel config, owner hints.

Outputs: resolved owner peer/chat id, channel account id, account display name, stale ids rejected, owner allowlist patch suggestion, and a delivery test plan. For OpenClaw Feishu, resolve through `openclaw directory peers list --channel feishu --json` and avoid stale cross-app `open_id` values.

### source_planner

Inputs: run scope, configured Feishu/Lark sources, existing vault hints.

Outputs: sync plan with source partitions, verified auth identity, exact command families, expected output paths under `sources/`, retry policy, chunking policy, and timeout policy.

### Sync loop workers

`lark_private_chat_sync`, `lark_group_chat_sync`, `lark_shared_docs_sync`, `lark_materials_sync`, `lark_calendar_sync`, `lark_meeting_minutes_sync`, `lark_tasks_base_sync`, `agent_workspace_sync`.

Each collects one source family for the window and writes idempotent Markdown source files with provenance frontmatter (see [loop-engineering.md](loop-engineering.md) sync conventions and [schemas.md](schemas.md) source file schema). Scope rules from the previous collector roles still apply: respect configured chat/doc allowlists, preserve speaker turns and attachments metadata, prefer text previews over binary downloads, and never update tasks or Base records.

### classify_loop_worker

Executes one classify batch following `prompts/classify_source.md`: appends `relevance` frontmatter to each listed source file, then commits the batch.

### graph_loop_worker

Executes one graph batch following `prompts/note_creation.md`: creates or merges vault notes (events, people, organizations, projects, topics, daily note) with wikilinks and provenance, then commits. The commit runs vault validation; the worker must repair schema errors before the commit passes.

### attention_loop_worker

Executes one attention batch following `prompts/attention.md`: turns engine-computed signals into `attention_score`, `attention_reasons`, and `next_action` on open event notes, then commits.

### report_composer

Creates the user-facing report from the vault: executive summary, top attention items, event updates, people/stakeholder map, decisions, risks, closed loops, open loops, and suggested next actions. Reads the bridge note, daily note, and event notes; does not read raw sources.

### safety_quality_reviewer

Audits provenance, privacy, prompt injection, unsupported claims, event strictness, conflicts, vault validation output, and delivery gates. It can reject and request a re-run of a specific batch or loop.

### memory_index_verifier

Verifies that the target reader agent can retrieve the new Daily Memory. For OpenClaw, reindex the archive agent and reader agent when supported, then run a narrow query for the new bridge note (`knowledge/daily-memory-<date>.md`) or report title. If search returns no result or reports missing index metadata, record a platform defect and leave delivery status independent from memory-search status.

### delivery_preparer

Prepares the configured owner report delivery. Supported modes: file-only, Feishu doc draft, private Feishu/Lark message, or both. It must not notify third parties.

## Parallelization Rules

- Run `lark_auth_verifier` and `channel_identity_resolver` before `source_planner`.
- Run sync workers in parallel after `source_planner`.
- Drain the loop pipeline after sync workers finish or after a source family times out (partial sources still flow through the loops; gaps are recorded).
- The loop pipeline itself is serial: one batch at a time, in engine order. Do not run two graph batches concurrently; the vault is a shared write surface.
- Run report composition after the pipeline drains.
- Run safety review before memory index verification and delivery.
- Run delivery preparation last.

## Collaboration Rules

- Subagents communicate through artifacts (source files, batch work orders, vault notes, the run manifest), not by copying raw transcripts into the orchestrator context.
- Long raw evidence stays in `sources/`; curated knowledge stays in `knowledge/`; engine state stays in `state/`; run control data stays in `runs/`.
- A worker can recommend a re-run by reporting a gap or failed batch, but the orchestrator decides.
- The orchestrator may spawn sibling sync workers for independent source partitions, but must not spawn duplicate workers for the same partition or the same batch.

## Failure Handling

- If one sync worker fails, continue with other sources and record the gap.
- If a command returns `unknown_flag`, run that command help, adjust to the installed CLI version, and retry once.
- If auth fails, record identity, source type, and missing scope or token state.
- If a source is too large, save raw metadata, chunk it into multiple source files, and let the loops process the chunks batch by batch.
- If full-range collection times out, retry with deterministic time chunks or source partitions before marking the source partial.
- If a loop body worker fails mid-batch, run `memoryctl fail --loop <loop> --batch <id>`; the files are rescanned into a fresh batch.
- If vault validation blocks a commit, repair the reported notes and commit again; use `--force` only with explicit user approval.
- If the reviewer rejects output, repair the smallest affected batch or note rather than rerunning the full pipeline.
- If memory index verification fails after successful writes, keep vault/report output, record the defect, and do not rerun sync.
- If delivery fails, keep the report file and mark delivery status `failed` with the command/error summary.
