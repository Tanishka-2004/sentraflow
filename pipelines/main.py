"""
SentraFlow Pipelines Service.
Exposes pipeline triggers, DAG status, and streaming ingestion health.
Supports internal Vercel Service Bindings for BACKEND_URL and ML_SERVICE_URL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure root is in sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI(
    title="SentraFlow Pipelines Service",
    description="Orchestrates batch ETL, stream consumer triggers, and pipeline health.",
    version="1.0.0",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001").rstrip("/")


class PipelineTriggerResponse(BaseModel):
    pipeline_id: str
    status: str
    backend_url: str
    ml_service_url: str


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "pipelines",
        "backend_url": BACKEND_URL,
        "ml_service_url": ML_SERVICE_URL,
    }


@app.post("/trigger/{pipeline_id}", response_model=PipelineTriggerResponse)
def trigger_pipeline(pipeline_id: str):
    valid_pipelines = ["sentraflow_batch_pipeline", "bronze_to_silver", "silver_to_gold"]
    if pipeline_id not in valid_pipelines:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not registered",
        )
    return PipelineTriggerResponse(
        pipeline_id=pipeline_id,
        status="TRIGGERED",
        backend_url=BACKEND_URL,
        ml_service_url=ML_SERVICE_URL,
    )
