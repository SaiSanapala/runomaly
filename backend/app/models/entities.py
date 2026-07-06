from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid_str() -> str:
    return str(uuid.uuid4())


class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class StepStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class NodeType(str, enum.Enum):
    SOURCE = "SOURCE"
    PIPELINE_STEP = "PIPELINE_STEP"
    TABLE = "TABLE"
    DASHBOARD = "DASHBOARD"
    MODEL = "MODEL"


class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFORMATIONAL = "INFORMATIONAL"


class Confidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Pipeline(Base):
    __tablename__ = "pipelines"

    pipeline_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runs: Mapped[list[PipelineRun]] = relationship(back_populates="pipeline")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.pipeline_id"), index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    git_commit: Mapped[str | None] = mapped_column(String(80))
    input_filename: Mapped[str | None] = mapped_column(String(500))
    input_snapshot_path: Mapped[str | None] = mapped_column(String(1000))
    error_type: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    environment_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    pipeline_parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    replay_of_run_id: Mapped[str | None] = mapped_column(String(64), index=True)

    pipeline: Mapped[Pipeline] = relationship(back_populates="runs")
    steps: Mapped[list[PipelineStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    logs: Mapped[list[PipelineLog]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    profiles: Mapped[list[DatasetProfile]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    diagnoses: Mapped[list[DiagnosisResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    step_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), index=True)
    step_name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)

    run: Mapped[PipelineRun] = relationship(back_populates="steps")


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    level: Mapped[str] = mapped_column(String(40), default="INFO")
    message: Mapped[str] = mapped_column(Text)

    run: Mapped[PipelineRun] = relationship(back_populates="logs")


class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), index=True)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[PipelineRun] = relationship(back_populates="profiles")
    columns: Mapped[list[ColumnProfile]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    column_profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("dataset_profiles.profile_id"), index=True)
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(80), nullable=False)
    null_count: Mapped[int] = mapped_column(Integer, nullable=False)
    null_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    unique_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_value: Mapped[str | None] = mapped_column(String(200))
    maximum_value: Mapped[str | None] = mapped_column(String(200))
    mean_value: Mapped[float | None] = mapped_column(Float)
    standard_deviation: Mapped[float | None] = mapped_column(Float)
    most_common_values: Mapped[list] = mapped_column(JSON, default=list)

    profile: Mapped[DatasetProfile] = relationship(back_populates="columns")


class PipelineNode(Base):
    __tablename__ = "pipeline_nodes"

    node_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    node_type: Mapped[NodeType] = mapped_column(Enum(NodeType), nullable=False)


class PipelineDependency(Base):
    __tablename__ = "pipeline_dependencies"

    dependency_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("pipeline_nodes.node_id"))
    target_node_id: Mapped[str] = mapped_column(ForeignKey("pipeline_nodes.node_id"))

    __table_args__ = (UniqueConstraint("source_node_id", "target_node_id"),)


class DiagnosisResult(Base):
    __tablename__ = "diagnosis_results"

    diagnosis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False)
    confidence: Mapped[Confidence] = mapped_column(Enum(Confidence), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[PipelineRun] = relationship(back_populates="diagnoses")


class ReplayRun(Base):
    __tablename__ = "replay_runs"

    replay_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    original_run_id: Mapped[str] = mapped_column(String(64), index=True)
    replay_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), default="RUNNING")
    reproduced: Mapped[bool] = mapped_column(default=False)
    logs: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
