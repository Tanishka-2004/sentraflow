# ADR-002: Delta Lake over Apache Iceberg for Lakehouse Storage

## Status
Accepted

## Context
SentraFlow requires ACID transactions, time travel, schema evolution (`mergeSchema`), schema enforcement, partition pruning, and fast multi-dimensional clustering (`OPTIMIZE ... Z-ORDER BY`) across Bronze, Silver, and Gold layers. We evaluated Delta Lake and Apache Iceberg.

## Decision
We chose **Delta Lake 3.x / delta-rs** as the primary storage format.

## Rationale
1. **Local Developer Parity:** Through `deltalake` (`delta-rs`), Delta Lake provides 100% native Rust-backed ACID reads, writes, and partition management locally without requiring a heavyweight JVM or local Spark cluster.
2. **Schema Evolution:** Delta Lake's native `mergeSchema` and automatic quarantine integration gracefully accommodates inbound schema drift from upstream financial feeds.
3. **Z-ORDER Maturity:** Delta's multi-dimensional Z-ORDER clustering provides superior query latency on composite lookups (`customer_id`, `txn_ts`).
4. **Athena & Glue Native Support:** Delta tables can be queried directly via AWS Athena and registered in AWS Glue Data Catalog with zero external catalog bridges.

## Consequences
- PySpark and dbt-spark/dbt-athena models target Delta format.
- Vacuum operations must be scheduled weekly to manage log snapshot retention (`VACUUM RETAIN 168 HOURS`).

