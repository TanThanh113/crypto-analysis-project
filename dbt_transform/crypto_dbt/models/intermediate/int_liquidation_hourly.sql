-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous two days as a reference point.
WITH buckets AS (

    SELECT *
    FROM {{ ref('int_liquidation_bucket_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 2 DAY
          )
    {% endif %}

),

aggregated AS (

    SELECT
        hour_ts,
        symbol,
        
        -- Count the number of liquidation buckets.
        COUNT(*) AS liquidation_bucket_count,

        -- Summarize some data collected hourly.
        SUM(total_liq_usd_bucket) AS total_liq_usd,
        SUM(long_sum) AS long_liq_sum,
        SUM(short_sum) AS short_liq_sum,

        -- Compare the difference between total long and total short positions.
        SUM(long_sum) - SUM(short_sum) AS net_long_short_liq_usd,

        -- Calculate the ratio of the difference between total long and total short positions.
        SAFE_DIVIDE(
            SUM(long_sum) - SUM(short_sum),
            NULLIF(SUM(long_sum) + SUM(short_sum), 0)
        ) AS net_long_short_liq_ratio,

        -- Summarize and Average some data collected hourly.
        SUM(vol_sum) AS liquidation_related_volume_usd,
        SUM(hit_count) AS liquidation_hit_count,
        AVG(oi_avg) AS avg_open_interest,

        -- Calculate the averages of data weighted by liquidation ratio.
        AVG(weighted_liq_ratio) AS avg_weighted_liq_ratio,

        -- Calculate weighted liquidation ratio according to the weight of total liquidation value.
        SAFE_DIVIDE(
            SUM(weighted_liq_ratio * total_liq_usd_bucket),
            NULLIF(SUM(total_liq_usd_bucket), 0)
        ) AS liq_weighted_liq_ratio,

        -- Find the maximum absolute value of weighted liquidation ratio.
        MAX(ABS(weighted_liq_ratio)) AS max_abs_weighted_liq_ratio,

        -- Calculate the averages and max values of data collected hourly.
        AVG(avg_money_flow) AS avg_money_flow,
        AVG(avg_panic) AS avg_panic,
        AVG(panic_norm) AS avg_panic_norm,
        MAX(panic_norm) AS max_panic_norm,
        
        -- Calculate the averages and max values of data magnet collected hourly.
        AVG(magnet_norm) AS avg_magnet_norm,
        MAX(magnet_norm) AS max_magnet_norm,
        MAX(rank_score) AS max_rank_score,

        -- Find the top price bucket based on the rank score and total liquidation value.
        ARRAY_AGG(
            price_bucket IGNORE NULLS
            ORDER BY rank_score DESC, total_liq_usd_bucket DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_liq_price_bucket,
        
        -- Find the top distance percentile based on the rank score and total liquidation value.
        ARRAY_AGG(
            distance_pct IGNORE NULLS
            ORDER BY rank_score DESC, total_liq_usd_bucket DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_liq_distance_pct,

        -- Find the top squeeze signal based on the rank score and total liquidation value.
        ARRAY_AGG(
            squeeze_signal IGNORE NULLS
            ORDER BY rank_score DESC, total_liq_usd_bucket DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_squeeze_signal,

        -- Find the dominant side based on the total liquidation value and rank score.
        ARRAY_AGG(
            dominant_side IGNORE NULLS
            ORDER BY total_liq_usd_bucket DESC, rank_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS dominant_side_by_liq,
        
        -- Find the top stress level based on the total liquidation value and rank score.
        ARRAY_AGG(
            stress_level IGNORE NULLS
            ORDER BY total_liq_usd_bucket DESC, rank_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_stress_level,

        -- Calculate the sum based on the conditions
        COUNTIF(squeeze_signal = 'SHORT_SQUEEZE_SETUP') AS short_squeeze_bucket_count,
        COUNTIF(squeeze_signal = 'LONG_SQUEEZE_SETUP') AS long_squeeze_bucket_count,
        COUNTIF(stress_level = 'HIGH') AS high_stress_bucket_count,

        -- The proportion of certain data sets in the total data set
        SAFE_DIVIDE(
            COUNTIF(squeeze_signal = 'SHORT_SQUEEZE_SETUP'),
            NULLIF(COUNT(*), 0)
        ) AS short_squeeze_bucket_ratio,

        SAFE_DIVIDE(
            COUNTIF(squeeze_signal = 'LONG_SQUEEZE_SETUP'),
            NULLIF(COUNT(*), 0)
        ) AS long_squeeze_bucket_ratio,

        SAFE_DIVIDE(
            COUNTIF(stress_level = 'HIGH'),
            NULLIF(COUNT(*), 0)
        ) AS high_stress_bucket_ratio,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    price_bucket,
                    total_liq_usd_bucket,
                    long_sum,
                    short_sum,
                    distance_pct,
                    magnet_norm,
                    panic_norm,
                    rank_score,
                    squeeze_signal,
                    dominant_side,
                    stress_level
                )
                ORDER BY rank_score DESC, total_liq_usd_bucket DESC
                LIMIT 10
            )
        ) AS top_10_buckets_json,

        -- Calculate max latest_snapshot_at, loaded_at, and available_at.
        MAX(latest_snapshot_at) AS latest_snapshot_at,
        MAX(loaded_at) AS loaded_at,
        MAX(available_at) AS available_at

    FROM buckets
    GROUP BY hour_ts, symbol

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM aggregated

{% if is_incremental() %}
WHERE hour_ts >= TIMESTAMP_SUB(
    COALESCE(
        (SELECT MAX(hour_ts) FROM {{ this }}),
        TIMESTAMP('1970-01-01')
    ),
    INTERVAL 2 DAY
)
{% endif %}