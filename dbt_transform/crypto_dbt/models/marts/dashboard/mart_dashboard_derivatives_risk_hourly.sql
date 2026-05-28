-- Perpetual Futures, Liquidations data, and Options contracts help traders or systems detect early "liquidation sweeps" or market reversals.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_derivatives_risk_sk',
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

scored AS (

    SELECT
        *,
        
        -- Labeling the annual funding rate of coin-backed contracts.
        CASE
            WHEN COALESCE(avg_annualized_funding_coin, 0) >= 10 THEN 'EXTREME_LONG_CROWDING'
            WHEN COALESCE(avg_annualized_funding_coin, 0) >= 2 THEN 'LONG_BIAS'
            WHEN COALESCE(avg_annualized_funding_coin, 0) <= -10 THEN 'EXTREME_SHORT_CROWDING'
            WHEN COALESCE(avg_annualized_funding_coin, 0) <= -2 THEN 'SHORT_BIAS'
            ELSE 'NEUTRAL_FUNDING'
        END AS funding_bias_label,

        -- Labeling the Options Market
        CASE
            WHEN COALESCE(put_call_oi_ratio, 0) >= 1.5 THEN 'PUT_HEAVY_DEFENSIVE'
            WHEN COALESCE(put_call_oi_ratio, 0) > 0
                AND COALESCE(put_call_oi_ratio, 0) <= 0.6 THEN 'CALL_HEAVY_RISK_ON'
            ELSE 'BALANCED_OPTIONS'
        END AS options_positioning_label,

        -- Labeling for Actual Liquidation Pressure
        CASE
            WHEN COALESCE(net_long_short_liq_ratio, 0) >= 0.35 THEN 'LONG_LIQUIDATION_DOMINANT'
            WHEN COALESCE(net_long_short_liq_ratio, 0) <= -0.35 THEN 'SHORT_LIQUIDATION_DOMINANT'
            ELSE 'BALANCED_LIQUIDATION'
        END AS liquidation_pressure_label,

        -- Calculate the percentage of Long positions within the total Long and Short positions.
        SAFE_DIVIDE(
            COALESCE(long_liq_sum, 0),
            NULLIF(COALESCE(long_liq_sum, 0) + COALESCE(short_liq_sum, 0), 0)
        ) AS long_liquidation_share,

        -- Calculate the percentage of Short positions within the total Long and Short positions.
        SAFE_DIVIDE(
            COALESCE(short_liq_sum, 0),
            NULLIF(COALESCE(long_liq_sum, 0) + COALESCE(short_liq_sum, 0), 0)
        ) AS short_liquidation_share,

        -- Calculate the percentage of Call Open Interest within the total Call and Put Open Interest.
        SAFE_DIVIDE(
            COALESCE(call_open_interest, 0),
            NULLIF(COALESCE(call_open_interest, 0) + COALESCE(put_open_interest, 0), 0)
        ) AS call_open_interest_share,

        -- Calculate the percentage of Put Open Interest within the total Call and Put Open Interest.
        SAFE_DIVIDE(
            COALESCE(put_open_interest, 0),
            NULLIF(COALESCE(call_open_interest, 0) + COALESCE(put_open_interest, 0), 0)
        ) AS put_open_interest_share

    FROM fact

),

-- Final table with the standardized derivatives risk data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|derivatives_risk'))) AS dashboard_derivatives_risk_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        exchanges_reporting,
        avg_basis_pct,
        max_abs_basis_pct,
        avg_funding_rate_coin,
        avg_funding_rate_usdt,
        avg_annualized_funding_coin,
        avg_annualized_funding_usdt,
        funding_dispersion_coin,
        avg_arbitrage_spread,
        max_abs_arbitrage_spread,
        max_leverage_stress,
        avg_leverage_stress,
        dominant_funding_regime,
        dominant_arbitrage_opportunity,
        strongest_arbitrage_exchange,
        highest_stress_exchange,
        funding_bias_label,

        total_liq_usd,
        long_liq_sum,
        short_liq_sum,
        long_liquidation_share,
        short_liquidation_share,
        net_long_short_liq_ratio,
        liquidation_hit_count,
        avg_panic_norm,
        max_panic_norm,
        avg_magnet_norm,
        max_magnet_norm,
        max_rank_score,
        top_liq_price_bucket,
        top_liq_distance_pct,
        top_squeeze_signal,
        dominant_side_by_liq,
        top_stress_level,
        liquidation_pressure_label,

        option_instrument_count,
        atm_instrument_count,
        avg_mark_iv,
        atm_avg_mark_iv,
        avg_mid_iv,
        atm_avg_mid_iv,
        avg_iv_spread,
        put_call_iv_skew,
        options_total_open_interest,
        call_open_interest,
        put_open_interest,
        call_open_interest_share,
        put_open_interest_share,
        put_call_oi_ratio,
        total_option_volume_usd,
        put_call_volume_ratio,
        delta_exposure_proxy,
        gamma_exposure_proxy,
        vega_exposure_proxy,
        theta_exposure_proxy,
        top_oi_instrument,
        top_oi_strike,
        top_oi_option_type,
        options_positioning_label,

        derivatives_risk_score,
        overall_risk_score,

        -- Labeling the derivatives risk score
        CASE
            WHEN COALESCE(derivatives_risk_score, 0) >= 80 THEN 'CRITICAL_DERIVATIVES_RISK'
            WHEN COALESCE(derivatives_risk_score, 0) >= 65 THEN 'HIGH_DERIVATIVES_RISK'
            WHEN COALESCE(derivatives_risk_score, 0) >= 40 THEN 'MEDIUM_DERIVATIVES_RISK'
            ELSE 'LOW_DERIVATIVES_RISK'
        END AS derivatives_alert_level,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM scored

)

SELECT *
FROM final