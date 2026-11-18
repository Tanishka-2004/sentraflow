-- Dim Merchant
{{ config(materialized='table', tags=['pii_safe']) }}

SELECT
    merchant_id,
    merchant_name,
    mcc_code,
    city,
    risk_tier
FROM {{ ref('stg_merchants') }}

