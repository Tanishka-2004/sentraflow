# Phase 3: Governance Layer (The Automated PII-Masking Gate)

## Overview
Phase 3 builds the core security and regulatory compliance pillar of SentraFlow: an automated **PII-Masking Gate** operating in `spark_jobs/governance/` between the Bronze and Silver Lakehouse layers. The gate guarantees that no direct or quasi-identifier PII can ever reach Silver or Gold tables unmasked.

## Key Subsystems

1. **Classification Registry (`classification_registry.yaml`)**
   * Configures column-level classifications across `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `PII_DIRECT`, and `PII_QUASI`.
   * Enforces organizational policies on identities, financials, and locations.

2. **Dual-Method PII Scanner (`pii_scanner.py`)**
   * **Metadata Inspection:** Catalog lookup for known schema attributes.
   * **Content Pattern & Heuristic Scanning:** Evaluates sample values using regex evaluators for Indian PAN, Aadhaar-like numbers, phone numbers, emails, bank accounts, and IPv4 addresses.
   * Distinguishes between raw unmasked data and properly masked tokens (`XXXXX1234X`, `h_...`, `TOK_...`).

3. **Policy-Driven Masking Engine (`masking.py`, `policies.yaml`)**
   * **Deterministic HMAC-SHA256 Tokenization:** Generates joinable pseudonyms (`TOK_<hexdigest>`) for customer names and devices.
   * **Partial Masking:** Protects PANs (`XXXXX1234X`), phone numbers (`XXXXXX3210`), and bank account numbers (`XXXXXXXX1234`).
   * **Format-Preserving Hashing:** Obfuscates email localparts while preserving domain names (`h_ab12cd34@domain.com`).
   * **Generalization:** Converts exact Date of Birth to age bands (`25-34`, `35-49`), pincodes to 3-digit regional prefixes (`400XXX`), and IP addresses to `/16` subnets (`192.168.X.X`).
   * **Key Rotation:** Embeds `_masking_key_version` in output datasets.

4. **The Hard-Fail Gate (`gate.py`)**
   * Pre-scans input data from Bronze.
   * Executes masking policies.
   * **Post-scans output to mathematically verify 0% residual PII.**
   * Emits digital signatures (HMAC-SHA256) committed to `governance.pii_gate_audit`.
   * **Hard Fail Enforcement:** If any unmasked PII is found in post-scan (e.g. an injected shadow column), it throws `PIIGateViolationError`, logs a `BLOCKED` audit record, and aborts Silver promotion.

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_governance_gate.py -v
```
- `test_pii_scanner_metadata_and_regex`: Verifies regex detection of PAN, phone, email, Aadhaar-like IDs, and catalog metadata.
- `test_masking_engine_techniques`: Verifies HMAC tokenization, partial masking, generalisation, and email hashing.
- `test_pii_gate_normal_pass`: Verifies successful masking, post-scan verification, signed audit log entry, and output generation.
- `test_pii_gate_deliberate_leak_blocks_pipeline`: Deliberately injects an unmasked PAN column `shadow_unmasked_pan`, verifies gate immediately blocks the batch, raises `PIIGateViolationError`, and records `BLOCKED` in `pii_gate_audit`.

