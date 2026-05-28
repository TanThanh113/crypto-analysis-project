{{ config(materialized='view') }}

-- This model creates hourly ML inference features from realtime streaming candles.
-- Market features come from int_streaming_market_hourly.
-- Slow-changing context features come from fact_crypto_features_hourly using latest-known value.
-- Important: this table does NOT include future labels.

-- Here we will take one line for each coin.
WITH market_base AS (

    SELECT
        hour_ts,
        DATE(hour_ts) AS feature_date,
        UPPER(symbol) AS symbol,
        CONCAT(UPPER(symbol), 'USDT') AS pair_symbol,

        open_price,
        high_price,
        low_price,
        close_price,
        vwap_price,

        minute_candle_count,
        latest_minute_at,
        available_at AS market_available_at,

        base_volume,
        SAFE_CAST(base_volume * COALESCE(vwap_price, close_price) AS FLOAT64) AS quote_volume

    FROM {{ ref('int_streaming_market_hourly') }}
    WHERE hour_ts IS NOT NULL
      AND symbol IN ('BTC', 'ETH')
      AND close_price IS NOT NULL
      AND close_price > 0

),

-- Calculate the necessary formulas for prediction.
market_returns AS (

    SELECT
        *,

        -- Calculate the return of the previous 1 hours.
        SAFE_DIVIDE(
            close_price - LAG(close_price, 1) OVER (
                PARTITION BY symbol
                ORDER BY hour_ts
            ),
            NULLIF(
                LAG(close_price, 1) OVER (
                    PARTITION BY symbol
                    ORDER BY hour_ts
                ),
                0
            )
        ) AS return_1h,

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

        -- Calculate the log return of the previous 1 hours.
        CASE
            WHEN close_price > 0
                AND LAG(close_price, 1) OVER (
                    PARTITION BY symbol
                    ORDER BY hour_ts
                ) > 0
                THEN LN(
                    close_price / LAG(close_price, 1) OVER (
                        PARTITION BY symbol
                        ORDER BY hour_ts
                    )
                )
        END AS log_return_1h,

        -- Calculate the change in price of the previous 1 hours.
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
        ) AS price_change_24h

    FROM market_base

),

