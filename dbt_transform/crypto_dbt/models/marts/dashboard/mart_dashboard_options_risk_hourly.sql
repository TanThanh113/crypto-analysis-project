-- Dashboard Options Risk Data Marting
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_options_risk_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
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

final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|options_risk'))) AS dashboard_options_risk_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        option_instrument_count,
        call_instrument_count,
        put_instrument_count,
        atm_instrument_count,

        -- ATM (At-The-Money) contract rate
        -- Meaning: That is, options with strike prices that are closest to the current market price of the coin.
        SAFE_DIVIDE(
            atm_instrument_count,
            NULLIF(option_instrument_count, 0)
        ) AS atm_instrument_ratio,

        -- Product odds up(Calls)
        SAFE_DIVIDE(
            call_instrument_count,
            NULLIF(option_instrument_count, 0)
        ) AS call_instrument_ratio,

        -- Product odds down(Puts)
        SAFE_DIVIDE(
            put_instrument_count,
            NULLIF(option_instrument_count, 0)
        ) AS put_instrument_ratio,

        avg_mark_iv,
        avg_mid_iv,
        atm_avg_mark_iv,
        atm_avg_mid_iv,
        avg_iv_spread,
        put_call_iv_skew,

        options_total_open_interest,
        call_open_interest,
        put_open_interest,
        put_call_oi_ratio,

        SAFE_DIVIDE(
            call_open_interest,
            NULLIF(COALESCE(call_open_interest, 0) + COALESCE(put_open_interest, 0), 0)
        ) AS call_open_interest_share,

        SAFE_DIVIDE(
            put_open_interest,
            NULLIF(COALESCE(call_open_interest, 0) + COALESCE(put_open_interest, 0), 0)
        ) AS put_open_interest_share,

        total_option_volume_usd,
        put_call_volume_ratio,

        delta_exposure_proxy,
        gamma_exposure_proxy,
        vega_exposure_proxy,
        theta_exposure_proxy,

        top_oi_instrument,
        top_oi_strike,
        top_oi_option_type,

        -- Labeling for Hidden Volatility Risk Measurement
        -- Meaning: Implied Volatility (IV) reflects the high cost of the option premium, representing the market's expectation of future price swings.
        CASE
            WHEN COALESCE(atm_avg_mark_iv, avg_mark_iv, 0) >= 90 THEN 'EXTREME_IV'
            WHEN COALESCE(atm_avg_mark_iv, avg_mark_iv, 0) >= 65 THEN 'HIGH_IV'
            WHEN COALESCE(atm_avg_mark_iv, avg_mark_iv, 0) > 0
                AND COALESCE(atm_avg_mark_iv, avg_mark_iv, 0) <= 35 THEN 'LOW_IV'
            ELSE 'NORMAL_IV'
        END AS implied_volatility_regime,

        -- Labeling for Implied Volatility Skew
        -- Meaning: The put_call_iv_skew (IV deviation between Put and Call orders) is an excellent tool for determining whether the market is "fearful" or "greedy".
        CASE
            WHEN COALESCE(put_call_iv_skew, 0) >= 10 THEN 'PUT_SKEW_PANIC_HEDGE'
            WHEN COALESCE(put_call_iv_skew, 0) <= -10 THEN 'CALL_SKEW_UPSIDE_DEMAND'
            ELSE 'BALANCED_SKEW'
        END AS iv_skew_label,

        CASE
            WHEN COALESCE(put_call_oi_ratio, 0) >= 1.5 THEN 'DEFENSIVE_OI'
            WHEN COALESCE(put_call_oi_ratio, 0) > 0
                AND COALESCE(put_call_oi_ratio, 0) <= 0.6 THEN 'UPSIDE_OI'
            ELSE 'BALANCED_OI'
        END AS oi_positioning_label,

        -- Systematic risk management through Greek indicators
        CASE
            WHEN COALESCE(gamma_exposure_proxy, 0) >= 0 THEN 'POSITIVE_GAMMA_PROXY'
            ELSE 'NEGATIVE_GAMMA_PROXY'
        END AS gamma_exposure_label,

        CASE
            WHEN COALESCE(vega_exposure_proxy, 0) >= 100000 THEN 'HIGH_VEGA_EXPOSURE'
            WHEN COALESCE(vega_exposure_proxy, 0) >= 25000 THEN 'MEDIUM_VEGA_EXPOSURE'
            ELSE 'LOW_VEGA_EXPOSURE'
        END AS vega_exposure_label,

        derivatives_risk_score,
        overall_risk_score,

        -- Send specific alert signals for Options
        CASE
            WHEN COALESCE(derivatives_risk_score, 0) >= 80 THEN 'CRITICAL_OPTIONS_RISK'
            WHEN COALESCE(derivatives_risk_score, 0) >= 65 THEN 'HIGH_OPTIONS_RISK'
            WHEN COALESCE(derivatives_risk_score, 0) >= 40 THEN 'MEDIUM_OPTIONS_RISK'
            ELSE 'LOW_OPTIONS_RISK'
        END AS options_alert_level,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM fact

)

SELECT *
FROM final