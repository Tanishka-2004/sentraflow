-- Dim Channel
{{ config(materialized='table', tags=['pii_safe']) }}

SELECT DISTINCT
    channel as channel_id,
    channel as channel_name,
    CASE 
        WHEN channel IN ('UPI', 'CARD') THEN 'DIGITAL_RETAIL'
        WHEN channel IN ('NEFT', 'IMPS') THEN 'INTERBANK_TRANSFER'
        ELSE 'CASH_TERMINAL'
    END as channel_category
FROM {{ ref('stg_transactions') }}

