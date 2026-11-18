-- Mart Data Quality Scorecard
{{ config(materialized='table', tags=['marts', 'finance_critical', 'pii_safe']) }}

SELECT
    'TRANSACTIONS' as dataset_name,
    COUNT(*) as total_records_evaluated,
    SUM(CASE WHEN amount <= 0 THEN 1 ELSE 0 END) as non_positive_amounts,
    SUM(CASE WHEN account_id IS NULL THEN 1 ELSE 0 END) as orphan_account_txns,
    ROUND(100.0 * (1.0 - (SUM(CASE WHEN amount <= 0 OR account_id IS NULL THEN 1 ELSE 0 END) * 1.0 / MAX(1, COUNT(*)))), 2) as quality_score_pct
FROM {{ ref('fct_transactions') }}
UNION ALL
SELECT
    'CUSTOMERS' as dataset_name,
    COUNT(*) as total_records_evaluated,
    SUM(CASE WHEN pan IS NULL THEN 1 ELSE 0 END) as null_pans,
    SUM(CASE WHEN kyc_status NOT IN ('VERIFIED', 'PENDING', 'REJECTED') THEN 1 ELSE 0 END) as invalid_kyc_statuses,
    ROUND(100.0 * (1.0 - (SUM(CASE WHEN pan IS NULL THEN 1 ELSE 0 END) * 1.0 / MAX(1, COUNT(*)))), 2) as quality_score_pct
FROM {{ ref('dim_customer') }}

