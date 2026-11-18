"""
Silver Layer Main Processor for SentraFlow.

Orchestrates Bronze promotion through:
1. PII-Masking Gate enforcement
2. Standardisation (E.164 phones, ISO state codes, UTC timestamps)
3. Window-based deduplication
4. Quality validation & reject routing
5. SCD Type 2 dimension merge for customers
6. Atomic append to Silver Delta tables
"""

from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import write_deltalake

from spark_jobs.governance.gate import PIIGate
from spark_jobs.silver.cleaners import (
    clean_amount,
    clean_phone_e164,
    clean_state_iso,
    clean_timestamp_utc,
)
from spark_jobs.silver.deduplicator import deduplicate_records
from spark_jobs.silver.quality_checks import SilverQualityValidator
from spark_jobs.silver.scd2 import CustomerSCD2Manager


class SilverProcessor:
    """
    Coordinates end-to-end promotion from Bronze to Silver.
    """

    def __init__(
        self,
        silver_base_path: str = "./data/delta/silver",
        rejects_base_path: str = "./data/delta/silver_rejects",
        gate: PIIGate | None = None,
        max_reject_threshold: float = 0.20,
    ):
        self.silver_base_path = silver_base_path
        self.gate = gate or PIIGate()
        self.validator = SilverQualityValidator(
            rejects_base_path=rejects_base_path,
            max_reject_threshold=max_reject_threshold,
        )
        self.scd2_manager = CustomerSCD2Manager(
            silver_customer_table_path=str(Path(silver_base_path) / "customers")
        )

    def process_customers(
        self, bronze_df: pd.DataFrame, batch_id: str
    ) -> dict[str, Any]:
        """Processes customer batch through gate, cleaning, dedupe, DQ, and SCD2."""
        # 1. Governance gate
        masked_df = self.gate.process(bronze_df, "customers", batch_id)

        # 2. Cleaning & Standardisation
        cleaned_df = masked_df.copy()
        cleaned_df["phone"] = cleaned_df["phone"].apply(clean_phone_e164)
        cleaned_df["state"] = cleaned_df["state"].apply(clean_state_iso)
        cleaned_df["created_at"] = cleaned_df["created_at"].apply(clean_timestamp_utc)
        cleaned_df["updated_at"] = cleaned_df["updated_at"].apply(clean_timestamp_utc)

        # 3. Deduplicate
        deduped_df = deduplicate_records(cleaned_df, business_keys=["customer_id"])

        # 4. Data Quality validation
        valid_df, reject_df = self.validator.validate_customers(deduped_df, batch_id)

        # 5. SCD Type 2 merge into Silver Delta table
        scd2_df = self.scd2_manager.process_scd2_merge(valid_df)

        return {
            "entity": "customers",
            "batch_id": batch_id,
            "processed_count": len(bronze_df),
            "valid_count": len(valid_df),
            "reject_count": len(reject_df),
            "scd2_total_rows": len(scd2_df),
        }

    def process_transactions(
        self,
        bronze_df: pd.DataFrame,
        batch_id: str,
        valid_account_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Processes transaction batch through gate, cleaning, dedupe, DQ, and partition append."""
        # 1. Governance gate
        masked_df = self.gate.process(bronze_df, "transactions", batch_id)

        # 2. Cleaning
        cleaned_df = masked_df.copy()
        cleaned_df["amount"] = cleaned_df["amount"].apply(clean_amount)
        cleaned_df["txn_ts"] = cleaned_df["txn_ts"].apply(clean_timestamp_utc)
        # Create partition column txn_date
        cleaned_df["txn_date"] = cleaned_df["txn_ts"].apply(
            lambda s: str(s)[:10] if s else "1970-01-01"
        )

        # 3. Deduplicate
        deduped_df = deduplicate_records(cleaned_df, business_keys=["txn_id"])

        # 4. Data Quality
        valid_df, reject_df = self.validator.validate_transactions(
            deduped_df, batch_id, valid_account_ids=valid_account_ids
        )

        # 5. Atomic append to Silver partitioned by txn_date
        table_path = Path(self.silver_base_path) / "transactions"
        table_path.mkdir(parents=True, exist_ok=True)

        if not valid_df.empty:
            write_deltalake(
                str(table_path),
                valid_df,
                mode="append",
                partition_by=["txn_date"],
                schema_mode="merge",
            )

        return {
            "entity": "transactions",
            "batch_id": batch_id,
            "processed_count": len(bronze_df),
            "valid_count": len(valid_df),
            "reject_count": len(reject_df),
        }

    def process_accounts(
        self, bronze_df: pd.DataFrame, batch_id: str
    ) -> dict[str, Any]:
        """Processes accounts batch."""
        masked_df = self.gate.process(bronze_df, "accounts", batch_id)
        cleaned_df = masked_df.copy()
        cleaned_df["balance"] = cleaned_df["balance"].apply(clean_amount)
        cleaned_df["open_date"] = cleaned_df["open_date"].apply(clean_timestamp_utc)

        deduped_df = deduplicate_records(cleaned_df, business_keys=["account_id"])

        table_path = Path(self.silver_base_path) / "accounts"
        table_path.mkdir(parents=True, exist_ok=True)

        if not deduped_df.empty:
            write_deltalake(
                str(table_path),
                deduped_df,
                mode="append",
                schema_mode="merge",
            )

        return {
            "entity": "accounts",
            "batch_id": batch_id,
            "processed_count": len(bronze_df),
            "valid_count": len(deduped_df),
        }

    def process_merchants(
        self, bronze_df: pd.DataFrame, batch_id: str
    ) -> dict[str, Any]:
        """Processes merchants batch."""
        masked_df = self.gate.process(bronze_df, "merchants", batch_id)
        deduped_df = deduplicate_records(masked_df, business_keys=["merchant_id"])

        table_path = Path(self.silver_base_path) / "merchants"
        table_path.mkdir(parents=True, exist_ok=True)

        if not deduped_df.empty:
            write_deltalake(
                str(table_path),
                deduped_df,
                mode="append",
                schema_mode="merge",
            )

        return {
            "entity": "merchants",
            "batch_id": batch_id,
            "processed_count": len(bronze_df),
            "valid_count": len(deduped_df),
        }
