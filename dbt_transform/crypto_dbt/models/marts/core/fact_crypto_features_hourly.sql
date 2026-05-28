-- 
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='crypto_feature_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Only retrieve data that is no more than 7 days old from the table.
WITH base AS (

    SELECT *
    FROM {{ ref('int_crypto_features_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- Calculate and force the score to fall within a certain range.
scored AS (

    SELECT
        *,

        -- Market Momentum Score
        -- Meaning: This section measures whether the market is experiencing a strong upward or downward trend
        GREATEST(
            -100,
            LEAST(
                100,
                COALESCE(return_1h, 0) * 500
                + COALESCE(avg_return_24h, 0) * 300
                + COALESCE(quote_volume_zscore_24h, 0) * 5
            )
        ) AS computed_market_momentum_score,

        -- Social Sentiment Score
        -- Meaning: A positive score is given when the community is excited and full of praise; 
        -- a negative score is given when it's panicked and full of insults (FUD).
        GREATEST(
            -100,
            LEAST(
                100,
                COALESCE(social_weighted_avg_sentiment, 0) * 100
            )
        ) AS computed_social_sentiment_score,

        -- Derivatives Risk Score
        -- Meaning: A higher score indicates that the derivatives market is overheating, making it easy for "kill Short/kill Long" trades 
        -- to wipe out traders' accounts.
        GREATEST(
            0,
            LEAST(
                100,
                COALESCE(ABS(avg_annualized_funding_coin), 0) * 1.2
                + COALESCE(ABS(avg_basis_pct), 0) * 2
                + COALESCE(max_leverage_stress, 0) * 0.5
                + COALESCE(avg_panic_norm, 0) * 25
                + COALESCE(ABS(max_magnet_norm), 0) * 10
                + COALESCE(put_call_oi_ratio, 0) * 5
            )
        ) AS computed_derivatives_risk_score,

        -- Liquidity Risk Score
        -- Meaning: A higher score indicates liquidity congestion and a high risk of a chain reaction collapse.
        GREATEST(
            0,
            LEAST(
                100,
                COALESCE(max_abs_peg_deviation_pct, 0) * 15
                + COALESCE(max_depeg_risk_score, 0) * 20
                + COALESCE(normalized_system_reserve_utilization, 0) * 25
                + COALESCE(high_bank_run_risk_exchange_count, 0) * 10
            )
        ) AS computed_liquidity_risk_score,

        -- Macro Risk Score
        -- Meaning: If US stocks crash and the VIX fear index rises, the macroeconomic risk score for crypto will increase accordingly.
        GREATEST(
            0,
            LEAST(
                100,
                CASE UPPER(COALESCE(macro_risk_regime, 'NEUTRAL'))
                    WHEN 'RISK_OFF' THEN 75
                    WHEN 'DEFENSIVE' THEN 55
                    WHEN 'RISK_ON' THEN 20
                    ELSE 40
                END
                + COALESCE(vix_return_1d, 0) * 100
                - COALESCE(sp500_return_1d, 0) * 50
            )
        ) AS computed_macro_risk_score

    FROM base

),

-- The total score of all the points calculated above.
risked AS (

    SELECT
        *,

        GREATEST(
            0,
            LEAST(
                100,
                COALESCE(computed_derivatives_risk_score, 0) * 0.40
                + COALESCE(computed_liquidity_risk_score, 0) * 0.25
                + COALESCE(computed_macro_risk_score, 0) * 0.25
                + GREATEST(0, -COALESCE(computed_social_sentiment_score, 0)) * 0.10
            )
        ) AS computed_overall_risk_score

    FROM scored

),

-- Label the calculated score.
classified AS (

    SELECT
        *,

        -- Market status classification
        CASE
            WHEN close_price IS NULL THEN 'NO_PRICE'
            WHEN computed_derivatives_risk_score >= 75
                OR computed_liquidity_risk_score >= 75 THEN 'SYSTEM_RISK'
            WHEN UPPER(COALESCE(macro_risk_regime, 'NEUTRAL')) = 'RISK_OFF'
                AND COALESCE(return_1h, 0) < 0 THEN 'RISK_OFF_SELL_PRESSURE'
            WHEN COALESCE(computed_market_momentum_score, 0) >= 20
                AND COALESCE(computed_social_sentiment_score, 0) >= 10
                AND COALESCE(computed_macro_risk_score, 0) < 60 THEN 'BULLISH_RISK_ON'
            WHEN COALESCE(computed_market_momentum_score, 0) <= -20
                AND COALESCE(computed_social_sentiment_score, 0) <= -10 THEN 'BEARISH_MOMENTUM'
            WHEN COALESCE(ABS(avg_annualized_funding_coin), 0) >= 10
                OR COALESCE(max_leverage_stress, 0) >= 10 THEN 'LEVERAGE_CROWDED'
            ELSE 'NEUTRAL'
        END AS market_regime,

        -- Send out action signals
        CASE
            WHEN close_price IS NULL THEN 'NO_SIGNAL'
            WHEN COALESCE(computed_derivatives_risk_score, 0) >= 80
                OR COALESCE(computed_liquidity_risk_score, 0) >= 80 THEN 'REDUCE_RISK'
            WHEN COALESCE(computed_market_momentum_score, 0) >= 25
                AND COALESCE(computed_social_sentiment_score, 0) >= 15
                AND COALESCE(computed_overall_risk_score, 0) < 60 THEN 'BULLISH'
            WHEN COALESCE(computed_market_momentum_score, 0) <= -25
                OR COALESCE(computed_social_sentiment_score, 0) <= -25 THEN 'BEARISH'
            ELSE 'NEUTRAL'
        END AS core_signal,

        -- Check AI/Machine Learning runtime conditions
        CASE
            WHEN close_price IS NOT NULL
                AND return_1h IS NOT NULL
                AND feature_available_at IS NOT NULL
                AND feature_available_at <= CURRENT_TIMESTAMP()
                THEN TRUE
            ELSE FALSE
        END AS is_ml_feature_eligible,

        -- Check the display conditions on the dashboard.
        CASE
            WHEN close_price IS NOT NULL
                AND feature_available_at IS NOT NULL
                THEN TRUE
            ELSE FALSE
        END AS is_dashboard_ready

    FROM risked

),

-- Final table
final AS (

    SELECT
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', CAST(symbol AS STRING)))) AS crypto_feature_sk,
        hour_ts,
        DATE(hour_ts) AS feature_date,
        symbol AS symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        TIMESTAMP_DIFF(feature_available_at, hour_ts, MINUTE) AS feature_latency_minutes,

        -- Core prices / market structure
        open_price,
        high_price,
        low_price,
        close_price,
        vwap_price,
        trade_count,
        unique_trade_count,
        base_volume,
        quote_volume,
        taker_buy_quote_volume,
        taker_sell_quote_volume,
        taker_buy_quote_ratio,
        return_1h,
        log_return_1h,
        quote_volume_24h,
        avg_return_24h,
        realized_volatility_24h,
        quote_volume_zscore_24h,

        -- Funding / basis
        exchanges_reporting,
        funding_avg_mark_price,
        funding_avg_spot_price,
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

        -- Liquidation
        liquidation_bucket_count,
        total_liq_usd,
        long_liq_sum,
        short_liq_sum,
        net_long_short_liq_ratio,
        liquidation_hit_count,
        avg_open_interest,
        avg_weighted_liq_ratio,
        avg_money_flow,
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
        short_squeeze_bucket_count,
        long_squeeze_bucket_count,
        high_stress_bucket_count,

        -- Options
        option_instrument_count,
        call_instrument_count,
        put_instrument_count,
        atm_instrument_count,
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
        total_option_volume_usd,
        put_call_volume_ratio,
        delta_exposure_proxy,
        gamma_exposure_proxy,
        vega_exposure_proxy,
        theta_exposure_proxy,
        top_oi_instrument,
        top_oi_strike,
        top_oi_option_type,

        -- Social
        social_item_count,
        social_engagement_proxy,
        social_weighted_avg_sentiment,
        social_bullish_count,
        social_bearish_count,
        social_bullish_ratio,
        social_bearish_ratio,
        reddit_post_count,
        reddit_weighted_avg_sentiment,
        reddit_etf_mentions,
        reddit_hack_mentions,
        reddit_whale_mentions,
        reddit_liquidation_mentions,
        reddit_fed_mentions,
        telegram_message_count,
        telegram_weighted_avg_sentiment,
        telegram_technical_topic_count,
        telegram_regulation_topic_count,
        telegram_hack_scam_topic_count,
        telegram_macro_topic_count,
        telegram_high_importance_count,

        -- Stablecoin liquidity
        total_stablecoin_market_cap_usd,
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

        -- Exchange reserve
        exchange_count,
        total_exchange_reserve_usd,
        total_exchange_volume_24h_usd,
        system_reserve_utilization,
        normalized_system_reserve_utilization,
        avg_exchange_trust_score,
        reserve_hhi,
        high_bank_run_risk_exchange_count,
        top_reserve_exchange,
        highest_utilization_risk_label,
        highest_utilization_exchange,

        -- Macro / ETF
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
        btc_etf_flow_proxy,
        eth_etf_flow_proxy,
        ibit_return_1d,
        etha_return_1d,
        crypto_etf_momentum_regime,

        -- Core derived scores
        computed_market_momentum_score AS market_momentum_score,
        computed_social_sentiment_score AS social_sentiment_score,
        computed_derivatives_risk_score AS derivatives_risk_score,
        computed_liquidity_risk_score AS liquidity_risk_score,
        computed_macro_risk_score AS macro_risk_score,
        computed_overall_risk_score AS overall_risk_score,
        market_regime,
        core_signal,
        is_ml_feature_eligible,
        is_dashboard_ready,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM classified

)

SELECT *
FROM final