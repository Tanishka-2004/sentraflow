-- Mart Fraud Engine Operational & Accuracy KPIs
{{ config(materialized='table', tags=['marts', 'finance_critical', 'pii_safe']) }}

SELECT
    COUNT(*) as total_scored_transactions,
    SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END) as total_blocked_alerts,
    ROUND(100.0 * SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END) / MAX(1, COUNT(*)), 2) as alert_rate_pct,
    SUM(CASE WHEN decision = 'BLOCK' AND actual_label = 1 THEN 1 ELSE 0 END) as true_positive_count,
    SUM(CASE WHEN decision = 'BLOCK' AND actual_label = 0 THEN 1 ELSE 0 END) as false_positive_count,
    ROUND(
        100.0 * SUM(CASE WHEN decision = 'BLOCK' AND actual_label = 1 THEN 1 ELSE 0 END) 
        / MAX(1, SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)), 2
    ) as precision_pct,
    ROUND(AVG(latency_ms), 1) as avg_scoring_latency_ms
FROM {{ ref('fct_fraud_scores') }}

