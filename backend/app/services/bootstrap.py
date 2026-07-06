from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import NodeType, Pipeline, PipelineDependency, PipelineNode

PIPELINE_ID = "daily_order_analytics"

GRAPH_NODES = [
    ("orders_csv", "orders_csv", NodeType.SOURCE),
    ("raw_orders", "raw_orders", NodeType.TABLE),
    ("clean_orders", "clean_orders", NodeType.TABLE),
    ("daily_revenue", "daily_revenue", NodeType.TABLE),
    ("sales_dashboard", "sales_dashboard", NodeType.DASHBOARD),
    ("revenue_forecast", "revenue_forecast", NodeType.MODEL),
]

GRAPH_EDGES = [
    ("orders_csv", "raw_orders"),
    ("raw_orders", "clean_orders"),
    ("clean_orders", "daily_revenue"),
    ("daily_revenue", "sales_dashboard"),
    ("daily_revenue", "revenue_forecast"),
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed_defaults(db: Session) -> None:
    pipeline = db.get(Pipeline, PIPELINE_ID)
    if pipeline is None:
        db.add(
            Pipeline(
                pipeline_id=PIPELINE_ID,
                name=PIPELINE_ID,
                description="Sample daily order analytics pipeline with profiling and diagnosis.",
            )
        )
    for node_id, name, node_type in GRAPH_NODES:
        if db.get(PipelineNode, node_id) is None:
            db.add(PipelineNode(node_id=node_id, name=name, node_type=node_type))
    db.flush()
    existing = {
        (dep.source_node_id, dep.target_node_id) for dep in db.query(PipelineDependency).all()
    }
    for source, target in GRAPH_EDGES:
        if (source, target) not in existing:
            db.add(PipelineDependency(source_node_id=source, target_node_id=target))
    db.commit()
