"""
Data models for Column-Level Lineage in SentraFlow.
"""

from pydantic import BaseModel


class LineageNode(BaseModel):
    node_id: str  # e.g. "silver.customers.pan"
    table_name: str
    column_name: str
    layer: str  # LANDING, BRONZE, GATE, SILVER, GOLD
    is_masked: bool = False
    data_type: str = "VARCHAR"


class LineageEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    transformation_type: str  # DIRECT, DERIVED, AGGREGATED, MASKED
    job_name: str
    run_id: str
    passes_gate: bool = True


class LineageRun(BaseModel):
    run_id: str
    job_name: str
    status: str  # SUCCESS, FAILED
    started_at: str
    completed_at: str
    nodes_count: int
    edges_count: int
