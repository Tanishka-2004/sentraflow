from sqlalchemy.orm import Session
from fastapi import Request
from backend.models.models import AuditLog
from typing import Optional, Any, Dict

def log_audit_event(
    db: Session,
    actor_id: Optional[int],
    action: str,
    resource: str,
    target_id: Optional[int] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    reason: str = "N/A",
    ip_address: str = "127.0.0.1",
    user_agent: str = "Unknown"
) -> AuditLog:
    """
    Creates an immutable audit log entry in the database.
    """
    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource=resource,
        target_id=target_id,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
