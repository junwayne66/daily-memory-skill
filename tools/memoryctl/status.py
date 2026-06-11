"""Per-loop progress accounting."""

from .config import LOOPS, Workspace
from .fsutil import list_files
from .scan import eligible_files, pending_batches
from .state import load_state


def loop_status(ws: Workspace, loop: str) -> dict:
    spec = LOOPS[loop]
    if spec.kind == "deterministic":
        return {
            "loop": loop,
            "kind": spec.kind,
            "inputs": len(list_files(ws.path(spec.input_dir))),
        }
    state = load_state(ws, loop)
    batches = pending_batches(ws, loop)
    in_flight = sum(len(b.get("files", [])) for b in batches)
    return {
        "loop": loop,
        "kind": spec.kind,
        "inputs": len(list_files(ws.path(spec.input_dir))),
        "processed": len(state["processed"]),
        "pending": len(eligible_files(ws, loop)),
        "in_flight_batches": len(batches),
        "in_flight_files": in_flight,
        "last_run": state.get("last_run"),
    }


def workspace_status(ws: Workspace) -> dict:
    return {
        "workdir": ws.root,
        "loops": {name: loop_status(ws, name) for name in LOOPS},
    }
