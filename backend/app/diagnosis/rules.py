from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.comparison.engine import compare_run
from backend.app.models import Confidence, DiagnosisResult, PipelineRun, Severity

SEVERITY_SCORE = {Severity.CRITICAL: 3, Severity.WARNING: 2, Severity.INFORMATIONAL: 1}
CONFIDENCE_SCORE = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}


def _diagnosis(
    *,
    category: str,
    severity: Severity,
    confidence: Confidence,
    title: str,
    description: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "description": description,
        "supporting_evidence": evidence,
    }


def generate_diagnoses(db: Session, run_id: str, persist: bool = True) -> list[dict[str, Any]]:
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    comparison = compare_run(db, run_id)
    error_message = (run.error_message or "").lower()
    diagnoses: list[dict[str, Any]] = []

    for change in comparison["schema_changes"]:
        if change["change_type"] == "REMOVED":
            diagnoses.append(
                _diagnosis(
                    category="SCHEMA_CHANGE",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    title=f"{change['column']} required column is missing",
                    description=f"The required {change['column']} column is missing from the failed input.",
                    evidence=change,
                )
            )
        if change["change_type"] == "TYPE_CHANGED":
            numeric_to_string = (
                change["previous_type"] in {"integer", "decimal"}
                and change["current_type"] == "string"
            )
            conversion_error = any(
                phrase in error_message
                for phrase in ["numeric", "parse string", "convert", "conversion"]
            )
            high = change["column"].lower() in error_message or (
                numeric_to_string and conversion_error
            )
            diagnoses.append(
                _diagnosis(
                    category="TYPE_CHANGE",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH if high else Confidence.MEDIUM,
                    title=(
                        f"{change['column']} changed from "
                        f"{change['previous_type'].upper()} to {change['current_type'].upper()}"
                    ),
                    description=(
                        f"The {change['column']} column changed type between the baseline and failed run. "
                        "This likely caused a downstream transformation to reject the input."
                    ),
                    evidence=change,
                )
            )

    for change in comparison["profile_changes"]:
        metric = change["metric"]
        previous = change["previous_value"]
        current = change["current_value"]
        if metric == "row_count" and previous and current == 0:
            diagnoses.append(
                _diagnosis(
                    category="EMPTY_INPUT",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    title="Input dataset contains no records",
                    description="The failed input has a valid header but zero data rows.",
                    evidence=change,
                )
            )
        elif metric == "row_count" and previous and current < previous * 0.5:
            diagnoses.append(
                _diagnosis(
                    category="VOLUME_CHANGE",
                    severity=Severity.WARNING,
                    confidence=Confidence.HIGH,
                    title="Input row count decreased significantly",
                    description="The input row count decreased by at least 50% compared with the latest successful run.",
                    evidence=change,
                )
            )
        elif (
            metric == "email_null_percentage" and current >= 25 and current > max(previous * 2, 10)
        ):
            diagnoses.append(
                _diagnosis(
                    category="NULL_RATE_INCREASE",
                    severity=Severity.WARNING,
                    confidence=Confidence.HIGH,
                    title="email null rate increased from the historical baseline",
                    description="The failed input has a much higher null rate in email than the successful baseline.",
                    evidence=change,
                )
            )
        elif metric == "order_id_duplicate_rate" and current >= max(previous + 20, previous * 2):
            diagnoses.append(
                _diagnosis(
                    category="DUPLICATE_IDENTIFIERS",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    title="Duplicate rate for order_id increased significantly",
                    description="Many order identifiers are repeated in the failed input.",
                    evidence=change,
                )
            )

    if not diagnoses and run.error_message:
        diagnoses.append(
            _diagnosis(
                category="PIPELINE_ERROR",
                severity=Severity.WARNING,
                confidence=Confidence.LOW,
                title="Pipeline failed without a known data-profile rule match",
                description="The failure message should be inspected alongside the run logs.",
                evidence={"error_type": run.error_type, "error_message": run.error_message},
            )
        )

    diagnoses.sort(
        key=lambda item: (
            CONFIDENCE_SCORE[item["confidence"]],
            SEVERITY_SCORE[item["severity"]],
        ),
        reverse=True,
    )
    if persist:
        db.query(DiagnosisResult).filter(DiagnosisResult.run_id == run_id).delete()
        for item in diagnoses:
            db.add(DiagnosisResult(run_id=run_id, **item))
        db.commit()
    return [
        {
            **item,
            "severity": (
                item["severity"].value
                if isinstance(item["severity"], Severity)
                else item["severity"]
            ),
            "confidence": (
                item["confidence"].value
                if isinstance(item["confidence"], Confidence)
                else item["confidence"]
            ),
        }
        for item in diagnoses
    ]
