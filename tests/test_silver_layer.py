"""
Unit tests for SentraFlow Silver Layer (Phase 4).
"""

import pandas as pd
import pytest
from deltalake import DeltaTable

from data_generator.generator import FinancialDataGenerator
from spark_jobs.governance.gate import PIIGate
from spark_jobs.silver.cleaners import (
    clean_phone_e164,
    clean_state_iso,
    clean_timestamp_utc,
)
from spark_jobs.silver.deduplicator import deduplicate_records
from spark_jobs.silver.processor import SilverProcessor
from spark_jobs.silver.quality_checks import (
    DataQualityThresholdExceededError,
    SilverQualityValidator,
)
from spark_jobs.silver.scd2 import CustomerSCD2Manager


def test_cleaners_standardisation():
    """
    Asserts standardisation of phone numbers to E.164, states to ISO codes, and UTC timestamps.
    """
    assert clean_phone_e164("9876543210") == "+919876543210"
    assert clean_phone_e164("+919876543210") == "+919876543210"

    assert clean_state_iso("Maharashtra") == "IN-MH"
    assert clean_state_iso("Delhi") == "IN-DL"
    assert clean_state_iso("Karnataka") == "IN-KA"
    assert clean_state_iso("UnknownState") == "UnknownState"

    utc_str = clean_timestamp_utc("2026-11-07 10:00:00")
    assert utc_str is not None
    assert "+00:00" in utc_str or "Z" in utc_str


def test_deduplicator():
    """
    Asserts deduplication on business keys keeping the latest record by ingest timestamp.
    """
    records = [
        {"customer_id": "c1", "val": "old", "_ingest_ts": "2026-11-01T00:00:00"},
        {"customer_id": "c1", "val": "new", "_ingest_ts": "2026-11-02T00:00:00"},
        {"customer_id": "c2", "val": "single", "_ingest_ts": "2026-11-01T00:00:00"},
    ]
    df = pd.DataFrame(records)
    deduped = deduplicate_records(
        df, business_keys=["customer_id"], order_by_col="_ingest_ts"
    )

    assert len(deduped) == 2
    c1_row = deduped[deduped["customer_id"] == "c1"].iloc[0]
    assert c1_row["val"] == "new"


def test_silver_quality_checks_and_rejects(tmp_path):
    """
    Asserts quality validation routes bad records to silver_rejects
    and enforces maximum reject thresholds.
    """
    rejects_path = tmp_path / "silver_rejects"
    validator = SilverQualityValidator(
        rejects_base_path=str(rejects_path),
        max_reject_threshold=0.60,
    )

    txns = [
        {"txn_id": "t1", "amount": 100.0, "account_id": "a1"},
        {"txn_id": "t2", "amount": -50.0, "account_id": "a1"},  # Invalid: negative
        {"txn_id": None, "amount": 200.0, "account_id": "a2"},  # Invalid: null key
        {"txn_id": "t3", "amount": 350.0, "account_id": "a2"},
    ]
    df = pd.DataFrame(txns)

    valid_df, reject_df = validator.validate_transactions(df, batch_id="b_test")

    assert len(valid_df) == 2
    assert len(reject_df) == 2
    assert (rejects_path / "transactions").exists()

    df_rej = DeltaTable(str(rejects_path / "transactions")).to_pandas()
    assert len(df_rej) == 2
    assert "rejection_reason" in df_rej.columns


def test_silver_quality_threshold_breach(tmp_path):
    """
    Asserts that exceeding the reject threshold raises DataQualityThresholdExceededError.
    """
    validator = SilverQualityValidator(
        rejects_base_path=str(tmp_path / "silver_rejects"),
        max_reject_threshold=0.10,  # 10% max reject allowed
    )

    # 50% rejection rate
    txns = [
        {"txn_id": "t1", "amount": 100.0, "account_id": "a1"},
        {"txn_id": "t2", "amount": -50.0, "account_id": "a1"},
    ]
    with pytest.raises(DataQualityThresholdExceededError):
        validator.validate_transactions(pd.DataFrame(txns), batch_id="b_fail")


def test_scd2_lifecycle(tmp_path):
    """
    Asserts complete SCD Type 2 lifecycle:
    - Initial insert has is_current=True, valid_to=None.
    - Updated record expires previous row (is_current=False) and creates new current row.
    """
    table_path = tmp_path / "silver_customers_scd2"
    scd2_mgr = CustomerSCD2Manager(silver_customer_table_path=str(table_path))

    gen = FinancialDataGenerator(seed=42)
    customers = gen.generate_customers(count=10)
    initial_df = pd.DataFrame([c.model_dump() for c in customers])

    # Initial load
    res1 = scd2_mgr.process_scd2_merge(initial_df)
    assert len(res1) == 10
    assert all(res1["is_current"] == True)
    assert all(res1["valid_to"].isna())

    # Generate mutations on 3 customers
    updates = gen.generate_customer_updates(update_ratio=0.30)
    updates_df = pd.DataFrame([u.model_dump() for u in updates])
    updated_ids = set(updates_df["customer_id"])

    # Merge updates
    res2 = scd2_mgr.process_scd2_merge(updates_df)

    # Table must now contain 10 original/active + len(updates) expired records = 10 + len(updates)
    assert len(res2) == 10 + len(updated_ids)

    # For each updated customer, verify one current and one expired record exists
    for cid in updated_ids:
        records = res2[res2["customer_id"] == cid]
        assert len(records) == 2, f"Customer {cid} should have exactly 2 versions"
        curr_ver = records[records["is_current"] == True]
        hist_ver = records[records["is_current"] == False]
        assert len(curr_ver) == 1
        assert len(hist_ver) == 1
        assert hist_ver.iloc[0]["valid_to"] is not None


def test_silver_processor_end_to_end(tmp_path):
    """
    Asserts end-to-end SilverProcessor handling customers and partitioned transactions.
    """
    silver_base = tmp_path / "silver"
    rejects_base = tmp_path / "silver_rejects"
    audit_base = tmp_path / "pii_gate_audit"

    gate = PIIGate(audit_table_path=str(audit_base))
    processor = SilverProcessor(
        silver_base_path=str(silver_base),
        rejects_base_path=str(rejects_base),
        gate=gate,
    )

    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=15)
    accounts = gen.generate_accounts()[:15]
    merchants = gen.generate_merchants(count=5)
    txns = gen.generate_transactions(count=30)

    # Process all layers
    c_res = processor.process_customers(
        pd.DataFrame([c.model_dump() for c in customers]), "b1"
    )
    a_res = processor.process_accounts(
        pd.DataFrame([a.model_dump() for a in accounts]), "b1"
    )
    m_res = processor.process_merchants(
        pd.DataFrame([m.model_dump() for m in merchants]), "b1"
    )
    t_res = processor.process_transactions(
        pd.DataFrame([t.model_dump() for t in txns]), "b1"
    )

    assert c_res["valid_count"] == 15
    assert a_res["valid_count"] == 15
    assert m_res["valid_count"] == 5
    assert t_res["valid_count"] == 30

    # Verify transactions partitioned by txn_date
    tx_table = DeltaTable(str(silver_base / "transactions"))
    df_tx = tx_table.to_pandas()
    assert "txn_date" in df_tx.columns
    assert len(df_tx) == 30
