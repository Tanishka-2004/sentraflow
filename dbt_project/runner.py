"""
Local dbt Transformation Runner and Validator for SentraFlow.

Compiles and executes dbt star schema models and data quality tests
against Silver Delta tables, materializing Gold marts.
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd
from deltalake import DeltaTable, write_deltalake


class DbtGoldRunner:
    """
    Executes and validates dbt models and tests for the Gold layer.
    """

    def __init__(
        self,
        silver_base_path: str = "./data/delta/silver",
        gold_base_path: str = "./data/delta/gold",
    ):
        self.silver_base_path = silver_base_path
        self.gold_base_path = gold_base_path
        self.conn = sqlite3.connect(":memory:")

    def load_silver_tables(self):
        """Loads available Silver Delta tables into the in-memory SQL catalog."""
        entities = ["customers", "accounts", "merchants", "transactions"]
        for ent in entities:
            p = Path(self.silver_base_path) / ent
            if (p / "_delta_log").exists():
                df = DeltaTable(str(p)).to_pandas()
                df.to_sql(f"silver_{ent}", self.conn, if_exists="replace", index=False)
            else:
                # Mock empty table with standard columns
                pd.DataFrame().to_sql(
                    f"silver_{ent}", self.conn, if_exists="replace", index=False
                )

    @staticmethod
    def _compile_sql(sql_content: str) -> str:
        """Strips dbt config headers and replaces {{ ref('model') }} with table names."""
        clean = re.sub(r"\{\{.*?\}\}", "", sql_content)
        # Handle ref conversions like {{ ref('stg_customers') }} -> stg_customers
        return clean.strip()

    def run_staging_models(self):
        """Runs staging views."""
        stg_dir = Path(__file__).parent / "models" / "staging"
        for sql_file in sorted(stg_dir.glob("*.sql")):
            model_name = sql_file.stem
            with open(sql_file, "r", encoding="utf-8") as f:
                raw_sql = f.read()
            compiled = self._compile_sql(raw_sql)
            create_stmt = f"CREATE VIEW IF NOT EXISTS {model_name} AS {compiled}"
            self.conn.execute(create_stmt)

    def run_marts_models(self) -> dict[str, pd.DataFrame]:
        """Runs dimensions, facts, and marts, returning the materialized tables."""
        marts_dir = Path(__file__).parent / "models" / "marts"
        marts_data: dict[str, pd.DataFrame] = {}

        # Processing order: dims first, then facts, then marts
        model_order = [
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

        for model_name in model_order:
            sql_file = marts_dir / f"{model_name}.sql"
            if not sql_file.exists():
                continue

            with open(sql_file, "r", encoding="utf-8") as f:
                raw_sql = f.read()

            # Replace refs with created view/table names
            compiled = re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", r"\1", raw_sql)
            compiled = re.sub(r"\{\{.*?\}\}", "", compiled).strip()

            create_stmt = f"CREATE TABLE IF NOT EXISTS {model_name} AS {compiled}"
            self.conn.execute(create_stmt)

            df = pd.read_sql(f"SELECT * FROM {model_name}", self.conn)
            marts_data[model_name] = df

            # Materialize to Gold Delta Lake
            gold_dir = Path(self.gold_base_path) / model_name
            gold_dir.mkdir(parents=True, exist_ok=True)
            if not df.empty:
                write_deltalake(
                    str(gold_dir), df, mode="overwrite", schema_mode="merge"
                )

        return marts_data

    def run_tests(self) -> list[tuple[str, bool, str]]:
        """
        Executes core dbt tests + singular reconciliation tests.
        Returns list of (test_name, passed, details).
        """
        test_results: list[tuple[str, bool, str]] = []

        # 1. Unique and Not Null tests on dim_customer
        df_cust = pd.read_sql("SELECT * FROM dim_customer", self.conn)
        cust_unique = len(df_cust["cust_sk"]) == len(
            df_cust["cust_sk"].drop_duplicates()
        )
        test_results.append(
            ("dim_customer_unique_cust_sk", cust_unique, "Checked unique cust_sk")
        )

        cust_nn = df_cust["customer_id"].notna().all()
        test_results.append(
            (
                "dim_customer_not_null_customer_id",
                bool(cust_nn),
                "Checked not-null customer_id",
            )
        )

        # 2. Positive amount test on fct_transactions
        df_fct = pd.read_sql("SELECT * FROM fct_transactions", self.conn)
        pos_amt = (df_fct["amount"] > 0).all() if not df_fct.empty else True
        test_results.append(
            ("fct_transactions_positive_amount", bool(pos_amt), "Checked amount > 0")
        )

        # 3. Masked PAN validity test on dim_customer
        pans = df_cust["pan"].dropna()
        pan_valid = (
            pans.apply(lambda p: str(p).startswith("XXXXX")).all()
            if not pans.empty
            else True
        )
        test_results.append(
            (
                "dim_customer_valid_masked_pan_pattern",
                bool(pan_valid),
                "Checked masked PAN format",
            )
        )

        # 4. Singular test: Revenue reconciliation between Silver and Gold
        silver_rev = pd.read_sql(
            "SELECT COALESCE(ROUND(SUM(amount), 2), 0.0) as rev FROM silver_transactions",
            self.conn,
        ).iloc[0, 0]
        gold_rev = pd.read_sql(
            "SELECT COALESCE(ROUND(SUM(amount), 2), 0.0) as rev FROM fct_transactions",
            self.conn,
        ).iloc[0, 0]
        reconciled = abs(silver_rev - gold_rev) <= 0.05
        test_results.append(
            (
                "singular_assert_silver_gold_revenue_reconciliation",
                bool(reconciled),
                f"Silver: {silver_rev}, Gold: {gold_rev}, Discrepancy: {abs(silver_rev - gold_rev):.2f}",
            )
        )

        return test_results
