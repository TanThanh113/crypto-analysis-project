-- Dashboard Liquidation Heatmap displays the liquidation buckets and their distributions.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_liquidation_heatmap_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol', 'bucket_rank_in_hour']
) }}

-- Specify data from the previous 14 days to avoid data errors, delayed data, etc. (liquidation buckets)
WITH buckets AS (

    SELECT *
    FROM {{ ref('int_liquidation_bucket_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 14 DAY
          )
    {% endif %}

),

-- Specify data from the previous 14 days to avoid data errors, delayed data, etc.
market AS (

    SELECT
        hour_ts,
        symbol,
        close_price,
        top_liq_price_bucket,
        top_squeeze_signal,
        derivatives_risk_score,
        overall_risk_score,
        market_regime,
        core_signal

    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE

    {% if is_incremental() %}
      AND hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 14 DAY
          )
    {% endif %}

),

-- Join the liquidation buckets with the market data
joined AS (

    SELECT
        b.*,
        m.close_price,
        m.top_liq_price_bucket,
        m.top_squeeze_signal AS hourly_top_squeeze_signal,
        m.derivatives_risk_score,
        m.overall_risk_score,
        m.market_regime,
        m.core_signal

    FROM buckets AS b
    LEFT JOIN market AS m
        ON b.hour_ts = m.hour_ts
       AND b.symbol = m.symbol

),

final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(hour_ts AS STRING),
                    '|',
                    symbol,
                    '|',
                    COALESCE(CAST(price_bucket_key AS STRING), CAST(ROUND(price_bucket, 2) AS STRING)),
                    '|liquidation_heatmap'
                )
            )
        ) AS dashboard_liquidation_heatmap_sk,

        -- The section of the dashboard where the metric is displayed
        hour_ts,
        DATE(hour_ts) AS feature_date,
        symbol,

        price_bucket,
        price_bucket_key,
        close_price,

        SAFE_DIVIDE(price_bucket - close_price, NULLIF(close_price, 0)) AS bucket_distance_ratio,
        distance_pct,

        total_liq_usd_bucket,
        long_sum,
        short_sum,

        -- Calculate the difference between the long and short positions within the bucket.
        -- Calculate whether, at a specific price level, the amount of money being liquidated by the Long side or the Short side is greater.
        SAFE_DIVIDE(
            COALESCE(long_sum, 0) - COALESCE(short_sum, 0),
            NULLIF(COALESCE(long_sum, 0) + COALESCE(short_sum, 0), 0)
        ) AS long_short_bucket_imbalance,

        -- Calculate the percentage of Long positions within the total Long and Short positions.
        SAFE_DIVIDE(
            COALESCE(long_sum, 0),
            NULLIF(COALESCE(long_sum, 0) + COALESCE(short_sum, 0), 0)
        ) AS long_liq_share,    

        -- Calculate the percentage of Short positions within the total Long and Short positions.
        SAFE_DIVIDE(
            COALESCE(short_sum, 0),
            NULLIF(COALESCE(long_sum, 0) + COALESCE(short_sum, 0), 0)
        ) AS short_liq_share,

        -- he section of the dashboard where the metric is displayed
        oi_avg,
        vol_sum,
        hit_count,

        avg_weighted_liq_ratio,
        avg_panic,
        avg_money_flow,
        weighted_liq_ratio,
        distance_decay,
        magnet_score,
        magnet_zscore,
        magnet_norm,
        panic_norm,
        hit_norm,
        rank_score,
        bucket_rank_in_hour,
        squeeze_signal,
        dominant_side,
        stress_level,

        -- Labeling the bucket location
        -- Is this liquidation zone above or below the current price
        CASE
            WHEN close_price IS NULL THEN 'UNKNOWN'
            WHEN price_bucket > close_price THEN 'ABOVE_PRICE'
            WHEN price_bucket < close_price THEN 'BELOW_PRICE'
            ELSE 'AT_PRICE'
        END AS bucket_location,

        -- Measure the distance of the liquidation zone from the spot price.
        CASE
            WHEN ABS(COALESCE(distance_pct, 999)) <= 1 THEN 'NEAR_SPOT'
            WHEN ABS(COALESCE(distance_pct, 999)) <= 3 THEN 'MID_RANGE'
            WHEN ABS(COALESCE(distance_pct, 999)) <= 7 THEN 'FAR_RANGE'
            ELSE 'TAIL_RANGE'
        END AS distance_band,

        -- Labeling the heatmap intensity
        CASE
            WHEN COALESCE(rank_score, 0) >= 0.75 THEN 'EXTREME_CLUSTER'
            WHEN COALESCE(rank_score, 0) >= 0.50 THEN 'HIGH_CLUSTER'
            WHEN COALESCE(rank_score, 0) >= 0.25 THEN 'MEDIUM_CLUSTER'
            ELSE 'LOW_CLUSTER'
        END AS heatmap_intensity_label,

        -- Processing color intensity for heat maps.
        GREATEST(
            0,
            LEAST(
                100,
                COALESCE(rank_score, 0) * 60
                + COALESCE(panic_norm, 0) * 20
                + ABS(COALESCE(magnet_norm, 0)) * 20
            )
        ) AS heatmap_intensity_score,

        CASE
            WHEN bucket_rank_in_hour = 1 THEN TRUE
            ELSE FALSE
        END AS is_top_bucket_in_hour,

        -- Mark the most dangerous liquidation zone.
        CASE
            WHEN price_bucket = top_liq_price_bucket THEN TRUE
            ELSE FALSE
        END AS is_hourly_top_liq_bucket,

        top_liq_price_bucket,
        hourly_top_squeeze_signal,

        latest_snapshot_at,
        loaded_at,
        available_at,

        derivatives_risk_score,
        overall_risk_score,
        market_regime,
        core_signal,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM joined

)

SELECT *
FROM final