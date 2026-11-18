# Phase 1: Synthetic Financial Data Generator

## Overview
Phase 1 implements `data_generator/`, an enterprise-grade synthetic data generation engine tailored for Indian financial ecosystems. It creates realistic customer demographics, bank accounts, merchants, and transactional payments across multiple payment rails (`UPI`, `CARD`, `NEFT`, `IMPS`, `ATM`) in Indian Rupees (`INR`).

## Core Components Built

1. **Synthetic Aadhaar & Verhoeff Checksum Engine (`verhoeff.py`)**
   * **Problem:** In a financial lakehouse containing PII, synthetic IDs must never collide with real government identification (UIDAI Aadhaar).
   * **Solution:** Aadhaar numbers use the Verhoeff dihedral group $D_5$ checksum algorithm. Our generator calculates the valid check digit and deliberately mutates it `(check + 1) % 10`, ensuring every generated 12-digit number **strictly fails the Verhoeff checksum**.

2. **Entities & Schemas (`entities.py`)**
   * `Customer`: UUID, full name, email, phone, PAN, synthetic Aadhaar, DOB, address, city, state, pincode, KYC status (`VERIFIED`, `PENDING`, `REJECTED`), timestamps.
   * `Account`: UUID, customer ID, account number (11-16 digits), bank IFSC (`SBIN`, `HDFC`, `ICIC`, `AXIS`, etc.), account type (`SAVINGS`, `CURRENT`, `SALARY`), status (`ACTIVE`, `DORMANT`, `FROZEN`), initial balance.
   * `Merchant`: Merchant ID, name, Merchant Category Code (`MCC`), city, risk tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   * `Transaction`: UUID, account ID, merchant ID, amount (INR), channel, timestamp, device ID, IP address, coordinates (lat/lon), status, and hidden evaluation label `is_fraud`.

3. **Dirty Data Injection Engine (`generator.py`)**
   * Seeded, deterministic generation (`Faker`, `random.Random`, `np.random.default_rng`).
   * Configurable `dirty_rate`:
     * Malformed PANs (violating regex `[A-Z]{5}[0-9]{4}[A-Z]`).
     * Malformed phone numbers (non-10 digits, invalid prefixes).
     * Null fields in non-key columns.
     * Duplicate rows to test deduplication in Silver.
     * Late-arriving events (timestamps shifted 5-14 days into past).
     * Schema drift injection (dynamic columns like `promo_code`).

4. **Complex Fraud Pattern Injection (`generator.py`)**
   * Target fraud rate of ~1-2%:
     * **Velocity Bursts:** Multiple rapid transactions (<90s) from the same account.
     * **Impossible Travel:** High-speed geo-distance jumps (e.g. Mumbai to Delhi in 15 minutes).
     * **High-Value Night Payments:** Unusually large transfers (>₹85,000) between 01:00 AM and 04:30 AM.
     * **New Device + High Amount:** Unrecognized device fingerprint with elevated transaction amount.
     * **Merchant Risk Spikes:** Transfers routed to critical-risk merchants / MCCs (`7995`, `6051`).
     * **Card Testing Micro-Transactions:** Rapid ₹1 to ₹5 authorization probes followed by account draining.

5. **SCD Type 2 Mutation Generator (`generator.py`)**
   * Emits customer attribute mutations (address, pincode, KYC status progression) preserving the immutable `customer_id` with updated timestamps to feed Delta Lake SCD2 merges.

6. **Batch Landing & Streaming Producer (`writer.py`, `producer.py`, `cli.py`)**
   * **Batch Mode:** Exports partitioned landing datasets in Parquet (Snappy-compressed via `pyarrow`) and CSV.
   * **Streaming Mode:** Streams transactional payloads to Apache Kafka topic `txn.raw` with configurable events-per-second (EPS) and local fallback.

## Running the Data Generator CLI

```bash
# Generate 10,000 customers and 50,000 transactions with 1.5% fraud rate
python data_generator/cli.py --customers 10000 --txns 50000 --seed 42 --format parquet --output-dir ./landing --with-scd-updates
```

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_data_generator.py -v
```
- `test_verhoeff_checksum_algorithm`: 100% verification that synthetic Aadhaar IDs fail Verhoeff.
- `test_clean_pan_regex`: Verifies adherence to income tax PAN formats.
- `test_customer_generation`: Validates entity integrity and field schemas.
- `test_dirty_data_injection`: Validates corrupted rows appear when dirty rate > 0.
- `test_fraud_patterns_injection`: Validates injection and tagging of all 6 fraud patterns.
- `test_scd_customer_updates`: Validates mutating updates for SCD Type 2 dimension tables.
- `test_batch_landing_export`: Tests Parquet and CSV output generation and readability.
- `test_seed_reproducibility`: Validates deterministic repeatability across seeds.

