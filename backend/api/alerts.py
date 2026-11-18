from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import get_current_user, require_analyst, require_any
from backend.models.models import Alert, User
from backend.schemas.schemas import AlertResponse, AlertUpdate, AlertsListResponse
from backend.services.audit_service import log_audit_event
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("", response_model=AlertsListResponse)
def get_alerts(
    request: Request,
    status: Optional[str] = Query(None, pattern="^(open|resolved|false_positive)$"),
    risk_level: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Paginated alerts query with status and risk level filtering.
    """
    query = db.query(Alert)
    
    if status:
        query = query.filter(Alert.status == status)
    if risk_level:
        query = query.filter(Alert.risk_level == risk_level)
        
    total = query.count()
    alerts = query.order_by(Alert.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "alerts": alerts,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.patch("/{alert_id}", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    payload: AlertUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst)
):
    """
    Resolve or mark an alert as false positive. Writes audit log entries.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
        
    if alert.status in ["resolved", "false_positive"]:
        # Idempotent response if already resolved
        return alert
        
    # Keep track of state for audit trail
    before_state = {
        "status": alert.status,
        "resolved_by": alert.resolved_by,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "notes": alert.resolution_notes
    }
    
    alert.status = payload.status
    alert.resolved_by = current_user.id
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = payload.reason
    
    db.commit()
    db.refresh(alert)
    
    after_state = {
        "status": alert.status,
        "resolved_by": alert.resolved_by,
        "resolved_at": alert.resolved_at.isoformat(),
        "notes": alert.resolution_notes
    }
    
    # Write audit log entry
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="RESOLVE_ALERT",
        resource="alerts",
        target_id=alert.id,
        before_state=before_state,
        after_state=after_state,
        reason=payload.reason,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    return alert
