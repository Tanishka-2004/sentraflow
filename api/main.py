"""
SentraFlow Unified Lakehouse & Governance API.

Exposes RBAC-protected endpoints for financial transactions, fraud queues,
SHAP explainability, column-level lineage, and automated PII audit records.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from api.config import settings
from api.database import Base, SessionLocal, engine
from api.models import AuditLog, GateAuditRun, TransactionModel, User
from api.routers.auth import router as auth_router
from api.routers.dq import router as dq_router
from api.routers.fraud import router as fraud_router
from api.routers.governance import router as governance_router
from api.routers.lineage import router as lineage_router
from api.routers.pipelines import router as pipelines_router
from api.routers.transactions import router as transactions_router
from api.security import decode_token, hash_password

logger = logging.getLogger("sentraflow.api")


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware tracking every sensitive read and state-changing write.
    Captures user identity, RBAC role, endpoint, query parameters, and client IP.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Skip health check & docs from audit log
        path = request.url.path
        if path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return response

        # Extract user identity if present in Authorization header
        auth_header = request.headers.get("Authorization")
        user_id = "anonymous"
        role = "none"
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                claims = decode_token(token)
                user_id = claims.get("sub", "unknown")
                role = claims.get("role", "none")
            except Exception:
                pass

        client_ip = request.client.host if request.client else "127.0.0.1"

        # Log sensitive data access or mutating calls
        try:
            db: Session = SessionLocal()
            audit_entry = AuditLog(
                user_id=user_id,
                role=role,
                endpoint=path,
                method=request.method,
                status_code=response.status_code,
                query_params=str(request.query_params),
                client_ip=client_ip,
                details=f"HTTP {request.method} {path} completed with status {response.status_code}",
                timestamp=datetime.now(timezone.utc),
            )
            db.add(audit_entry)
            db.commit()
            db.close()
        except Exception as e:
            logger.warning("Audit logging failed: %s", e)

        return response


def seed_database(db: Session) -> None:
    """Populate database with demo users, initial transactions, and gate audit history."""
    # 1. Seed demo users
    demo_users = [
        {"email": "admin@sentraflow.io", "name": "Aditi Sharma", "role": "admin", "pwd": "Admin@123"},
        {"email": "analyst@sentraflow.io", "name": "Rohan Verma", "role": "fraud_analyst", "pwd": "Analyst@123"},
        {"email": "engineer@sentraflow.io", "name": "Kavita Rao", "role": "data_engineer", "pwd": "Engineer@123"},
        {"email": "auditor@sentraflow.io", "name": "Sunil Mehta", "role": "compliance_auditor", "pwd": "Auditor@123"},
        {"email": "viewer@sentraflow.io", "name": "Pooja Patel", "role": "viewer", "pwd": "Viewer@123"},
    ]

    for u in demo_users:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            user = User(
                email=u["email"],
                full_name=u["name"],
                role=u["role"],
                hashed_password=hash_password(u["pwd"]),
                is_active=True,
            )
            db.add(user)

    # 2. Seed initial transactions
    if db.query(TransactionModel).count() == 0:
        channels = ["UPI", "CARD", "IMPS", "NEFT"]
        for i in range(1, 31):
            is_fraud_case = (i % 6 == 0)
            score = 0.88 if is_fraud_case else (0.02 + (i * 0.01))
            amt = 75000.0 if is_fraud_case else float(200 + (i * 150))
            txn = TransactionModel(
                txn_id=f"TXN_SEED_{i:04d}",
                account_id=f"ACC_{1000 + (i % 5)}",
                customer_id=f"CUST_{500 + (i % 5)}",
                pan_masked=f"XXXXX{i:04d}A",
                email_masked=f"h_{i:04d}@bank.com",
                phone_masked=f"XXXXXX{1000 + i}",
                amount=amt,
                currency="INR",
                channel=channels[i % len(channels)],
                status="FLAGGED" if is_fraud_case else "SUCCESS",
                fraud_score=round(score, 4),
                is_fraud=1 if is_fraud_case else 0,
                txn_ts=datetime.now(timezone.utc),
            )
            db.add(txn)

    # 3. Seed gate audit runs
    if db.query(GateAuditRun).count() == 0:
        db.add(
            GateAuditRun(
                batch_id="BATCH_20260801_001",
                table_name="customers",
                passed=True,
                records_scanned=10000,
                residual_pii_count=0,
                signature="sig_sha256_certified_clean_001",
                executed_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            GateAuditRun(
                batch_id="BATCH_20260801_002",
                table_name="transactions",
                passed=True,
                records_scanned=50000,
                residual_pii_count=0,
                signature="sig_sha256_certified_clean_002",
                executed_at=datetime.now(timezone.utc),
            )
        )

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Governed Financial Data Lakehouse API with RBAC, Fraud Explainability, and Lineage Tracing",
    lifespan=lifespan,
)

# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditLoggingMiddleware)

# Include Routers
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(fraud_router)
app.include_router(lineage_router)
app.include_router(governance_router)
app.include_router(dq_router)
app.include_router(pipelines_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "HEALTHY", "service": settings.app_name, "version": "1.0.0"}


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    """Root info endpoint."""
    return {
        "message": "Welcome to SentraFlow Governed Financial Lakehouse API",
        "docs_url": "/docs",
        "version": "1.0.0",
    }

