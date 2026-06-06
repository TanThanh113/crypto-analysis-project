{{ config(
    materialized='table',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol', 'split_name']
) }}

-- This model creates the final ML training dataset.
-- It joins ML features with future labels and creates time-based train/validation/test splits.
-- Important: split must be time-based, not random, to avoid financial time-series leakage.

-- Check if the features are working correctly.
WITH features AS (

    -- Keep only rows that have enough feature quality for ML training.
    SELECT *
    FROM {{ ref('mart_ml_features_hourly') }}
    WHERE is_training_feature_ready = TRUE

),

-- Check if the labels are working correctly.
labels AS (

    -- Keep only rows where future labels are already available.
    -- Latest rows will not have labels yet, because future prices do not exist.
    SELECT *
    FROM {{ ref('mart_ml_labels_hourly') }}
    WHERE is_label_available = TRUE

),

-- Join the features and labels.
joined AS (

    -- Join each feature row at time T with its future-return labels.
    -- This is safe for training because labels are targets, not input features.
    SELECT
        f.*,

        l.ml_label_sk,
        l.future_close_price_1h,
        l.future_close_price_4h,
        l.future_close_price_24h,
        l.future_return_1h,
        l.future_return_4h,
        l.future_return_24h,
        l.future_volatility_24h,
        l.future_direction_1h,
        l.future_direction_4h,
        l.future_direction_24h,
        l.binary_direction_4h_excluding_flat,
        l.sample_weight_4h,
        l.label_available_at,

        CASE
            WHEN f.feature_available_at <= l.label_available_at THEN TRUE
            ELSE FALSE
        END AS is_feature_available_before_label,

        -- Time rank per symbol for deterministic time-series split.
        -- Older data becomes train, newer data becomes validation/test.
        PERCENT_RANK() OVER (
            PARTITION BY f.symbol
            ORDER BY f.hour_ts
        ) AS symbol_time_rank

    FROM features AS f
    INNER JOIN labels AS l
        ON f.hour_ts = l.hour_ts
       AND f.symbol = l.symbol

    WHERE f.close_price IS NOT NULL
      AND l.future_return_4h IS NOT NULL

),

-- Split the data into train/validation/test.
split AS (

    -- Time-based split:
    -- 70% oldest rows: train
    -- next 15%: validation
    -- newest 15%: test
    SELECT
        *,

        CASE
            WHEN symbol_time_rank < 0.70 THEN 'train'
            WHEN symbol_time_rank < 0.85 THEN 'validation'
            ELSE 'test'
        END AS split_name,

        CASE
            WHEN feature_completeness_score >= 0.60
                AND close_price > 0
                AND return_1h IS NOT NULL
                AND return_4h IS NOT NULL
                AND future_direction_4h IS NOT NULL
                THEN TRUE
            ELSE FALSE
        END AS is_training_row

    FROM joined

),

-- Final table with the standardized ML training dataset
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(hour_ts AS STRING),
                    '|',
                    CAST(symbol AS STRING),
                    '|ml_training_dataset_v1'
                )
            )
        ) AS ml_training_row_sk,

        ml_feature_sk,
        ml_label_sk,
        crypto_feature_sk,

        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,

        feature_available_at,
        label_available_at,
        feature_latency_minutes,

        split_name,
        symbol_time_rank,
        is_training_row,
        feature_completeness_score,

        -- Recommended baseline feature subset for v1 direction model.
        -- Price and market features
        close_price,
        return_1h,
        return_4h,
        return_24h,
        log_return_1h,
        avg_return_24h,
        realized_volatility_24h,
        rolling_avg_return_7h,
        rolling_avg_return_24h,
        rolling_volatility_24h,
        rolling_volatility_7d,
        quote_volume,
        quote_volume_24h,
        volume_zscore_24h,
        quote_volume_lag_1h,
        quote_volume_24h_lag_1h,
        quote_volume_zscore_24h,
        volume_zscore_24h_lag_1h,
        liquidity_regime_high,
        liquidity_regime_low,
        liquidity_risk_score_lag_1h,
        is_eth_x_quote_volume_zscore_24h,
        return_4h_lag_1h,
        return_24h_lag_1h,
        return_24h_symbol_zscore,
        return_1h_rolling_mean_4h,
        return_1h_rolling_sum_4h,
        return_1h_rolling_mean_24h,
        return_1h_rolling_sum_24h,
        rolling_drawdown_24h,
        taker_buy_quote_ratio,

        -- Funding / derivatives features
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

        -- Liquidation features
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

        -- Options features
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

        -- Social sentiment features
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

        -- Liquidity / reserve features
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

        -- Macro / ETF features
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

        -- Core score features
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

        -- Categorical features.
        -- Python training script should one-hot encode or ordinal encode these.
        dominant_funding_regime,
        dominant_arbitrage_opportunity,
        top_squeeze_signal,
        dominant_side_by_liq,
        top_stress_level,
        macro_risk_regime,
        crypto_etf_momentum_regime,
        market_regime,
        core_signal,

        -- Labels / targets
        future_close_price_1h,
        future_close_price_4h,
        future_close_price_24h,
        future_return_1h,
        future_return_4h,
        future_return_24h,
        future_volatility_24h,
        future_direction_1h,
        future_direction_4h,
        future_direction_24h,

        is_feature_available_before_label,

        -- Main v1 classification target.
        -- UP = 1, DOWN = 0, FLAT = NULL.
        -- For binary model, train script should filter binary_direction_4h_excluding_flat IS NOT NULL.
        binary_direction_4h_excluding_flat,

        -- Sample weight for 4h direction model.
        sample_weight_4h,

        'ml_training_dataset_v1' AS dataset_version,
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM split
    WHERE is_training_row = TRUE

)

SELECT *
FROM final
