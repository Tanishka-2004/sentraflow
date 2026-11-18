"""
Unit tests for SentraFlow Bronze Layer (Phase 2).
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from deltalake import DeltaTable

from data_generator.generator import FinancialDataGenerator
from data_generator.writer import export_batch_to_landing
from spark_jobs.bronze.ingest_batch import BronzeBatchIngestor
from spark_jobs.bronze.ingest_stream import BronzeStreamIngestor
from spark_jobs.common.drift_logger import SchemaDriftLogger


@pytest.fixture
def test_environment(tmp_path):
    """
    Sets up isolated temporary paths for bronze, quarantine, and landing zones.
    """
    landing_dir = tmp_path / "landing"
    bronze_dir = tmp_path / "bronze"
    quarantine_dir = tmp_path / "bronze_quarantine"
    drift_dir = tmp_path / "schema_drift_log"

    landing_dir.mkdir()
    bronze_dir.mkdir()
    quarantine_dir.mkdir()
    drift_dir.mkdir()

    ingestor = BronzeBatchIngestor(
        bronze_base_path=str(bronze_dir),
        quarantine_base_path=str(quarantine_dir),
        drift_log_path=str(drift_dir),
    )

    return {
        "landing": landing_dir,
        "bronze": bronze_dir,
        "quarantine": quarantine_dir,
        "drift": drift_dir,
        "ingestor": ingestor,
    }


def test_bronze_batch_ingest_metadata(test_environment):
    """
    Asserts that raw landing files are ingested into Delta tables with all
    required metadata columns and partition columns.
    """
    landing_dir = test_environment["landing"]
    ingestor = test_environment["ingestor"]

    # 1. Generate clean test data
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=25)
    file_path = export_batch_to_landing(
        records=customers,
        entity_name="customers",
        output_dir=str(landing_dir),
        batch_id="b1",
    )

    # 2. Ingest into Bronze Delta table
    result = ingestor.ingest_file(
        file_path=file_path,
        entity_name="customers",
        batch_id="b1",
        schema_version="v1.0",
    )

    assert result["rows_ingested"] == 25
    assert result["rows_quarantined"] == 0

    # 3. Read back Delta table and inspect metadata
    dt_path = test_environment["bronze"] / "customers"
    assert (dt_path / "_delta_log").exists(), "Delta log directory must exist"

    dt = DeltaTable(str(dt_path))
    df = dt.to_pandas()

    assert len(df) == 25
    expected_meta = [
        "_ingest_ts",
        "_source_file",
        "_batch_id",
        "_schema_version",
        "_record_hash",
        "ingest_date",
    ]
    for col in expected_meta:
        assert col in df.columns, f"Metadata column {col} missing"

    # Check hash format (64-char SHA256 hex)
    for h in df["_record_hash"]:
        assert len(h) == 64
        assert int(h, 16) > 0


def test_bronze_idempotency(test_environment):
    """
    Asserts that re-running the same batch_id never produces duplicate rows.
    """
    landing_dir = test_environment["landing"]
    ingestor = test_environment["ingestor"]

    gen = FinancialDataGenerator(seed=42)
    gen.generate_customers(count=20)
    acc_records = gen.generate_accounts()[:20]

    file_path = export_batch_to_landing(
        records=acc_records,
        entity_name="accounts",
        output_dir=str(landing_dir),
        batch_id="batch_idem_1",
    )

    # First run
    res1 = ingestor.ingest_file(file_path, "accounts", batch_id="batch_idem_1")
    assert res1["rows_ingested"] == 20

    dt = DeltaTable(str(test_environment["bronze"] / "accounts"))
    assert len(dt.to_pandas()) == 20

    # Re-run same batch
    res2 = ingestor.ingest_file(file_path, "accounts", batch_id="batch_idem_1")
    assert res2["rows_ingested"] == 20

    # Table must still have exactly 20 rows, NOT 40
    dt_after = DeltaTable(str(test_environment["bronze"] / "accounts"))
    df_after = dt_after.to_pandas()
    assert len(df_after) == 20, "Idempotent re-ingestion must not duplicate rows"

    # Second distinct batch
    file_path_2 = export_batch_to_landing(
        records=acc_records[:10],
        entity_name="accounts",
        output_dir=str(landing_dir),
        batch_id="batch_idem_2",
    )
    res3 = ingestor.ingest_file(file_path_2, "accounts", batch_id="batch_idem_2")
    assert res3["rows_ingested"] == 10

    # Total must now be 30
    dt_final = DeltaTable(str(test_environment["bronze"] / "accounts"))
    assert len(dt_final.to_pandas()) == 30


def test_bronze_schema_drift_handling_and_logging(test_environment):
    """
    Asserts that Delta schema merges gracefully when new columns are introduced,
    and logs the drift event into governance.schema_drift_log.
    """
    landing_dir = test_environment["landing"]
    ingestor = test_environment["ingestor"]

    # Batch 1: Standard merchants
    gen = FinancialDataGenerator(seed=42)
    merchants = gen.generate_merchants(count=15)
    file_path_1 = export_batch_to_landing(
        records=merchants,
        entity_name="merchants",
        output_dir=str(landing_dir),
        batch_id="m_b1",
    )
    ingestor.ingest_file(file_path_1, "merchants", batch_id="m_b1")

    # Batch 2: Merchants with schema drift (new column 'merchant_discount_rate')
    drift_data = [m.model_dump() for m in merchants[:5]]
    for row in drift_data:
        row["merchant_discount_rate"] = 0.025  # Injected drift column
        row["tax_classification"] = "GST_REGULAR"  # Second drift column

    drift_file = landing_dir / "merchants_drift.parquet"
    pd.DataFrame(drift_data).to_parquet(drift_file, index=False)

    res_drift = ingestor.ingest_file(
        str(drift_file),
        entity_name="merchants",
        batch_id="m_b2_drift",
    )

    assert "merchant_discount_rate" in res_drift["schema_drift_detected"]
    assert "tax_classification" in res_drift["schema_drift_detected"]

    # Verify Delta table evolved
    dt = DeltaTable(str(test_environment["bronze"] / "merchants"))
    df = dt.to_pandas()
    assert "merchant_discount_rate" in df.columns
    assert "tax_classification" in df.columns

    # Verify drift logger table
    drift_logger = SchemaDriftLogger(str(test_environment["drift"]))
    drift_df = drift_logger.get_drift_history()
    assert not drift_df.empty
    assert "merchants" in drift_df["entity_name"].values
    assert any("merchant_discount_rate" in str(x) for x in drift_df["new_columns"])


def test_bronze_quarantine_routing(test_environment):
    """
    Asserts that unparseable or completely corrupted rows are diverted to bronze_quarantine/
    with an error reason and do not contaminate the Bronze Delta table.
    """
    landing_dir = test_environment["landing"]
    ingestor = test_environment["ingestor"]

    # Create CSV containing 5 valid rows and 2 completely corrupt rows
    valid_data = [
        {"customer_id": f"c_{i}", "full_name": f"User {i}", "dob": "1990-01-01"}
        for i in range(5)
    ]
    corrupt_data = [
        {"customer_id": None, "full_name": None, "dob": None},
        {"customer_id": None, "full_name": None, "dob": None},
    ]

    combined = pd.DataFrame(valid_data + corrupt_data)
    csv_file = landing_dir / "customers_with_corrupt.csv"
    combined.to_csv(csv_file, index=False)

    res = ingestor.ingest_file(
        str(csv_file),
        entity_name="customers_corrupt_test",
        batch_id="q_b1",
    )

    assert res["rows_ingested"] == 5
    assert res["rows_quarantined"] == 2
    assert res["quarantine_path"] is not None
    assert Path(res["quarantine_path"]).exists()

    # Verify quarantine file contents
    df_q = pd.read_parquet(res["quarantine_path"])
    assert len(df_q) == 2
    assert "quarantine_reason" in df_q.columns
    assert "quarantined_at" in df_q.columns

    # Verify bronze table only has the 5 valid rows
    dt = DeltaTable(str(test_environment["bronze"] / "customers_corrupt_test"))
    assert len(dt.to_pandas()) == 5


def test_bronze_partitioning_by_date(test_environment):
    """
    Asserts that Delta files are partitioned by ingest_date=YYYY-MM-DD.
    """
    landing_dir = test_environment["landing"]
    ingestor = test_environment["ingestor"]

    gen = FinancialDataGenerator(seed=42)
    merchants = gen.generate_merchants(count=10)
    file_path = export_batch_to_landing(
        merchants, "merchants_part", str(landing_dir), batch_id="p1"
    )

    custom_ts = datetime(2026, 11, 7, 10, 30, 0, tzinfo=timezone.utc)
    ingestor.ingest_file(
        file_path, "merchants_part", batch_id="p1", ingest_ts=custom_ts
    )

    dt_path = test_environment["bronze"] / "merchants_part"
    partition_folder = dt_path / "ingest_date=2026-11-07"
    assert partition_folder.exists(), (
        "Partition directory 'ingest_date=2026-11-07' must exist on disk"
    )


def test_bronze_streaming_ingestion(test_environment):
    """
    Asserts that BronzeStreamIngestor successfully ingests streaming micro-batches.
    """
    stream_ingestor = BronzeStreamIngestor(
        bronze_base_path=str(test_environment["bronze"])
    )

    sample_txns = [
        {"txn_id": f"tx_{i}", "amount": 100.0 * (i + 1), "channel": "UPI"}
        for i in range(8)
    ]

    ingested = stream_ingestor.ingest_records(sample_txns, batch_id="micro_001")
    assert ingested == 8

    dt = DeltaTable(str(test_environment["bronze"] / "transactions"))
    df = dt.to_pandas()
    assert len(df) == 8
    assert "_source_file" in df.columns
    assert df["_source_file"].iloc[0] == "kafka:txn.raw"
