-- Dashboard Liquidity Risk Daily Marting
{{ config(
    materialized='table',
    partition_by={"field": "feature_date", "data_type": "date", "granularity": "day"},
    cluster_by=['liquidity_risk_level']
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

        MAX(total_stablecoin_market_cap_usd) AS total_stablecoin_market_cap_usd,
        MAX(total_stablecoin_volume_24h_usd) AS total_stablecoin_volume_24h_usd,
        MAX(stablecoin_volume_to_mcap) AS stablecoin_volume_to_mcap,
        MAX(mcap_weighted_peg_deviation_pct) AS mcap_weighted_peg_deviation_pct,
        MAX(max_abs_peg_deviation_pct) AS max_abs_peg_deviation_pct,
        MAX(max_depeg_risk_score) AS max_depeg_risk_score,
        MAX(depeg_risk_coin_count) AS depeg_risk_coin_count,
        MAX(usdt_dominance_pct) AS usdt_dominance_pct,
        MAX(usdc_dominance_pct) AS usdc_dominance_pct,

        ARRAY_AGG(
            worst_peg_symbol IGNORE NULLS
            ORDER BY max_abs_peg_deviation_pct DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_symbol,

        ARRAY_AGG(
            worst_peg_regime IGNORE NULLS
            ORDER BY max_abs_peg_deviation_pct DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_regime,

        MAX(total_exchange_reserve_usd) AS total_exchange_reserve_usd,
        MAX(total_exchange_volume_24h_usd) AS total_exchange_volume_24h_usd,
        MAX(system_reserve_utilization) AS system_reserve_utilization,
        MAX(normalized_system_reserve_utilization) AS normalized_system_reserve_utilization,
        MAX(avg_exchange_trust_score) AS avg_exchange_trust_score,
        MAX(reserve_hhi) AS reserve_hhi,
        MAX(high_bank_run_risk_exchange_count) AS high_bank_run_risk_exchange_count,
        MAX(top_reserve_exchange) AS top_reserve_exchange,
        MAX(highest_utilization_risk_label) AS highest_utilization_risk_label,
        MAX(highest_utilization_exchange) AS highest_utilization_exchange,

        AVG(liquidity_risk_score) AS liquidity_risk_score,
        AVG(overall_risk_score) AS overall_risk_score

    FROM daily_latest_by_symbol
    GROUP BY feature_date

),

-- Compare with the previous day's data.
with_lag AS (

    SELECT
        *,

        LAG(total_stablecoin_market_cap_usd) OVER (
            ORDER BY feature_date
        ) AS previous_total_stablecoin_market_cap_usd,

        LAG(total_exchange_reserve_usd) OVER (
            ORDER BY feature_date
        ) AS previous_total_exchange_reserve_usd

    FROM agg

),

-- Final table with the standardized liquidity risk data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(feature_date AS STRING), '|liquidity_risk_daily'))) AS dashboard_liquidity_risk_daily_sk,

        -- The section of the dashboard where the metric is displayed
        feature_date,
        latest_hour_ts,
        latest_feature_available_at,
        symbol_count,

        total_stablecoin_market_cap_usd,
        previous_total_stablecoin_market_cap_usd,

        -- The change in the market cap of stablecoins in the previous day.
        SAFE_DIVIDE(
            total_stablecoin_market_cap_usd - previous_total_stablecoin_market_cap_usd,
            NULLIF(previous_total_stablecoin_market_cap_usd, 0)
        ) AS stablecoin_market_cap_change_1d,

        total_stablecoin_volume_24h_usd,
        stablecoin_volume_to_mcap,
        mcap_weighted_peg_deviation_pct,
        max_abs_peg_deviation_pct,
        max_depeg_risk_score,
        depeg_risk_coin_count,
        usdt_dominance_pct,
        usdc_dominance_pct,
        worst_peg_symbol,
        worst_peg_regime,

        total_exchange_reserve_usd,
        previous_total_exchange_reserve_usd,

        -- The change in the reserves of exchanges in the previous day.
        SAFE_DIVIDE(
            total_exchange_reserve_usd - previous_total_exchange_reserve_usd,
            NULLIF(previous_total_exchange_reserve_usd, 0)
        ) AS exchange_reserve_change_1d,

        total_exchange_volume_24h_usd,
        system_reserve_utilization,
        normalized_system_reserve_utilization,
        avg_exchange_trust_score,
        reserve_hhi,
        high_bank_run_risk_exchange_count,
        top_reserve_exchange,
        highest_utilization_risk_label,
        highest_utilization_exchange,

        liquidity_risk_score,
        overall_risk_score,

        -- Labeling the liquidity risk score
        CASE
            WHEN COALESCE(liquidity_risk_score, 0) >= 80 THEN 'CRITICAL_LIQUIDITY_RISK'
            WHEN COALESCE(liquidity_risk_score, 0) >= 65 THEN 'HIGH_LIQUIDITY_RISK'
            WHEN COALESCE(liquidity_risk_score, 0) >= 40 THEN 'MEDIUM_LIQUIDITY_RISK'
            ELSE 'LOW_LIQUIDITY_RISK'
        END AS liquidity_risk_level,

        -- Labeling the stablecoin peg status
        CASE
            WHEN COALESCE(max_abs_peg_deviation_pct, 0) >= 2 THEN 'DEPEG_ALERT'
            WHEN COALESCE(max_abs_peg_deviation_pct, 0) >= 0.5 THEN 'PEG_WATCH'
            ELSE 'PEG_STABLE'
        END AS stablecoin_peg_status,
    
        -- Labeling the liquidity trend
        CASE
            WHEN total_stablecoin_market_cap_usd > previous_total_stablecoin_market_cap_usd THEN 'LIQUIDITY_EXPANDING'
            WHEN total_stablecoin_market_cap_usd < previous_total_stablecoin_market_cap_usd THEN 'LIQUIDITY_CONTRACTING'
            ELSE 'LIQUIDITY_FLAT'
        END AS stablecoin_liquidity_trend,

        -- Labeling the exchange reserve trend
        CASE
            WHEN total_exchange_reserve_usd > previous_total_exchange_reserve_usd THEN 'RESERVES_EXPANDING'
            WHEN total_exchange_reserve_usd < previous_total_exchange_reserve_usd THEN 'RESERVES_CONTRACTING'
            ELSE 'RESERVES_FLAT'
        END AS exchange_reserve_trend,

        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM with_lag

)

SELECT *
FROM final