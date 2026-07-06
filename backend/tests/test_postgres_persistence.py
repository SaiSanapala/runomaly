from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.models import DatasetProfile, PipelineRun
from backend.app.services.pipeline_runner import run_daily_order_analytics


@pytest.mark.integration
def test_persistence_round_trip_uses_configured_database(db):
    if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL integration test runs when DATABASE_URL points to PostgreSQL")
    run = run_daily_order_analytics(db, input_path=Path("sample_data/valid/orders.csv"))
    db.expire_all()
    assert db.get(PipelineRun, run.run_id) is not None
    assert db.query(DatasetProfile).filter_by(run_id=run.run_id).one().row_count == 20
