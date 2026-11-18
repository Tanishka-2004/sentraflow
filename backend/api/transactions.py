from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_any, User
from backend.models.models import FactTransaction
from backend.schemas.schemas import TransactionResponse, TransactionsListResponse
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

@router.get("", response_model=TransactionsListResponse)
def get_transactions(
    account_id: Optional[str] = Query(None),
    is_flagged: Optional[bool] = Query(None),
    transaction_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Query the Gold fact_transactions table with filters and pagination.
    """
    query = db.query(FactTransaction)
    
    if account_id:
        query = query.filter(FactTransaction.account_id == account_id)
    if is_flagged is not None:
        query = query.filter(FactTransaction.is_flagged == is_flagged)
    if transaction_type:
        query = query.filter(FactTransaction.transaction_type == transaction_type)
        
    total = query.count()
    transactions = query.order_by(FactTransaction.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "limit": limit
    }
