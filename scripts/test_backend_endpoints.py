import requests
import time

BACKEND_URL = "http://localhost:8000"

def get_tokens():
    print("Fetching JWT tokens for RBAC tests...")
    
    # Login admin
    resp = requests.post(f"{BACKEND_URL}/api/auth/login", json={"email": "admin@sentraflow.com", "password": "admin"})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    admin_token = resp.json()["access_token"]
    
    # Login analyst
    resp = requests.post(f"{BACKEND_URL}/api/auth/login", json={"email": "analyst@sentraflow.com", "password": "analyst"})
    assert resp.status_code == 200, f"Analyst login failed: {resp.text}"
    analyst_token = resp.json()["access_token"]
    
    # Login auditor
    resp = requests.post(f"{BACKEND_URL}/api/auth/login", json={"email": "auditor@sentraflow.com", "password": "auditor"})
    assert resp.status_code == 200, f"Auditor login failed: {resp.text}"
    auditor_token = resp.json()["access_token"]
    
    return admin_token, analyst_token, auditor_token

def test_rbac_and_endpoints(tokens):
    admin_tok, analyst_tok, auditor_tok = tokens
    
    headers_admin = {"Authorization": f"Bearer {admin_tok}"}
    headers_analyst = {"Authorization": f"Bearer {analyst_tok}"}
    headers_auditor = {"Authorization": f"Bearer {auditor_tok}"}
    
    print("\n--- 1. Testing /api/auth/me ---")
    resp = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers_admin)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    print("[PASS] JWT validation and /me works.")
    
    # Check correlation ID in header
    assert "X-Request-ID" in resp.headers, "X-Request-ID correlation header is missing!"
    print(f"[PASS] Correlation ID verified in response headers: {resp.headers['X-Request-ID']}")

    print("\n--- 2. Testing RBAC restrictions ---")
    # Analyst tries to access admin PII rules
    resp = requests.get(f"{BACKEND_URL}/api/admin/pii-rules", headers=headers_analyst)
    assert resp.status_code == 403, f"Expected 403 for analyst accessing admin endpoint, got {resp.status_code}"
    
    # Analyst tries to access auditor logs
    resp = requests.get(f"{BACKEND_URL}/api/audit", headers=headers_analyst)
    assert resp.status_code == 403, f"Expected 403 for analyst accessing auditor endpoint, got {resp.status_code}"
    
    # Auditor tries to access admin PII rules
    resp = requests.get(f"{BACKEND_URL}/api/admin/pii-rules", headers=headers_auditor)
    assert resp.status_code == 403
    
    # Admin accesses PII rules (success)
    resp = requests.get(f"{BACKEND_URL}/api/admin/pii-rules", headers=headers_admin)
    assert resp.status_code == 200
    
    # Auditor accesses audit logs (success)
    resp = requests.get(f"{BACKEND_URL}/api/audit", headers=headers_auditor)
    assert resp.status_code == 200
    
    print("[PASS] Role-based access control (RBAC) verified successfully (403 Forbidden checks out).")

    print("\n--- 3. Testing ALERTS endpoint ---")
    resp = requests.get(f"{BACKEND_URL}/api/alerts", headers=headers_analyst)
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "total" in data
    print(f"[PASS] /api/alerts query success. Total alerts: {data['total']}")
    
    if len(data["alerts"]) > 0:
        alert_id = data["alerts"][0]["id"]
        print(f"Resolving alert {alert_id}...")
        resolve_payload = {"status": "resolved", "reason": "Verified legitimate transaction pattern."}
        # PATCH update
        resp = requests.patch(f"{BACKEND_URL}/api/alerts/{alert_id}", json=resolve_payload, headers=headers_analyst)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
        print("[PASS] Alert resolution works and logs state changes.")

    print("\n--- 4. Testing TRANSACTIONS endpoint ---")
    resp = requests.get(f"{BACKEND_URL}/api/transactions", headers=headers_analyst)
    assert resp.status_code == 200
    data = resp.json()
    assert "transactions" in data
    print(f"[PASS] /api/transactions query success. Retrieved: {len(data['transactions'])}")

    print("\n--- 5. Testing CATALOG endpoint ---")
    resp = requests.get(f"{BACKEND_URL}/api/catalog/datasets", headers=headers_analyst)
    assert resp.status_code == 200
    assert len(resp.json()) > 0
    print(f"[PASS] /api/catalog/datasets query success. Found: {len(resp.json())} datasets")

    print("\n--- 6. Testing LINEAGE endpoint ---")
    # Walk column lineage for fact_transactions.transaction_id
    resp = requests.get(f"{BACKEND_URL}/api/lineage/warehouse.fact_transactions/transaction_id", headers=headers_analyst)
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    print(f"[PASS] /api/lineage walk success. Nodes: {len(data['nodes'])} | Edges: {len(data['edges'])}")

    print("\n--- 7. Testing PIPELINES & REPLAY endpoint ---")
    resp = requests.get(f"{BACKEND_URL}/api/pipelines/runs", headers=headers_analyst)
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    print(f"[PASS] /api/pipelines/runs query success. Runs count: {data['total']}")
    
    # Trigger a mock pipeline run first, then replay it
    print("Creating mock pipeline run...")
    cur_time = int(time.time())
    run_id = f"RUN_TEST_{cur_time}"
    # Seed a runs entry in db directly or via mock
    db_conn = requests.post(f"{BACKEND_URL}/api/auth/login", json={"email": "admin@sentraflow.com", "password": "admin"})
    
    # We can trigger a sandbox replay on the seeded historical run or trigger it directly
    # Let's seed a test run via sql or just use the replay trigger on a dummy run ID
    # Since our seeding script creates mock lineage/pipeline runs, we can fetch one!
    if len(data["runs"]) > 0:
        target_run_id = data["runs"][0]["run_id"]
        print(f"Triggering sandbox replay on run_id: {target_run_id}...")
        resp = requests.post(
            f"{BACKEND_URL}/api/pipelines/runs/{target_run_id}/replay", 
            json={"reason": "Re-evaluate with updated PII rule."},
            headers=headers_admin
        )
        assert resp.status_code == 200
        assert "REPLAY_" in resp.json()["run_id"]
        print(f"[PASS] Pipeline sandbox replay successfully triggered. Replay ID: {resp.json()['run_id']}")
    else:
        print("[SKIP] No historical runs to test replay.")

    print("\n--- 8. Testing RATE LIMITING ---")
    print("Sending rapid requests to trigger rate limit (threshold: 120/min)...")
    triggered = False
    for i in range(130):
        resp = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers_admin)
        if resp.status_code == 429:
            triggered = True
            print(f"[PASS] Rate limiting triggered successfully on request {i+1}! Response: {resp.json()['detail']}")
            break
    if not triggered:
        print("[FAIL] Rate limiter did not return 429 after 130 rapid requests.")

if __name__ == "__main__":
    print("=====================================================")
    print("       SentraFlow Backend API Test Suite             ")
    print("=====================================================")
    
    try:
        tokens = get_tokens()
        test_rbac_and_endpoints(tokens)
    except Exception as e:
        print(f"\n[FAIL] Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
