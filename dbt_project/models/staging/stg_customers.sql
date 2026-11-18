-- Staging model for masked and conformed silver customers
{{ config(materialized='view', tags=['pii_safe']) }}

SELECT
    cust_sk,
    customer_id,
    full_name,
    email,
    phone,
    pan,
    aadhaar_id,
    date_of_birth,
    address,
    city,
    state,
    pincode,
    kyc_status,
    valid_from,
    valid_to,
    is_current
FROM silver_customers

