-- Dashboard AI Signal Marting
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_ai_signal_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol', 'dashboard_signal']
) }}

-- Specify data from the previous 14 days to avoid data errors, delayed data, etc.
WITH fact AS (

    SELECT *
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

signal_base AS (

    SELECT
        *,
        -- The signal that is displayed on the dashboard
        CASE
            WHEN core_signal = 'REDUCE_RISK' THEN 'RISK_REDUCTION'
            WHEN market_regime = 'SYSTEM_RISK' THEN 'SYSTEM_RISK_ALERT'
            WHEN core_signal = 'BULLISH'
                AND COALESCE(overall_risk_score, 0) < 60 THEN 'BULLISH_SETUP'
            WHEN core_signal = 'BEARISH' THEN 'BEARISH_SETUP'
            ELSE 'NEUTRAL_WAIT'
        END AS dashboard_signal,

        -- The signal confidence score
        --- Meaning: The AI ​​starts with an average score of 50. 
        --- If market conditions are good, it gains up to 40% more points. 
        --- If people online are enthusiastic, it gains up to 20% more points. 
        --- But if global economic risks increase, it loses up to 20% more points.
        GREATEST(
            0,
            LEAST(
                100,
                CASE
                    WHEN core_signal = 'BULLISH' THEN
                        50
                        + COALESCE(market_momentum_score, 0) * 0.40
                        + COALESCE(social_sentiment_score, 0) * 0.20
                        - COALESCE(overall_risk_score, 0) * 0.20

                    WHEN core_signal = 'BEARISH' THEN
                        50
                        + ABS(COALESCE(market_momentum_score, 0)) * 0.40
                        + GREATEST(0, -COALESCE(social_sentiment_score, 0)) * 0.20
                        + COALESCE(overall_risk_score, 0) * 0.20

                    WHEN core_signal = 'REDUCE_RISK'
                        OR market_regime = 'SYSTEM_RISK' THEN
                        60
                        + COALESCE(overall_risk_score, 0) * 0.40

                    ELSE
                        50
                        - ABS(COALESCE(market_momentum_score, 0)) * 0.10
                END
            )
        ) AS signal_confidence_score

    FROM fact

),

-- Final table with the standardized AI signal data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|ai_signal'))) AS dashboard_ai_signal_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        close_price,
        return_1h,
        avg_return_24h,
        realized_volatility_24h,
        quote_volume_zscore_24h,

        market_momentum_score,
        social_sentiment_score,
        derivatives_risk_score,
        liquidity_risk_score,
        macro_risk_score,
        overall_risk_score,

        market_regime,
        core_signal,
        dashboard_signal,
        signal_confidence_score,

        top_squeeze_signal,
        dominant_funding_regime,
        macro_risk_regime,
        crypto_etf_momentum_regime,
        worst_peg_symbol,
        worst_peg_regime,
        highest_utilization_risk_label,

        -- Labeling the signal confidence score
        CASE
            WHEN COALESCE(signal_confidence_score, 0) >= 80 THEN 'HIGH_CONFIDENCE'
            WHEN COALESCE(signal_confidence_score, 0) >= 60 THEN 'MEDIUM_CONFIDENCE'
            ELSE 'LOW_CONFIDENCE'
        END AS signal_confidence_label,

        -- Labeling the signal direction
        CASE
            WHEN dashboard_signal IN ('RISK_REDUCTION', 'SYSTEM_RISK_ALERT') THEN 'DEFENSIVE'
            WHEN dashboard_signal = 'BEARISH_SETUP' THEN 'BEARISH'
            WHEN dashboard_signal = 'BULLISH_SETUP' THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END AS dashboard_signal_direction,

        -- Labeling the signal sort order
        CASE
            WHEN dashboard_signal IN ('RISK_REDUCTION', 'SYSTEM_RISK_ALERT') THEN 1
            WHEN dashboard_signal = 'BEARISH_SETUP' THEN 2
            WHEN dashboard_signal = 'BULLISH_SETUP' THEN 3
            ELSE 4
        END AS dashboard_signal_sort_order,

        -- Labeling the signal explanation
        CASE
            WHEN dashboard_signal = 'SYSTEM_RISK_ALERT' THEN 'System risk is elevated from derivatives, liquidity, or macro stress.'
            WHEN dashboard_signal = 'RISK_REDUCTION' THEN 'Risk score is high enough to prioritize capital protection.'
            WHEN dashboard_signal = 'BULLISH_SETUP' THEN 'Momentum and sentiment are supportive while overall risk remains acceptable.'
            WHEN dashboard_signal = 'BEARISH_SETUP' THEN 'Momentum or sentiment is negative enough to flag bearish pressure.'
            ELSE 'No strong directional setup detected.'
        END AS signal_explanation,
    
        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM signal_base

)

SELECT *
FROM final