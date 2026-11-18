-- Dim Account
{{ config(materialized='table', tags=['pii_safe']) }}

SELECT
    account_id,
    customer_id,
    account_number,
    ifsc,
    account_type,
    open_date,
    status,
    balance
FROM {{ ref('stg_accounts') }}

