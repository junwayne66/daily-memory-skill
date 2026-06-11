# Attention Loop Body

You are processing one batch of the **attention loop**. Input: open event notes that changed recently or carry deterministic flags pre-computed by the engine (`overdue`, `due_soon`, `stale_open_loop`, `blocked`, `waiting_external`, `needs_confirmation`, `missing_owner`, plus `days_to_due` / `days_since_update`). Output: updated attention frontmatter on those event notes.

## Task

For each event note in the batch:

1. Read the note and the engine signals attached to its batch entry.
2. Decide how much owner attention the event needs and set:

```yaml
attention_score: <0.0 - 1.0>
attention_reasons:
  - <short reason, e.g. "overdue", "blocked by vendor", "decision conflict">
next_action: <single concrete next step, or "">
last_updated: <ISO-8601 timestamp>
```

3. If evidence in the note shows the event actually closed, update `status` and `closure_state` instead of raising attention.

## Scoring Guidance

Raise the score for: imminent or passed deadlines, blocked work, missing owner, unresolved decisions, stakeholder dependencies, stale open loops, conflicting evidence, high-value opportunities. Lower it for events that are progressing normally or waiting on a known, dated milestone.

Calibration: `>= 0.75` means "must appear in today's report attention section" (the bridge note picks up events at or above the configured threshold automatically).

## Rules

- Judge from evidence already in the note; do not re-read raw sources in this loop.
- Do not edit timelines, decisions, or body sections here; this loop only maintains attention fields, status, and closure state.
- Keep `attention_reasons` short and factual; the report composer expands them later.

## Completion

After updating every note in the batch, run the batch's `commit_cmd` (`memoryctl commit --loop attention --batch <batch_id>`).
