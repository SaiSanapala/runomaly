from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.comparison.engine import compare_run
from backend.app.core import get_settings
from backend.app.db.session import get_db
from backend.app.diagnosis.rules import generate_diagnoses
from backend.app.models import (
    DiagnosisResult,
    Pipeline,
    PipelineLog,
    PipelineRun,
    PipelineStep,
    ReplayRun,
    RunStatus,
)
from backend.app.replay.service import replay_run
from backend.app.schemas.api import (
    DiagnosisOut,
    LogOut,
    PipelineOut,
    PipelineRunOut,
    ReplayOut,
    StepOut,
)
from backend.app.services.bootstrap import PIPELINE_ID
from backend.app.services.impact import downstream_impact
from backend.app.services.pipeline_runner import PipelineFailed, run_daily_order_analytics

router = APIRouter(prefix="/api")


@router.get("/pipelines", response_model=list[PipelineOut])
def pipelines(db: Session = Depends(get_db)):
    return db.query(Pipeline).order_by(Pipeline.name).all()


@router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
def pipeline_detail(pipeline_id: str, db: Session = Depends(get_db)):
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    return pipeline


@router.get("/pipelines/{pipeline_id}/runs", response_model=list[PipelineRunOut])
def pipeline_runs(pipeline_id: str, db: Session = Depends(get_db)):
    return (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == pipeline_id)
        .order_by(desc(PipelineRun.started_at))
        .all()
    )


@router.get("/runs", response_model=list[PipelineRunOut])
def runs(status: str | None = None, pipeline_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(PipelineRun)
    if status:
        query = query.filter(PipelineRun.status == RunStatus(status))
    if pipeline_id:
        query = query.filter(PipelineRun.pipeline_id == pipeline_id)
    return query.order_by(desc(PipelineRun.started_at)).limit(200).all()


@router.get("/runs/{run_id}", response_model=PipelineRunOut)
def run_detail(run_id: str, db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/runs/{run_id}/steps", response_model=list[StepOut])
def run_steps(run_id: str, db: Session = Depends(get_db)):
    return db.query(PipelineStep).filter_by(run_id=run_id).order_by(PipelineStep.started_at).all()


@router.get("/runs/{run_id}/logs", response_model=list[LogOut])
def run_logs(run_id: str, db: Session = Depends(get_db)):
    return db.query(PipelineLog).filter_by(run_id=run_id).order_by(PipelineLog.created_at).all()


@router.get("/runs/{run_id}/comparison")
def run_comparison(run_id: str, db: Session = Depends(get_db)):
    try:
        return compare_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/runs/{run_id}/diagnoses", response_model=list[DiagnosisOut])
def run_diagnoses(run_id: str, db: Session = Depends(get_db)):
    existing = (
        db.query(DiagnosisResult)
        .filter_by(run_id=run_id)
        .order_by(DiagnosisResult.diagnosis_id)
        .all()
    )
    if existing:
        return existing
    try:
        return generate_diagnoses(db, run_id, persist=True)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/runs/{run_id}/impact")
def run_impact(run_id: str, db: Session = Depends(get_db)):
    try:
        return downstream_impact(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/runs/{run_id}/replay", response_model=ReplayOut)
def create_replay(run_id: str, db: Session = Depends(get_db)):
    try:
        return replay_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/replays/{replay_id}", response_model=ReplayOut)
def replay_detail(replay_id: str, db: Session = Depends(get_db)):
    replay = db.get(ReplayRun, replay_id)
    if not replay:
        raise HTTPException(404, "Replay not found")
    return replay


@router.post("/pipelines/{pipeline_id}/run", response_model=PipelineRunOut)
def run_pipeline(
    pipeline_id: str,
    file: Annotated[UploadFile | None, File()] = None,
    test_file: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    if pipeline_id != PIPELINE_ID:
        raise HTTPException(404, "Only daily_order_analytics is implemented")
    settings = get_settings()
    temp_dir = settings.snapshots_dir / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if file is not None:
        input_path = temp_dir / (file.filename or "uploaded_orders.csv")
        with input_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
    elif test_file:
        input_path = Path(test_file)
        if not input_path.is_absolute():
            input_path = settings.sample_data_dir / test_file
    else:
        raise HTTPException(400, "Provide an uploaded CSV or test_file")

    try:
        return run_daily_order_analytics(db, input_path=input_path)
    except PipelineFailed:
        failed = db.query(PipelineRun).order_by(desc(PipelineRun.started_at)).first()
        return failed
