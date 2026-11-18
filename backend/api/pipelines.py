from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_admin, require_any, User
from backend.models.models import PipelineRun, DqResult
from backend.schemas.schemas import PipelineRunResponse, PipelineRunsListResponse
from backend.services.audit_service import log_audit_event
from typing import List, Optional, Dict, Any
from datetime import datetime
import time

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

@router.get("/runs", response_model=PipelineRunsListResponse)
def get_pipeline_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves all pipeline runs with pagination.
    """
    query = db.query(PipelineRun)
    total = query.count()
    runs = query.order_by(PipelineRun.started_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "runs": runs,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
def get_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves detailed statuses and metrics for a specific pipeline execution.
    """
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found"
        )
    return run

def run_simulated_replay(run_id: str, db_url: str):
    """
    Simulates a sandboxed pipeline replay in the background, updating DB checkpoints.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        run = session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            return
            
        time.sleep(2)
        run.bronze_status = "success"
        session.commit()
        
        time.sleep(2)
        run.silver_status = "success"
        session.commit()
        
        time.sleep(2)
        # Sandbox PII auto-detector classifies and approves
        run.pii_status = "success"
        session.commit()
        
        time.sleep(2)
        # DQ passes in sandbox (mock fixes applied)
        run.dq_status = "success"
        
        # Add a mock passing DQ result for the replay run
        dq_res = DqResult(
            run_id=run_id,
            test_name="replay_assert_schema_match",
            model_name="fact_transactions",
            status="pass",
            details={"assertion": "columns match sandbox schema", "columns_checked": 9}
        )
        session.add(dq_res)
        session.commit()
        
        time.sleep(2)
        run.gold_status = "success"
        run.status = "success"
        run.completed_at = datetime.utcnow()
        session.commit()
        
    except Exception as e:
        print(f"Error in simulated replay background execution: {e}")
    finally:
        session.close()

@router.post("/runs/{run_id}/replay", response_model=PipelineRunResponse)
def trigger_pipeline_replay(
    run_id: str,
    payload: Dict[str, Any], # e.g. {"reason": "Fix schema and rerun in sandbox"}
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Triggers a pipeline run replay in a sandboxed mode against a snapshot of that day's data.
    """
    original_run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not original_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original pipeline run not found"
        )
        
    reason = payload.get("reason", "Manual admin trigger for replay investigation.")
    replay_run_id = f"REPLAY_{original_run.run_id}_{int(time.time())}"
    
    # Create the sandbox run version
    sandbox_run = PipelineRun(
        run_id=replay_run_id,
        pipeline_version=original_run.pipeline_version,
        code_version=original_run.code_version + "-sandbox-patch",
        schema_version=original_run.schema_version,
        model_version=original_run.model_version,
        input_snapshot=original_run.input_snapshot,
        started_at=datetime.utcnow(),
        status="running",
        bronze_status="pending",
        silver_status="pending",
        pii_status="pending",
        dq_status="pending",
        gold_status="pending"
    )
    db.add(sandbox_run)
    db.commit()
    
    # Audit log this admin action
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="TRIGGER_REPLAY",
        resource="pipeline_runs",
        target_id=None, # no single int PK for this run_id
        before_state={"original_run_id": original_run.run_id, "original_status": original_run.status},
        after_state={"replay_run_id": replay_run_id, "sandbox_status": "running"},
        reason=reason,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    # Start the sandbox execution background task
    db_url = str(db.get_bind().url)
    background_tasks.add_task(run_simulated_replay, replay_run_id, db_url)
    
    return sandbox_run
