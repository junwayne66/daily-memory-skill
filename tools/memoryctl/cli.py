"""memoryctl command-line interface."""

import argparse
import json
import sys

from .commit import commit_batch, fail_batch
from .config import DEFAULT_BATCH_SIZE, DEFAULT_STEPS, LOOPS, resolve_workspace
from .index import DEFAULT_ATTENTION_THRESHOLD, run_index
from .pipeline import run_pipeline
from .scan import scan
from .state import reset_state
from .status import workspace_status
from .validate import validate_vault

LLM_LOOPS = [name for name, spec in LOOPS.items() if spec.kind == "llm"]


def _emit(data, as_json: bool, human: str | None = None) -> None:
    if as_json or human is None:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(human)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memoryctl",
        description="Deterministic loop engine for the Daily Memory knowledge vault.",
    )
    parser.add_argument(
        "--workdir",
        help="Daily Memory working directory (default: $DAILY_MEMORY_WORKDIR or cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the workspace directory layout")

    p = sub.add_parser("scan", help="emit the next batch of work for an LLM loop")
    p.add_argument("--loop", required=True, choices=LLM_LOOPS)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    p = sub.add_parser("commit", help="mark a processed batch as done")
    p.add_argument("--loop", required=True, choices=LLM_LOOPS)
    p.add_argument("--batch", required=True, dest="batch_id")
    p.add_argument("--force", action="store_true", help="commit despite validation errors")
    p.add_argument("--skip-validation", action="store_true")

    p = sub.add_parser("fail", help="mark a batch as failed (files will be rescanned)")
    p.add_argument("--loop", required=True, choices=LLM_LOOPS)
    p.add_argument("--batch", required=True, dest="batch_id")
    p.add_argument("--reason", default="")

    p = sub.add_parser("validate", help="validate vault notes")
    p.add_argument("paths", nargs="*", help="workspace-relative note paths (default: whole vault)")

    p = sub.add_parser("index", help="rebuild edges.json and the daily bridge note")
    p.add_argument("--date", help="bridge note date YYYY-MM-DD (default: today UTC)")
    p.add_argument(
        "--attention-threshold",
        type=float,
        default=DEFAULT_ATTENTION_THRESHOLD,
    )

    p = sub.add_parser("run", help="drive the pipeline and report the next action")
    p.add_argument("--steps", default=",".join(DEFAULT_STEPS), help="comma-separated loop names")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--date", help="date passed to the index step")

    p = sub.add_parser("status", help="show per-loop progress")

    p = sub.add_parser("reset", help="clear loop state to force reprocessing")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--loop", choices=LLM_LOOPS)
    group.add_argument("--all", action="store_true")

    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ws = resolve_workspace(args.workdir)
    as_json = getattr(args, "json", False)

    if args.command == "init":
        ws.ensure_layout()
        _emit({"initialized": True, "workdir": ws.root}, as_json, f"initialized {ws.root}")
        return 0

    if args.command == "scan":
        result = scan(ws, args.loop, batch_size=args.batch_size)
        _emit(result, True)
        return 0

    if args.command == "commit":
        result = commit_batch(
            ws,
            args.loop,
            args.batch_id,
            force=args.force,
            skip_validation=args.skip_validation,
        )
        _emit(result, True)
        return 0 if result.get("committed") else 1

    if args.command == "fail":
        _emit(fail_batch(ws, args.loop, args.batch_id, reason=args.reason), True)
        return 0

    if args.command == "validate":
        result = validate_vault(ws, paths=args.paths or None)
        _emit(result, True)
        return 0 if result["ok"] else 1

    if args.command == "index":
        result = run_index(ws, date=args.date, attention_threshold=args.attention_threshold)
        _emit(result, True)
        return 0

    if args.command == "run":
        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
        result = run_pipeline(ws, steps=steps, batch_size=args.batch_size, date=args.date)
        _emit(result, True)
        return 0

    if args.command == "status":
        _emit(workspace_status(ws), True)
        return 0

    if args.command == "reset":
        loops = LLM_LOOPS if args.all else [args.loop]
        cleared = {loop: reset_state(ws, loop) for loop in loops}
        _emit({"reset": cleared}, True)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
