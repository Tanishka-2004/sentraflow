"""
Unit tests for SentraFlow Data Generator (Phase 1).
"""

import re
from pathlib import Path

import pandas as pd

from data_generator.generator import FinancialDataGenerator
from data_generator.verhoeff import (
    compute_verhoeff_checksum,
    generate_invalid_verhoeff_12_digit,
    validate_verhoeff,
)
from data_generator.writer import export_batch_to_landing


def test_verhoeff_checksum_algorithm():
    """
    Asserts that the Verhoeff algorithm works and that all synthetic
    12-digit IDs mathematically fail Verhoeff (can never collide with real Aadhaar).
    """
    # Known test cases for Verhoeff
    test_num = "236"
    check = compute_verhoeff_checksum(test_num)
    assert validate_verhoeff(f"{test_num}{check}") is True

    # Check that our generator creates 100% failing numbers
    for i in range(100):
        prefix = f"{10000000000 + i}"
        invalid_id = generate_invalid_verhoeff_12_digit(prefix)
        assert len(invalid_id) == 12
        assert validate_verhoeff(invalid_id) is False, (
            f"ID {invalid_id} should fail Verhoeff"
        )


def test_clean_pan_regex():
    """
    Asserts that clean PAN numbers follow the standard format:
    5 uppercase letters (4th is 'P') + 4 digits + 1 uppercase letter.
    """
    gen = FinancialDataGenerator(seed=123, dirty_rate=0.0)
    pan_regex = re.compile(r"^[A-Z]{3}P[A-Z][0-9]{4}[A-Z]$")

    for _ in range(50):
        pan = gen.generate_pan(is_valid=True)
        assert pan_regex.match(pan) is not None, (
            f"PAN {pan} does not match standard pattern"
        )


def test_customer_generation():
    """
    Tests generation of synthetic customer entities.
    """
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=50)

    assert len(customers) == 50
    for cust in customers:
        assert cust.customer_id is not None
        assert cust.full_name is not None
        assert cust.city in [
            "Mumbai",
            "Delhi",
            "Bengaluru",
            "Hyderabad",
            "Chennai",
            "Kolkata",
            "Pune",
            "Ahmedabad",
            "Jaipur",
            "Lucknow",
        ]
        assert cust.kyc_status in ["VERIFIED", "PENDING", "REJECTED"]
        # Aadhaar ID must strictly fail Verhoeff
        assert validate_verhoeff(cust.aadhaar_id) is False


def test_dirty_data_injection():
    """
    Asserts that dirty data (nulls, malformed PANs) are injected when dirty_rate > 0.
    """
    gen_clean = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    clean_custs = gen_clean.generate_customers(count=100)
    clean_pans = [c.pan for c in clean_custs if c.pan]
    pan_regex = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    assert all(pan_regex.match(p) for p in clean_pans)

    # With 30% dirty rate, there must be malformed PANs or null fields
    gen_dirty = FinancialDataGenerator(seed=42, dirty_rate=0.30)
    dirty_custs = gen_dirty.generate_customers(count=100)
    has_malformed = any(not pan_regex.match(c.pan) for c in dirty_custs if c.pan)
    has_null_email = any(c.email is None for c in dirty_custs)
    assert has_malformed or has_null_email


def test_fraud_patterns_injection():
    """
    Asserts that fraud patterns (velocity, impossible travel, night, card testing)
    are injected and properly tagged with is_fraud=1.
    """
    gen = FinancialDataGenerator(seed=99, dirty_rate=0.0, fraud_rate=0.05)
    gen.generate_customers(count=30)
    gen.generate_accounts()
    gen.generate_merchants()
    txns = gen.generate_transactions(count=200)

    fraud_txns = [t for t in txns if t.is_fraud == 1]
    assert len(fraud_txns) > 0, "Fraud transactions must be generated"

    patterns = {t.fraud_pattern for t in fraud_txns if t.fraud_pattern}
    expected_patterns = {
        "velocity_burst",
        "impossible_travel",
        "high_value_night",
        "new_device_high_amount",
        "merchant_risk_spike",
        "card_testing_micro",
    }
    # At least some of the patterns must be present
    assert len(patterns.intersection(expected_patterns)) > 0


def test_scd_customer_updates():
    """
    Asserts that generate_customer_updates produces mutated customer records
    maintaining the same customer_id but with modified fields.
    """
    gen = FinancialDataGenerator(seed=42)
    customers = gen.generate_customers(count=20)
    updates = gen.generate_customer_updates(update_ratio=0.5)

    assert len(updates) > 0
    orig_map = {c.customer_id: c for c in customers}

    for u in updates:
        assert u.customer_id in orig_map
        orig = orig_map[u.customer_id]
        # At least address, city, or KYC status changed
        changed = (
            u.address != orig.address
            or u.city != orig.city
            or u.kyc_status != orig.kyc_status
            or u.pincode != orig.pincode
        )
        assert changed is True


def test_batch_landing_export(tmp_path):
    """
    Asserts that batch export successfully creates valid Parquet and CSV files.
    """
    gen = FinancialDataGenerator(seed=42)
    customers = gen.generate_customers(count=15)

    # Parquet test
    pq_path = export_batch_to_landing(
        records=customers,
        entity_name="customers",
        output_dir=str(tmp_path),
        file_format="parquet",
        batch_id="test_b1",
    )
    assert Path(pq_path).exists()
    df_pq = pd.read_parquet(pq_path)
    assert len(df_pq) == 15
    assert "aadhaar_id" in df_pq.columns

    # CSV test
    csv_path = export_batch_to_landing(
        records=customers,
        entity_name="customers",
        output_dir=str(tmp_path),
        file_format="csv",
        batch_id="test_b2",
    )
    assert Path(csv_path).exists()
    df_csv = pd.read_csv(csv_path)
    assert len(df_csv) == 15


def test_seed_reproducibility():
    """
    Asserts that the generator produces identical results with the same seed.
    """
    gen1 = FinancialDataGenerator(seed=777)
    c1 = gen1.generate_customers(count=10)

    gen2 = FinancialDataGenerator(seed=777)
    c2 = gen2.generate_customers(count=10)

    assert [c.customer_id for c in c1] == [c.customer_id for c in c2]
    assert [c.pan for c in c1] == [c.pan for c in c2]


def test_kafka_stream_producer_mock():
    """
    Asserts that the stream producer operates gracefully in offline/mock mode.
    """
    from data_generator.producer import KafkaStreamProducer

    gen = FinancialDataGenerator(seed=42)
    gen.generate_customers(count=5)
    gen.generate_accounts()
    gen.generate_merchants()
    txns = gen.generate_transactions(count=10)

    producer = KafkaStreamProducer(bootstrap_servers="nonexistent:9092")
    count = producer.stream_transactions(txns, events_per_second=100.0, max_events=5)
    assert count == 5


def test_cli_execution_batch(tmp_path, monkeypatch):
    """
    Tests invoking the CLI main() function directly.
    """
    from data_generator.cli import main

    test_args = [
        "cli.py",
        "--customers",
        "10",
        "--txns",
        "20",
        "--seed",
        "101",
        "--format",
        "parquet",
        "--output-dir",
        str(tmp_path),
        "--batch-id",
        "test_cli_b1",
        "--with-scd-updates",
    ]
    monkeypatch.setattr("sys.argv", test_args)
    main()

    assert (tmp_path / "customers" / "batch_id=test_cli_b1").exists()
    assert (tmp_path / "transactions" / "batch_id=test_cli_b1").exists()
    assert (tmp_path / "customers" / "batch_id=test_cli_b1_scd_updates").exists()