market_features AS (

    SELECT
        *,

        -- Calculate the sum value of quote volume of the previous 24 hours.
        SUM(quote_volume) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS quote_volume_24h,

        -- Calculate the average rolling value of return of the previous 24 hours.
        AVG(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS avg_return_24h,

        -- Calculate the average rolling value of return of the previous 7 hours.
        AVG(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_return_7h,

        -- Calculate the average rolling value of return of the previous 24 hours.
        AVG(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_return_24h,

        -- Calculate the standard deviation of return of the previous 24 hours.
        STDDEV_SAMP(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS realized_volatility_24h,

        -- Calculate the standard deviation of return of the previous 24 hours.
        STDDEV_SAMP(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_volatility_24h,

        -- Calculate the standard deviation of return of the previous 7 days.
        STDDEV_SAMP(return_1h) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
        ) AS rolling_volatility_7d,

        -- Calculate the average rolling value of quote volume of the previous 24 hours.
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
        ) AS volume_zscore_24h

    FROM market_returns

),

-- Only take data smaller than the actual time to avoid revealing the answer.
context_base AS (

    SELECT *
    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE
      AND feature_available_at <= CURRENT_TIMESTAMP()

),

context AS (

    SELECT
        *,

        market_momentum_score - LAG(market_momentum_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS market_momentum_delta_24h,

        overall_risk_score - LAG(overall_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS overall_risk_delta_24h,

        social_sentiment_score - LAG(social_sentiment_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS social_sentiment_delta_24h,

        derivatives_risk_score - LAG(derivatives_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS derivatives_risk_delta_24h,

        liquidity_risk_score - LAG(liquidity_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS liquidity_risk_delta_24h,

        macro_risk_score - LAG(macro_risk_score, 24) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
        ) AS macro_risk_delta_24h,

        AVG(overall_risk_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_overall_risk_24h,

        AVG(social_sentiment_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_social_sentiment_24h,

        AVG(derivatives_risk_score) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_derivatives_risk_24h

    FROM context_base

),

-- Join the market features with the latest context-ready row per symbol.
joined AS (

    SELECT
        m.*,
        c.crypto_feature_sk AS context_crypto_feature_sk,
        c.feature_available_at AS context_feature_available_at,
        c.feature_latency_minutes AS context_feature_latency_minutes,

        -- Funding and exchanges
        c.exchanges_reporting,
        c.avg_basis_pct,
        c.max_abs_basis_pct,
        c.avg_funding_rate_coin,
        c.avg_funding_rate_usdt,
        c.avg_annualized_funding_coin,
        c.avg_annualized_funding_usdt,
        c.funding_dispersion_coin,
        c.avg_arbitrage_spread,
        c.max_leverage_stress,
        c.avg_leverage_stress,
        c.dominant_funding_regime,
        c.dominant_arbitrage_opportunity,

        -- Liquidation
        c.total_liq_usd,
        c.net_long_short_liq_ratio,
        c.liquidation_hit_count,
        c.avg_open_interest,
        c.avg_money_flow,
        c.avg_panic_norm,
        c.max_panic_norm,
        c.avg_magnet_norm,
        c.max_magnet_norm,
        c.max_rank_score,
        c.short_squeeze_bucket_count,
        c.long_squeeze_bucket_count,
        c.high_stress_bucket_count,
        c.top_squeeze_signal,
        c.dominant_side_by_liq,
        c.top_stress_level,

        -- Options
        c.avg_mark_iv,
        c.avg_mid_iv,
        c.atm_avg_mark_iv,
        c.atm_avg_mid_iv,
        c.avg_iv_spread,
        c.put_call_iv_skew,
        c.options_total_open_interest,
        c.put_call_oi_ratio,
        c.total_option_volume_usd,
        c.put_call_volume_ratio,
        c.delta_exposure_proxy,
        c.gamma_exposure_proxy,
        c.vega_exposure_proxy,
        c.theta_exposure_proxy,

        -- Social sentiment
        c.social_weighted_avg_sentiment,
        c.social_bullish_ratio,
        c.social_bearish_ratio,
        c.social_engagement_proxy,
        c.reddit_weighted_avg_sentiment,
        c.telegram_weighted_avg_sentiment,
        c.reddit_etf_mentions,
        c.reddit_hack_mentions,
        c.reddit_whale_mentions,
        c.reddit_liquidation_mentions,
        c.reddit_fed_mentions,
        c.telegram_high_importance_count,

        -- Stablecoins
        c.total_stablecoin_market_cap_usd,
        c.stablecoin_volume_to_mcap,
        c.mcap_weighted_peg_deviation_pct,
        c.max_abs_peg_deviation_pct,
        c.max_depeg_risk_score,
        c.depeg_risk_coin_count,
        c.usdt_dominance_pct,
        c.usdc_dominance_pct,
        c.total_exchange_reserve_usd,
        c.system_reserve_utilization,
        c.normalized_system_reserve_utilization,
        c.avg_exchange_trust_score,
        c.reserve_hhi,
        c.high_bank_run_risk_exchange_count,

        -- Macro and etf
        c.sp500_return_1d,
        c.nasdaq_return_1d,
        c.gold_return_1d,
        c.vix_return_1d,
        c.oil_return_1d,
        c.sp500_return_5d,
        c.nasdaq_return_5d,
        c.vix_return_5d,
        c.nasdaq_sp500_ratio,
        c.safe_haven_bid_1d,
        c.btc_etf_volume_weighted_return_1d,
        c.eth_etf_volume_weighted_return_1d,
        c.total_etf_volume_weighted_return_1d,
        c.btc_etf_flow_proxy,
        c.eth_etf_flow_proxy,
        c.ibit_return_1d,
        c.etha_return_1d,

        c.social_sentiment_score,
        c.derivatives_risk_score,
        c.liquidity_risk_score,
        c.macro_risk_score,
        c.overall_risk_score,
        c.market_momentum_delta_24h,
        c.overall_risk_delta_24h,
        c.social_sentiment_delta_24h,
        c.derivatives_risk_delta_24h,
        c.liquidity_risk_delta_24h,
        c.macro_risk_delta_24h,
        c.rolling_avg_overall_risk_24h,
        c.rolling_avg_social_sentiment_24h,
        c.rolling_avg_derivatives_risk_24h,

        c.macro_risk_regime,
        c.crypto_etf_momentum_regime,
        c.market_regime,
        c.core_signal
    
    -- Logic join table
    -- Here, we will join symbols together; according to the macro's condition, we will take the most recent data to join.
    FROM market_features AS m
    LEFT JOIN context AS c
        ON m.symbol = c.symbol
       AND c.feature_available_at <= COALESCE(m.market_available_at, m.hour_ts)

    -- Here we will take one line for each coin.
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY m.hour_ts, m.symbol
        ORDER BY c.feature_available_at DESC, c.hour_ts DESC
    ) = 1

),

-- Here we will create the final table.
final AS (

    SELECT
        -- Here we will create a unique key for each row.
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|ml_prediction_input_hourly_v1'))) AS ml_prediction_input_sk,
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|streaming_ml_features_v1'))) AS ml_feature_sk,

        context_crypto_feature_sk AS crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol AS symbol_key,
        symbol,
        pair_symbol,

        -- Here we will use the latest available time for the row.
        GREATEST(
            COALESCE(market_available_at, TIMESTAMP('1970-01-01')),
            COALESCE(context_feature_available_at, TIMESTAMP('1970-01-01'))
        ) AS feature_available_at,

        -- Here we will calculate the latency between the row and the latest available time.
        TIMESTAMP_DIFF(
            GREATEST(
                COALESCE(market_available_at, TIMESTAMP('1970-01-01')),
                COALESCE(context_feature_available_at, TIMESTAMP('1970-01-01'))
            ),
            hour_ts,
            MINUTE
        ) AS feature_latency_minutes,

        -- Base metrics
        close_price,
        open_price,
        high_price,
        low_price,
        vwap_price,

        minute_candle_count AS trade_count,
        minute_candle_count AS unique_trade_count,
        base_volume,
        quote_volume,
        CAST(NULL AS FLOAT64) AS taker_buy_quote_volume,
        CAST(NULL AS FLOAT64) AS taker_sell_quote_volume,
        CAST(NULL AS FLOAT64) AS taker_buy_quote_ratio,

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
        volume_zscore_24h,

        exchanges_reporting,
        avg_basis_pct,
        max_abs_basis_pct,
        avg_funding_rate_coin,
        avg_funding_rate_usdt,
        avg_annualized_funding_coin,
        avg_annualized_funding_usdt,
        funding_dispersion_coin,
        avg_arbitrage_spread,
        max_leverage_stress,
        avg_leverage_stress,
        dominant_funding_regime,
        dominant_arbitrage_opportunity,

        total_liq_usd,
        net_long_short_liq_ratio,
        liquidation_hit_count,
        avg_open_interest,
        avg_money_flow,
        avg_panic_norm,
        max_panic_norm,
        avg_magnet_norm,
        max_magnet_norm,
        max_rank_score,
        short_squeeze_bucket_count,
        long_squeeze_bucket_count,
        high_stress_bucket_count,
        top_squeeze_signal,
        dominant_side_by_liq,
        top_stress_level,

        avg_mark_iv,
        avg_mid_iv,
        atm_avg_mark_iv,
        atm_avg_mid_iv,
        avg_iv_spread,
        put_call_iv_skew,
        options_total_open_interest,
        put_call_oi_ratio,
        total_option_volume_usd,
        put_call_volume_ratio,
        delta_exposure_proxy,
        gamma_exposure_proxy,
        vega_exposure_proxy,
        theta_exposure_proxy,

        social_weighted_avg_sentiment,
        social_bullish_ratio,
        social_bearish_ratio,
        social_engagement_proxy,
        reddit_weighted_avg_sentiment,
        telegram_weighted_avg_sentiment,
        reddit_etf_mentions,
        reddit_hack_mentions,
        reddit_whale_mentions,
        reddit_liquidation_mentions,
        reddit_fed_mentions,
        telegram_high_importance_count,

        total_stablecoin_market_cap_usd,
        stablecoin_volume_to_mcap,
        mcap_weighted_peg_deviation_pct,
        max_abs_peg_deviation_pct,
        max_depeg_risk_score,
        depeg_risk_coin_count,
        usdt_dominance_pct,
        usdc_dominance_pct,
        total_exchange_reserve_usd,
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
        btc_etf_volume_weighted_return_1d,
        eth_etf_volume_weighted_return_1d,
        total_etf_volume_weighted_return_1d,
        btc_etf_flow_proxy,
        eth_etf_flow_proxy,
        ibit_return_1d,
        etha_return_1d,

        -- Scoring based on market momentum.
        GREATEST(
            -100,
            LEAST(
                100,
                COALESCE(return_1h, 0) * 500
                + COALESCE(avg_return_24h, 0) * 300
                + COALESCE(volume_zscore_24h, 0) * 5
            )
        ) AS market_momentum_score,

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

        macro_risk_regime,
        crypto_etf_momentum_regime,
        market_regime,
        core_signal,

        -- Scoring based on the completeness of predictive data.
        (
            IF(close_price IS NOT NULL, 1, 0)
            + IF(return_1h IS NOT NULL, 1, 0)
            + IF(return_4h IS NOT NULL, 1, 0)
            + IF(return_24h IS NOT NULL, 1, 0)
            + IF(volume_zscore_24h IS NOT NULL, 1, 0)
            + IF(rolling_volatility_24h IS NOT NULL, 1, 0)
            + IF(avg_basis_pct IS NOT NULL, 1, 0)
            + IF(avg_annualized_funding_coin IS NOT NULL, 1, 0)
            + IF(avg_panic_norm IS NOT NULL, 1, 0)
            + IF(social_weighted_avg_sentiment IS NOT NULL, 1, 0)
            + IF(total_stablecoin_market_cap_usd IS NOT NULL, 1, 0)
            + IF(overall_risk_score IS NOT NULL, 1, 0)
        ) / 12.0 AS feature_completeness_score,

        -- 
        CASE
            WHEN close_price IS NOT NULL
                AND return_1h IS NOT NULL
                AND return_4h IS NOT NULL
                AND rolling_volatility_24h IS NOT NULL
                AND market_available_at IS NOT NULL
                AND market_available_at <= CURRENT_TIMESTAMP()
                THEN TRUE
            ELSE FALSE
        END AS is_prediction_row,

        'streaming_realtime_plus_latest_context' AS prediction_feature_source,
        CURRENT_TIMESTAMP() AS prediction_input_built_at

    FROM joined

)

SELECT *
FROM final