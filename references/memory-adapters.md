# Memory Adapters

Use this reference to write Daily Memory into the active agent's own memory system without duplicating or polluting long-term bootstrap memory.

## Adapter Selection

Detect the active platform from user input, environment, config, or filesystem:

- OpenClaw: `OPENCLAW_*`, `~/.openclaw/workspace`, OpenClaw memory tools, or OpenClaw docs/config.
- Hermes Agent: `HERMES_HOME`, `~/.hermes`, `hermes memory status`, or `~/.hermes/memories`.
- Codex: `~/.codex/memories`, workspace instructions, or Codex memory tooling.
- Generic: no native memory detected.

If multiple agents need the same Daily Memory knowledge, designate one authoritative memory root. Let the archive agent write the canonical graph and let other agents read it through native search extra paths, symlinks, provider collections, or compact bridge notes. Do not merge all agents into one workspace just to share memory.

## OpenClaw

OpenClaw's memory model is a strong fit for Daily Memory:

- `MEMORY.md`: compact curated long-term facts, decisions, preferences, and standing instructions.
- `memory/YYYY-MM-DD.md` or slugged daily files: detailed daily notes and observations.
- Optional wiki/memory plugins: provenance-rich knowledge vaults and search tools.
- Memory search can combine semantic and keyword retrieval when providers are configured.
- In current OpenClaw layouts, shallow `memory/*.md` files are the safest bridge for reader-agent search. Deep graph YAML is useful as state, but may not be indexed by the default search path.

Recommended mapping for a dedicated Daily Memory archive agent:

```text
~/.openclaw/workspace-daily-memory/
  MEMORY.md
  runs/YYYY-MM-DD/run_manifest.yaml
  raw/YYYY-MM-DD/
  memory/
    historical-backfill-before-YYYY-MM-DD.md
    daily-memory-YYYY-MM-DD.md
    daily/YYYY-MM-DD.md
    graph/events/active_events.yaml
    graph/events/closed_events.yaml
    graph/people/people.yaml
    graph/people/relationships.yaml
    graph/documents/documents.yaml
    graph/edges.yaml
    attention/open_items.yaml
    projects/<project-slug>.md
    people/<person-slug>.md
    tasks/active_tasks.yaml
    decisions/decisions.yaml
    risks/risks.yaml
  reports/YYYY-MM-DD.md
```

Write full daily output to the daily memory file and graph files. Promote only compact, durable, high-confidence items to root `MEMORY.md`. Include action-sensitive boundaries when the fact affects future behavior, approvals, handoffs, expiry, or safe-to-act timing.

Also write a compact bridge note directly under `memory/*.md` for every run that should be visible to another OpenClaw agent. The bridge note should include:

- Run id, date window, report title, and report path/doc URL.
- Event ids and titles for new, updated, and closed events.
- Top attention items and unresolved loops.
- People/project/doc keywords likely to be searched later.
- Links to structured graph files and daily note paths.

The bridge note is the reader-agent recall surface; the graph YAML remains the deterministic source of truth.

Recommended sharing pattern when the main Feishu bot agent should answer from Daily Memory:

```json5
{
  agents: {
    list: [
      {
        id: "main",
        memorySearch: {
          extraPaths: [
            "/home/botinkit/.openclaw/workspace-daily-memory/memory"
          ]
        }
      },
      {
        id: "daily-memory",
        workspace: "/home/botinkit/.openclaw/workspace-daily-memory",
        skills: ["daily-memory-skill"]
      }
    ]
  }
}
```

After scheduled archive writes, reindex both the archive agent and any reader agent that depends on `extraPaths`.

Useful checks when available:

```bash
openclaw memory status
openclaw memory search "query"
openclaw memory index --agent daily-memory --force
openclaw memory index --agent main --force
```

Do not treat indexing as successful until retrieval is proven through the same agent that will answer the user. A minimal verification sequence is:

```bash
openclaw memory index --agent daily-memory --force
openclaw memory index --agent main --force
openclaw memory status --agent main --deep
openclaw memory search --agent main "<bridge note title or event id>"
```

