"""
SentraFlow Autonomous Platform Verification & Live Integration Suite.

Performs comprehensive end-to-end verification across:
1. Security Persona Authentication & RBAC Matrices
2. Medallion Storage & Serving REST APIs
3. SHAP TreeExplainer & Fraud Review Overrides
4. Automated PII Gate & Zero Residual Leaks
5. Column-Level Lineage Graph Structure
6. Pipeline Triggers & Audit Logging
7. Web Console Route Availability
"""

import json
import sys
import urllib.error
import urllib.request

API_BASE = "http://127.0.0.1:8000"
WEB_BASE = "http://localhost:3001"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


def request(url: str, method: str = "GET", data: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed


def check(description: str, condition: bool, details: str = ""):
    if condition:
        print(f"  {PASS} {description} {details}")
    else:
        print(f"  {FAIL} {description} {details}")
        sys.exit(1)


def main():
    print("=" * 80)
    print("🚀 SENTRAFLOW: COMPREHENSIVE LIVE AUDIT & INTEGRATION VERIFICATION")
    print("=" * 80)

    # 1. AUTHENTICATION & PERSONA VERIFICATION
    print("\n1. Verifying 5 Security Persona JWT Authentication...")
    roles = {
        "admin": ("admin@sentraflow.io", "Admin@123"),
        "analyst": ("analyst@sentraflow.io", "Analyst@123"),
        "engineer": ("engineer@sentraflow.io", "Engineer@123"),
        "auditor": ("auditor@sentraflow.io", "Auditor@123"),
        "viewer": ("viewer@sentraflow.io", "Viewer@123"),
    }
    tokens = {}
    for role_name, (email, pwd) in roles.items():
        status, res = request(f"{API_BASE}/auth/token", method="POST", data={"email": email, "password": pwd})
        check(f"Persona '{role_name}' Login", status == 200 and "access_token" in res)
        tokens[role_name] = res["access_token"]

    # 2. RBAC ACCESS CONTROL BOUNDARIES
    print("\n2. Verifying RBAC Security Boundaries & Permission Gates...")
    # Viewer must be rejected from viewing row-level financial transactions
    status, _ = request(f"{API_BASE}/transactions", token=tokens["viewer"])
    check("Viewer Persona Row-Level Access Blocked", status == 403, "(HTTP 403 Forbidden)")

    # Analyst must be rejected from triggering lakehouse pipelines
    status, _ = request(f"{API_BASE}/pipelines/trigger/sentraflow_batch_pipeline", method="POST", token=tokens["analyst"])
    check("Analyst Persona Pipeline Trigger Blocked", status == 403, "(HTTP 403 Forbidden)")

    # Data Engineer must be rejected from viewing analyst fraud queue
    status, _ = request(f"{API_BASE}/fraud/queue", token=tokens["engineer"])
    check("Data Engineer Persona Fraud Queue Blocked", status == 403, "(HTTP 403 Forbidden)")

    # Admin persona can access everything
    status, res = request(f"{API_BASE}/transactions?page=1&page_size=5", token=tokens["admin"])
    check("Admin Persona Unrestricted Transactions Access", status == 200 and len(res["items"]) > 0)

    # 3. TRANSACTIONS & COLUMN MASKING
    print("\n3. Verifying Ingested Lakehouse Transactions & Column-Level Masking...")
    status, res = request(f"{API_BASE}/transactions?page=1&page_size=10", token=tokens["analyst"])
    check("Analyst Retrieved Transactions", status == 200 and res["total"] > 0, f"(Total: {res['total']})")
    first_txn = res["items"][0]
    check("PAN Column Masked (XXXXX...)", first_txn["pan"].startswith("XXXXX"), f"({first_txn['pan']})")
    check("Email Column Format-Preserving Salted Hash", first_txn["email"].startswith("h_"), f"({first_txn['email']})")
    check("Phone Column Partial Mask", first_txn["phone"].startswith("XXXXXX"), f"({first_txn['phone']})")

    # 4. FRAUD ENGINE & SHAP WATERFALL ATTR
    print("\n4. Verifying XGBoost Real-Time Fraud Engine & SHAP Explainability...")
    status, queue = request(f"{API_BASE}/fraud/queue", token=tokens["analyst"])
    check("Fraud Review Queue Loaded", status == 200 and len(queue) > 0, f"({len(queue)} pending reviews)")
    sample_id = queue[0]["txn_id"]

    status, exp = request(f"{API_BASE}/fraud/{sample_id}/explanation", token=tokens["analyst"])
    check(f"SHAP Waterfall Attribution for {sample_id}", status == 200 and "steps" in exp and len(exp["steps"]) > 0)
    check("SHAP Explanation Includes Masked Metadata", "pan_masked" in exp and "amount" in exp)

    # Submit Analyst Case Disposition Override
    override_payload = {
        "decision": "CONFIRMED_FRAUD",
        "notes": "Verified impossible travel velocity. Account flagged.",
    }
    status, ov_res = request(f"{API_BASE}/fraud/{sample_id}/override", method="POST", data=override_payload, token=tokens["analyst"])
    check(f"Analyst Decision Override on {sample_id}", status == 200 and ov_res["status"] == "OVERRIDE_RECORDED")

    # 5. LINEAGE & PII GOVERNANCE GATE
    print("\n5. Verifying Column Lineage & Zero-Residual Governance Gate...")
    status, lin = request(f"{API_BASE}/lineage/graph", token=tokens["auditor"])
    check("Lineage Graph Retrieved", status == 200 and len(lin["nodes"]) > 0 and len(lin["edges"]) > 0, f"({len(lin['nodes'])} nodes, {len(lin['edges'])} edges)")

    status, gate_runs = request(f"{API_BASE}/governance/gate-runs", token=tokens["auditor"])
    check("Gate Certification Runs Retrieved", status == 200 and len(gate_runs) > 0, f"({len(gate_runs)} gate certifications)")
    check("Zero-Residual PII Guarantee Verified", all(r["residual_pii_count"] == 0 for r in gate_runs))

    status, dq = request(f"{API_BASE}/dq/scorecard", token=tokens["auditor"])
    check("Data Quality Scorecard Verified", status == 200 and dq["overall_status"] == "HEALTHY", f"({dq['pass_rate_pct']}% pass rate)")

    # 6. AIRFLOW PIPELINE ORCHESTRATION
    print("\n6. Verifying Lakehouse Pipeline Trigger...")
    status, trig = request(f"{API_BASE}/pipelines/trigger/sentraflow_batch_pipeline", method="POST", token=tokens["engineer"])
    check("Engineer Triggered Batch Pipeline", status == 200 and trig["status"] == "QUEUED", f"(Run ID: {trig['run_id']})")

    # 7. WEB CONSOLE ROUTE INTEGRITY
    print("\n7. Verifying Next.js 14 Web Console Page Availability (HTTP 200)...")
    web_pages = [
        ("/", "Lakehouse Intelligence Overview"),
        ("/login", "Sign in to SentraFlow"),
        ("/fraud", "Real-Time Fraud Queue"),
        (f"/fraud/{sample_id}", "Transaction Review & SHAP"),
        ("/lineage", "Column Lineage Explorer"),
        ("/governance", "Data Governance & PII Gate"),
        ("/dq", "Data Quality Scorecard"),
        ("/pipelines", "Lakehouse Pipeline Orchestration"),
        ("/admin", "Enterprise User Administration"),
    ]
    for path, desc in web_pages:
        try:
            with urllib.request.urlopen(f"{WEB_BASE}{path}") as resp:
                check(f"Page '{path}' ({desc})", resp.status == 200)
        except Exception as e:
            check(f"Page '{path}' ({desc})", False, str(e))

    print("\n" + "=" * 80)
    print("🎯 AUDIT COMPLETE: 100% OF CHECKS PASSED. SYSTEM FULLY OPERATIONAL.")
    print("=" * 80)


if __name__ == "__main__":
    main()
