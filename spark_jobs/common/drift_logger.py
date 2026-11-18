"""
Schema Drift Detector and Logger.

Tracks and persists schema evolution events across Delta Lake ingestion runs
to the governance.schema_drift_log table.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from deltalake import DeltaTable, write_deltalake


class SchemaDriftLogger:
    """
    Detects and logs schema drift events during Bronze ingestion.
    """

    def __init__(self, log_table_path: str):
        self.log_table_path = log_table_path

    def check_and_log_drift(
        self,
        entity_name: str,
        incoming_columns: list[str],
        existing_columns: list[str] | None,
        batch_id: str,
        schema_version: str = "v1.0",
    ) -> list[str]:
        """
        Compares incoming columns against existing schema columns.
        If new columns are detected, logs an event to the schema_drift_log table.
        Returns the list of newly detected columns.
        """
        if not existing_columns:
            return []

        new_columns = [col for col in incoming_columns if col not in existing_columns]
        if not new_columns:
            return []

        drift_record = {
            "entity_name": entity_name,
            "batch_id": batch_id,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "new_columns": ",".join(new_columns),
            "total_columns": len(incoming_columns),
            "schema_version": schema_version,
        }

        df_drift = pd.DataFrame([drift_record])
        target_dir = Path(self.log_table_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        write_deltalake(
            self.log_table_path,
            df_drift,
            mode="append",
            schema_mode="merge",
        )

        return new_columns

    def get_drift_history(self) -> pd.DataFrame:
        """
        Retrieves all logged schema drift events.
        """
        try:
            dt = DeltaTable(self.log_table_path)
            return dt.to_pandas()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
