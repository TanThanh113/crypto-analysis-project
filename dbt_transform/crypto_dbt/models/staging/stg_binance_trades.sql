{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'binance_trades_raw') }}

),

cleaned AS (

    SELECT
        UPPER(symbol) AS symbol,
        REGEXP_REPLACE(UPPER(symbol), r'USDT$', '') AS base_symbol,

        SAFE_CAST(trade_id AS INT64) AS trade_id,
        SAFE_CAST(trade_ts AS TIMESTAMP) AS trade_ts,
        SAFE_CAST(trade_time AS FLOAT64) AS trade_time,

        SAFE_CAST(price AS FLOAT64) AS price,
        SAFE_CAST(quantity AS FLOAT64) AS quantity,
        SAFE_CAST(quote_quantity AS FLOAT64) AS quote_quantity,

        LOWER(CAST(is_buyer_maker AS STRING)) AS is_buyer_maker,
        LOWER(CAST(is_best_match AS STRING)) AS is_best_match,

        source,
        data_provider,
        run_id,
        SAFE_CAST(ingestion_time AS TIMESTAMP) AS ingestion_time,

        CAST(year AS STRING) AS year,
        CAST(month AS STRING) AS month,
        CAST(day AS STRING) AS day

    FROM source_data

),

deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, trade_id
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE symbol IS NOT NULL
      AND trade_id IS NOT NULL
      AND trade_ts IS NOT NULL
      AND price > 0
      AND quantity > 0
      AND quote_quantity > 0

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1