-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

WITH trades AS (
    SELECT
        TIMESTAMP_TRUNC(trade_ts, HOUR) AS hour_ts,
        base_symbol AS symbol,
        symbol AS pair_symbol,
        trade_id,
        trade_ts,
        price,
        quantity,
        quote_quantity,
        LOWER(CAST(is_buyer_maker AS STRING)) IN ('true', '1') AS is_buyer_maker,
        ingestion_time

    FROM {{ ref('stg_binance_trades') }}
    WHERE trade_ts IS NOT NULL
      AND price > 0
      AND quantity > 0
      AND quote_quantity > 0

    {% if is_incremental() %}
      AND trade_ts >= TIMESTAMP_SUB(
            COALESCE((SELECT MAX(hour_ts) FROM {{ this }}), TIMESTAMP('1970-01-01')),
            INTERVAL 3 DAY
          )
    {% endif %}
),
hourly AS(
    SELECT
        hour_ts,
        symbol,
        ANY_VALUE(pair_symbol) AS pair_symbol,

        -- Candlestick - OHLCV
        ARRAY_AGG(price ORDER BY trade_ts ASC, trade_id ASC LIMIT 1)[OFFSET(0)] AS open_price,
        MAX(price) AS high_price,
        MIN(price) AS low_price,
        ARRAY_AGG(price ORDER BY trade_ts DESC, trade_id DESC LIMIT 1)[OFFSET(0)] AS close_price,
        SAFE_DIVIDE(SUM(price * quantity), NULLIF(SUM(quantity), 0)) AS vwap_price,

        -- Caculate simple metrics (volume)
        COUNT(*) AS trade_count,
        COUNT(DISTINCT trade_id) AS unique_trade_count,
        SUM(quantity) AS base_volume,
        SUM(quote_quantity) AS quote_volume,

        -- Caculate taker pressure metrics
        -- Binance is_buyer_maker=true usually means sell taker pressure.
        SUM(IF(is_buyer_maker, quote_quantity, 0)) AS taker_sell_quote_volume,
        SUM(IF(NOT is_buyer_maker, quote_quantity, 0)) AS taker_buy_quote_volume,
        SAFE_DIVIDE(
            SUM(IF(NOT is_buyer_maker, quote_quantity, 0)),
            NULLIF(SUM(quote_quantity), 0)
        ) AS taker_buy_quote_ratio,

        -- Caculate simple metrics (time)
        MIN(trade_ts) AS first_trade_at,
        MAX(trade_ts) AS last_trade_at,
        MAX(ingestion_time) AS loaded_at,

        -- Binance daily Vision data is only available after the daily collector runs.
        TIMESTAMP(DATETIME(DATE_ADD(DATE(hour_ts), INTERVAL 1 DAY), TIME '04:30:00'), 'UTC') AS available_at

    FROM trades
    GROUP BY hour_ts, symbol
),

with_returns AS (
    SELECT
        *,

        -- Calculate Simple Returns
        SAFE_DIVIDE(
            close_price - LAG(close_price) OVER (PARTITION BY symbol ORDER BY hour_ts),
            NULLIF(LAG(close_price) OVER (PARTITION BY symbol ORDER BY hour_ts), 0)
        ) AS return_1h,

        -- Calculate Log Returns(Train model)
        CASE
            WHEN LAG(close_price) OVER (PARTITION BY symbol ORDER BY hour_ts) > 0
            THEN LN(SAFE_DIVIDE(close_price, LAG(close_price) OVER (PARTITION BY symbol ORDER BY hour_ts)))
        END AS log_return_1h
    FROM hourly
),

-- Features that help in training the model
features AS (
    SELECT
        *,
        -- Calculate Sum of Quote Volume
        SUM(quote_volume) OVER (
            PARTITION BY symbol ORDER BY hour_ts ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS quote_volume_24h,

        -- Calculate Rolling Metrics of Simple Returns
        AVG(return_1h) OVER (
            PARTITION BY symbol ORDER BY hour_ts ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS avg_return_24h,    

        -- Caculate Standard Deviation of Log Returns (Volatility measure)
        STDDEV_SAMP(log_return_1h) OVER (
            PARTITION BY symbol ORDER BY hour_ts ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS realized_volatility_24h,

        -- Caculate Z-Score of Quote Volume
        SAFE_DIVIDE(
            quote_volume - AVG(quote_volume) OVER (PARTITION BY symbol ORDER BY hour_ts ROWS BETWEEN 23 PRECEDING AND CURRENT ROW),
            NULLIF(STDDEV_SAMP(quote_volume) OVER (PARTITION BY symbol ORDER BY hour_ts ROWS BETWEEN 23 PRECEDING AND CURRENT ROW), 0)
        ) AS quote_volume_zscore_24h
    FROM with_returns
)

SELECT *
FROM features

{% if is_incremental() %}
where hour_ts >= timestamp_sub(
    coalesce((select max(hour_ts) from {{ this }}), timestamp('1970-01-01')),
    interval 2 day
)
{% endif %}

