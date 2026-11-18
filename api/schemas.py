"""Pydantic v2 schemas for SentraFlow API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    email: str | None = None
    role: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    txn_id: str
    account_id: str
    customer_id: str
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    amount: float
    currency: str
    channel: str
    status: str
    fraud_score: float
    txn_ts: datetime


class PaginatedTransactions(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TransactionResponse]


class FraudQueueItem(BaseModel):
    txn_id: str
    account_id: str
    customer_id: str
    amount: float
    channel: str
    fraud_score: float
    status: str
    txn_ts: datetime
    flagged_reasons: list[str] = Field(default_factory=list)


class FraudOverrideRequest(BaseModel):
    decision: str  # CONFIRMED_FRAUD or FALSE_POSITIVE
    notes: str | None = None


class FraudOverrideResponse(BaseModel):
    status: str
    txn_id: str
    decision: str
    analyst_id: str
    timestamp: str


class ShapStep(BaseModel):
    feature_name: str
    feature_value: float
    contribution: float
    cumulative_score: float
    impact: str


class FraudExplanationResponse(BaseModel):
    txn_id: str
    account_id: str | None = None
    customer_id: str | None = None
    amount: float | None = None
    channel: str | None = None
    pan_masked: str | None = None
    phone_masked: str | None = None
    txn_ts: datetime | None = None
    base_value: float
    final_score: float
    steps: list[ShapStep]


class LineageGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class LineageTraceResponse(BaseModel):
    target_node: str
    direction: str
    traversal_path: list[dict[str, Any]]


class GateAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    table_name: str
    passed: bool
    records_scanned: int
    residual_pii_count: int
    signature: str
    executed_at: datetime


class DQScorecardResponse(BaseModel):
    suite_name: str
    overall_status: str
    pass_rate_pct: float
    total_checks: int
    passed_checks: int
    failed_checks: int
    checks: list[dict[str, Any]]
    evaluated_at: str


class PipelineTriggerResponse(BaseModel):
    dag_id: str
    run_id: str
    status: str
    triggered_at: str

