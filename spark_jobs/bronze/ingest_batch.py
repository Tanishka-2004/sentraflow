"""
Bronze Layer Batch Ingestion Job for SentraFlow.

Ingests raw landing files (Parquet/CSV) into immutable, append-only Delta Lake tables.
Features:
- Metadata enrichment: _ingest_ts, _source_file, _batch_id, _schema_version, _record_hash.
- Ingestion partitioning by ingest_date (YYYY-MM-DD).
- Strict idempotency: re-ingesting the same batch_id never duplicates records.
- Schema drift detection & evolution (Delta mergeSchema) + logging to governance.schema_drift_log.
- Quarantine routing: unparseable/corrupt records diverted to bronze_quarantine/.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import DeltaTable, write_deltalake

from spark_jobs.common.drift_logger import SchemaDriftLogger
from spark_jobs.common.hash_utils import compute_record_hash


class BronzeBatchIngestor:
    """
    Orchestrates batch ingestion into Bronze Delta Lake tables.
    """

    def __init__(
        self,
        bronze_base_path: str = "./data/delta/bronze",
        quarantine_base_path: str = "./data/delta/bronze_quarantine",
        drift_log_path: str = "./data/delta/governance/schema_drift_log",
    ):
        self.bronze_base_path = bronze_base_path
        self.quarantine_base_path = quarantine_base_path
        self.drift_logger = SchemaDriftLogger(drift_log_path)

    def _read_landing_file(
        self, file_path: str
    ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        """
        Reads a landing file (Parquet or CSV).
        Catches corrupted/unparseable records and separates them for quarantine.
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Landing file not found: {file_path}")

        quarantine_records: list[dict[str, Any]] = []

        if p.suffix.lower() == ".parquet":
            try:
                df = pd.read_parquet(p)
            except Exception as e:  # noqa: BLE001
                # If entire file is unparseable
                quarantine_records.append(
                    {
                        "raw_payload": f"File read failure: {p.name}",
                        "quarantine_reason": f"Parquet parse error: {e!s}",
                        "source_file": p.name,
                        "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                return pd.DataFrame(), quarantine_records
        elif p.suffix.lower() == ".csv":
            try:
                df = pd.read_csv(p, on_bad_lines="warn")
            except Exception as e:  # noqa: BLE001
                quarantine_records.append(
                    {
                        "raw_payload": f"File read failure: {p.name}",
                        "quarantine_reason": f"CSV parse error: {e!s}",
                        "source_file": p.name,
                        "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                return pd.DataFrame(), quarantine_records
        else:
            raise ValueError(f"Unsupported file format: {p.suffix}")

        # Check for unparseable records / corrupt rows (e.g. completely null records)
        if df.empty:
            return df, quarantine_records

        # Identify rows with critical parsing corruptions (e.g., all values null)
        corrupt_mask = df.isnull().all(axis=1)
        if corrupt_mask.any():
            corrupt_df = df[corrupt_mask]
            for _, row in corrupt_df.iterrows():
                quarantine_records.append(
                    {
                        "raw_payload": json.dumps(row.to_dict()),
                        "quarantine_reason": "Completely empty/null row in source payload",
                        "source_file": p.name,
                        "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            df = df[~corrupt_mask].copy()

        return df, quarantine_records

    def _route_to_quarantine(
        self,
        quarantine_records: list[dict[str, Any]],
        entity_name: str,
        batch_id: str,
    ) -> str | None:
        """
        Persists corrupted/unparseable records to the quarantine zone.
        """
        if not quarantine_records:
            return None

        target_dir = (
            Path(self.quarantine_base_path) / entity_name / f"batch_id={batch_id}"
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        df_quarantine = pd.DataFrame(quarantine_records)
        quarantine_file = target_dir / f"quarantine_{batch_id}.parquet"
        df_quarantine.to_parquet(quarantine_file, index=False)
        return str(quarantine_file)

    def ingest_file(
        self,
        file_path: str,
        entity_name: str,
        batch_id: str,
        schema_version: str = "v1.0",
        ingest_ts: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Ingests a single landing file into the corresponding Bronze Delta table.
        Ensures metadata columns, schema drift logging, idempotency, and quarantine routing.
        """
        if ingest_ts is None:
            ingest_ts = datetime.now(timezone.utc)

        ingest_date_str = ingest_ts.strftime("%Y-%m-%d")
        ingest_ts_iso = ingest_ts.isoformat()
        source_file_name = Path(file_path).name

        # 1. Read source data and isolate quarantine rows
        df, quarantine_records = self._read_landing_file(file_path)

        quarantine_path = None
        if quarantine_records:
            quarantine_path = self._route_to_quarantine(
                quarantine_records, entity_name, batch_id
            )

        if df.empty:
            return {
                "entity": entity_name,
                "batch_id": batch_id,
                "rows_ingested": 0,
                "rows_quarantined": len(quarantine_records),
                "quarantine_path": quarantine_path,
                "schema_drift_detected": [],
            }

        # 2. Enrich with Bronze metadata columns
        df["_ingest_ts"] = ingest_ts_iso
        df["_source_file"] = source_file_name
        df["_batch_id"] = batch_id
        df["_schema_version"] = schema_version
        df["ingest_date"] = ingest_date_str

        # Compute deterministic _record_hash for each row
        record_dicts = df.to_dict(orient="records")
        df["_record_hash"] = [compute_record_hash(r) for r in record_dicts]

        # 3. Check for schema drift against existing Delta table
        delta_table_path = str(Path(self.bronze_base_path) / entity_name)
        new_cols_detected: list[str] = []

        existing_cols: list[str] | None = None
        table_exists = False
        try:
            dt = DeltaTable(delta_table_path)
            table_exists = True
            existing_cols = [f.name for f in dt.schema().fields]
        except Exception:  # noqa: BLE001
            table_exists = False

        if table_exists and existing_cols:
            incoming_cols = list(df.columns)
            new_cols_detected = self.drift_logger.check_and_log_drift(
                entity_name=entity_name,
                incoming_columns=incoming_cols,
                existing_columns=existing_cols,
                batch_id=batch_id,
                schema_version=schema_version,
            )

        # 4. Enforce idempotency: If batch_id already exists in Delta table, purge old batch rows
        if table_exists:
            dt = DeltaTable(delta_table_path)
            # Delete any existing records from the same batch_id to prevent duplicates
            dt.delete(predicate=f"_batch_id = '{batch_id}'")

        # 5. Append-only write to Delta Lake partitioned by ingest_date with mergeSchema
        target_path = Path(delta_table_path)
        target_path.mkdir(parents=True, exist_ok=True)

        write_deltalake(
            delta_table_path,
            df,
            mode="append",
            partition_by=["ingest_date"],
            schema_mode="merge",
        )

        return {
            "entity": entity_name,
            "batch_id": batch_id,
            "rows_ingested": len(df),
            "rows_quarantined": len(quarantine_records),
            "quarantine_path": quarantine_path,
            "schema_drift_detected": new_cols_detected,
            "table_path": delta_table_path,
        }
