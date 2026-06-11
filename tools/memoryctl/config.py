"""Workspace layout, loop registry, and defaults."""

import os
from dataclasses import dataclass, field

# Skill root = parent of tools/ (this file lives at tools/memoryctl/config.py).
SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPTS_DIR = os.path.join(SKILL_ROOT, "prompts")

DEFAULT_BATCH_SIZE = 25

# Workspace subdirectories (relative to --workdir).
SOURCES_DIR = "sources"
KNOWLEDGE_DIR = "knowledge"
STATE_DIR = "state"
BATCHES_DIR = os.path.join(STATE_DIR, "batches")
INDEX_DIR = "index"
RUNS_DIR = "runs"
REPORTS_DIR = "reports"

# Vault entity folders.
VAULT_FOLDERS = ["Events", "People", "Organizations", "Projects", "Topics", "Daily"]

# Source relevance values written by the classify loop into source frontmatter.
RELEVANCE_EVENT = "event"      # contains event/task/decision signals
RELEVANCE_CONTEXT = "context"  # background context worth merging into notes
RELEVANCE_SKIP = "skip"        # casual / private / notification-only content
RELEVANCE_VALUES = (RELEVANCE_EVENT, RELEVANCE_CONTEXT, RELEVANCE_SKIP)

# Attention loop deterministic signal defaults.
DUE_SOON_DAYS = 3
STALE_OPEN_LOOP_DAYS = 3

OPEN_EVENT_STATUSES = (
    "open",
    "in_progress",
    "waiting",
    "blocked",
    "stale",
    "needs_confirmation",
)


@dataclass(frozen=True)
class LoopSpec:
    """Static definition of one processing loop."""

    name: str
    kind: str  # "llm" (agent processes batches) or "deterministic" (engine runs it)
    input_dir: str  # workspace-relative directory scanned for inputs
    prompt: str | None = None  # skill-relative prompt file for the loop body
    description: str = ""
    glob_suffixes: tuple = (".md",)
    excluded_prefixes: tuple = field(default_factory=tuple)


LOOPS: dict[str, LoopSpec] = {
    "classify": LoopSpec(
        name="classify",
        kind="llm",
        input_dir=SOURCES_DIR,
        prompt="prompts/classify_source.md",
        description="Label each synced source file with work relevance frontmatter.",
    ),
    "graph": LoopSpec(
        name="graph",
        kind="llm",
        input_dir=SOURCES_DIR,
        prompt="prompts/note_creation.md",
        description="Extract entities from relevant sources and merge them into vault notes.",
    ),
    "attention": LoopSpec(
        name="attention",
        kind="llm",
        input_dir=os.path.join(KNOWLEDGE_DIR, "Events"),
        prompt="prompts/attention.md",
        description="Score open events for attention and surface open loops.",
    ),
    "index": LoopSpec(
        name="index",
        kind="deterministic",
        input_dir=KNOWLEDGE_DIR,
        description="Rebuild wikilink edges index and the daily bridge note.",
    ),
}

# Default pipeline order. LLM loops first, deterministic index last so that
# edges.json and the bridge note reflect the final state of the vault.
DEFAULT_STEPS = ["classify", "graph", "attention", "index"]


class Workspace:
    """Resolved paths for one Daily Memory working directory."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    @property
    def sources(self) -> str:
        return self.path(SOURCES_DIR)

    @property
    def knowledge(self) -> str:
        return self.path(KNOWLEDGE_DIR)

    @property
    def state(self) -> str:
        return self.path(STATE_DIR)

    @property
    def batches(self) -> str:
        return self.path(BATCHES_DIR)

    @property
    def index(self) -> str:
        return self.path(INDEX_DIR)

    @property
    def reports(self) -> str:
        return self.path(REPORTS_DIR)

    def state_file(self, loop: str) -> str:
        return self.path(STATE_DIR, f"{loop}_state.json")

    def batch_dir(self, loop: str) -> str:
        return self.path(BATCHES_DIR, loop)

    def relpath(self, abspath: str) -> str:
        return os.path.relpath(abspath, self.root).replace(os.sep, "/")

    def ensure_layout(self) -> None:
        for d in (
            self.sources,
            self.knowledge,
            self.state,
            self.batches,
            self.index,
            self.reports,
        ):
            os.makedirs(d, exist_ok=True)
        for folder in VAULT_FOLDERS:
            os.makedirs(os.path.join(self.knowledge, folder), exist_ok=True)


def resolve_workspace(workdir: str | None) -> Workspace:
    root = workdir or os.environ.get("DAILY_MEMORY_WORKDIR") or os.getcwd()
    return Workspace(root)
