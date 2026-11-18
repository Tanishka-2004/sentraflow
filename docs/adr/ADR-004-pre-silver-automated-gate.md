# ADR-004: Pre-Silver Automated Security Gate vs Post-Hoc Policy Auditing

## Status
Accepted

## Context
Many data platforms rely on "post-hoc" audit scanners or retrospective data discovery tools to find PII leaks after data is already materialized in analytical data lakes. In banking and financial compliance, a single unmasked PII record exposed to downstream BI or ML pipelines constitutes a critical regulatory breach.

## Decision
We implemented a **Pre-Silver Hard-Stop Automated Governance Gate (`spark_jobs/governance/gate.py`)**.

## Rationale
1. **Preventive Enforcement:** Data cannot physically be written to Silver or Gold without passing through the gate. The gate verifies 0% residual PII through content-based regex and classification scanning.
2. **Hard Pipeline Failure:** If even a single unmasked PAN, email, or Aadhaar number is detected in the transformed payload, the gate fails with an exception, blocks the batch, and emits a high-priority alert.
3. **IAM Boundary Backing:** The IAM policy exclusively allows `spark-gate-role` to write to S3 Silver (`s3:PutObject`). No developer or batch job can bypass this constraint.
4. **Audit Immutability:** Gate runs output cryptographically signed audit certifications to `governance.pii_gate_audit`.

## Consequences
- Upstream changes introducing schema drift or unclassified PII columns will halt the batch pipeline until classification policies are updated.

