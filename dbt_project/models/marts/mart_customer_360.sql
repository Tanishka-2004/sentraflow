-- Mart Customer 360 (PII Safe & Governed)
{{ config(materialized='table', tags=['marts', 'finance_critical', 'pii_safe']) }}

SELECT
    c.customer_id,
    c.full_name as masked_name,
    c.pan as masked_pan,
    c.city,
    c.state,
    c.kyc_status,
    COUNT(DISTINCT a.account_id) as total_accounts,
    COUNT(f.txn_id) as total_transactions,
    ROUND(COALESCE(SUM(f.amount), 0.0), 2) as lifetime_spend_inr,
    ROUND(COALESCE(AVG(f.amount), 0.0), 2) as avg_spend_per_txn_inr,
    MAX(f.txn_ts) as last_active_ts
FROM {{ ref('dim_customer') }} c
LEFT JOIN {{ ref('dim_account') }} a ON c.customer_id = a.customer_id
LEFT JOIN {{ ref('fct_transactions') }} f ON c.customer_id = f.customer_id
WHERE c.is_current = 1
GROUP BY 1, 2, 3, 4, 5, 6

