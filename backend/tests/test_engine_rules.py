from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import desc

from backend.app.comparison.engine import compare_run
from backend.app.diagnosis.rules import generate_diagnoses
from backend.app.models import PipelineRun, RunStatus
from backend.app.services.impact import downstream_impact
from backend.app.services.pipeline_runner import PipelineFailed, run_daily_order_analytics

VALID = Path("sample_data/valid/orders.csv")


def _run_valid_then_failure(db, failure_path: str):
    baseline = run_daily_order_analytics(db, input_path=VALID)
    assert baseline.status == RunStatus.SUCCESS
    with pytest.raises(PipelineFailed):
        run_daily_order_analytics(db, input_path=Path(failure_path))
    failed = (
        db.query(PipelineRun)
        .filter_by(status=RunStatus.FAILED)
        .order_by(desc(PipelineRun.started_at))
        .first()
    )
    assert failed is not None
    return baseline, failed


@pytest.mark.parametrize(
    ("failure_path", "expected_text"),
    [
        ("sample_data/failures/price_type_change.csv", "price changed"),
        ("sample_data/failures/missing_customer_id.csv", "customer_id"),
        ("sample_data/failures/duplicate_order_ids.csv", "Duplicate rate"),
        ("sample_data/failures/email_null_increase.csv", "email null rate"),
        ("sample_data/failures/row_count_decrease.csv", "row count decreased"),
        ("sample_data/failures/empty_orders.csv", "no records"),
    ],
)
def test_required_failure_scenarios_generate_diagnosis(db, failure_path, expected_text):
    _baseline, failed = _run_valid_then_failure(db, failure_path)
    diagnoses = generate_diagnoses(db, failed.run_id)
    joined = " ".join(
        diagnosis["title"] + " " + diagnosis["description"] for diagnosis in diagnoses
    )
    assert expected_text.lower() in joined.lower()


def test_schema_null_duplicate_and_row_count_comparison(db):
    _baseline, failed = _run_valid_then_failure(db, "sample_data/failures/email_null_increase.csv")
    comparison = compare_run(db, failed.run_id)
    metrics = {change["metric"]: change for change in comparison["profile_changes"]}
    assert metrics["email_null_percentage"]["current_value"] >= 25
    assert metrics["row_count"]["previous_value"] == 20

    _baseline, duplicate_failed = _run_valid_then_failure(
        db, "sample_data/failures/duplicate_order_ids.csv"
    )
    duplicate_comparison = compare_run(db, duplicate_failed.run_id)
    duplicate_metrics = {
        change["metric"]: change for change in duplicate_comparison["profile_changes"]
    }
    assert duplicate_metrics["order_id_duplicate_rate"]["current_value"] >= 20


def test_diagnosis_ranking_prefers_high_confidence_critical(db):
    _baseline, failed = _run_valid_then_failure(db, "sample_data/failures/price_type_change.csv")
    diagnoses = generate_diagnoses(db, failed.run_id)
    assert diagnoses[0]["confidence"] == "HIGH"
    assert diagnoses[0]["severity"] == "CRITICAL"


def test_downstream_impact_traversal(db):
    _baseline, failed = _run_valid_then_failure(db, "sample_data/failures/price_type_change.csv")
    impact = downstream_impact(db, failed.run_id)
    affected = {node["name"] for node in impact["affected_nodes"]}
    assert "daily_revenue" in affected
    assert "sales_dashboard" in affected
    assert "revenue_forecast" in affected
