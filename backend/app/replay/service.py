from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core import get_settings
from backend.app.models import PipelineRun, ReplayRun, RunStatus, StepStatus
from backend.app.services.pipeline_runner import run_pipeline_capturing_failure


def _now() -> datetime:
    return datetime.now(UTC)


def _failed_step(run: PipelineRun | None) -> str | None:
    if run is None:
        return None
    failed = next((step for step in run.steps if step.status == StepStatus.FAILED), None)
    return failed.step_name if failed else None


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "--version"], check=True, capture_output=True, text=True, timeout=5
        )
        return True
    except Exception:
        return False


def replay_run(db: Session, run_id: str) -> ReplayRun:
    original = db.get(PipelineRun, run_id)
    if original is None:
        raise ValueError(f"Run {run_id} not found")
    if not original.input_snapshot_path:
        raise ValueError("Original run has no input snapshot")

    replay = ReplayRun(original_run_id=run_id, status="RUNNING", logs="")
    db.add(replay)
    db.commit()
    db.refresh(replay)

    settings = get_settings()
    docker_note = "Docker replay requested; running local fallback because Docker is unavailable."
    if settings.replay_mode == "docker" and _docker_available():
        docker_note = (
            "Docker is available. The same snapshot can be replayed with "
            f"`docker compose run --rm backend python -m investigator replay --run-id {run_id}`. "
            "The API uses the local runner to keep the request synchronous."
        )

    replayed = run_pipeline_capturing_failure(
        db,
        input_path=Path(original.input_snapshot_path),
        parameters=original.pipeline_parameters,
        replay_of_run_id=run_id,
    )
    reproduced = (
        original.status == RunStatus.FAILED
        and replayed is not None
        and replayed.status == RunStatus.FAILED
        and original.error_type == replayed.error_type
        and _failed_step(original) == _failed_step(replayed)
    )
    replay.replay_run_id = replayed.run_id if replayed else None
    replay.status = "REPRODUCED" if reproduced else "NOT_REPRODUCED"
    replay.reproduced = reproduced
    replay.finished_at = _now()
    replay.logs = "\n".join(
        [
            docker_note,
            f"Original error type: {original.error_type}",
            f"Replay error type: {replayed.error_type if replayed else None}",
            f"Original failed step: {_failed_step(original)}",
            f"Replay failed step: {_failed_step(replayed)}",
        ]
    )
    db.commit()
    return replay
