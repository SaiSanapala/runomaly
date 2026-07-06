from __future__ import annotations

import json
import platform
import shutil
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import pandas as pd
from prefect import flow, task
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.comparison.engine import latest_successful_baseline
from backend.app.core import get_settings
from backend.app.db.session import engine
from backend.app.diagnosis.rules import generate_diagnoses
from backend.app.models import (
    DatasetProfile,
    PipelineLog,
    PipelineRun,
    PipelineStep,
    RunStatus,
    StepStatus,
)
from backend.app.profiling.dataset import save_profile
from backend.app.services.bootstrap import PIPELINE_ID, seed_defaults

REQUIRED_COLUMNS = [
    "order_id",
    "customer_id",
    "price",
    "quantity",
    "order_date",
    "status",
    "email",
]


class PipelineFailed(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _duration(started_at: datetime, finished_at: datetime) -> float:
    return round((finished_at - started_at).total_seconds(), 6)


def dependency_versions() -> dict[str, str]:
    packages = ["fastapi", "pandas", "prefect", "pydantic", "sqlalchemy"]
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions


def environment_metadata() -> dict:
    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "dependency_versions": dependency_versions(),
    }


def log(db: Session, run_id: str, message: str, level: str = "INFO") -> None:
    db.add(PipelineLog(run_id=run_id, level=level, message=message))
    db.commit()


@contextmanager
def monitored_step(db: Session, run_id: str, step_name: str) -> Iterator[PipelineStep]:
    started = _now()
    step = PipelineStep(
        run_id=run_id, step_name=step_name, status=StepStatus.RUNNING, started_at=started
    )
    db.add(step)
    db.commit()
    log(db, run_id, f"Started step {step_name}")
    try:
        yield step
    except Exception as exc:
        finished = _now()
        step.status = StepStatus.FAILED
        step.finished_at = finished
        step.duration_seconds = _duration(started, finished)
        step.error_message = str(exc)
        db.commit()
        log(db, run_id, f"Failed step {step_name}: {exc}", "ERROR")
        raise
    else:
        finished = _now()
        step.status = StepStatus.SUCCESS
        step.finished_at = finished
        step.duration_seconds = _duration(started, finished)
        db.commit()
        log(db, run_id, f"Completed step {step_name}")


def snapshot_input(run_id: str, pipeline_name: str, input_path: Path) -> Path:
    settings = get_settings()
    target_dir = settings.snapshots_dir / pipeline_name / run_id
    target_dir.mkdir(parents=True, exist_ok=False)
    target_file = target_dir / input_path.name
    shutil.copy2(input_path, target_file)
    metadata_path = target_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "pipeline": pipeline_name,
                "git_commit": settings.git_commit,
                "input_file": input_path.name,
                "created_at": _now().isoformat(),
            },
            indent=2,
        )
    )
    return target_file


def latest_profile_for_run(db: Session, run_id: str) -> DatasetProfile | None:
    return (
        db.query(DatasetProfile)
        .filter_by(run_id=run_id)
        .order_by(DatasetProfile.created_at.desc())
        .first()
    )


def validate_input(db: Session, run: PipelineRun, df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")
    if df.empty:
        raise ValueError("The input dataset contains no records")

    profile = latest_profile_for_run(db, run.run_id)
    columns = {column.column_name: column for column in profile.columns} if profile else {}
    order_id = columns.get("order_id")
    if order_id and profile and profile.row_count:
        duplicate_rate = ((profile.row_count - order_id.unique_count) / profile.row_count) * 100
        if duplicate_rate >= 20:
            raise ValueError(f"Duplicate order_id rate is {duplicate_rate:.1f}%")

    email = columns.get("email")
    if email and email.null_percentage >= 25:
        raise ValueError(f"email null rate is {email.null_percentage:.1f}%")

    baseline = latest_successful_baseline(db, run)
    baseline_profile = latest_profile_for_run(db, baseline.run_id) if baseline else None
    if baseline_profile and profile and profile.row_count < baseline_profile.row_count * 0.5:
        raise ValueError(
            "Input row count decreased significantly compared with the previous successful run"
        )


@task
def normalize_orders(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    clean["order_id"] = pd.to_numeric(clean["order_id"], errors="raise").astype("int64")
    clean["customer_id"] = pd.to_numeric(clean["customer_id"], errors="raise").astype("int64")
    clean["price"] = pd.to_numeric(clean["price"], errors="raise")
    clean["quantity"] = pd.to_numeric(clean["quantity"], errors="raise").astype("int64")
    clean["order_date"] = pd.to_datetime(clean["order_date"], errors="raise").dt.date.astype(str)
    clean["status"] = clean["status"].astype(str).str.lower().str.strip()
    clean["email"] = clean["email"].astype("string").str.lower().str.strip()
    return clean


@task
def calculate_daily_revenue(clean: pd.DataFrame) -> pd.DataFrame:
    completed = clean[clean["status"].isin(["paid", "complete", "completed", "shipped"])].copy()
    completed["revenue"] = completed["price"] * completed["quantity"]
    return (
        completed.groupby("order_date", as_index=False)
        .agg(order_count=("order_id", "nunique"), total_revenue=("revenue", "sum"))
        .sort_values("order_date")
    )


def _write_table(df: pd.DataFrame, table_name: str) -> None:
    df.to_sql(table_name, con=engine, if_exists="replace", index=False)


def _ensure_warehouse_indexes() -> None:
    with engine.begin() as connection:
        try:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_raw_orders_order_id ON raw_orders(order_id)")
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_clean_orders_order_id ON clean_orders(order_id)"
                )
            )
        except Exception:
            # SQLite and PostgreSQL both support the above, but indexes are not critical for the demo.
            pass


