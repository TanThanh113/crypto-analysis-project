-- Dashboard Macro ETF Daily Marting
{{ config(
    materialized='table',
    partition_by={"field": "feature_date", "data_type": "date", "granularity": "day"},
    cluster_by=['macro_risk_regime', 'crypto_etf_momentum_regime']
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

        MAX(macro_price_date) AS macro_price_date,
        MAX(sp500_return_1d) AS sp500_return_1d,
        MAX(nasdaq_return_1d) AS nasdaq_return_1d,
        MAX(gold_return_1d) AS gold_return_1d,
        MAX(vix_return_1d) AS vix_return_1d,
        MAX(oil_return_1d) AS oil_return_1d,
        MAX(sp500_return_5d) AS sp500_return_5d,
        MAX(nasdaq_return_5d) AS nasdaq_return_5d,
        MAX(vix_return_5d) AS vix_return_5d,
        MAX(nasdaq_sp500_ratio) AS nasdaq_sp500_ratio,
        MAX(safe_haven_bid_1d) AS safe_haven_bid_1d,

        -- Find the macro risk regime based on the macro risk score.
        ARRAY_AGG(
            macro_risk_regime IGNORE NULLS
            ORDER BY hour_ts DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS macro_risk_regime,

        MAX(etf_price_date) AS etf_price_date,
        MAX(btc_etf_volume) AS btc_etf_volume,
        MAX(eth_etf_volume) AS eth_etf_volume,
        MAX(btc_etf_volume_weighted_return_1d) AS btc_etf_volume_weighted_return_1d,
        MAX(eth_etf_volume_weighted_return_1d) AS eth_etf_volume_weighted_return_1d,
        MAX(total_etf_volume_weighted_return_1d) AS total_etf_volume_weighted_return_1d,
        MAX(btc_etf_flow_proxy) AS btc_etf_flow_proxy,
        MAX(eth_etf_flow_proxy) AS eth_etf_flow_proxy,
        MAX(ibit_return_1d) AS ibit_return_1d,
        MAX(etha_return_1d) AS etha_return_1d,

        -- Find the crypto ETF momentum regime based on the crypto ETF momentum score.
        ARRAY_AGG(
            crypto_etf_momentum_regime IGNORE NULLS
            ORDER BY hour_ts DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS crypto_etf_momentum_regime,

        AVG(macro_risk_score) AS macro_risk_score,
        AVG(overall_risk_score) AS overall_risk_score

    FROM daily_latest_by_symbol
    GROUP BY feature_date

),

-- Compare with the previous day's data.
with_lag AS (

    SELECT
        *,

        LAG(macro_risk_score) OVER (
            ORDER BY feature_date
        ) AS previous_macro_risk_score,

        LAG(btc_etf_flow_proxy) OVER (
            ORDER BY feature_date
        ) AS previous_btc_etf_flow_proxy,

        LAG(eth_etf_flow_proxy) OVER (
            ORDER BY feature_date
        ) AS previous_eth_etf_flow_proxy,

        LAG(total_etf_volume_weighted_return_1d) OVER (
            ORDER BY feature_date
        ) AS previous_total_etf_volume_weighted_return_1d

    FROM agg

),

-- Final table with the standardized macro ETF data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(feature_date AS STRING), '|macro_etf_daily'))) AS dashboard_macro_etf_daily_sk,

        feature_date,
        latest_hour_ts,
        latest_feature_available_at,
        symbol_count,

        macro_price_date,
        sp500_return_1d,
        nasdaq_return_1d,
        gold_return_1d,
        vix_return_1d,
        oil_return_1d,
        sp500_return_5d,
        nasdaq_return_5d,
        vix_return_5d,
        nasdaq_sp500_ratio,
        safe_haven_bid_1d,
        macro_risk_regime,

        etf_price_date,
        btc_etf_volume,
        eth_etf_volume,
        btc_etf_volume_weighted_return_1d,
        eth_etf_volume_weighted_return_1d,
        total_etf_volume_weighted_return_1d,
        previous_total_etf_volume_weighted_return_1d,
        btc_etf_flow_proxy,
        previous_btc_etf_flow_proxy,
        eth_etf_flow_proxy,
        previous_eth_etf_flow_proxy,
        ibit_return_1d,
        etha_return_1d,
        crypto_etf_momentum_regime,

        macro_risk_score,
        previous_macro_risk_score,
        -- The change in the macro risk score in the previous day.
        macro_risk_score - previous_macro_risk_score AS macro_risk_score_change_1d,
        overall_risk_score,

        -- Labeling the macro risk score
        CASE
            WHEN COALESCE(macro_risk_score, 0) >= 75 THEN 'MACRO_RISK_OFF'
            WHEN COALESCE(macro_risk_score, 0) >= 55 THEN 'MACRO_DEFENSIVE'
            WHEN COALESCE(macro_risk_score, 0) <= 25 THEN 'MACRO_RISK_ON'
            ELSE 'MACRO_NEUTRAL'
        END AS macro_dashboard_label,

        -- Labeling the ETF demand
        CASE
            WHEN COALESCE(btc_etf_flow_proxy, 0) > 0
                AND COALESCE(eth_etf_flow_proxy, 0) > 0 THEN 'BROAD_INSTITUTIONAL_DEMAND'
            WHEN COALESCE(btc_etf_flow_proxy, 0) > 0 THEN 'BTC_LED_INSTITUTIONAL_DEMAND'
            WHEN COALESCE(eth_etf_flow_proxy, 0) > 0 THEN 'ETH_LED_INSTITUTIONAL_DEMAND'
            WHEN COALESCE(btc_etf_flow_proxy, 0) < 0
                AND COALESCE(eth_etf_flow_proxy, 0) < 0 THEN 'INSTITUTIONAL_OUTFLOW_PRESSURE'
            ELSE 'ETF_NEUTRAL'
        END AS etf_demand_label,

        -- Labeling the ETF flow trend
        CASE
            WHEN COALESCE(btc_etf_flow_proxy, 0) > COALESCE(previous_btc_etf_flow_proxy, 0) THEN 'BTC_ETF_FLOW_IMPROVING'
            WHEN COALESCE(btc_etf_flow_proxy, 0) < COALESCE(previous_btc_etf_flow_proxy, 0) THEN 'BTC_ETF_FLOW_WEAKENING'
            ELSE 'BTC_ETF_FLOW_FLAT'
        END AS btc_etf_flow_trend,

        -- Labeling the ETF flow trend
        CASE
            WHEN COALESCE(eth_etf_flow_proxy, 0) > COALESCE(previous_eth_etf_flow_proxy, 0) THEN 'ETH_ETF_FLOW_IMPROVING'
            WHEN COALESCE(eth_etf_flow_proxy, 0) < COALESCE(previous_eth_etf_flow_proxy, 0) THEN 'ETH_ETF_FLOW_WEAKENING'
            ELSE 'ETH_ETF_FLOW_FLAT'
        END AS eth_etf_flow_trend,

        -- Labeling the macro risk trend
        CASE
            WHEN COALESCE(macro_risk_score, 0) > COALESCE(previous_macro_risk_score, 0) THEN 'MACRO_RISK_INCREASING'
            WHEN COALESCE(macro_risk_score, 0) < COALESCE(previous_macro_risk_score, 0) THEN 'MACRO_RISK_DECREASING'
            ELSE 'MACRO_RISK_FLAT'
        END AS macro_risk_trend,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM with_lag

)

SELECT *
FROM final