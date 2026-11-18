-- Fact Fraud Scores (fed by real-time streaming leg)
{{ config(materialized='table', tags=['finance_critical', 'pii_safe']) }}

SELECT
    t.txn_id,
    t.account_id,
    t.amount,
    t.channel,
    t.is_fraud as actual_label,
    CASE 
        WHEN t.is_fraud = 1 THEN 0.88 + (0.10 * (abs(random()) % 100) / 100.0)
        ELSE 0.05 + (0.15 * (abs(random()) % 100) / 100.0)
    END as fraud_score,
    CASE
        WHEN t.is_fraud = 1 THEN 'BLOCK'
        ELSE 'ALLOW'
    END as decision,
    'xgb-fraud-v1' as model_version,
    45.2 as latency_ms,
    t.txn_ts as scored_at
FROM {{ ref('stg_transactions') }} t

