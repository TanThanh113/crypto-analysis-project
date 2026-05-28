{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='ml_feature_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Specify data from the previous 21 days to avoid data errors, delayed data, etc.
WITH incremental_bound AS (

    SELECT
        {% if is_incremental() %}
            TIMESTAMP_SUB(
                COALESCE(
                    (SELECT MAX(hour_ts) FROM {{ this }}),
                    TIMESTAMP('1970-01-01')
                ),
                INTERVAL 14 DAY
            ) AS output_start_hour,

            TIMESTAMP_SUB(
                COALESCE(
                    (SELECT MAX(hour_ts) FROM {{ this }}),
                    TIMESTAMP('1970-01-01')
                ),
                INTERVAL 21 DAY
            ) AS source_start_hour
        {% else %}
            TIMESTAMP('1970-01-01') AS output_start_hour,
            TIMESTAMP('1970-01-01') AS source_start_hour
        {% endif %}

),

-- Filter the data to ensure there are no errors.
base AS (

    SELECT f.*
    FROM {{ ref('fact_crypto_features_hourly') }} AS f
    CROSS JOIN incremental_bound AS b
    WHERE f.is_ml_feature_eligible = TRUE
      AND f.close_price IS NOT NULL
      AND f.hour_ts IS NOT NULL
      AND f.symbol IN ('BTC', 'ETH')
      AND f.hour_ts >= b.source_start_hour

),

feature_windows AS (

    SELECT
        *,
        -- Calculate the return of the previous 4 hours.
        SAFE_DIVIDE(
            close_price - LAG(close_price, 4) OVER (
                PARTITION BY symbol
                ORDER BY hour_ts
            ),
            NULLIF(
                LAG(close_price, 4) OVER (
                    PARTITION BY symbol
                    ORDER BY hour_ts
                ),
                0
            )
        ) AS return_4h,

        -- Calculate the return of the previous 24 hours.
        SAFE_DIVIDE(
            close_price - LAG(close_price, 24) OVER (
                PARTITION BY symbol
                ORDER BY hour_ts
            ),
            NULLIF(
                LAG(close_price, 24) OVER (
                    PARTITION BY symbol
                    ORDER BY hour_ts
                ),
                0
            )
        ) AS return_24h,

        -- Calculate the change in price of the previous hour.
        close_price - LAG(close_price, 1) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS price_change_1h,

        -- Calculate the change in price of the previous 4 hours.
        close_price - LAG(close_price, 4) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS price_change_4h,

        -- Calculate the change in price of the previous 24 hours.
        close_price - LAG(close_price, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS price_change_24h,

        -- Calculate the average rolling return of the previous 7 days.
        AVG(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_return_7h,

        -- Calculate the average rolling return of the previous 24 hours.
        AVG(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_return_24h,

        -- Calculate the volatility of the rolling return of the previous 24 hours.(standard deviation)
        STDDEV_SAMP(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_volatility_24h,

        -- Calculate the volatility of the rolling return of the previous 7 days.(standard deviation)
        STDDEV_SAMP(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
        ) AS rolling_volatility_7d,

        -- Calculate the average rolling quote volume of the previous 24 hours.
        AVG(quote_volume) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_quote_volume_24h,

        -- Calculate the z-score of the quote volume of the previous 24 hours.
        SAFE_DIVIDE(
            quote_volume - AVG(quote_volume) OVER (
                PARTITION BY symbol
                ORDER BY hour_ts
                ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
            ),
            NULLIF(
                STDDEV_SAMP(quote_volume) OVER (
                    PARTITION BY symbol
                    ORDER BY hour_ts
                    ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
                ),
                0
            )
        ) AS quote_volume_zscore_calc_24h,

        -- Calculate the change in market momentum over the last 24 hours.
        market_momentum_score - LAG(market_momentum_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS market_momentum_delta_24h,

        -- Calculate the change in overall risk over the last 24 hours.
        overall_risk_score - LAG(overall_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS overall_risk_delta_24h,

        -- Calculate the change in social sentiment over the last 24 hours.
        social_sentiment_score - LAG(social_sentiment_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS social_sentiment_delta_24h,

        -- Calculate the change in derivatives risk over the last 24 hours.
        derivatives_risk_score - LAG(derivatives_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS derivatives_risk_delta_24h,

        -- Calculate the change in liquidity risk over the last 24 hours.
        liquidity_risk_score - LAG(liquidity_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS liquidity_risk_delta_24h,

        -- Calculate the change in macro risk over the last 24 hours.
        macro_risk_score - LAG(macro_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS macro_risk_delta_24h,

        -- Calculate the average rolling value of overall risk over the last 24 hours.
        AVG(overall_risk_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_overall_risk_24h,
    
        -- Calculate the average rolling value of social sentiment over the last 24 hours.
        AVG(social_sentiment_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_social_sentiment_24h,

        -- Calculate the average rolling value of derivatives risk over the last 24 hours.
        AVG(derivatives_risk_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_derivatives_risk_24h

    FROM base

),

-- Final table with the standardized ML features
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', CAST(symbol AS STRING), '|ml_features_v1'))) AS ml_feature_sk,

        -- The section of the feature AI is learning from
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        close_price,
        open_price,
        high_price,
        low_price,
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
        return_4h,
        return_24h,
        price_change_1h,
        price_change_4h,
        price_change_24h,
        quote_volume_24h,
        avg_return_24h,
        realized_volatility_24h,
        rolling_avg_return_7h,
        rolling_avg_return_24h,
        rolling_volatility_24h,
        rolling_volatility_7d,
        rolling_avg_quote_volume_24h,
        COALESCE(quote_volume_zscore_24h, quote_volume_zscore_calc_24h) AS volume_zscore_24h,

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
        top_liq_distance_pct,
        top_squeeze_signal,
        dominant_side_by_liq,
        top_stress_level,
        short_squeeze_bucket_count,
        long_squeeze_bucket_count,
        high_stress_bucket_count,

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

        total_stablecoin_market_cap_usd,
        total_stablecoin_volume_24h_usd,
        stablecoin_volume_to_mcap,
        mcap_weighted_peg_deviation_pct,
        max_abs_peg_deviation_pct,
        max_depeg_risk_score,
        depeg_risk_coin_count,
        usdt_dominance_pct,
        usdc_dominance_pct,
        exchange_count,
        total_exchange_reserve_usd,
        total_exchange_volume_24h_usd,
        system_reserve_utilization,
        normalized_system_reserve_utilization,
        avg_exchange_trust_score,
        reserve_hhi,
        high_bank_run_risk_exchange_count,

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

        market_momentum_score,
        social_sentiment_score,
        derivatives_risk_score,
        liquidity_risk_score,
        macro_risk_score,
        overall_risk_score,
        market_momentum_delta_24h,
        overall_risk_delta_24h,
        social_sentiment_delta_24h,
        derivatives_risk_delta_24h,
        liquidity_risk_delta_24h,
        macro_risk_delta_24h,
        rolling_avg_overall_risk_24h,
        rolling_avg_social_sentiment_24h,
        rolling_avg_derivatives_risk_24h,
        market_regime,
        core_signal,

        -- Score to see if the data is complete.
        (
            IF(close_price IS NOT NULL, 1, 0)
            + IF(return_1h IS NOT NULL, 1, 0)
            + IF(return_4h IS NOT NULL, 1, 0)
            + IF(return_24h IS NOT NULL, 1, 0)
            + IF(COALESCE(quote_volume_zscore_24h, quote_volume_zscore_calc_24h) IS NOT NULL, 1, 0)
            + IF(COALESCE(realized_volatility_24h, rolling_volatility_24h) IS NOT NULL, 1, 0)
            + IF(avg_basis_pct IS NOT NULL, 1, 0)
            + IF(avg_annualized_funding_coin IS NOT NULL, 1, 0)
            + IF(avg_panic_norm IS NOT NULL, 1, 0)
            + IF(social_weighted_avg_sentiment IS NOT NULL, 1, 0)
            + IF(total_stablecoin_market_cap_usd IS NOT NULL, 1, 0)
            + IF(overall_risk_score IS NOT NULL, 1, 0)
        ) / 12.0 AS feature_completeness_score,

        -- Check if the data is ready for training.
        CASE
            WHEN close_price IS NOT NULL
                AND return_1h IS NOT NULL
                AND return_4h IS NOT NULL
                AND COALESCE(realized_volatility_24h, rolling_volatility_24h) IS NOT NULL
                AND feature_available_at IS NOT NULL
                THEN TRUE
            ELSE FALSE
        END AS is_training_feature_ready,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM feature_windows
    CROSS JOIN incremental_bound AS b
    WHERE hour_ts >= b.output_start_hour

)

SELECT *
FROM final