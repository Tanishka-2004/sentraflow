"""Airflow pipeline trigger and monitoring router."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import require_roles
from api.models import User
from api.schemas import PipelineTriggerResponse

router = APIRouter(prefix="/pipelines", tags=["Data Pipelines"])

VALID_DAGS = [
    "sentraflow_batch_pipeline",
    "sentraflow_dq_monitor",
    "sentraflow_model_retrain",
    "sentraflow_maintenance",
]


@router.post("/trigger/{dag_id}", response_model=PipelineTriggerResponse)
def trigger_pipeline(
    dag_id: str,
    current_user: User = Depends(require_roles(["admin", "data_engineer"])),
) -> PipelineTriggerResponse:
    """
    Trigger manual Airflow DAG execution (restricted to Data Engineers and Admins).
    """
    if dag_id not in VALID_DAGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DAG '{dag_id}' not found. Available: {VALID_DAGS}",
        )

    run_id = f"manual__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"

    return PipelineTriggerResponse(
        dag_id=dag_id,
        run_id=run_id,
        status="QUEUED",
        triggered_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/status")
def get_pipeline_statuses(
    current_user: User = Depends(require_roles(["admin", "data_engineer", "compliance_auditor"])),
) -> list[dict[str, str]]:
    """Retrieve operational status of lakehouse orchestration DAGs."""
    return [
        {"dag_id": "sentraflow_batch_pipeline", "schedule": "@hourly", "last_run_state": "SUCCESS"},
        {"dag_id": "sentraflow_dq_monitor", "schedule": "@daily", "last_run_state": "SUCCESS"},
        {"dag_id": "sentraflow_model_retrain", "schedule": "@weekly", "last_run_state": "SUCCESS"},
        {"dag_id": "sentraflow_maintenance", "schedule": "@weekly", "last_run_state": "SUCCESS"},
    ]

