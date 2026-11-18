-- Dim Customer (SCD Type 2)
{{ config(materialized='table', tags=['pii_safe']) }}

SELECT
    cust_sk,
    customer_id,
    full_name,
    email,
    phone,
    pan,
    date_of_birth as age_band,
    city,
    state,
    pincode,
    kyc_status,
    valid_from,
    valid_to,
    is_current
FROM {{ ref('stg_customers') }}

