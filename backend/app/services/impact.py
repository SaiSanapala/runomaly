from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import PipelineDependency, PipelineNode, PipelineRun, StepStatus

STEP_TO_NODE = {
    "load_input": "orders_csv",
    "profile_input": "orders_csv",
    "validate_schema": "orders_csv",
    "load_raw_orders": "raw_orders",
    "transform_orders": "clean_orders",
    "calculate_revenue": "daily_revenue",
}


def failed_node_for_run(run: PipelineRun) -> str | None:
    failed_step = next((step for step in run.steps if step.status == StepStatus.FAILED), None)
    if failed_step:
        return STEP_TO_NODE.get(failed_step.step_name, "orders_csv")
    return None


def downstream_impact(db: Session, run_id: str) -> dict[str, Any]:
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    failed_node = failed_node_for_run(run)
    nodes = {node.node_id: node for node in db.query(PipelineNode).all()}
    graph: dict[str, list[str]] = defaultdict(list)
    for dep in db.query(PipelineDependency).all():
        graph[dep.source_node_id].append(dep.target_node_id)

    affected: list[str] = []
    if failed_node:
        queue: deque[str] = deque(graph[failed_node])
        seen: set[str] = set()
        while queue:
            node_id = queue.popleft()
            if node_id in seen:
                continue
            seen.add(node_id)
            affected.append(node_id)
            queue.extend(graph[node_id])

    return {
        "run_id": run_id,
        "failed_node": failed_node,
        "affected_nodes": [
            {
                "node_id": node_id,
                "name": nodes[node_id].name,
                "node_type": nodes[node_id].node_type.value,
            }
            for node_id in affected
            if node_id in nodes
        ],
        "graph": {
            "nodes": [
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "node_type": node.node_type.value,
                    "state": (
                        "FAILED"
                        if node.node_id == failed_node
                        else "AFFECTED" if node.node_id in affected else "OK"
                    ),
                }
                for node in nodes.values()
            ],
            "edges": [
                {"source": dep.source_node_id, "target": dep.target_node_id}
                for dep in db.query(PipelineDependency).all()
            ],
        },
    }
