-- Dim Date
{{ config(materialized='table', tags=['pii_safe']) }}

SELECT DISTINCT
    txn_date as date_id,
    txn_date as calendar_date,
    substr(txn_date, 1, 4) as year,
    substr(txn_date, 6, 2) as month,
    substr(txn_date, 9, 2) as day
FROM {{ ref('stg_transactions') }}
WHERE txn_date IS NOT NULL