If search returns empty results while files/chunks exist, or if logs mention missing index metadata/provider state, record it as an OpenClaw memory-search defect in:

- `runs/YYYY-MM-DD/run_manifest.yaml`
- `reports/YYYY-MM-DD.md`
- the owner delivery summary, if delivery is enabled

Do not claim that the main Feishu bot can search the new memory until a query returns the bridge note or a relevant chunk.

## Hermes Agent

Hermes has small built-in memory files and optional external memory providers.

- Built-in memory lives under `~/.hermes/memories/`.
- `MEMORY.md` stores compact agent notes such as project conventions, tool lessons, and durable work facts.
- `USER.md` stores user profile and preferences.
- Built-in memory is injected as a frozen snapshot at session start; updates persist immediately but may not appear in prompt context until a later session.
- The memory tool usually supports add, replace, and remove rather than direct read.
- External providers such as Honcho, Mem0, or others are additive; built-in memory remains active. Hermes typically enables one external provider at a time.

Recommended mapping:

```text
~/.hermes/
  memories/
    MEMORY.md
    USER.md
  daily-memory/
    daily/YYYY-MM-DD.md
    graph/events/active_events.yaml
    graph/people/people.yaml
    graph/edges.yaml
    attention/open_items.yaml
    tasks/active_tasks.yaml
    decisions/decisions.yaml
    raw/<date>/
```

Do not store raw transcripts or large project files in Hermes built-in memory. Store full Daily Memory artifacts in the external folder or active provider. Add only 1-3 compact memory entries when a durable lesson, project invariant, or recurring user preference should be visible in future sessions.

Useful checks when available:

```bash
hermes memory status
hermes memory setup
hermes memory off
```

If an external provider is active, use it for searchable semantic recall. Keep source ids and file paths so provider facts remain auditable.

## Codex

When running in Codex, follow the active memory instructions from the environment. Prefer project-local artifacts for Daily Memory details and only update Codex durable memory when the user explicitly asks to remember something or when the environment's memory policy permits it.

Recommended project-local mapping:

```text
<workspace>/.daily-memory/
    daily/YYYY-MM-DD.md
    graph/events/active_events.yaml
    graph/people/people.yaml
    graph/edges.yaml
    attention/open_items.yaml
    tasks/active_tasks.yaml
    decisions/decisions.yaml
    raw/<date>/
  index/
```

## Generic Agent

When no native memory exists, create a portable memory root:

```text
daily-memory/
  memory/
    daily/
    graph/
      events/
      people/
      documents/
      edges.yaml
    attention/
    projects/
    people/
    tasks/
    decisions/
    glossary/
  raw/
    feishu_messages/
    feishu_docs/
    feishu_materials/
    feishu_minutes/
    agent_logs/
  index/
    memory.db
    vector_store/
    graph.db
```

Use Markdown as the human-readable source of truth, YAML/JSON for state that needs deterministic diffing, and SQLite/PostgreSQL plus vector search only when the volume justifies it.

## Promotion Strategy

Promote memory in this order:

1. Raw evidence: save unchanged source snapshots.
2. Daily memory: summarize the day's work with evidence links.
3. Event graph memory: merge event goals, people, relationships, timelines, progress, results, closure state, tasks, risks, and decisions.
4. Project memory: merge stable project facts, current architecture, tasks, risks, and decisions.
5. Native long-term memory: add compact durable items only when they are useful in many future sessions.

Every promotion must preserve source references and confidence. If a new item conflicts with an old memory, write a conflict note and ask the user or source owner to confirm before overwriting.

## Cross-Agent Sharing

For OpenClaw + Hermes or multi-agent setups:

- Keep one canonical Daily Memory root.
- Let each agent write pointers to the canonical root in its native memory.
- Use append-only source records and deterministic ids so agents can reconcile without duplicate tasks.
- Avoid direct writes into another agent's private memory database unless that agent exposes an official memory tool or provider API.
- Verify delivery and recall: after a cross-agent write, query/read through the same channel the target agent will use.
