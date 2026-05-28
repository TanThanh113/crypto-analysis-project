-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol', 'price_bucket_key'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous two days as a reference point.
WITH source_data AS (

    SELECT
        TIMESTAMP_TRUNC(snapshot_at, HOUR) AS hour_ts,
        symbol,
        price_bucket,
        CAST(ROUND(price_bucket, 2) AS STRING) AS price_bucket_key,

        snapshot_at,
        total_liq_usd_bucket,
        long_sum,
        short_sum,
        oi_avg,
        vol_sum,
        hit_count,
        avg_weighted_liq_ratio,
        avg_panic,
        avg_money_flow,
        distance_pct,
        weighted_liq_ratio,
        distance_decay,
        magnet_score,
        magnet_zscore,
        magnet_norm,
        squeeze_signal,
        panic_norm,
        hit_norm,
        rank_score,
        dominant_side,
        stress_level,
        ingestion_time

    FROM {{ ref('stg_liquidation_map') }}
    WHERE snapshot_at IS NOT NULL
      AND symbol IN ('BTC', 'ETH')
      AND price_bucket > 0

    {% if is_incremental() %}
      AND snapshot_at >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 2 DAY
          )
    {% endif %}

),

bucketed AS (

    SELECT
        hour_ts,
        symbol,
        price_bucket,
        price_bucket_key,

        -- Summarize some data collected hourly.
        SUM(total_liq_usd_bucket) AS total_liq_usd_bucket,
        SUM(long_sum) AS long_sum,
        SUM(short_sum) AS short_sum,
        AVG(oi_avg) AS oi_avg,
        SUM(vol_sum) AS vol_sum,
        SUM(hit_count) AS hit_count,

        -- Average some data collected hourly.
        AVG(avg_weighted_liq_ratio) AS avg_weighted_liq_ratio,
        AVG(avg_panic) AS avg_panic,
        AVG(avg_money_flow) AS avg_money_flow,
        AVG(distance_pct) AS distance_pct,
        AVG(weighted_liq_ratio) AS weighted_liq_ratio,
        AVG(distance_decay) AS distance_decay,

        -- Calculate the averages and sums of the data magnet collected hourly.
        SUM(magnet_score) AS magnet_score,
        AVG(magnet_zscore) AS magnet_zscore,
        AVG(magnet_norm) AS magnet_norm,

        -- Find the squeeze signal based on the rank score.
        ARRAY_AGG(
            squeeze_signal IGNORE NULLS
            ORDER BY rank_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS squeeze_signal,

        -- Find the maximum of some data collected per hour.
        MAX(panic_norm) AS panic_norm,
        MAX(hit_norm) AS hit_norm,
        MAX(rank_score) AS rank_score,

        -- Find the dominant side based on the total liquidation value.
        ARRAY_AGG(
            dominant_side IGNORE NULLS
            ORDER BY total_liq_usd_bucket DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS dominant_side,

        -- Find the dominant stress level based on the total liquidation value.
        ARRAY_AGG(
            stress_level IGNORE NULLS
            ORDER BY total_liq_usd_bucket DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS stress_level,

        -- Find the latest snapshot_at, loaded_at, and available_at.
        MAX(snapshot_at) AS latest_snapshot_at,
        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM source_data
    GROUP BY hour_ts, symbol, price_bucket, price_bucket_key

),

-- Rank the buckets based on the rank score, total liquidation value, and price bucket.
ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY hour_ts, symbol
            ORDER BY rank_score DESC, total_liq_usd_bucket DESC, price_bucket ASC
        ) AS bucket_rank_in_hour
    FROM bucketed

)

SELECT *
FROM ranked

-- -- To be sure, here we will only consider events from the previous two days.
{% if is_incremental() %}
WHERE hour_ts >= TIMESTAMP_SUB(
    COALESCE(
        (SELECT MAX(hour_ts) FROM {{ this }}),
        TIMESTAMP('1970-01-01')
    ),
    INTERVAL 2 DAY
)
{% endif %}