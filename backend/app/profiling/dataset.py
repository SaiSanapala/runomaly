from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.models import ColumnProfile, DatasetProfile


def infer_data_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    numeric = pd.to_numeric(non_null, errors="coerce")
    numeric_ratio = float(numeric.notna().mean())
    if numeric_ratio >= 0.95:
        if (numeric.dropna() % 1 == 0).all():
            return "integer"
        return "decimal"
    dates = pd.to_datetime(non_null, errors="coerce")
    if float(dates.notna().mean()) >= 0.9:
        return "datetime"
    return "string"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _most_common(series: pd.Series) -> list[dict[str, Any]]:
    counts = series.dropna().astype(str).value_counts().head(5)
    return [{"value": str(index), "count": int(value)} for index, value in counts.items()]


def build_profile(df: pd.DataFrame, file_path: Path | None = None) -> dict[str, Any]:
    row_count = int(len(df))
    profile: dict[str, Any] = {
        "row_count": row_count,
        "column_count": int(len(df.columns)),
        "duplicate_count": int(df.duplicated().sum()),
        "file_size": int(file_path.stat().st_size) if file_path and file_path.exists() else 0,
        "columns": [],
    }
    for column in df.columns:
        series = df[column]
        data_type = infer_data_type(series)
        null_count = int(series.isna().sum())
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_values = numeric.dropna()
        stats: dict[str, Any] = {
            "column_name": column,
            "data_type": data_type,
            "null_count": null_count,
            "null_percentage": round((null_count / row_count) * 100, 4) if row_count else 0.0,
            "unique_count": int(series.nunique(dropna=True)),
            "minimum_value": None,
            "maximum_value": None,
            "mean_value": None,
            "standard_deviation": None,
            "most_common_values": _most_common(series),
        }
        if data_type in {"integer", "decimal"} and not numeric_values.empty:
            stats["minimum_value"] = str(_json_safe(numeric_values.min()))
            stats["maximum_value"] = str(_json_safe(numeric_values.max()))
            stats["mean_value"] = _json_safe(float(numeric_values.mean()))
            std = numeric_values.std()
            stats["standard_deviation"] = _json_safe(float(std)) if not pd.isna(std) else None
        elif not series.dropna().empty:
            stats["minimum_value"] = str(series.dropna().astype(str).min())
            stats["maximum_value"] = str(series.dropna().astype(str).max())
        profile["columns"].append(stats)
    return profile


def save_profile(
    db: Session, *, run_id: str, dataset_name: str, df: pd.DataFrame, file_path: Path | None = None
) -> DatasetProfile:
    built = build_profile(df, file_path)
    dataset_profile = DatasetProfile(
        run_id=run_id,
        dataset_name=dataset_name,
        row_count=built["row_count"],
        column_count=built["column_count"],
        duplicate_count=built["duplicate_count"],
        file_size=built["file_size"],
    )
    db.add(dataset_profile)
    db.flush()
    for column in built["columns"]:
        db.add(
            ColumnProfile(
                profile_id=dataset_profile.profile_id,
                column_name=column["column_name"],
                data_type=column["data_type"],
                null_count=column["null_count"],
                null_percentage=column["null_percentage"],
                unique_count=column["unique_count"],
                minimum_value=column["minimum_value"],
                maximum_value=column["maximum_value"],
                mean_value=column["mean_value"],
                standard_deviation=column["standard_deviation"],
                most_common_values=column["most_common_values"],
            )
        )
    db.flush()
    return dataset_profile
