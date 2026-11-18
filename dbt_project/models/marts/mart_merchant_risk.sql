-- Mart Merchant Risk & Volume Analysis
{{ config(materialized='table', tags=['marts', 'finance_critical', 'pii_safe']) }}

SELECT
    m.risk_tier,
    m.mcc_code,
    COUNT(f.txn_id) as total_txns,
    ROUND(SUM(f.amount), 2) as total_volume_inr,
    ROUND(AVG(f.amount), 2) as avg_amount_inr,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as fraud_txn_count,
    ROUND(100.0 * SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) / MAX(1, COUNT(f.txn_id)), 2) as fraud_rate_pct
FROM {{ ref('fct_transactions') }} f
JOIN {{ ref('dim_merchant') }} m ON f.merchant_id = m.merchant_id
GROUP BY 1, 2

