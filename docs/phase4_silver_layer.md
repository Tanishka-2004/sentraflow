# Phase 4: Silver Layer (Clean, Conformed, Masked, Deduplicated)

## Overview
Phase 4 implements the **Silver Layer** in `spark_jobs/silver/`. The Silver layer transforms raw, immutable Bronze data into clean, conformed, deduplicated, and masked datasets. It enforces data quality contracts with quarantine/reject routing and implements Slowly Changing Dimension Type 2 (SCD2) history tracking for customers.

## Architectural Components

1. **Cleaners & Standardisation (`cleaners.py`)**
   * **Phone Numbers:** Standardised to E.164 format (`+91XXXXXXXXXX`).
   * **State Names:** Normalized to official ISO 3166-2:IN codes (`Maharashtra` -> `IN-MH`, `Delhi` -> `IN-DL`, `Karnataka` -> `IN-KA`).
   * **Timestamps:** Canonicalized to UTC ISO-8601 strings.
   * **Monetary Values:** Sanitized into rounded two-decimal positive floats.

2. **Deduplication Engine (`deduplicator.py`)**
   * Implements window ranking over primary business keys (`customer_id`, `account_id`, `merchant_id`, `txn_id`).
   * Selects the most recent record by `_ingest_ts`, eliminating duplicate deliveries from streaming or landing batch retries.

3. **Data Quality Suite & Rejection Routing (`quality_checks.py`)**
   * Validates non-null primary keys, positive transactional amounts, masked PAN formatting, and referential integrity.
   * Failing records are routed to Delta table `silver_rejects/<entity>/` with `rejection_reason` and `rejected_at`.
   * Enforces a maximum rejection threshold (e.g. 20%): if the rejection rate exceeds the threshold, `DataQualityThresholdExceededError` aborts the pipeline.

4. **SCD Type 2 Customer Dimension (`scd2.py`)**
   * Tracks customer address moves, city/state relocations, and KYC status transitions (`PENDING` -> `VERIFIED`).
   * Generates deterministic surrogate keys `cust_sk`.
   * Maintains `valid_from`, `valid_to`, and `is_current` boolean flags using atomic Delta transactions.

5. **Silver Processor (`processor.py`)**
   * Orchestrates the full Bronze -> Governance Gate -> Clean & Standardize -> Dedupe -> Quality Validation -> SCD2 / Table Append flow.
   * Persists `silver.customers`, `silver.accounts`, `silver.merchants`, and `silver.transactions` (partitioned by `txn_date`).

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_silver_layer.py -v
```
- `test_cleaners_standardisation`: Verifies E.164 phone formatting, ISO state conversions, and UTC timestamps.
- `test_deduplicator`: Verifies latest `_ingest_ts` record selection across duplicates.
- `test_silver_quality_checks_and_rejects`: Verifies routing of bad records to `silver_rejects` Delta table.
- `test_silver_quality_threshold_breach`: Verifies hard failure when rejection rate exceeds threshold.
- `test_scd2_lifecycle`: Verifies initial load, attribute mutation, version expiration, and surrogate key generation.
- `test_silver_processor_end_to_end`: Verifies full multi-entity processing pipeline and partition layouts.

