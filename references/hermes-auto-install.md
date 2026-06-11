# Hermes Auto Install Guide

Use this guide when a Hermes agent should install and run `daily-memory-skill`. Hermes and OpenClaw can share the same canonical Daily Memory root, but Hermes should keep native memory compact.

## Target Result

- One canonical skill copy at `~/.agents/skills/daily-memory-skill`.
- Hermes skill link at `~/.hermes/skills/daily-memory-skill`.
- Canonical Daily Memory artifacts under `~/.hermes/daily-memory` or a shared root such as `~/.openclaw/workspace-daily-memory`.
- Hermes native memory contains only pointers, durable user preferences, and high-confidence long-term rules.
- Scheduled job can run the skill with dynamic subagent-style role separation.
- Feishu/Lark collection uses `lark-cli` with verified user/bot auth.

## Inputs

```bash
export SOURCE_SKILL_DIR="/path/to/daily-memory-skill"
export AGENT_HOME="${AGENT_HOME:-$HOME/.agents}"
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export HERMES_BIN="${HERMES_BIN:-hermes}"
export LARK_BIN="${LARK_BIN:-lark-cli}"
export DAILY_ROOT="${DAILY_ROOT:-$HERMES_HOME/daily-memory}"
export TZ_NAME="Asia/Shanghai"
```

## 1. Install The Skill

```bash
set -euo pipefail
test -f "$SOURCE_SKILL_DIR/SKILL.md"
test -f "$SOURCE_SKILL_DIR/references/subagent-workflow.md"
test -f "$SOURCE_SKILL_DIR/references/hermes-auto-install.md"

ts="$(date +%Y%m%d%H%M%S)"
mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/skill-backups"
if [ -e "$AGENT_HOME/skills/daily-memory-skill" ]; then
  mv "$AGENT_HOME/skills/daily-memory-skill" \
    "$AGENT_HOME/skill-backups/daily-memory-skill.$ts"
fi

mkdir -p "$AGENT_HOME/skills/daily-memory-skill"
tar -C "$SOURCE_SKILL_DIR" -cf - SKILL.md README.md agents assets references \
  | tar -C "$AGENT_HOME/skills/daily-memory-skill" -xf -

mkdir -p "$HERMES_HOME/skills"
ln -sfn "$AGENT_HOME/skills/daily-memory-skill" \
  "$HERMES_HOME/skills/daily-memory-skill"
```

If Hermes uses a different skill registry path, keep the canonical copy in `~/.agents/skills` and create a pointer according to the installed Hermes config.

## 2. Create The Daily Memory Root

```bash
mkdir -p \
  "$DAILY_ROOT/runs" \
  "$DAILY_ROOT/raw" \
  "$DAILY_ROOT/reports" \
  "$DAILY_ROOT/memory/daily" \
  "$DAILY_ROOT/memory/graph/events" \
  "$DAILY_ROOT/memory/graph/people" \
  "$DAILY_ROOT/memory/graph/documents" \
  "$DAILY_ROOT/memory/attention" \
  "$DAILY_ROOT/memory/projects" \
  "$DAILY_ROOT/memory/tasks" \
  "$DAILY_ROOT/memory/decisions" \
  "$DAILY_ROOT/memory/risks" \
  "$DAILY_ROOT/memory/people" \
  "$DAILY_ROOT/memory/glossary"
```

Bootstrap:

