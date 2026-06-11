"""memoryctl: deterministic loop engine for the Daily Memory knowledge vault.

Inspired by rowboat's knowledge graph pipeline (graph_state.ts / build_graph.ts /
run_pipeline.ts): small idempotent loops, per-loop state files with mtime+hash
change detection, bounded batches, incremental commits, and a Markdown vault
where [[wikilinks]] are the graph edges.

The engine is fully deterministic. LLM judgment (classification, note creation,
attention review) happens inside the loop body, executed by the host agent.
"""

__version__ = "0.1.0"