@flow(name="daily_order_analytics")
def daily_order_analytics_flow(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    clean = normalize_orders(df)
    revenue = calculate_daily_revenue(clean)
    return clean, revenue


def run_daily_order_analytics(
    db: Session,
    *,
    input_path: str | Path,
    parameters: dict | None = None,
    replay_of_run_id: str | None = None,
) -> PipelineRun:
    seed_defaults(db)
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    settings = get_settings()
    started = _now()
    run = PipelineRun(
        pipeline_id=PIPELINE_ID,
        status=RunStatus.RUNNING,
        started_at=started,
        git_commit=settings.git_commit,
        input_filename=input_path.name,
        environment_metadata=environment_metadata(),
        pipeline_parameters=parameters or {},
        replay_of_run_id=replay_of_run_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    log(db, run.run_id, f"Created run {run.run_id} for {input_path.name}")

    try:
        snapshot_path = snapshot_input(run.run_id, PIPELINE_ID, input_path)
        run.input_snapshot_path = str(snapshot_path)
        db.commit()

        with monitored_step(db, run.run_id, "load_input"):
            df = pd.read_csv(snapshot_path)
            log(db, run.run_id, f"Loaded {len(df)} rows and {len(df.columns)} columns")

        with monitored_step(db, run.run_id, "profile_input"):
            save_profile(
                db, run_id=run.run_id, dataset_name="orders_csv", df=df, file_path=snapshot_path
            )
            db.commit()

        with monitored_step(db, run.run_id, "validate_schema"):
            validate_input(db, run, df)

        with monitored_step(db, run.run_id, "load_raw_orders"):
            _write_table(df, "raw_orders")

        with monitored_step(db, run.run_id, "transform_orders"):
            clean, revenue = daily_order_analytics_flow(df)
            _write_table(clean, "clean_orders")

        with monitored_step(db, run.run_id, "calculate_revenue"):
            _write_table(revenue, "daily_revenue")
            _ensure_warehouse_indexes()

        finished = _now()
        run.status = RunStatus.SUCCESS
        run.finished_at = finished
        run.duration_seconds = _duration(started, finished)
        db.commit()
        log(db, run.run_id, "Pipeline completed successfully")
    except Exception as exc:
        finished = _now()
        run.status = RunStatus.FAILED
        run.finished_at = finished
        run.duration_seconds = _duration(started, finished)
        run.error_type = exc.__class__.__name__
        run.error_message = str(exc)
        db.commit()
        log(db, run.run_id, traceback.format_exc(), "ERROR")
        try:
            generate_diagnoses(db, run.run_id, persist=True)
        except Exception as diagnosis_exc:
            log(db, run.run_id, f"Diagnosis generation failed: {diagnosis_exc}", "ERROR")
        raise PipelineFailed(str(exc)) from exc
    return run


def run_pipeline_capturing_failure(db: Session, **kwargs) -> PipelineRun:
    try:
        return run_daily_order_analytics(db, **kwargs)
    except PipelineFailed:
        replay_of_run_id = kwargs.get("replay_of_run_id")
        query = db.query(PipelineRun)
        if replay_of_run_id:
            query = query.filter(PipelineRun.replay_of_run_id == replay_of_run_id)
        failed_run = query.order_by(PipelineRun.started_at.desc()).first()
        if failed_run is None:
            raise
        return failed_run