```bash
cat > "$DAILY_ROOT/MEMORY.md" <<'EOF'
# Daily Memory Bootstrap

Canonical Daily Memory archive for Hermes. Raw evidence lives under `raw/`; graph state under `memory/graph`; bridge notes under `memory/*.md`; reports under `reports/`.
EOF
```

## 3. Hermes Native Memory Policy

Do not put raw transcripts, full meeting minutes, or large graph files in Hermes native memory. Add only compact pointers like:

```markdown
Daily Memory canonical root: /home/botinkit/.hermes/daily-memory. Search or read bridge notes under memory/*.md before answering project/event questions.
```

If Hermes exposes memory commands, use them conservatively:

```bash
"$HERMES_BIN" memory status || true
"$HERMES_BIN" memory add "Daily Memory canonical root: $DAILY_ROOT. Use bridge notes in memory/*.md for recall." || true
```

If Hermes has an external semantic memory provider, index `"$DAILY_ROOT/memory"` and keep source paths in every stored fact.

## 4. Feishu/Lark Auth

Hermes should use the same source policy as OpenClaw:

```bash
"$LARK_BIN" --version
"$LARK_BIN" config strict-mode
"$LARK_BIN" auth status
"$LARK_BIN" im +chat-list --as user --types p2p --page-size 3
```

Rules:

- Prefer `--as user` for private chats, user-visible docs, personal calendar, meetings, and minutes.
- Use `--as bot` only for bot-visible groups or bot-owned delivery.
- If user auth is usable, do not start interactive login inside an unattended run.
- Record auth proof in `runs/YYYY-MM-DD/artifacts/lark_auth_verifier.yaml`.

## 5. Dynamic Subagent Execution In Hermes

Use real Hermes subagents/delegation if available. If Hermes does not expose native subagents, emulate subagents with short isolated Hermes turns or deterministic scripts that write the same role artifacts.

The orchestration contract is platform-neutral:

```text
orchestrator
  -> run_guard
  -> lark_auth_verifier
  -> channel_identity_resolver
  -> source_planner
  -> parallel source collectors
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
```

Each role receives a small YAML envelope:

```yaml
role: lark_private_chat_collector
run_id: daily-memory_YYYY-MM-DD_hash
date_window:
  start: "YYYY-MM-DDT00:00:00+08:00"
  end: "YYYY-MM-DDT22:00:00+08:00"
memory_root: "/home/botinkit/.hermes/daily-memory/memory"
raw_root: "/home/botinkit/.hermes/daily-memory/raw/YYYY-MM-DD"
run_root: "/home/botinkit/.hermes/daily-memory/runs/YYYY-MM-DD"
source_partition:
  kind: feishu_private_chat
  chat_id: oc_xxx
constraints:
  no_third_party_notifications: true
  no_long_term_memory_writes: true
  preserve_source_refs: true
```

Parallel-safe roles:

- `lark_private_chat_collector`
- `lark_group_chat_collector`
- `lark_shared_docs_collector`
- `lark_materials_collector`
- `lark_calendar_collector`
- `lark_meeting_minutes_collector`
- `lark_tasks_base_collector`
- `agent_workspace_collector`

Serial roles:

- `knowledge_graph_merge_writer`
- `safety_quality_reviewer`
- `memory_index_verifier`
- `delivery_preparer`

## 6. Scheduling

Use Hermes native scheduler if available. Otherwise use cron or systemd user timer.

Cron script example:

```bash
cat > "$HERMES_HOME/daily-memory/run-nightly.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERMES_BIN="${HERMES_BIN:-hermes}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
"$HERMES_BIN" run \
  --skill daily-memory-skill \
  --message "$(cat "$HERMES_HOME/daily-memory/nightly-prompt.txt")" \
  >> "$HERMES_HOME/daily-memory/runs/cron.log" 2>&1
EOF
chmod +x "$HERMES_HOME/daily-memory/run-nightly.sh"
```

Cron entry:

```cron
0 22 * * * /home/botinkit/.hermes/daily-memory/run-nightly.sh
```

`nightly-prompt.txt`:

```text
Use $daily-memory-skill to run the Daily Memory nightly archive.

Timezone: Asia/Shanghai.
Window: current local date from 00:00 to now.
Canonical memory root: ~/.hermes/daily-memory.

Operate as an orchestrator. Create dynamic short-lived subagents where Hermes supports them; otherwise emulate the same atomic roles through isolated turns/scripts and artifact handoffs. Run guard/auth/channel checks first, collect sources in parallel where possible, merge serially, verify memory recall, and prepare the owner report. Do not notify third parties.
```

## 7. Delivery

Recommended default for Hermes is file-only delivery:

```text
$DAILY_ROOT/reports/YYYY-MM-DD.md
```

For Feishu private delivery, prefer `lark-cli im +messages-send --as bot` or the platform's official Feishu channel connector if configured. Always keep owner delivery separate from third-party notification.

## 8. Validation

No-data validation:

```bash
test -L "$HERMES_HOME/skills/daily-memory-skill" || test -d "$HERMES_HOME/skills/daily-memory-skill"
test -f "$DAILY_ROOT/MEMORY.md"
"$LARK_BIN" auth status
```

Hermes skill smoke test, command shape may vary by installation:

```bash
"$HERMES_BIN" run \
  --skill daily-memory-skill \
  --message "Installation no-op. Do not collect Feishu/Lark data, write files, or send messages. Report visible skill, Daily Memory root, and required subagent roles."
```

Memory recall validation:

- Write a bridge note under `"$DAILY_ROOT/memory/daily-memory-install-test.md"`.
- Add or index a pointer through Hermes memory/provider.
- Ask Hermes a narrow query for the bridge note title.
- Record whether retrieval is native memory, external provider, file search, or unsupported.

## 9. OpenClaw + Hermes Shared Root

If OpenClaw and Hermes run on the same host, prefer one authoritative root:

```text
/home/botinkit/.openclaw/workspace-daily-memory
```

Hermes then stores only a pointer:

```markdown
Daily Memory is authoritative at /home/botinkit/.openclaw/workspace-daily-memory. Use memory/*.md bridge notes and graph files under memory/ for source-backed recall.
```

This avoids duplicate graph writes and keeps event ids stable across agents.

## 10. Rollback

1. Relink `~/.hermes/skills/daily-memory-skill` to the previous backup.
2. Restore any Hermes memory pointer if changed.
3. Disable the cron/systemd timer.
4. Keep `daily-memory/runs/` and `daily-memory/raw/` unless the user explicitly asks to delete them.
