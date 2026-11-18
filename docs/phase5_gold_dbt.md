# Phase 5: Gold Layer with dbt Star Schema and Analytical Marts

## Overview
Phase 5 implements the **Gold Layer** in `dbt_project/`. The Gold layer organizes clean Silver data into an enterprise Star Schema (Dimensions & Facts) and produces analytical data marts powering the fraud engine, customer 360 view, and business intelligence dashboards.

## Models Built

1. **Staging Layer (`models/staging/`)**
   * `stg_customers.sql`: Staging view over `silver_customers`.
   * `stg_accounts.sql`: Staging view over `silver_accounts`.
   * `stg_merchants.sql`: Staging view over `silver_merchants`.
   * `stg_transactions.sql`: Staging view over `silver_transactions`.

2. **Star Schema Dimensions & Facts (`models/marts/`)**
   * **Dimensions:**
     * `dim_customer.sql`: SCD Type 2 dimension preserving historical versions with `cust_sk`, `valid_from`, `valid_to`, `is_current`.
     * `dim_account.sql`: Bank accounts with masked account numbers and current balances.
     * `dim_merchant.sql`: Merchant directory with category classification and risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
     * `dim_channel.sql`: Payment channels (`UPI`, `CARD`, `NEFT`, `IMPS`, `ATM`) categorized into digital retail, interbank, and cash.
     * `dim_date.sql`: Calendar date dimension with year, month, day attributes.
   * **Facts:**
     * `fct_transactions.sql`: Core fact table linking transaction amounts to dimension foreign keys (`cust_sk`, `account_id`, `merchant_id`, `date_id`, `channel_id`).
     * `fct_fraud_scores.sql`: Fact table storing real-time streaming inference scores, decisions (`ALLOW`, `BLOCK`), and latency metrics.

3. **Analytical Marts (`models/marts/`)**
   * `mart_daily_spend_by_segment.sql`: Aggregates volume and ticket size by customer age band, payment rail, and state.
   * `mart_merchant_risk.sql`: Evaluates fraud incidence rate and transaction volumes by merchant risk tiers and MCC codes.
   * `mart_customer_360.sql`: PII-safe customer summary detailing active accounts, lifetime volume, and transaction frequency.
   * `mart_fraud_kpis.sql`: Executive KPI summary reporting alert rate percentage, precision, and average scoring latency.
   * `mart_data_quality_scorecard.sql`: Automated scorecard measuring dataset health and quality pass rates.

4. **Testing Suite & Reconciliation (`tests/`)**
   * **Generic Tests:** `unique`, `not_null`, `accepted_values`, `positive_amount`, `valid_pan_masked_pattern`.
   * **Singular Reconciliation Test:** `assert_silver_gold_revenue_reconciliation.sql` reconciles financial amounts between Silver and Gold within 0.05 INR tolerance.
   * **Governance Tags:** All models tagged with `pii_safe` and `finance_critical`.

## Unit Test Coverage
Run with:
```bash
python -m pytest tests/test_gold_dbt.py -v
```
- `test_dbt_star_schema_and_marts_execution`: Verifies end-to-end materialization of all 12 dimensions, facts, and marts.
- `test_dbt_tests_and_singular_revenue_reconciliation`: Verifies data quality assertions and exact financial revenue reconciliation between Silver and Gold.
- `test_dbt_project_configuration_and_tags`: Verifies dbt configuration contracts and governance tags.

