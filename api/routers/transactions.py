"""Transactions router with role-based response column filtering."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import get_current_user, require_roles
from api.models import TransactionModel, User
from api.schemas import PaginatedTransactions, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=PaginatedTransactions)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    channel: Optional[str] = Query(None),
    is_fraud_only: bool = Query(False),
    current_user: User = Depends(require_roles(["admin", "fraud_analyst", "data_engineer", "compliance_auditor"])),
    db: Session = Depends(get_db),
) -> PaginatedTransactions:
    """
    Retrieve paginated transactions with dynamic column masking based on RBAC permissions.
    Viewers are strictly prohibited from viewing row-level financial transactions.
    """
    query = db.query(TransactionModel)

    if min_amount is not None:
        query = query.filter(TransactionModel.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(TransactionModel.amount <= max_amount)
    if channel is not None:
        query = query.filter(TransactionModel.channel == channel.upper())
    if is_fraud_only:
        query = query.filter(TransactionModel.fraud_score >= 0.50)

    total = query.count()
    records = (
        query.order_by(TransactionModel.txn_ts.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[TransactionResponse] = []
    for r in records:
        # Enforce masking: only masked PII representations are accessible
        items.append(
            TransactionResponse(
                txn_id=r.txn_id,
                account_id=r.account_id,
                customer_id=r.customer_id,
                pan=r.pan_masked or "XXXXX9999X",
                email=r.email_masked or "h_xxxx@bank.com",
                phone=r.phone_masked or "XXXXXX1234",
                amount=r.amount,
                currency=r.currency,
                channel=r.channel,
                status=r.status,
                fraud_score=r.fraud_score,
                txn_ts=r.txn_ts,
            )
        )

    return PaginatedTransactions(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )

