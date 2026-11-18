-- Staging model for silver merchants
{{ config(materialized='view', tags=['pii_safe']) }}

SELECT
    merchant_id,
    name as merchant_name,
    mcc_code,
    city,
    risk_tier
FROM silver_merchants

