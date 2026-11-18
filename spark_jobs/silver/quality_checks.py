"""
Data Quality Validation and Rejection Routing for SentraFlow Silver Layer.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import write_deltalake


class DataQualityThresholdExceededError(Exception):
    """Raised when Silver data rejection rate exceeds allowed threshold."""


MASKED_PAN_REGEX = re.compile(r"^XXXXX[0-9]{4}X$")


class SilverQualityValidator:
    """
    Validates Silver records against contract rules and routes invalid rows to silver_rejects.
    """

    def __init__(
        self,
        rejects_base_path: str = "./data/delta/silver_rejects",
        max_reject_threshold: float = 0.20,
    ):
        self.rejects_base_path = rejects_base_path
        self.max_reject_threshold = max_reject_threshold

    def validate_customers(
        self,
        df: pd.DataFrame,
        batch_id: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Validates customer records:
        - customer_id must not be null
        - pan format must be validly masked (XXXXX1234X)
        """
        valid_rows: list[dict[str, Any]] = []
        reject_rows: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for _, row in df.iterrows():
            r = row.to_dict()
            reasons = []

            # 1. Not-null key
            if pd.isna(r.get("customer_id")) or not str(r.get("customer_id")).strip():
                reasons.append("Null or empty customer_id")

            # 2. Masked PAN validity
            pan_val = str(r.get("pan", "")).strip()
            if (
                pan_val
                and not MASKED_PAN_REGEX.match(pan_val)
                and not pan_val.startswith("XXXXX")
            ):
                reasons.append(f"Invalid masked PAN pattern: {pan_val}")

            if reasons:
                r["rejection_reason"] = "; ".join(reasons)
                r["rejected_at"] = now_iso
                r["_batch_id"] = batch_id
                reject_rows.append(r)
            else:
                valid_rows.append(r)

        valid_df = (
            pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(columns=df.columns)
        )
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
        return self._process_results("customers", df, valid_df, reject_df, batch_id)

    def validate_transactions(
        self,
        df: pd.DataFrame,
        batch_id: str,
        valid_account_ids: set[str] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Validates transaction records:
        - txn_id must not be null
        - amount must be strictly > 0
        - referential integrity: account_id must exist in known accounts (if provided)
        """
        valid_rows: list[dict[str, Any]] = []
        reject_rows: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for _, row in df.iterrows():
            r = row.to_dict()
            reasons = []

            # 1. Not null txn_id
            if pd.isna(r.get("txn_id")) or not str(r.get("txn_id")).strip():
                reasons.append("Null or empty txn_id")

            # 2. Amount > 0
            try:
                amt = float(r.get("amount", 0))
                if amt <= 0:
                    reasons.append(f"Non-positive amount: {amt}")
            except Exception:  # noqa: BLE001
                reasons.append(f"Unparseable amount: {r.get('amount')}")

            # 3. Referential integrity
            acc_id = str(r.get("account_id", ""))
            if valid_account_ids is not None and acc_id not in valid_account_ids:
                reasons.append(f"Orphan transaction: account_id {acc_id} not found")

            if reasons:
                r["rejection_reason"] = "; ".join(reasons)
                r["rejected_at"] = now_iso
                r["_batch_id"] = batch_id
                reject_rows.append(r)
            else:
                valid_rows.append(r)

        valid_df = (
            pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(columns=df.columns)
        )
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
        return self._process_results("transactions", df, valid_df, reject_df, batch_id)

    def _process_results(
        self,
        entity_name: str,
        total_df: pd.DataFrame,
        valid_df: pd.DataFrame,
        reject_df: pd.DataFrame,
        batch_id: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Routes rejected rows to Delta silver_rejects and evaluates reject threshold.
        """
        total_count = len(total_df)
        reject_count = len(reject_df)

        if reject_count > 0:
            target_path = Path(self.rejects_base_path) / entity_name
            target_path.mkdir(parents=True, exist_ok=True)
            write_deltalake(
                str(target_path),
                reject_df,
                mode="append",
                schema_mode="merge",
            )

        if total_count > 0:
            rejection_rate = reject_count / total_count
            if rejection_rate > self.max_reject_threshold:
                raise DataQualityThresholdExceededError(
                    f"Data Quality Failure on '{entity_name}': rejection rate "
                    f"{rejection_rate:.2%} exceeded maximum allowed threshold of {self.max_reject_threshold:.2%} "
                    f"({reject_count}/{total_count} rows rejected)."
                )

        return valid_df, reject_df
