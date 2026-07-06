from __future__ import annotations


def test_api_end_to_end_failure_investigation_and_replay(client):
    success = client.post(
        "/api/pipelines/daily_order_analytics/run",
        data={"test_file": "valid/orders.csv"},
    )
    assert success.status_code == 200
    assert success.json()["status"] == "SUCCESS"

    failure = client.post(
        "/api/pipelines/daily_order_analytics/run",
        data={"test_file": "failures/price_type_change.csv"},
    )
    assert failure.status_code == 200
    failed_run = failure.json()
    assert failed_run["status"] == "FAILED"

    diagnoses = client.get(f"/api/runs/{failed_run['run_id']}/diagnoses")
    assert diagnoses.status_code == 200
    assert any("price" in item["title"].lower() for item in diagnoses.json())

    impact = client.get(f"/api/runs/{failed_run['run_id']}/impact")
    assert impact.status_code == 200
    affected = {node["name"] for node in impact.json()["affected_nodes"]}
    assert {"daily_revenue", "sales_dashboard", "revenue_forecast"} <= affected

    replay = client.post(f"/api/runs/{failed_run['run_id']}/replay")
    assert replay.status_code == 200
    assert replay.json()["reproduced"] is True


def test_api_lists_runs_and_exposes_logs_steps_and_comparison(client):
    run = client.post(
        "/api/pipelines/daily_order_analytics/run",
        data={"test_file": "valid/orders.csv"},
    ).json()
    assert client.get("/api/pipelines").status_code == 200
    assert client.get("/api/runs").json()[0]["run_id"] == run["run_id"]
    assert client.get(f"/api/runs/{run['run_id']}/steps").json()
    assert client.get(f"/api/runs/{run['run_id']}/logs").json()
    assert client.get(f"/api/runs/{run['run_id']}/comparison").status_code == 200
