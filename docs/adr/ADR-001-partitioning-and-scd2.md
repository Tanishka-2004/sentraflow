# ADR-001: Partitioning Strategy and SCD Type 2 Implementation in Delta Lake

## Status
Accepted

## Context
SentraFlow ingests multi-rail financial transactions, account snapshots, merchant registries, and customer demographics into a Medallion Lakehouse. The platform needs:
1. Low-latency point lookups and range scans on millions of transactions.
2. Low storage overhead without small-file proliferation.
3. Historical auditability of customer attribute mutations (address, pincode, KYC compliance status).

## Decision

### 1. Partitioning Strategy
- **`silver.transactions` (Fact):** Partitioned by `txn_date` (`YYYY-MM-DD`). Transactions are naturally append-heavy and queried by operational date ranges. Partitioning by day enables partition pruning during downstream dbt Gold mart transforms and feature store aggregations.
- **Dimensions (`customers`, `accounts`, `merchants`):** **Unpartitioned**. These tables have low-to-medium cardinality (< 1 million rows). Partitioning small dimension tables causes small-file fragmentation ("small file syndrome"), degrades metadata performance, and hurts Delta transaction commit latency. Instead, dimensions leverage Parquet column statistics and data skipping.

### 2. Slowly Changing Dimension (SCD Type 2) on `silver.customers`
- Implemented using Delta Lake atomic transaction semantics (`Delta MERGE`):
  - Tracks business mutations in: `address`, `city`, `state`, `pincode`, and `kyc_status`.
  - Maintains `valid_from`, `valid_to`, `is_current`, and surrogate key `cust_sk` (`SHA256(customer_id, valid_from)`).
  - Preserves full point-in-time state for regulatory compliance (RBI guidelines on KYC audits) without destructive overwrites.

### 3. Compaction and Maintenance
- Scheduled maintenance jobs run `OPTIMIZE` and `VACUUM` weekly to compact small partition files and expire tombstoned Delta snapshots older than 7 days.

