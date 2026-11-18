from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_auditor, User
from backend.models.models import AuditLog
from backend.schemas.schemas import AuditLogResponse, AuditLogListResponse
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("", response_model=AuditLogListResponse)
def get_audit_logs(
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor)
):
    """
    Retrieves system audit logs (only viewable by Auditor and Admin roles).
    """
    query = db.query(AuditLog)
    
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.resource == resource)
        
    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "limit": limit
    }
