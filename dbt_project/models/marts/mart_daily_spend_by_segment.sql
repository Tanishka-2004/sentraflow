-- Mart Daily Spend by Customer Segment & Payment Rail
{{ config(materialized='table', tags=['marts', 'finance_critical', 'pii_safe']) }}

SELECT
    f.date_id,
    COALESCE(c.date_of_birth, 'UNKNOWN') as age_band,
    f.channel_id,
    COALESCE(c.state, 'UNKNOWN') as state_code,
    COUNT(f.txn_id) as total_txns,
    ROUND(SUM(f.amount), 2) as total_volume_inr,
    ROUND(AVG(f.amount), 2) as avg_ticket_size_inr
FROM {{ ref('fct_transactions') }} f
LEFT JOIN {{ ref('stg_customers') }} c ON f.customer_id = c.customer_id AND c.is_current = 1
GROUP BY 1, 2, 3, 4

