"""Pipeline driver: walk the loop chain and report the next required action.

The engine owns ordering and state; the host agent owns LLM judgment. The
agent's outer loop is simply:

    while True:
        result = memoryctl run --steps classify,graph,attention,index
        if result.next_action is None: break
        process the indicated batch following its prompt
        memoryctl commit --loop <loop> --batch <batch_id>

Deterministic steps (index) execute inline. The driver stops at the first LLM
loop that still has pending work, because downstream loops consume upstream
output.
"""

from .config import DEFAULT_BATCH_SIZE, DEFAULT_STEPS, LOOPS, Workspace
from .index import run_index
from .scan import scan


def run_pipeline(
    ws: Workspace,
    steps: list[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    date: str | None = None,
) -> dict:
    steps = steps or list(DEFAULT_STEPS)
    for step in steps:
        if step not in LOOPS:
            raise ValueError(f"unknown step '{step}'; valid steps: {', '.join(LOOPS)}")

    ws.ensure_layout()
    executed: list[dict] = []
    next_action: dict | None = None

    for step in steps:
        spec = LOOPS[step]
        if spec.kind == "deterministic":
            result = run_index(ws, date=date)
            executed.append({"step": step, "status": "executed", **result})
            continue

        result = scan(ws, step, batch_size=batch_size)
        batch = result["batch"]
        if batch is None:
            executed.append({"step": step, "status": "clean", "pending": 0})
            continue

        executed.append(
            {
                "step": step,
                "status": "needs_processing",
                "batch_id": batch["batch_id"],
                "batch_files": len(batch["files"]),
                "remaining": result["remaining"],
                "resumed": result["resumed"],
            }
        )
        next_action = {
            "action": "process_batch",
            "loop": step,
            "batch_id": batch["batch_id"],
            "batch_file": f"state/batches/{step}/{batch['batch_id']}.json",
            "files": [f["path"] for f in batch["files"]],
            "prompt": batch.get("prompt"),
            "prompt_path": batch.get("prompt_path"),
            "commit_cmd": (
                f"memoryctl --workdir {ws.root} commit --loop {step} --batch {batch['batch_id']}"
            ),
        }
        break  # downstream loops depend on this one; stop here

    return {
        "steps": executed,
        "next_action": next_action,
        "done": next_action is None,
    }
