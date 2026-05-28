{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='ml_label_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- This model creates supervised ML labels.
-- At each hour, it looks forward 1h, 4h, and 24h to calculate future returns.
-- These labels are used only for training/evaluation, not for live prediction.

-- Specify data from the previous 35 days to avoid data errors, delayed data, etc.
WITH incremental_bound AS (

    SELECT
        {% if is_incremental() %}
            TIMESTAMP_SUB(
                COALESCE(
                    (SELECT MAX(hour_ts) FROM {{ this }}),
                    TIMESTAMP('1970-01-01')
                ),
                INTERVAL 35 DAY
            ) AS output_start_hour
        {% else %}
            TIMESTAMP('1970-01-01') AS output_start_hour
        {% endif %}

),

price_series AS (

    SELECT
        f.hour_ts,
        f.feature_date,
        f.symbol,
        f.close_price

    FROM {{ ref('mart_ml_features_hourly') }} AS f
    CROSS JOIN incremental_bound AS b

    WHERE f.close_price IS NOT NULL
      AND f.hour_ts IS NOT NULL
      AND f.symbol IN ('BTC', 'ETH')
      AND f.hour_ts >= b.output_start_hour

),

-- Look ahead to future close prices. LEAD(close_price, 4) means close price 4 hours after the current row.
future_prices AS (

    SELECT
        hour_ts,
        feature_date,
        symbol,
        close_price,

        -- Calculate the future close price 1 hour ahead.
        LEAD(close_price, 1) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS future_close_price_1h,

        -- Calculate the future close price 4 hours ahead.
        LEAD(close_price, 4) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS future_close_price_4h,

        -- Calculate the future close price 24 hours ahead.
        LEAD(close_price, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS future_close_price_24h

    FROM price_series

),

-- Convert future prices into future returns.
-- These become regression targets or inputs for classification labels.
returns AS (

    SELECT
        *,
        -- Calculate the future return of 1 hour.
        SAFE_DIVIDE(
            future_close_price_1h - close_price,
            NULLIF(close_price, 0)
        ) AS future_return_1h,

        -- Calculate the future return of 4 hours.
        SAFE_DIVIDE(
            future_close_price_4h - close_price,
            NULLIF(close_price, 0)
        ) AS future_return_4h,

        -- Calculate the future return of 24 hours.
        SAFE_DIVIDE(
            future_close_price_24h - close_price,
            NULLIF(close_price, 0)
        ) AS future_return_24h,

        -- Calculate the future log return of 1 hour.
        CASE
            WHEN close_price > 0
                AND future_close_price_1h > 0
                THEN LN(future_close_price_1h / close_price)
        END AS future_log_return_1h

    FROM future_prices

),

-- Future 24h realized volatility.
-- Uses the next 24 one-hour log returns from the current timestamp.
volatility AS (

    SELECT
        *,
        -- Calculate the future volatility of 24 hours.(standard deviation)
        STDDEV_SAMP(future_log_return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING
        ) AS future_volatility_24h,

        -- Calculate the number of future log returns of 24 hours.
        COUNT(future_log_return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING
        ) AS future_return_count_24h

    FROM returns

),

-- Classify future returns into UP / DOWN / FLAT.
-- Thresholds match the ML target catalog:
-- 1h:  ±0.10%
-- 4h:  ±0.30%
-- 24h: ±1.00%
classified AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(hour_ts AS STRING),
                    '|',
                    CAST(symbol AS STRING),
                    '|ml_labels_v1'
                )
            )
        ) AS ml_label_sk,

        -- The section of the feature AI is learning from
        hour_ts,
        feature_date,
        symbol,
        close_price,

        future_close_price_1h,
        future_close_price_4h,
        future_close_price_24h,

        future_return_1h,
        future_return_4h,
        future_return_24h,
        future_volatility_24h,
        future_return_count_24h,

        -- Classify future returns into UP / DOWN / FLAT.
        CASE
            WHEN future_return_1h IS NULL THEN NULL
            WHEN future_return_1h > 0.001 THEN 'UP'
            WHEN future_return_1h < -0.001 THEN 'DOWN'
            ELSE 'FLAT'
        END AS future_direction_1h,

        CASE
            WHEN future_return_4h IS NULL THEN NULL
            WHEN future_return_4h > 0.003 THEN 'UP'
            WHEN future_return_4h < -0.003 THEN 'DOWN'
            ELSE 'FLAT'
        END AS future_direction_4h,

        CASE
            WHEN future_return_24h IS NULL THEN NULL
            WHEN future_return_24h > 0.010 THEN 'UP'
            WHEN future_return_24h < -0.010 THEN 'DOWN'
            ELSE 'FLAT'
        END AS future_direction_24h,

        -- Binary target for simple ML classifier.
        -- UP = 1, DOWN = 0, FLAT = NULL.
        -- Training script can filter out NULL rows for binary classification.
        CASE
            WHEN future_return_4h IS NULL THEN NULL
            WHEN future_return_4h > 0.003 THEN 1
            WHEN future_return_4h < -0.003 THEN 0
            ELSE NULL
        END AS binary_direction_4h_excluding_flat,

        -- Sample weight gives more importance to larger future moves.
        -- Flat/small moves receive lower weight.
        CASE
            WHEN future_return_4h IS NULL THEN NULL
            WHEN ABS(future_return_4h) <= 0.003 THEN 0.50
            WHEN ABS(future_return_4h) <= 0.010 THEN 1.00
            WHEN ABS(future_return_4h) <= 0.030 THEN 1.50
            ELSE 2.00
        END AS sample_weight_4h,

        -- Label availability flags.
        -- Latest rows will not have future labels yet, which is expected.
        future_return_1h IS NOT NULL AS is_label_1h_available,
        future_return_4h IS NOT NULL AS is_label_4h_available,
        future_return_24h IS NOT NULL AS is_label_24h_available,
        future_return_count_24h = 24 AS is_volatility_24h_available,

        future_return_1h IS NOT NULL
            AND future_return_4h IS NOT NULL
            AND future_return_24h IS NOT NULL
            AND future_return_count_24h = 24
            AS is_label_available,

        -- When the full 24h label becomes safe to use.
        TIMESTAMP_ADD(hour_ts, INTERVAL 24 HOUR) AS label_available_at,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM volatility

)

SELECT *
FROM classified