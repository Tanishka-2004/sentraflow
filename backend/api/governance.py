from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_admin, require_any, User
from backend.models.models import ModelRegistry, ModelDriftMetric
from backend.schemas.schemas import ModelRegistryResponse, ModelDriftMetricResponse
from backend.services.audit_service import log_audit_event
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/governance", tags=["governance"])

@router.get("/models", response_model=List[ModelRegistryResponse])
def get_registered_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves all registered models, their metadata, and performance metrics.
    """
    return db.query(ModelRegistry).order_by(ModelRegistry.trained_at.desc()).all()

@router.get("/models/{version}/drift", response_model=List[ModelDriftMetricResponse])
def get_model_drift_metrics(
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves historical drift metrics (PSI) for a specific model version.
    """
    metrics = db.query(ModelDriftMetric).filter(ModelDriftMetric.model_version == version).order_by(ModelDriftMetric.checked_at.desc()).all()
    return metrics

@router.post("/models/{version}/approve", response_model=ModelRegistryResponse)
def approve_model(
    version: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Approves a model version for production deployment. Writes audit log.
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.model_version == version).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model version not found"
        )
        
    before_state = {
        "status": model.status,
        "approved_by": model.approved_by,
        "approved_at": model.approved_at.isoformat() if model.approved_at else None
    }
    
    # De-activate other production models
    db.query(ModelRegistry).filter(ModelRegistry.status == 'production').update({"status": "archived", "deployment_status": "inactive"})
    
    model.status = "production"
    model.deployment_status = "active"
    model.approved_by = current_user.email
    model.approved_at = datetime.utcnow()
    
    db.commit()
    db.refresh(model)
    
    after_state = {
        "status": model.status,
        "approved_by": model.approved_by,
        "approved_at": model.approved_at.isoformat()
    }
    
    # Audit log
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="APPROVE_MODEL",
        resource="model_registry",
        target_id=model.id,
        before_state=before_state,
        after_state=after_state,
        reason=f"Approved model {version} and set to production.",
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    return model
