"""Column-level lineage API router."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import require_roles
from api.models import User
from api.schemas import LineageGraphResponse, LineageTraceResponse
from lineage.store import LineageStore

router = APIRouter(prefix="/lineage", tags=["Lineage Tracing"])

# Shared in-memory lineage store instance
_lineage_store = LineageStore()


def get_shared_lineage_store() -> LineageStore:
    return _lineage_store


@router.get("/graph", response_model=LineageGraphResponse)
def get_lakehouse_lineage_graph(
    current_user: User = Depends(require_roles(["admin", "data_engineer", "compliance_auditor"])),
) -> LineageGraphResponse:
    """
    Retrieve full lakehouse lineage graph with nodes (columns/tables) and edges (transformations).
    """
    store = get_shared_lineage_store()
    graph_data = store.to_graph_json()

    # If empty, populate standard default lakehouse nodes
    if not graph_data["nodes"]:
        demo_nodes = [
            {"id": "bronze.customers.pan", "label": "customers.pan", "layer": "BRONZE", "table": "bronze.customers", "pii_type": "PAN"},
            {"id": "bronze.customers.email", "label": "customers.email", "layer": "BRONZE", "table": "bronze.customers", "pii_type": "EMAIL"},
            {"id": "gate.pii_masking_gate", "label": "PII Governance Gate", "layer": "GATE", "table": "governance.pii_gate"},
            {"id": "silver.customers.pan_masked", "label": "customers.pan_masked", "layer": "SILVER", "table": "silver.customers", "pii_type": "NONE"},
            {"id": "silver.customers.email_masked", "label": "customers.email_masked", "layer": "SILVER", "table": "silver.customers", "pii_type": "NONE"},
            {"id": "gold.mart_customer_360.pan_masked", "label": "customer_360.pan_masked", "layer": "GOLD", "table": "gold.mart_customer_360", "pii_type": "NONE"},
        ]
        demo_edges = [
            {"source": "bronze.customers.pan", "target": "gate.pii_masking_gate", "type": "TRANSFORM"},
            {"source": "gate.pii_masking_gate", "target": "silver.customers.pan_masked", "type": "MASK_HMAC"},
            {"source": "bronze.customers.email", "target": "gate.pii_masking_gate", "type": "TRANSFORM"},
            {"source": "gate.pii_masking_gate", "target": "silver.customers.email_masked", "type": "MASK_HASH"},
            {"source": "silver.customers.pan_masked", "target": "gold.mart_customer_360.pan_masked", "type": "DIRECT"},
        ]
        return LineageGraphResponse(nodes=demo_nodes, edges=demo_edges)

    return LineageGraphResponse(nodes=graph_data["nodes"], edges=graph_data["edges"])


@router.get("/trace", response_model=LineageTraceResponse)
def trace_lineage(
    column: str = Query(..., description="Column name to trace"),
    table: str = Query(..., description="Table name containing the column"),
    direction: str = Query("UPSTREAM", pattern="^(UPSTREAM|DOWNSTREAM)$"),
    current_user: User = Depends(require_roles(["admin", "data_engineer", "compliance_auditor"])),
) -> LineageTraceResponse:
    """
    Perform upstream or downstream column-level dependency audit.
    """
    target_node = f"{table}.{column}"
    store = get_shared_lineage_store()

    if direction.upper() == "UPSTREAM":
        trace_res = store.trace_upstream(target_node)
        path_nodes = trace_res.get("upstream_nodes", [])
    else:
        trace_res = store.trace_downstream(target_node)
        path_nodes = trace_res.get("downstream_nodes", [])

    return LineageTraceResponse(
        target_node=target_node,
        direction=direction.upper(),
        traversal_path=path_nodes,
    )
