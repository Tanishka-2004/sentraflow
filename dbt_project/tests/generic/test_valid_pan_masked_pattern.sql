{% test valid_pan_masked_pattern(model, column_name) %}

SELECT
    *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND NOT ({{ column_name }} LIKE 'XXXXX____X')

{% endtest %}

