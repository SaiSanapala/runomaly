from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.app.profiling.dataset import build_profile


def test_dataset_profile_records_dataset_and_column_metrics():
    df = pd.DataFrame(
        {
            "order_id": [1, 2, 2],
            "price": [10.0, 20.5, 20.5],
            "email": ["a@example.com", None, "b@example.com"],
        }
    )
    profile = build_profile(df, Path("missing.csv"))
    assert profile["row_count"] == 3
    assert profile["column_count"] == 3
    assert profile["duplicate_count"] == 0
    columns = {column["column_name"]: column for column in profile["columns"]}
    assert columns["price"]["data_type"] == "decimal"
    assert columns["email"]["null_count"] == 1
    assert round(columns["email"]["null_percentage"], 2) == 33.33
    assert columns["order_id"]["unique_count"] == 2
