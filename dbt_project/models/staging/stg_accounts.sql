-- Staging model for silver accounts
{{ config(materialized='view', tags=['pii_safe']) }}

SELECT
    account_id,
    customer_id,
    account_number,
    ifsc,
    account_type,
    open_date,
    status,
    balance
FROM silver_accounts

