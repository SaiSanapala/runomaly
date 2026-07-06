from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import desc

from backend.app.comparison.engine import compare_run
from backend.app.db.session import SessionLocal
from backend.app.diagnosis.rules import generate_diagnoses
from backend.app.models import PipelineLog, PipelineRun, RunStatus
from backend.app.replay.service import replay_run
from backend.app.services.bootstrap import PIPELINE_ID, create_tables, seed_defaults
from backend.app.services.impact import downstream_impact
from backend.app.services.pipeline_runner import PipelineFailed, run_daily_order_analytics


def _bootstrap() -> None:
    create_tables()
    with SessionLocal() as db:
        seed_defaults(db)


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    if args.pipeline != PIPELINE_ID:
        print(f"Unknown pipeline: {args.pipeline}", file=sys.stderr)
        return 2
    _bootstrap()
    with SessionLocal() as db:
        try:
            run = run_daily_order_analytics(db, input_path=args.input)
        except PipelineFailed:
            failed_run = db.query(PipelineRun).order_by(desc(PipelineRun.started_at)).first()
            if failed_run is None:
                print("Run failed before a run record was created", file=sys.stderr)
                return 1
            print(f"Run failed: {failed_run.run_id} {failed_run.error_message}", file=sys.stderr)
            return 1
        print(f"Run succeeded: {run.run_id}")
        return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    _bootstrap()
    with SessionLocal() as db:
        run = db.get(PipelineRun, args.run_id)
        if not run:
            print("Run not found", file=sys.stderr)
            return 2
        _print_json(
            {
                "run_id": run.run_id,
                "status": run.status.value,
                "input": run.input_filename,
                "snapshot": run.input_snapshot_path,
                "error": run.error_message,
                "steps": [
                    {
                        "step_name": step.step_name,
                        "status": step.status.value,
                        "duration_seconds": step.duration_seconds,
                        "error_message": step.error_message,
                    }
                    for step in run.steps
                ],
                "logs": [
                    {"level": log.level, "message": log.message}
                    for log in db.query(PipelineLog).filter_by(run_id=run.run_id).all()
                ],
            }
        )
        return 0 if run.status == RunStatus.SUCCESS else 1


def cmd_compare(args: argparse.Namespace) -> int:
    _bootstrap()
    with SessionLocal() as db:
        _print_json(compare_run(db, args.run_id))
        _print_json({"diagnoses": generate_diagnoses(db, args.run_id)})
        _print_json({"impact": downstream_impact(db, args.run_id)})
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    _bootstrap()
    with SessionLocal() as db:
        replay = replay_run(db, args.run_id)
        _print_json(
            {
                "replay_id": replay.replay_id,
                "original_run_id": replay.original_run_id,
                "replay_run_id": replay.replay_run_id,
                "status": replay.status,
                "reproduced": replay.reproduced,
                "logs": replay.logs,
            }
        )
        return 0 if replay.reproduced else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m investigator")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--pipeline", required=True)
    run.add_argument("--input", required=True)
    run.set_defaults(func=cmd_run)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--run-id", required=True)
    inspect.set_defaults(func=cmd_inspect)

    compare = sub.add_parser("compare")
    compare.add_argument("--run-id", required=True)
    compare.set_defaults(func=cmd_compare)

    replay = sub.add_parser("replay")
    replay.add_argument("--run-id", required=True)
    replay.set_defaults(func=cmd_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
