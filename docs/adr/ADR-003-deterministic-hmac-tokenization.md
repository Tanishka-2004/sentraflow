# ADR-003: Deterministic HMAC-SHA256 Tokenization vs Format-Preserving Encryption

## Status
Accepted

## Context
Sensitive identifiers such as Aadhaar IDs and PANs must be protected from exposure to downstream analysts and models while retaining the ability to perform high-performance analytical joins (e.g. joining `dim_customer` with `fct_transactions`).

## Decision
We chose **Keyed Deterministic HMAC-SHA256 Tokenization** over Format-Preserving Encryption (FPE / AES-FF1).

## Rationale
1. **Cryptographic Irreversibility:** HMAC-SHA256 is a one-way pseudorandom cryptographic function. Even if the transformed tokens are compromised, the raw Aadhaar numbers cannot be mathematically decrypted.
2. **Deterministic Joinability:** Generating `HMAC-SHA256(secret_key, raw_id)` yields identical token outputs for identical inputs, preserving referential integrity across Medallion tables.
3. **Key Rotation via Dual-Key Migration:** Supports key versioning (`key_version` column) and phased dual-token migration during KMS CMK rotation.
4. **Computational Performance:** Benchmarking indicates HMAC-SHA256 executes in sub-microseconds per record without specialized crypto hardware.

## Consequences
- The HMAC master key must be strictly protected in AWS KMS / Secrets Manager.
- Raw values can never be retrieved from tokens without access to the ingestion-layer mapping store.

