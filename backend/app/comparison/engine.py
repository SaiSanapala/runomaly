from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models import ColumnProfile, DatasetProfile, PipelineRun, RunStatus


@dataclass
class SchemaChange:
    column: str
    previous_type: str | None
    current_type: str | None
    change_type: str


@dataclass
class ProfileChange:
    metric: str
    previous_value: Any
    current_value: Any
    change_percentage: float | None = None


def latest_successful_baseline(db: Session, failed_run: PipelineRun) -> PipelineRun | None:
    return (
        db.query(PipelineRun)
        .filter(
            PipelineRun.pipeline_id == failed_run.pipeline_id,
            PipelineRun.status == RunStatus.SUCCESS,
            PipelineRun.started_at < failed_run.started_at,
        )
        .order_by(desc(PipelineRun.started_at))
        .first()
    )


def _profile_for_run(db: Session, run_id: str) -> DatasetProfile | None:
    return (
        db.query(DatasetProfile)
        .filter(DatasetProfile.run_id == run_id)
        .order_by(desc(DatasetProfile.created_at))
        .first()
    )


def _columns(db: Session, profile: DatasetProfile | None) -> dict[str, ColumnProfile]:
    if profile is None:
        return {}
    return {
        col.column_name: col
        for col in db.query(ColumnProfile).filter_by(profile_id=profile.profile_id)
    }


def _percentage(previous: float | int | None, current: float | int | None) -> float | None:
    if previous is None or previous == 0 or current is None:
        return None
    return round(((float(current) - float(previous)) / float(previous)) * 100, 4)


def compare_run(db: Session, run_id: str) -> dict[str, Any]:
    failed_run = db.get(PipelineRun, run_id)
    if failed_run is None:
        raise ValueError(f"Run {run_id} not found")
    baseline = latest_successful_baseline(db, failed_run)
    current_profile = _profile_for_run(db, run_id)
    baseline_profile = _profile_for_run(db, baseline.run_id) if baseline else None
    current_columns = _columns(db, current_profile)
    baseline_columns = _columns(db, baseline_profile)

    schema_changes: list[SchemaChange] = []
    for column in sorted(set(baseline_columns) | set(current_columns)):
        previous = baseline_columns.get(column)
        current = current_columns.get(column)
        if previous and not current:
            schema_changes.append(SchemaChange(column, previous.data_type, None, "REMOVED"))
        elif current and not previous:
            schema_changes.append(SchemaChange(column, None, current.data_type, "ADDED"))
        elif previous and current and previous.data_type != current.data_type:
            schema_changes.append(
                SchemaChange(column, previous.data_type, current.data_type, "TYPE_CHANGED")
            )

    profile_changes: list[ProfileChange] = []
    if baseline_profile and current_profile:
        profile_changes.append(
            ProfileChange(
                "row_count",
                baseline_profile.row_count,
                current_profile.row_count,
                _percentage(baseline_profile.row_count, current_profile.row_count),
            )
        )
        profile_changes.append(
            ProfileChange(
                "duplicate_row_count",
                baseline_profile.duplicate_count,
                current_profile.duplicate_count,
                _percentage(baseline_profile.duplicate_count, current_profile.duplicate_count),
            )
        )
    for column in sorted(set(baseline_columns) & set(current_columns)):
        previous = baseline_columns[column]
        current = current_columns[column]
        profile_changes.extend(
            [
                ProfileChange(
                    f"{column}_null_percentage",
                    previous.null_percentage,
                    current.null_percentage,
                    _percentage(previous.null_percentage, current.null_percentage),
                ),
                ProfileChange(
                    f"{column}_unique_count",
                    previous.unique_count,
                    current.unique_count,
                    _percentage(previous.unique_count, current.unique_count),
                ),
            ]
        )
        if column == "order_id":
            previous_dup = max(
                0, (baseline_profile.row_count if baseline_profile else 0) - previous.unique_count
            )
            current_dup = max(
                0, (current_profile.row_count if current_profile else 0) - current.unique_count
            )
            previous_rate = (
                (previous_dup / baseline_profile.row_count * 100)
                if baseline_profile and baseline_profile.row_count
                else 0
            )
            current_rate = (
                (current_dup / current_profile.row_count * 100)
                if current_profile and current_profile.row_count
                else 0
            )
            profile_changes.append(
                ProfileChange(
                    "order_id_duplicate_rate",
                    round(previous_rate, 4),
                    round(current_rate, 4),
                    _percentage(previous_rate, current_rate),
                )
            )
        if (
            previous.minimum_value != current.minimum_value
            or previous.maximum_value != current.maximum_value
        ):
            profile_changes.append(
                ProfileChange(
                    f"{column}_range",
                    {"min": previous.minimum_value, "max": previous.maximum_value},
                    {"min": current.minimum_value, "max": current.maximum_value},
                    None,
                )
            )

    return {
        "failed_run_id": run_id,
        "baseline_run_id": baseline.run_id if baseline else None,
        "schema_changes": [asdict(change) for change in schema_changes],
        "profile_changes": [asdict(change) for change in profile_changes],
        "environment_changes": {
            "git_commit": {
                "previous": baseline.git_commit if baseline else None,
                "current": failed_run.git_commit,
                "changed": bool(baseline and baseline.git_commit != failed_run.git_commit),
            },
            "dependency_versions": {
                "previous": (
                    (baseline.environment_metadata or {}).get("dependency_versions")
                    if baseline
                    else None
                ),
                "current": (failed_run.environment_metadata or {}).get("dependency_versions"),
            },
            "pipeline_parameters": {
                "previous": baseline.pipeline_parameters if baseline else None,
                "current": failed_run.pipeline_parameters,
                "changed": bool(
                    baseline and baseline.pipeline_parameters != failed_run.pipeline_parameters
                ),
            },
        },
        "error": {"type": failed_run.error_type, "message": failed_run.error_message},
    }
