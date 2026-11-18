# Phase 2: Bronze Layer (Raw, Immutable, Append-Only Lakehouse)

## Overview
Phase 2 implements the **Bronze Layer** for SentraFlow in `spark_jobs/bronze/` and `spark_jobs/common/`. The Bronze layer acts as the immutable, high-fidelity entry point for both batch landing files (Parquet/CSV) and streaming transaction micro-batches from Kafka (`txn.raw`), persisted in Delta Lake format (`s3://sentraflow-bronze/<entity>/`).

## Architecture & Design Principles

1. **Strict Immutability & Append-Only Semantics**
   * Raw payloads are stored as-is without destructive transformations, type coercions, or deletions.
   * Every write commits a new atomic version to the Delta Lake transaction log (`_delta_log/`), enabling point-in-time auditing and full reproducibility.

2. **Standardized Ingestion Metadata Columns**
   Every row ingested into Bronze is enriched with five audit columns plus an ingest partition date:
   * `_ingest_ts`: UTC ISO-8601 timestamp representing the exact ingestion time.
   * `_source_file`: The origin landing filename or streaming topic identifier (e.g., `kafka:txn.raw`).
   * `_batch_id`: A unique batch or pipeline run identifier.
   * `_schema_version`: Contract schema version (e.g., `v1.0`).
   * `_record_hash`: Deterministic SHA-256 fingerprint generated across payload values (ignoring ephemeral metadata).
   * `ingest_date`: Partitioning key formatted as `YYYY-MM-DD` for efficient partition pruning.

3. **Strict Idempotency**
   * Re-executing an ingestion job with an identical `_batch_id` replaces the previous batch slice atomically using Delta Lake transaction predicates (`_batch_id = '...'`).
   * Re-running the pipeline never duplicates records.

4. **Schema Drift Detection & Automatic Evolution (`drift_logger.py`)**
   * Incoming datasets are compared against existing Delta table schemas prior to commit.
   * If unexpected columns are detected (e.g. `promo_code` or `tax_rate_applied`), Delta's `mergeSchema` / `schema_mode="merge"` dynamically evolves the table schema.
   * Drift events are immediately logged into the `governance.schema_drift_log` table with `entity_name`, `batch_id`, `new_columns`, and timestamp for governance auditing.

5. **Quarantine Routing (`bronze_quarantine/`)**
   * Completely unparseable files, malformed records, or corrupted payloads are intercepted before entering Bronze tables.
   * Corrupted records are isolated in `bronze_quarantine/<entity>/batch_id=<batch_id>/` annotated with `quarantine_reason`, `source_file`, and `quarantined_at`.

6. **Dual Local / Cloud Support**
   * Native Python Delta Lake engine (`delta-rs`) enables high-speed local unit testing without JVM / Hadoop dependencies on Windows.
   * Cluster-ready PySpark jobs (`spark_session.py`, `ingest_stream.py`) provide production configs for AWS S3A connectors, MinIO local endpoints, and Delta extensions.

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_bronze_layer.py -v
```
- `test_bronze_batch_ingest_metadata`: Verifies all 6 metadata and partition columns exist with valid SHA-256 hashes.
- `test_bronze_idempotency`: Verifies re-ingesting the same batch ID produces identical row counts with zero duplicate explosion.
- `test_bronze_schema_drift_handling_and_logging`: Verifies schema merges and automatic entry generation in `schema_drift_log`.
- `test_bronze_quarantine_routing`: Verifies corrupt records are routed to quarantine and excluded from Bronze Delta tables.
- `test_bronze_partitioning_by_date`: Verifies files are partitioned under `ingest_date=YYYY-MM-DD`.
- `test_bronze_streaming_ingestion`: Verifies streaming micro-batch consumption into `bronze/transactions`.

