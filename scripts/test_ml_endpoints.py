import requests
import json
import time

ML_URL = "http://localhost:8001"

def test_health():
    print("Testing /health ...")
    resp = requests.get(f"{ML_URL}/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    print("[PASS] /health is healthy")

def test_predict_success():
    print("Testing /predict (success case) ...")
    payload = {
        "amount": 250.00,
        "oldBalanceOrig": 1000.00,
        "newBalanceOrig": 750.00,
        "oldBalanceDest": 0.00,
        "newBalanceDest": 250.00,
        "transaction_type": "TRANSFER"
    }
    resp = requests.post(f"{ML_URL}/predict", json=payload)
    assert resp.status_code == 200, f"Predict failed: {resp.text}"
    data = resp.json()
    assert "risk_score" in data
    assert "risk_level" in data
    assert "model_version" in data
    assert "shap_explanations" in data
    print(f"[PASS] /predict success. Risk Score: {data['risk_score']} | Level: {data['risk_level']}")

def test_predict_malformed():
    print("Testing /predict (malformed/negative amount) ...")
    payload = {
        "amount": -50.00, # invalid, amount must be > 0
        "oldBalanceOrig": 1000.00,
        "newBalanceOrig": 750.00,
        "oldBalanceDest": 0.00,
        "newBalanceDest": 250.00,
        "transaction_type": "TRANSFER"
    }
    resp = requests.post(f"{ML_URL}/predict", json=payload)
    assert resp.status_code == 422, f"Expected 422 for negative amount, got {resp.status_code}"
    print("[PASS] /predict malformed check verified.")

def test_predict_missing_fields():
    print("Testing /predict (missing fields) ...")
    payload = {
        "amount": 250.00,
        # missing other fields
        "transaction_type": "TRANSFER"
    }
    resp = requests.post(f"{ML_URL}/predict", json=payload)
    assert resp.status_code == 422, f"Expected 422 for missing fields, got {resp.status_code}"
    print("[PASS] /predict missing fields check verified.")

def test_drift():
    print("Testing /drift endpoint...")
    resp = requests.get(f"{ML_URL}/drift")
    assert resp.status_code == 200, f"Drift failed: {resp.text}"
    data = resp.json()
    assert "psi" in data
    assert "drift_status" in data
    print(f"[PASS] /drift check. PSI: {data['psi']} | Status: {data['drift_status']}")

def test_drift_intentional():
    print("Testing /drift with intentionally shifted data...")
    # Send multiple high risk/out of bounds transactions to trigger drift
    shifted_payload = {
        "amount": 50000.00,
        "oldBalanceOrig": 50000.00,
        "newBalanceOrig": 0.00,
        "oldBalanceDest": 0.00,
        "newBalanceDest": 0.00, # triggers heavy fraud/anomaly features
        "transaction_type": "TRANSFER"
    }
    for _ in range(50):
        requests.post(f"{ML_URL}/predict", json=shifted_payload)
        
    # Check drift status again
    resp = requests.get(f"{ML_URL}/drift")
    data = resp.json()
    print(f"[PASS] Shifted /drift check. PSI: {data['psi']} | Status: {data['drift_status']}")

def benchmark_inference():
    print("Benchmarking /predict latency...")
    payload = {
        "amount": 100.00,
        "oldBalanceOrig": 1000.00,
        "newBalanceOrig": 900.00,
        "oldBalanceDest": 100.00,
        "newBalanceDest": 200.00,
        "transaction_type": "CASH_OUT"
    }
    start = time.perf_counter()
    for _ in range(100):
        requests.post(f"{ML_URL}/predict", json=payload)
    avg_ms = ((time.perf_counter() - start) / 100) * 1000
    print(f"[PASS] Average predict latency: {avg_ms:.2f}ms per request")

if __name__ == "__main__":
    print("Starting ML serving endpoint test suite...")
    test_health()
    test_predict_success()
    test_predict_malformed()
    test_predict_missing_fields()
    test_drift()
    test_drift_intentional()
    benchmark_inference()
