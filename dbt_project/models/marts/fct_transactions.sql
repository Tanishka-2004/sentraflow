-- Fact Transactions
{{ config(materialized='table', tags=['finance_critical', 'pii_safe']) }}

SELECT
    t.txn_id,
    t.account_id,
    a.customer_id,
    c.cust_sk,
    t.merchant_id,
    t.channel as channel_id,
    t.txn_date as date_id,
    t.amount,
    t.currency,
    t.txn_ts,
    t.status,
    t.is_fraud
FROM {{ ref('stg_transactions') }} t
LEFT JOIN {{ ref('stg_accounts') }} a ON t.account_id = a.account_id
LEFT JOIN {{ ref('stg_customers') }} c ON a.customer_id = c.customer_id AND c.is_current = 1

