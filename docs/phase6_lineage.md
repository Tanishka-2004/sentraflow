# Phase 6: Column-Level Lineage Tracing & Zero-Bypass Verification

## Overview
Phase 6 builds `lineage/`, an end-to-end **column-level lineage parsing, tracing, and audit engine** for SentraFlow. It traces financial data transformations across every layer of the Medallion architecture (Landing $\rightarrow$ Bronze $\rightarrow$ Gate $\rightarrow$ Silver $\rightarrow$ Gold) and mathematically proves that no unmasked PII ever bypasses the governance gate.

## Key Capabilities

1. **SQLGlot-Based Column-Level Parser (`sql_parser.py`)**
   * Parses compiled SQL queries and dbt star schema models into ASTs.
   * Resolves column dependencies, mappings, and transformation types:
     * `DIRECT`: Straight column pass-through.
     * `AGGREGATED`: Functions such as `SUM()`, `AVG()`, `COUNT()`.
     * `DERIVED`: Scalar calculations, `CASE` statements, string manipulations.
     * `MASKED`: Transformations passing through tokenization, partial masking, or redaction.

2. **Pipeline Tracker Decorator (`spark_tracker.py`)**
   * Provides `@track_lineage(inputs=[...], outputs=[...], column_map={...})` for decorating PySpark and Python ingestion / transformation steps.
   * Registers runtime execution metadata into `LineageRegistry`.

3. **Graph Traversal & Audit API (`store.py`)**
   * **Upstream Tracing (`trace_upstream`):** Traces backwards from any target column (e.g. `mart_customer_360.masked_pan`) all the way to its root origin file in the landing zone.
   * **Downstream Impact Analysis (`trace_downstream`):** Evaluates forward impact of changes to upstream schema columns across all dependent facts and marts.
   * **Zero-Bypass Governance Verification (`verify_zero_gate_bypasses`):**
     * Scans all lineage paths carrying PII from raw Bronze sources to Gold marts.
     * Enforces that every single edge passes through the governance masking gate (`passes_gate == True`).
     * Raises violation alerts if any unmasked path bypasses the gate.
   * **React Flow Graph Exporter (`get_react_flow_graph`):** Produces node and edge JSON structures consumed directly by the Next.js visual dashboard.

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_lineage.py -v
```
- `test_sqlglot_column_lineage_parsing`: Validates extraction of column dependencies, aliases, and `AGGREGATED`/`DIRECT` types.
- `test_track_lineage_decorator`: Validates runtime lineage recording for pipeline jobs.
- `test_upstream_trace_to_source`: Verifies multi-hop backwards graph traversal from Gold mart to root landing file.
- `test_downstream_impact_analysis`: Verifies forward blast-radius calculation for source schema changes.
- `test_zero_gate_bypass_enforcement`: Asserts clean pass for compliant pipelines and proves that injecting a rogue bypass edge is detected and flagged immediately.

