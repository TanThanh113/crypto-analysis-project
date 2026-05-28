{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_market_overview_sk',
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

prepared AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|market_overview'))) AS dashboard_market_overview_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        open_price,
        high_price,
        low_price,
        close_price,
        vwap_price,

        -- Profit margin right there in that language.
        SAFE_DIVIDE(close_price - open_price, NULLIF(open_price, 0)) AS intrahour_return,
        -- Amplitude of sound fluctuations (Peak - Bottom).
        SAFE_DIVIDE(high_price - low_price, NULLIF(open_price, 0)) AS intrahour_range_pct,
        -- Determine whether the active buyers (Taker Buy) or active sellers (Taker Sell) are currently in a dominant position.
        SAFE_DIVIDE(close_price - vwap_price, NULLIF(vwap_price, 0)) AS close_vwap_deviation_pct,

        return_1h,
        log_return_1h,
        avg_return_24h,
        realized_volatility_24h,

        trade_count,
        unique_trade_count,
        base_volume,
        quote_volume,
        quote_volume_24h,
        quote_volume_zscore_24h,

        taker_buy_quote_volume,
        taker_sell_quote_volume,
        taker_buy_quote_ratio,

        SAFE_DIVIDE(
            taker_buy_quote_volume - taker_sell_quote_volume,
            NULLIF(taker_buy_quote_volume + taker_sell_quote_volume, 0)
        ) AS taker_buy_sell_imbalance,

        market_momentum_score,
        overall_risk_score,
        market_regime,
        core_signal,

        -- Tag the market status
        -- Hourly candlestick labels (GREEN - green candle, RED - red candle, FLAT - unchanged price).
        CASE
            WHEN close_price > open_price THEN 'GREEN' 
            WHEN close_price < open_price THEN 'RED'
            ELSE 'FLAT'
        END AS candle_direction,

        -- Classification of trading volume based on Z-score
        CASE
            WHEN COALESCE(quote_volume_zscore_24h, 0) >= 3 THEN 'EXTREME_VOLUME'
            WHEN COALESCE(quote_volume_zscore_24h, 0) >= 2 THEN 'HIGH_VOLUME'
            WHEN COALESCE(quote_volume_zscore_24h, 0) <= -2 THEN 'LOW_VOLUME'
            ELSE 'NORMAL_VOLUME'
        END AS volume_regime,

        -- Classification of price shock levels
        CASE
            WHEN COALESCE(realized_volatility_24h, 0) >= 0.08 THEN 'EXTREME_VOLATILITY'
            WHEN COALESCE(realized_volatility_24h, 0) >= 0.04 THEN 'HIGH_VOLATILITY'
            WHEN COALESCE(realized_volatility_24h, 0) <= 0.01 THEN 'LOW_VOLATILITY'
            ELSE 'NORMAL_VOLATILITY'
        END AS volatility_regime,

        -- Determine the direction of price momentum (STRONG_UP, STRONG_DOWN, SIDEWAYS...) & the overall level of risk.
        CASE
            WHEN COALESCE(market_momentum_score, 0) >= 30 THEN 'STRONG_UP'
            WHEN COALESCE(market_momentum_score, 0) >= 10 THEN 'UP'
            WHEN COALESCE(market_momentum_score, 0) <= -30 THEN 'STRONG_DOWN'
            WHEN COALESCE(market_momentum_score, 0) <= -10 THEN 'DOWN'
            ELSE 'SIDEWAYS'
        END AS momentum_regime,

        CASE
            WHEN COALESCE(overall_risk_score, 0) >= 80 THEN 'CRITICAL_RISK'
            WHEN COALESCE(overall_risk_score, 0) >= 65 THEN 'HIGH_RISK'
            WHEN COALESCE(overall_risk_score, 0) >= 45 THEN 'MEDIUM_RISK'
            ELSE 'LOW_RISK'
        END AS risk_regime,

        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM fact

)

SELECT *
FROM prepared