{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'etf_indicators_raw') }}

),

cleaned AS (

    SELECT
        SAFE_CAST(date AS DATE) AS price_date,
        TIMESTAMP_SECONDS(SAFE_CAST(timestamp AS INT64)) AS price_at,

        UPPER(CAST(symbol AS STRING)) AS symbol,
        UPPER(CAST(ticker AS STRING)) AS ticker,
        LOWER(CAST(asset_class AS STRING)) AS asset_class,

        SAFE_CAST(open AS FLOAT64) AS open_price,
        SAFE_CAST(high AS FLOAT64) AS high_price,
        SAFE_CAST(low AS FLOAT64) AS low_price,
        SAFE_CAST(close AS FLOAT64) AS close_price,
        SAFE_CAST(adj_close AS FLOAT64) AS adj_close_price,
        SAFE_CAST(volume AS FLOAT64) AS volume,

        SAFE_CAST(vwap AS FLOAT64) AS vwap,
        SAFE_CAST(trade_count AS FLOAT64) AS trade_count,

        UPPER(CAST(exchange AS STRING)) AS exchange,
        UPPER(CAST(currency AS STRING)) AS currency,
        LOWER(CAST(timeframe AS STRING)) AS timeframe,

        CAST(source AS STRING) AS source,
        CAST(data_provider AS STRING) AS data_provider,
        CAST(run_id AS STRING) AS run_id,
        SAFE_CAST(ingestion_time AS TIMESTAMP) AS ingestion_time,

        CAST(year AS STRING) AS year,
        CAST(month AS STRING) AS month,
        CAST(day AS STRING) AS day

    FROM source_data
    WHERE LOWER(CAST(asset_class AS STRING)) = 'etf'

),

deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, price_date
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE symbol IS NOT NULL
      AND price_date IS NOT NULL
      AND close_price > 0
      AND open_price > 0
      AND high_price > 0
      AND low_price > 0
      AND volume >= 0
      AND high_price >= low_price

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1