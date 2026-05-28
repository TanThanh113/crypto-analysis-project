{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

WITH source_data AS (

    SELECT
        TIMESTAMP_TRUNC(window_start, HOUR) AS hour_ts,
        symbol,
        window_start,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        vwap_price

    FROM {{ ref('stg_streaming_candlestick_1min') }}

    {% if is_incremental() %}
      WHERE window_start >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 2 DAY
          )
    {% endif %}

),

agg AS (

    SELECT
        hour_ts,
        symbol,

        ARRAY_AGG(open_price IGNORE NULLS ORDER BY window_start ASC LIMIT 1)[SAFE_OFFSET(0)] AS open_price,
        MAX(high_price) AS high_price,
        MIN(low_price) AS low_price,
        ARRAY_AGG(close_price IGNORE NULLS ORDER BY window_start DESC LIMIT 1)[SAFE_OFFSET(0)] AS close_price,

        SUM(volume) AS base_volume,

        SAFE_DIVIDE(
            SUM(vwap_price * volume),
            NULLIF(SUM(volume), 0)
        ) AS vwap_price,

        COUNT(*) AS minute_candle_count,
        MAX(window_start) AS latest_minute_at,
        CURRENT_TIMESTAMP() AS loaded_at,
        CURRENT_TIMESTAMP() AS available_at

    FROM source_data
    GROUP BY hour_ts, symbol

)

SELECT *
FROM agg
WHERE close_price IS NOT NULL