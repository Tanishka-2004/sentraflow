"""
Unit and Integration Tests for SentraFlow API and RBAC Matrix.

Tests JWT authentication, token refresh, role-based endpoint permissions,
response column masking, and audit logging middleware.
"""

from __future__ import annotations

import os
from typing import Dict
from fastapi.testclient import TestClient
import pytest

from api.database import Base, SessionLocal, engine
from api.main import app, seed_database
from api.models import AuditLog


@pytest.fixture(scope="module", autouse=True)
def initialize_database() -> None:
    """Ensure database schema is created and demo records seeded."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _get_token(client: TestClient, email: str, password: str) -> str:
    res = client.post("/auth/token", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def tokens(client: TestClient) -> dict[str, str]:
    return {
        "admin": _get_token(client, "admin@sentraflow.io", "Admin@123"),
        "analyst": _get_token(client, "analyst@sentraflow.io", "Analyst@123"),
        "engineer": _get_token(client, "engineer@sentraflow.io", "Engineer@123"),
        "auditor": _get_token(client, "auditor@sentraflow.io", "Auditor@123"),
        "viewer": _get_token(client, "viewer@sentraflow.io", "Viewer@123"),
    }


def test_auth_login_and_refresh(client: TestClient) -> None:
    # 1. Invalid login
    res = client.post("/auth/token", json={"email": "admin@sentraflow.io", "password": "WrongPassword"})
    assert res.status_code == 401

    # 2. Valid login
    login_res = client.post("/auth/token", json={"email": "admin@sentraflow.io", "password": "Admin@123"})
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # 3. Refresh token exchange
    refresh_res = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert refresh_res.status_code == 200
    refreshed_data = refresh_res.json()
    assert "access_token" in refreshed_data

    # 4. Get profile /auth/me
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "admin@sentraflow.io"
    assert me_res.json()["role"] == "admin"


def test_rbac_transaction_access_matrix(client: TestClient, tokens: dict[str, str]) -> None:
    # Admin can view transactions
    res_admin = client.get("/transactions", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert res_admin.status_code == 200
    assert len(res_admin.json()["items"]) > 0

    # Fraud analyst can view transactions
    res_analyst = client.get("/transactions", headers={"Authorization": f"Bearer {tokens['analyst']}"})
    assert res_analyst.status_code == 200

    # Viewer CANNOT view row-level transactions (403 Forbidden)
    res_viewer = client.get("/transactions", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert res_viewer.status_code == 403


def test_response_column_masking(client: TestClient, tokens: dict[str, str]) -> None:
    res = client.get("/transactions", headers={"Authorization": f"Bearer {tokens['analyst']}"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0

    first = items[0]
    # PAN must begin with XXXXX
    assert first["pan"].startswith("XXXXX")
    # Email must begin with h_
    assert first["email"].startswith("h_")
    # Phone must begin with XXXXXX
    assert first["phone"].startswith("XXXXXX")


def test_rbac_fraud_queue_and_override(client: TestClient, tokens: dict[str, str]) -> None:
    # Analyst can access fraud queue
    res_q = client.get("/fraud/queue", headers={"Authorization": f"Bearer {tokens['analyst']}"})
    assert res_q.status_code == 200
    queue = res_q.json()
    assert isinstance(queue, list)

    # Data engineer CANNOT access fraud queue (403)
    res_eng = client.get("/fraud/queue", headers={"Authorization": f"Bearer {tokens['engineer']}"})
    assert res_eng.status_code == 403

    # Explanation endpoint
    res_exp = client.get("/fraud/TXN_SEED_0006/explanation", headers={"Authorization": f"Bearer {tokens['analyst']}"})
    assert res_exp.status_code == 200
    exp = res_exp.json()
    assert "steps" in exp
    assert len(exp["steps"]) > 0

    # Manual decision override by Analyst
    override_payload = {"decision": "CONFIRMED_FRAUD", "notes": "Observed impossible travel velocity."}
    res_ov = client.post(
        "/fraud/TXN_SEED_0006/override",
        json=override_payload,
        headers={"Authorization": f"Bearer {tokens['analyst']}"},
    )
    assert res_ov.status_code == 200
    assert res_ov.json()["status"] == "OVERRIDE_RECORDED"


def test_rbac_pipeline_trigger(client: TestClient, tokens: dict[str, str]) -> None:
    # Data engineer CAN trigger pipelines
    res_eng = client.post(
        "/pipelines/trigger/sentraflow_batch_pipeline",
        headers={"Authorization": f"Bearer {tokens['engineer']}"},
    )
    assert res_eng.status_code == 200
    assert res_eng.json()["status"] == "QUEUED"

    # Fraud analyst CANNOT trigger pipelines (403)
    res_analyst = client.post(
        "/pipelines/trigger/sentraflow_batch_pipeline",
        headers={"Authorization": f"Bearer {tokens['analyst']}"},
    )
    assert res_analyst.status_code == 403


def test_lineage_and_governance_endpoints(client: TestClient, tokens: dict[str, str]) -> None:
    # Auditor can access governance gate runs
    res_gate = client.get("/governance/gate-runs", headers={"Authorization": f"Bearer {tokens['auditor']}"})
    assert res_gate.status_code == 200
    assert len(res_gate.json()) > 0

    # Auditor can access lineage graph
    res_lin = client.get("/lineage/graph", headers={"Authorization": f"Bearer {tokens['auditor']}"})
    assert res_lin.status_code == 200
    graph = res_lin.json()
    assert "nodes" in graph
    assert "edges" in graph


def test_audit_logging_middleware_records_calls(client: TestClient, tokens: dict[str, str]) -> None:
    # Trigger a transaction call with auditor token
    client.get("/transactions", headers={"Authorization": f"Bearer {tokens['auditor']}"})

    # Check database audit_log table
    db = SessionLocal()
    logs = db.query(AuditLog).filter(AuditLog.user_id == "auditor@sentraflow.io").all()
    db.close()

    assert len(logs) > 0
    endpoints = [l.endpoint for l in logs]
    assert any("/transactions" in ep for ep in endpoints)
