"""SQLAlchemy models for SentraFlow API."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from api.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    role = Column(String(50), nullable=True)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    query_params = Column(Text, nullable=True)
    client_ip = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class TransactionModel(Base):
    __tablename__ = "transactions"

    txn_id = Column(String(64), primary_key=True, index=True)
    account_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    pan_masked = Column(String(20), nullable=True)
    email_masked = Column(String(100), nullable=True)
    phone_masked = Column(String(30), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    channel = Column(String(20), nullable=False)
    status = Column(String(20), default="SUCCESS")
    fraud_score = Column(Float, default=0.0, index=True)
    is_fraud = Column(Integer, default=0)
    txn_ts = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class FraudOverride(Base):
    __tablename__ = "fraud_overrides"

    id = Column(Integer, primary_key=True, index=True)
    txn_id = Column(String(64), nullable=False, index=True)
    analyst_id = Column(String(255), nullable=False)
    decision = Column(String(50), nullable=False)  # CONFIRMED_FRAUD or FALSE_POSITIVE
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GateAuditRun(Base):
    __tablename__ = "gate_audit_runs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), nullable=False, index=True)
    table_name = Column(String(64), nullable=False)
    passed = Column(Boolean, nullable=False)
    records_scanned = Column(Integer, nullable=False)
    residual_pii_count = Column(Integer, nullable=False)
    signature = Column(String(128), nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

