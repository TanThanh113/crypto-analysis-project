-- Extract the latest data (Real-time snapshot) for each coin to display on the main indicator bar (KPI Widgets) of the Dashboard.
{{ config(materialized='table') }}

-- Get the latest record
WITH latest AS (

    SELECT *
    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY symbol
        ORDER BY hour_ts DESC, feature_available_at DESC
    ) = 1

),

-- Calculate how long ago the data was received to see if there is any congestion.
scored AS (

    SELECT
        *,
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            feature_available_at,
            MINUTE
        ) AS data_age_minutes

    FROM latest

),

-- Final table with the standardized KPI data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(symbol AS STRING), '|latest_kpi'))) AS dashboard_kpi_latest_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        data_age_minutes,

        close_price,
        return_1h,
        avg_return_24h,
        realized_volatility_24h,
        quote_volume,
        quote_volume_24h,

        market_momentum_score,
        social_sentiment_score,
        derivatives_risk_score,
        liquidity_risk_score,
        macro_risk_score,
        overall_risk_score,
        market_regime,
        core_signal,

        avg_annualized_funding_coin,
        avg_basis_pct,
        total_liq_usd,
        max_rank_score,
        top_squeeze_signal,
        avg_mark_iv,
        put_call_oi_ratio,
        social_weighted_avg_sentiment,
        total_stablecoin_market_cap_usd,
        total_exchange_reserve_usd,
        macro_risk_regime,
        crypto_etf_momentum_regime,

        -- The badge that is displayed on the KPI widget
        -- Check if it's new data and tag it.
        CASE
            WHEN data_age_minutes <= 90 THEN 'FRESH'
            WHEN data_age_minutes <= 240 THEN 'STALE'
            ELSE 'OLD'
        END AS freshness_status,

        -- Check if the risk score is high enough to warrant a badge.
        CASE
            WHEN overall_risk_score >= 80 THEN 'CRITICAL'
            WHEN overall_risk_score >= 65 THEN 'HIGH'
            WHEN overall_risk_score >= 45 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS risk_badge,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM scored

)

SELECT *
FROM final
ORDER BY symbol