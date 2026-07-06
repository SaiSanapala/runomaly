from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PipelineOut(OrmModel):
    pipeline_id: str
    name: str
    description: str | None = None
    created_at: datetime


class PipelineRunOut(OrmModel):
    run_id: str
    pipeline_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    git_commit: str | None = None
    input_filename: str | None = None
    input_snapshot_path: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    environment_metadata: dict[str, Any] = {}
    pipeline_parameters: dict[str, Any] = {}


class StepOut(OrmModel):
    step_id: int
    run_id: str
    step_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None


class LogOut(OrmModel):
    created_at: datetime
    level: str
    message: str


class DiagnosisOut(OrmModel):
    diagnosis_id: int | None = None
    run_id: str | None = None
    category: str
    severity: str
    confidence: str
    title: str
    description: str
    supporting_evidence: dict[str, Any]
    created_at: datetime | None = None


class ReplayOut(OrmModel):
    replay_id: str
    original_run_id: str
    replay_run_id: str | None = None
    status: str
    reproduced: bool
    logs: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
