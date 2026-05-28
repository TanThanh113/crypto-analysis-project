-- Dashboard Exchange Risk Daily Marting
{{ config(
    materialized='table',
    partition_by={"field": "feature_date", "data_type": "date", "granularity": "day"},
    cluster_by=['exchange_risk_level']
) }}

-- Get the latest snapshots
WITH daily_latest_by_symbol AS (

    SELECT *
    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY feature_date, symbol
        ORDER BY hour_ts DESC, feature_available_at DESC
    ) = 1

),

-- Basic calculations for summarizing data for a day.
agg AS (

    SELECT
        feature_date,
        MAX(hour_ts) AS latest_hour_ts,
        MAX(feature_available_at) AS latest_feature_available_at,
        COUNT(DISTINCT symbol) AS symbol_count,

        MAX(exchange_count) AS exchange_count,
        MAX(total_exchange_reserve_usd) AS total_exchange_reserve_usd,
        MAX(total_exchange_volume_24h_usd) AS total_exchange_volume_24h_usd,
        MAX(system_reserve_utilization) AS system_reserve_utilization,
        MAX(normalized_system_reserve_utilization) AS normalized_system_reserve_utilization,
        MAX(avg_exchange_trust_score) AS avg_exchange_trust_score,
        MAX(reserve_hhi) AS reserve_hhi,
        MAX(high_bank_run_risk_exchange_count) AS high_bank_run_risk_exchange_count,

        -- Find the top reserve exchange based on the total reserves.
        ARRAY_AGG(
            top_reserve_exchange IGNORE NULLS
            ORDER BY total_exchange_reserve_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reserve_exchange,

        -- Find the highest utilization exchange based on the normalized reserve utilization.
        ARRAY_AGG(
            highest_utilization_exchange IGNORE NULLS
            ORDER BY normalized_system_reserve_utilization DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_utilization_exchange,

        -- Find the highest utilization risk label based on the normalized reserve utilization.
        ARRAY_AGG(
            highest_utilization_risk_label IGNORE NULLS
            ORDER BY normalized_system_reserve_utilization DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_utilization_risk_label,

        AVG(liquidity_risk_score) AS liquidity_risk_score,
        AVG(overall_risk_score) AS overall_risk_score

    FROM daily_latest_by_symbol
    GROUP BY feature_date

),

-- Compare with the previous day's data.
with_lag AS (

    SELECT
        *,

        LAG(total_exchange_reserve_usd) OVER (
            ORDER BY feature_date
        ) AS previous_total_exchange_reserve_usd,

        LAG(total_exchange_volume_24h_usd) OVER (
            ORDER BY feature_date
        ) AS previous_total_exchange_volume_24h_usd,

        LAG(normalized_system_reserve_utilization) OVER (
            ORDER BY feature_date
        ) AS previous_normalized_system_reserve_utilization

    FROM agg

),

-- Final table with the standardized exchange risk data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(feature_date AS STRING), '|exchange_risk_daily'))) AS dashboard_exchange_risk_daily_sk,

        feature_date,
        latest_hour_ts,
        latest_feature_available_at,
        symbol_count,

        exchange_count,

        total_exchange_reserve_usd,
        previous_total_exchange_reserve_usd,

        -- The change in the reserves of exchanges in the previous day.
        SAFE_DIVIDE(
            total_exchange_reserve_usd - previous_total_exchange_reserve_usd,
            NULLIF(previous_total_exchange_reserve_usd, 0)
        ) AS exchange_reserve_change_1d,

        total_exchange_volume_24h_usd,
        previous_total_exchange_volume_24h_usd,

        -- The change in the volume of exchanges in the previous day.
        SAFE_DIVIDE(
            total_exchange_volume_24h_usd - previous_total_exchange_volume_24h_usd,
            NULLIF(previous_total_exchange_volume_24h_usd, 0)
        ) AS exchange_volume_change_1d,

        system_reserve_utilization,
        normalized_system_reserve_utilization,
        previous_normalized_system_reserve_utilization,

        normalized_system_reserve_utilization - previous_normalized_system_reserve_utilization
            AS normalized_reserve_utilization_change_1d,

        avg_exchange_trust_score,
        reserve_hhi,
        high_bank_run_risk_exchange_count,

        top_reserve_exchange,
        highest_utilization_exchange,
        highest_utilization_risk_label,

        liquidity_risk_score,
        overall_risk_score,

        -- Labeling the exchange risk score
        CASE
            WHEN COALESCE(high_bank_run_risk_exchange_count, 0) >= 2
                OR COALESCE(normalized_system_reserve_utilization, 0) >= 0.85
                THEN 'CRITICAL_EXCHANGE_RISK'
            WHEN COALESCE(high_bank_run_risk_exchange_count, 0) >= 1
                OR COALESCE(normalized_system_reserve_utilization, 0) >= 0.65
                THEN 'HIGH_EXCHANGE_RISK'
            WHEN COALESCE(normalized_system_reserve_utilization, 0) >= 0.40
                THEN 'MEDIUM_EXCHANGE_RISK'
            ELSE 'LOW_EXCHANGE_RISK'
        END AS exchange_risk_level,

        -- Labeling the reserve concentration
        CASE
            WHEN COALESCE(reserve_hhi, 0) >= 0.35 THEN 'HIGH_RESERVE_CONCENTRATION'
            WHEN COALESCE(reserve_hhi, 0) >= 0.20 THEN 'MEDIUM_RESERVE_CONCENTRATION'
            ELSE 'DIVERSIFIED_RESERVES'
        END AS reserve_concentration_label,

        -- Labeling the reserve trend
        CASE
            WHEN total_exchange_reserve_usd > previous_total_exchange_reserve_usd THEN 'RESERVES_INCREASING'
            WHEN total_exchange_reserve_usd < previous_total_exchange_reserve_usd THEN 'RESERVES_DECREASING'
            ELSE 'RESERVES_FLAT'
        END AS reserve_trend,

        -- Labeling the reserve utilization trend
        CASE
            WHEN normalized_system_reserve_utilization > previous_normalized_system_reserve_utilization
                THEN 'UTILIZATION_INCREASING'
            WHEN normalized_system_reserve_utilization < previous_normalized_system_reserve_utilization
                THEN 'UTILIZATION_DECREASING'
            ELSE 'UTILIZATION_FLAT'
        END AS reserve_utilization_trend,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM with_lag

)

SELECT *
FROM final