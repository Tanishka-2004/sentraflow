"""
Unit tests for SentraFlow Governance Layer and PII Masking Gate (Phase 3).
"""

import pandas as pd
import pytest

from data_generator.generator import FinancialDataGenerator
from spark_jobs.governance.gate import PIIGate, PIIGateViolationError
from spark_jobs.governance.masking import PIIMaskingEngine
from spark_jobs.governance.pii_scanner import PIIScanner


@pytest.fixture
def test_gate_env(tmp_path):
    audit_path = tmp_path / "pii_gate_audit"
    scanner = PIIScanner()
    masking_engine = PIIMaskingEngine()
    gate = PIIGate(
        audit_table_path=str(audit_path),
        scanner=scanner,
        masking_engine=masking_engine,
    )
    return {
        "audit_path": audit_path,
        "scanner": scanner,
        "masking_engine": masking_engine,
        "gate": gate,
    }


def test_pii_scanner_metadata_and_regex(test_gate_env):
    """
    Tests that the scanner correctly detects direct and quasi PII
    using both YAML metadata and regex pattern matching.
    """
    scanner = test_gate_env["scanner"]
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=30)
    df = pd.DataFrame([c.model_dump() for c in customers])

    report = scanner.scan_dataframe(df)

    assert report.has_pii is True
    # Critical PII columns must be detected
    assert "pan" in report.pii_columns_found
    assert "email" in report.pii_columns_found
    assert "phone" in report.pii_columns_found
    assert "aadhaar_id" in report.pii_columns_found

    pan_res = next(r for r in report.column_results if r.column_name == "pan")
    assert pan_res.detected_type == "PAN"
    assert pan_res.confidence >= 0.85
    assert pan_res.action_required == "MASK"


def test_masking_engine_techniques():
    """
    Asserts correctness of individual masking techniques:
    HMAC tokenization, partial masking, generalization, email hashing.
    """
    engine = PIIMaskingEngine()

    # 1. PAN partial mask
    assert engine.mask_pan("ABCDE1234F") == "XXXXX1234X"

    # 2. Phone partial mask
    assert engine.mask_phone("+919876543210", keep_last=4) == "XXXXXXXX3210"

    # 3. Account partial mask
    assert engine.mask_account("123456789012", keep_last=4) == "XXXXXXXX9012"

    # 4. Email format-preserving hash
    masked_email = engine.mask_email("analyst@sentraflow.io")
    assert masked_email.endswith("@sentraflow.io")
    assert masked_email.startswith("h_")
    assert "analyst" not in masked_email

    # 5. Generalization: DOB, pincode, IP
    assert engine.generalize_pincode("400001") == "400XXX"
    assert engine.generalize_ip("192.168.1.100") == "192.168.X.X"

    # 6. HMAC Tokenization (deterministic & joinable)
    tok1 = engine.hmac_token("John Doe")
    tok2 = engine.hmac_token("John Doe")
    tok3 = engine.hmac_token("Jane Doe")
    assert tok1 == tok2, "HMAC tokenization must be deterministic for identical input"
    assert tok1 != tok3, "Different inputs must produce different tokens"
    assert tok1.startswith("TOK_")


def test_pii_gate_normal_pass(test_gate_env):
    """
    Asserts that the automated PII gate safely masks input records,
    re-scans to verify zero residual PII, commits a signed audit entry,
    and returns a clean DataFrame.
    """
    gate = test_gate_env["gate"]
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=20)
    bronze_df = pd.DataFrame([c.model_dump() for c in customers])

    # Run through gate
    silver_df = gate.process(
        bronze_df=bronze_df,
        entity_name="customers",
        batch_id="batch_gov_001",
    )

    assert len(silver_df) == 20
    assert "_masking_key_version" in silver_df.columns

    # Verify fields are masked
    assert all(str(p).startswith("XXXXX") for p in silver_df["pan"])
    assert all(str(a) == "[REDACTED_AADHAAR]" for a in silver_df["aadhaar_id"])

    # Verify signed audit record
    audit_history = gate.get_audit_history()
    assert not audit_history.empty
    latest = audit_history.iloc[-1]
    assert latest["batch_id"] == "batch_gov_001"
    assert latest["status"] == "PASSED"
    assert latest["residual_pii_count"] == 0
    assert len(latest["digital_signature"]) == 64


def test_pii_gate_deliberate_leak_blocks_pipeline(test_gate_env):
    """
    CRITICAL GOVERNANCE TEST:
    Injects an unmasked PII column ('shadow_unmasked_pan') that bypasses
    standard policy mappings. The gate must catch the residual PII in its
    post-scan step, raise PIIGateViolationError, log 'BLOCKED', and abort.
    """
    gate = test_gate_env["gate"]
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=15)
    bronze_df = pd.DataFrame([c.model_dump() for c in customers])

    # Deliberate breach injection: unmasked PANs under an unmapped column name
    bronze_df["shadow_unmasked_pan"] = [
        gen.generate_pan(is_valid=True) for _ in range(15)
    ]

    # The gate MUST raise PIIGateViolationError and fail the pipeline
    with pytest.raises(PIIGateViolationError) as exc_info:
        gate.process(
            bronze_df=bronze_df,
            entity_name="customers",
            batch_id="batch_leak_attempt_999",
        )

    assert "Gate BLOCKED batch" in str(exc_info.value)
    assert "shadow_unmasked_pan" in str(exc_info.value)

    # Verify audit log reflects BLOCKED status
    audit_history = gate.get_audit_history()
    blocked_entry = audit_history[
        audit_history["batch_id"] == "batch_leak_attempt_999"
    ].iloc[0]
    assert blocked_entry["status"] == "BLOCKED"
    assert blocked_entry["residual_pii_count"] > 0
    assert "shadow_unmasked_pan" in blocked_entry["residual_pii_columns"]
