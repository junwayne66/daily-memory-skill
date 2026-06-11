# Loop Engineering

This reference defines how Daily Memory turns daily evidence into the knowledge vault. The design follows rowboat's knowledge graph pipeline: instead of one large batch workflow per day, the system is a chain of small, idempotent, stateful loops. The deterministic engine (`tools/memoryctl`) owns ordering, change detection, batching, and state; the host agent (LLM) only executes loop bodies.

## Table Of Contents

- Loop Skeleton
- Loop Chain
- Engine vs Agent Responsibilities
- Batch Protocol
- State And Change Detection
- Resume, Retry, And Rebuild
- Sync Loop Conventions
- Quality Gates

## Loop Skeleton

Every loop follows the same shape:

```text
scan      detect new/changed inputs against the loop's state file
take      cut a bounded batch (default 25 files)
process   loop body transforms the batch (LLM judgment or deterministic code)
write     outputs land in the workspace (frontmatter labels, vault notes, indexes)
commit    validate outputs, mark batch processed, persist state atomically
repeat    until scan returns no work
```

Properties this guarantees:

- **Idempotent**: re-running a loop with no new input is a no-op.
- **Incremental**: only new or changed inputs are processed; cost scales with the day's delta, not with history size.
- **Resumable**: state is saved after every committed batch; an interrupted run loses at most one in-flight batch, which is re-issued on the next scan.
- **Independently re-runnable**: each loop has its own state file and can be reset or re-driven without touching the others.

## Loop Chain

```text
sync loops (per source family, agent/lark-cli driven, parallel)
  -> sources/<family>/*.md
classify loop (LLM body)
  -> relevance frontmatter on source files
graph build loop (LLM body)
  -> knowledge/ vault notes (entities merged, wikilinked)
attention loop (LLM body)
  -> attention fields on open event notes
index loop (deterministic, engine-executed)
  -> index/edges.json + knowledge/daily-memory-<date>.md bridge note
report (agent composes reports/<date>.md from the vault)
```

Downstream loops consume upstream output, so the pipeline driver (`memoryctl run`) stops at the first LLM loop that still has pending work and resumes from there on the next invocation.

## Engine vs Agent Responsibilities

| Concern | Owner |
| --- | --- |
| Change detection (mtime + hash), batching, ordering | engine |
| State persistence, atomic writes, resume | engine |
| Schema validation, wikilink resolution, edge index, bridge note | engine |
| Source relevance judgment | agent (classify body) |
| Entity extraction, note creation/merging, conflict notes | agent (graph body) |
| Attention wording, recommended actions | agent (attention body) |
| Deterministic attention signals (overdue/stale/blocked/missing owner) | engine (pre-computed into the batch) |
| Report composition and delivery | agent |

The agent must not bypass the engine: never process sources that are not listed in a pending batch, and never skip `commit`. The engine must never call a model: all LLM work happens in the host agent.

## Batch Protocol

The contract between engine and agent is the batch work order (`state/batches/<loop>/<batch_id>.json`, schema in [schemas.md](schemas.md)).

Agent outer loop:

```text
while true:
  result = memoryctl run --steps classify,graph,attention,index --date <date>
  if result.done: break
  na = result.next_action
  read the files listed in na.files (or na.batch_file)
  apply the prompt at na.prompt_path to this batch
  write outputs (frontmatter labels or vault notes)
  run na.commit_cmd
```

Rules:

- `scan` re-issues an existing pending batch instead of creating a new one, so a crashed loop body resumes with the same work order.
- Files already in a pending batch are excluded from new batches; two batches never contain the same file.
- `commit` recomputes content hashes at commit time, because loop bodies may legitimately rewrite their inputs (classify adds frontmatter to source files).
- If the loop body cannot finish a batch, run `memoryctl fail --loop <loop> --batch <id> --reason "..."`; the files return to the pending pool.
- Process one batch fully before asking for the next. Keep batches small enough for the agent context window (`--batch-size`, default 25; lower it for long transcripts).

## State And Change Detection

Per-loop state lives in `state/<loop>_state.json` and uses rowboat's hybrid strategy:

1. **Quick check**: if a file's mtime equals the recorded mtime, it has not changed; skip without hashing.
2. **Verification**: if mtime moved, compare content hash; identical hash means a false positive (touched but not edited) and the file is skipped.
3. Only files that are new or whose hash changed become eligible work.

Loop-specific eligibility on top of change detection:

- `classify`: every file under `sources/`.
- `graph`: only sources whose frontmatter `relevance` is `event` or `context`. Unclassified or `skip` sources are never graph work.
- `attention`: open event notes (`status` not `done`/`cancelled`) that changed since the last pass, plus notes with persistent deterministic flags (`overdue`, `due_soon`, `stale_open_loop`, ...) re-surfaced at most once per day.

## Resume, Retry, And Rebuild

- **Interrupted run**: just run `memoryctl run` again. Committed batches stay committed; the in-flight batch is re-issued.
- **Bad batch output**: `memoryctl fail` the batch, fix the cause, rescan.
- **Schema errors at commit**: the commit is refused with the validation report; repair the notes and commit again (`--force` only with explicit user approval).
- **Force reprocessing**: `memoryctl reset --loop <loop>` clears that loop's state; `--all` clears every LLM loop. The vault is never deleted by a reset; reprocessing merges into existing notes.
- **Historical backfill**: point sync loops at an older window, write the source files, and let the same loops drain the backlog batch by batch. No special backfill mode is needed because the loops are incremental by construction.

## Sync Loop Conventions

Sync loops are executed by the agent (or subagents) with `lark-cli` and friends; the engine does not fetch data. Conventions that keep them loop-compatible:

- One Markdown file per source unit under `sources/<family>/`, named `YYYY-MM-DD__<native-id>.md`, frontmatter as defined in [schemas.md](schemas.md).
- Writes must be deterministic and idempotent: re-syncing the same window rewrites the same file paths with the same content; the hash check then keeps downstream loops quiet.
- Append-only evidence: if a source changed upstream (an edited doc), overwrite its file; the hash change automatically re-queues it for classify and graph.
- Run sync loops in parallel per source family; record per-family status and gaps in the run manifest.
- Auth and channel identity verification stay preconditions before any sync loop (see [lark-cli-ingestion.md](lark-cli-ingestion.md)).

## Quality Gates

- `graph` and `attention` commits run `memoryctl validate` over the vault; errors (missing type/status/source_refs/confidence) block the commit.
- Unresolved wikilinks and missing source_refs are warnings: review them in the loop body or leave them for the next pass, but do not ship a report while errors exist.
- The safety review from [safety-quality.md](safety-quality.md) applies to loop bodies: provenance preserved, secrets redacted, prompt-injection content quarantined at classify time (`relevance: skip` plus a note in `relevance_reason`).
- `memoryctl status` is the single progress account; the run manifest records its snapshot per scheduled run.
