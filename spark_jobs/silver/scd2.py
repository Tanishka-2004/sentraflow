"""
Slowly Changing Dimension Type 2 (SCD2) Implementation for SentraFlow.

Maintains historical dimension versions for customers:
- Tracks changes to: address, city, state, pincode, kyc_status.
- Maintains: valid_from, valid_to, is_current, cust_sk.
- Uses Delta Lake atomic transaction semantics.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from deltalake import DeltaTable, write_deltalake

TRACKED_SCD2_COLUMNS: list[str] = [
    "address",
    "city",
    "state",
    "pincode",
    "kyc_status",
]


def generate_surrogate_key(customer_id: str, valid_from: str) -> str:
    """Computes a deterministic surrogate key for the SCD2 version record."""
    raw = f"{customer_id}_{valid_from}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class CustomerSCD2Manager:
    """
    Manages SCD Type 2 dimension lifecycle for silver.customers.
    """

    def __init__(
        self, silver_customer_table_path: str = "./data/delta/silver/customers"
    ):
        self.table_path = silver_customer_table_path

    def process_scd2_merge(self, incoming_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merges incoming customer updates into the SCD2 Delta table:
        - Expires old active versions if tracked attributes changed.
        - Inserts new active versions.
        - Inserts brand-new customer records.
        """
        if incoming_df.empty:
            return incoming_df

        target_dir = Path(self.table_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        now_iso = datetime.now(timezone.utc).isoformat()

        # Check if table already exists
        existing_df: pd.DataFrame | None = None
        try:
            dt = DeltaTable(self.table_path)
            existing_df = dt.to_pandas()
        except Exception:  # noqa: BLE001
            existing_df = None

        # Case 1: Initial load
        if existing_df is None or existing_df.empty:
            initial_df = incoming_df.copy()
            initial_df["valid_from"] = initial_df.get("created_at", now_iso)
            initial_df["valid_to"] = None
            initial_df["is_current"] = True
            initial_df["cust_sk"] = [
                generate_surrogate_key(str(row["customer_id"]), str(row["valid_from"]))
                for _, row in initial_df.iterrows()
            ]

            write_deltalake(
                self.table_path,
                initial_df,
                mode="overwrite",
                schema_mode="merge",
            )
            return initial_df

        # Case 2: Incremental load with change detection
        current_records = existing_df[existing_df["is_current"] == True].copy()
        historical_records = existing_df[existing_df["is_current"] == False].copy()

        incoming_cids = set(incoming_df["customer_id"])
        # Untouched active customers remain as-is
        untouched_active = current_records[
            ~current_records["customer_id"].isin(incoming_cids)
        ].to_dict(orient="records")

        current_by_id = {
            row["customer_id"]: row for _, row in current_records.iterrows()
        }

        expired_rows = []
        new_version_rows = []
        unchanged_rows = []

        for _, inc_row in incoming_df.iterrows():
            cid = inc_row["customer_id"]
            inc_dict = inc_row.to_dict()

            if cid in current_by_id:
                curr = current_by_id[cid]
                # Check for mutations in tracked columns
                has_changed = any(
                    str(inc_dict.get(col, "")).strip() != str(curr.get(col, "")).strip()
                    for col in TRACKED_SCD2_COLUMNS
                )

                if has_changed:
                    # 1. Expire current version
                    expired_curr = curr.to_dict()
                    update_ts = inc_dict.get("updated_at", now_iso)
                    expired_curr["valid_to"] = update_ts
                    expired_curr["is_current"] = False
                    expired_rows.append(expired_curr)

                    # 2. Insert new active version
                    new_version = inc_dict.copy()
                    new_version["valid_from"] = update_ts
                    new_version["valid_to"] = None
                    new_version["is_current"] = True
                    new_version["cust_sk"] = generate_surrogate_key(cid, str(update_ts))
                    new_version_rows.append(new_version)
                else:
                    unchanged_rows.append(curr.to_dict())
            else:
                # Brand new customer
                brand_new = inc_dict.copy()
                valid_from = brand_new.get("created_at", now_iso)
                brand_new["valid_from"] = valid_from
                brand_new["valid_to"] = None
                brand_new["is_current"] = True
                brand_new["cust_sk"] = generate_surrogate_key(cid, str(valid_from))
                new_version_rows.append(brand_new)

        # Assemble full table: historical + untouched active + expired + unchanged + new versions
        combined_rows = (
            historical_records.to_dict(orient="records")
            + untouched_active
            + expired_rows
            + unchanged_rows
            + new_version_rows
        )

        final_df = (
            pd.DataFrame(combined_rows).drop_duplicates(subset=["cust_sk"]).copy()
        )

        # Write updated SCD2 table atomically
        write_deltalake(
            self.table_path,
            final_df,
            mode="overwrite",
            schema_mode="merge",
        )

        return final_df
