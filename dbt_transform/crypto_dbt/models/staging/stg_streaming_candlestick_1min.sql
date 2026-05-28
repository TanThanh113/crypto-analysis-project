{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('streaming_crypto', 'candlestick_1min') }}

),

cleaned AS (

    SELECT
        TIMESTAMP(window_start) AS window_start,
        TIMESTAMP(window_end) AS window_end,
        UPPER(CAST(symbol AS STRING)) AS symbol,
        SAFE_CAST(trade_id AS INT64) AS trade_id,

        SAFE_CAST(open_price AS FLOAT64) AS open_price,
        SAFE_CAST(high_price AS FLOAT64) AS high_price,
        SAFE_CAST(low_price AS FLOAT64) AS low_price,
        SAFE_CAST(close_price AS FLOAT64) AS close_price,
        SAFE_CAST(volume AS FLOAT64) AS volume,
        SAFE_CAST(VWAP AS FLOAT64) AS vwap_price,

        SAFE_CAST(sma20 AS FLOAT64) AS sma20,
        SAFE_CAST(upper_band AS FLOAT64) AS upper_band,
        SAFE_CAST(lower_band AS FLOAT64) AS lower_band

    FROM source_data
    WHERE window_start IS NOT NULL
      AND symbol IS NOT NULL
      AND close_price > 0

)

SELECT *
FROM cleaned