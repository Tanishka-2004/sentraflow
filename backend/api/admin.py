from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_admin, User
from backend.models.models import PiiRule, User as UserModel
from backend.schemas.schemas import PiiRuleResponse, PiiRuleCreate, UserResponse, UserCreate
from backend.core.security import get_password_hash
from backend.services.audit_service import log_audit_event
from typing import List, Dict, Any

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/pii-rules", response_model=List[PiiRuleResponse])
def get_pii_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Retrieves all PII masking rules.
    """
    return db.query(PiiRule).all()

@router.post("/pii-rules", response_model=PiiRuleResponse, status_code=status.HTTP_201_CREATED)
def create_pii_rule(
    payload: PiiRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Creates a new PII masking rule. Performs dry-run validation. Writes audit log.
    """
    # Dry run validation (checks if pattern is a valid sql/regex pattern)
    if not payload.column_pattern:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pattern cannot be empty"
        )
        
    # Check for duplicate
    duplicate = db.query(PiiRule).filter(PiiRule.column_pattern == payload.column_pattern).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PII rule with this pattern already exists"
        )
        
    rule = PiiRule(
        column_pattern=payload.column_pattern,
        rule_type=payload.rule_type,
        masking_strategy=payload.masking_strategy,
        created_by=current_user.id,
        active=True
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    # Audit log
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="CREATE_PII_RULE",
        resource="pii_rules",
        target_id=rule.id,
        before_state=None,
        after_state={"pattern": rule.column_pattern, "strategy": rule.masking_strategy, "type": rule.rule_type},
        reason="GDPR masking update requested by Admin.",
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    return rule

@router.patch("/pii-rules/{rule_id}/toggle", response_model=PiiRuleResponse)
def toggle_pii_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Enables/disables a PII masking rule. Writes audit log.
    """
    rule = db.query(PiiRule).filter(PiiRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
        
    before_state = {"active": rule.active}
    rule.active = not rule.active
    db.commit()
    db.refresh(rule)
    after_state = {"active": rule.active}
    
    # Audit log
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="TOGGLE_PII_RULE",
        resource="pii_rules",
        target_id=rule.id,
        before_state=before_state,
        after_state=after_state,
        reason=f"PII rule toggled. Active status now {rule.active}.",
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    return rule

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Lists all platform users.
    """
    return db.query(UserModel).all()

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Registers a new platform user. Writes audit log.
    """
    duplicate = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
        
    new_user = UserModel(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Audit log
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="CREATE_USER",
        resource="users",
        target_id=new_user.id,
        before_state=None,
        after_state={"email": new_user.email, "role": new_user.role},
        reason=f"Created new user account for email {new_user.email}.",
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
    
    return new_user
