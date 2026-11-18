-- Singular Test: Revenue Reconciles between Silver and Gold within tolerance
-- Returns records if absolute difference exceeds 0.05 INR tolerance

WITH silver_revenue AS (
    SELECT
        ROUND(SUM(amount), 2) as silver_total_inr
    FROM silver_transactions
),
gold_revenue AS (
    SELECT
        ROUND(SUM(amount), 2) as gold_total_inr
    FROM {{ ref('fct_transactions') }}
)
SELECT
    s.silver_total_inr,
    g.gold_total_inr,
    abs(s.silver_total_inr - g.gold_total_inr) as discrepancy
FROM silver_revenue s
CROSS JOIN gold_revenue g
WHERE abs(s.silver_total_inr - g.gold_total_inr) > 0.05

