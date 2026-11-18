"""
Unit and Integration tests for SentraFlow Gold Layer and dbt Models (Phase 5).
"""

from pathlib import Path

import pandas as pd
import pytest

from data_generator.generator import FinancialDataGenerator
from dbt_project.runner import DbtGoldRunner
from spark_jobs.governance.gate import PIIGate
from spark_jobs.silver.processor import SilverProcessor


@pytest.fixture
def test_gold_env(tmp_path):
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    rejects_dir = tmp_path / "silver_rejects"
    audit_dir = tmp_path / "pii_gate_audit"

    # 1. Populate Silver Delta tables using generator + processor
    gen = FinancialDataGenerator(seed=42, dirty_rate=0.0)
    customers = gen.generate_customers(count=20)
    accounts = gen.generate_accounts()[:20]
    merchants = gen.generate_merchants(count=5)
    txns = gen.generate_transactions(count=40)

    processor = SilverProcessor(
        silver_base_path=str(silver_dir),
        rejects_base_path=str(rejects_dir),
        gate=PIIGate(audit_table_path=str(audit_dir)),
    )

    processor.process_customers(pd.DataFrame([c.model_dump() for c in customers]), "b1")
    processor.process_accounts(pd.DataFrame([a.model_dump() for a in accounts]), "b1")
    processor.process_merchants(pd.DataFrame([m.model_dump() for m in merchants]), "b1")
    processor.process_transactions(pd.DataFrame([t.model_dump() for t in txns]), "b1")

    # 2. Initialize dbt runner
    runner = DbtGoldRunner(
        silver_base_path=str(silver_dir),
        gold_base_path=str(gold_dir),
    )
    runner.load_silver_tables()
    runner.run_staging_models()

    return {
        "silver_dir": silver_dir,
        "gold_dir": gold_dir,
        "runner": runner,
    }


def test_dbt_star_schema_and_marts_execution(test_gold_env):
    """
    Asserts that all dimensions, facts, and analytical marts materialize successfully
    with data into the Gold Delta Lake store.
    """
    runner = test_gold_env["runner"]
    marts = runner.run_marts_models()

    expected_models = [
        "dim_customer",
        "dim_account",
        "dim_merchant",
        "dim_channel",
        "dim_date",
        "fct_transactions",
        "fct_fraud_scores",
        "mart_daily_spend_by_segment",
        "mart_merchant_risk",
        "mart_customer_360",
        "mart_fraud_kpis",
        "mart_data_quality_scorecard",
    ]

    for model in expected_models:
        assert model in marts, f"Model {model} must be generated"
        df = marts[model]
        assert not df.empty, f"Model {model} should contain rows"

    # Specific assertions on marts
    c360 = marts["mart_customer_360"]
    assert "lifetime_spend_inr" in c360.columns
    assert "masked_name" in c360.columns

    kpis = marts["mart_fraud_kpis"]
    assert "alert_rate_pct" in kpis.columns
    assert "avg_scoring_latency_ms" in kpis.columns


def test_dbt_tests_and_singular_revenue_reconciliation(test_gold_env):
    """
    Asserts that all dbt tests (unique, not_null, positive_amount, masked_pan)
    and the singular revenue reconciliation test pass 100% green.
    """
    runner = test_gold_env["runner"]
    runner.run_marts_models()

    results = runner.run_tests()
    assert len(results) > 0

    for test_name, passed, details in results:
        assert passed is True, f"dbt test '{test_name}' failed: {details}"


def test_dbt_project_configuration_and_tags():
    """
    Asserts that dbt_project.yml and schema.yml contain mandatory tags (pii_safe, finance_critical).
    """
    import yaml

    proj_file = Path("dbt_project/dbt_project.yml")
    assert proj_file.exists()
    with open(proj_file, "r", encoding="utf-8") as f:
        proj_cfg = yaml.safe_load(f)

    marts_cfg = proj_cfg["models"]["sentraflow_lakehouse"]["marts"]
    assert "pii_safe" in marts_cfg["+tags"]
    assert "finance_critical" in marts_cfg["+tags"]
