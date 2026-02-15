{{ config(materialized='incremental', unique_key='transaction_id') }}

WITH deduped_transactions AS (
    SELECT
        transaction_id,
        account_id,
        amount,
        related_account_id,
        status,
        transaction_type,
        transaction_time,
        load_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id
            ORDER BY transaction_time DESC
        ) AS rn
    FROM {{ ref('stg_transactions') }}
)

SELECT
    t.transaction_id,
    t.account_id,
    a.customer_id,
    t.amount,
    t.related_account_id,
    t.status,
    t.transaction_type,
    t.transaction_time,
    CURRENT_TIMESTAMP AS load_timestamp
FROM deduped_transactions t
LEFT JOIN {{ ref('stg_account') }} a
    ON t.account_id = a.account_id
WHERE t.rn = 1