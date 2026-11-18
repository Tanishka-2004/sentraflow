-- Staging model for silver transactions
{{ config(materialized='view', tags=['pii_safe']) }}

SELECT
    txn_id,
    account_id,
    merchant_id,
    amount,
    currency,
    channel,
    txn_ts,
    device_id,
    ip_address,
    lat,
    lon,
    status,
    is_fraud,
    txn_date
FROM silver_transactions

