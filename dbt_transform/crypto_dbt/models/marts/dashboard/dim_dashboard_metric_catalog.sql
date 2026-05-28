{{ config(materialized='table') }}

-- Hardcoded. Customize the attributes yourself (source, column names, units, etc.).
WITH metric_catalog AS (

    SELECT
        'market' AS dashboard_section, -- The section of the dashboard where the metric is displayed
        'fact_crypto_features_hourly' AS source_model, -- The source model where the metric is derived from
        'close_price' AS metric_name, -- The name of the metric
        'Close Price' AS display_name, -- The name displayed on the screen looks nice.
        'USD' AS unit, -- The unit of the metric
        'line' AS default_chart_type, -- The default chart type for the metric
        'neutral' AS higher_is, -- The higher is better for the metric
        'numeric' AS value_type, -- The value type of the metric
        TRUE AS is_default_visible, -- Whether the metric is visible by default
        10 AS sort_order -- The sort order of the metric

    -- Customize the metrics here
    -- Key market indicators(return, volatility, volume, momentum...).
    UNION ALL

    SELECT 'market', 'fact_crypto_features_hourly', 'return_1h', '1H Return', 'pct', 'line', 'higher_better', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'market', 'fact_crypto_features_hourly', 'realized_volatility_24h', '24H Realized Volatility', 'ratio', 'line', 'higher_riskier', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'market', 'fact_crypto_features_hourly', 'quote_volume', 'Quote Volume', 'USD', 'bar', 'higher_attention', 'numeric', TRUE, 40
    UNION ALL
    SELECT 'market', 'fact_crypto_features_hourly', 'market_momentum_score', 'Market Momentum Score', 'score', 'line', 'higher_better', 'numeric', TRUE, 50

    -- Derivative indicators (Funding rate, Leverage, Put/Call ratio...).
    UNION ALL

    SELECT 'derivatives', 'fact_crypto_features_hourly', 'avg_annualized_funding_coin', 'Annualized Coin-M Funding', 'pct', 'line', 'extreme_riskier', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'derivatives', 'fact_crypto_features_hourly', 'avg_basis_pct', 'Basis %', 'pct', 'line', 'extreme_riskier', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'derivatives', 'fact_crypto_features_hourly', 'max_leverage_stress', 'Max Leverage Stress', 'score', 'line', 'higher_riskier', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'derivatives', 'fact_crypto_features_hourly', 'put_call_oi_ratio', 'Put/Call OI Ratio', 'ratio', 'line', 'higher_defensive', 'numeric', TRUE, 40
    UNION ALL
    SELECT 'derivatives', 'fact_crypto_features_hourly', 'derivatives_risk_score', 'Derivatives Risk Score', 'score', 'line', 'higher_riskier', 'numeric', TRUE, 50

    -- Liquidation data (liquidation zone magnet_norm, panic level panic_norm).
    UNION ALL

    SELECT 'liquidation', 'int_liquidation_bucket_hourly', 'total_liq_usd_bucket', 'Liquidation Bucket USD', 'USD', 'heatmap', 'higher_attention', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'liquidation', 'int_liquidation_bucket_hourly', 'rank_score', 'Bucket Rank Score', 'score', 'heatmap', 'higher_attention', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'liquidation', 'int_liquidation_bucket_hourly', 'panic_norm', 'Panic Normalized', 'score', 'heatmap', 'higher_riskier', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'liquidation', 'int_liquidation_bucket_hourly', 'magnet_norm', 'Magnet Normalized', 'score', 'heatmap', 'higher_attention', 'numeric', TRUE, 40

    -- Social sentiment (sentiment, engagement, bullish/bearish ratio...).
    UNION ALL

    SELECT 'social', 'fact_crypto_features_hourly', 'social_weighted_avg_sentiment', 'Social Weighted Sentiment', 'score', 'line', 'higher_better', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'social', 'fact_crypto_features_hourly', 'social_engagement_proxy', 'Social Engagement Proxy', 'count', 'bar', 'higher_attention', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'social', 'fact_crypto_features_hourly', 'social_bullish_ratio', 'Social Bullish Ratio', 'ratio', 'line', 'higher_better', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'social', 'fact_crypto_features_hourly', 'social_bearish_ratio', 'Social Bearish Ratio', 'ratio', 'line', 'higher_riskier', 'numeric', TRUE, 40

    -- Liquidity data (stablecoin market cap, peg deviation, reserves, utilization...).
    UNION ALL

    SELECT 'liquidity', 'fact_crypto_features_hourly', 'total_stablecoin_market_cap_usd', 'Stablecoin Market Cap', 'USD', 'line', 'higher_liquidity', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'liquidity', 'fact_crypto_features_hourly', 'max_abs_peg_deviation_pct', 'Max Stablecoin Peg Deviation', 'pct', 'line', 'higher_riskier', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'liquidity', 'fact_crypto_features_hourly', 'total_exchange_reserve_usd', 'Exchange Reserves', 'USD', 'line', 'higher_liquidity', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'liquidity', 'fact_crypto_features_hourly', 'system_reserve_utilization', 'System Reserve Utilization', 'ratio', 'line', 'higher_riskier', 'numeric', TRUE, 40

    -- Macroeconomics & Cash Flows (US Stocks S&P 500, ETF Cash Flows...).
    UNION ALL

    SELECT 'macro_etf', 'fact_crypto_features_hourly', 'vix_return_1d', 'VIX 1D Return', 'pct', 'line', 'higher_riskier', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'macro_etf', 'fact_crypto_features_hourly', 'sp500_return_1d', 'SP500 1D Return', 'pct', 'line', 'higher_better', 'numeric', TRUE, 20
    UNION ALL
    SELECT 'macro_etf', 'fact_crypto_features_hourly', 'btc_etf_flow_proxy', 'BTC ETF Flow Proxy', 'USD', 'bar', 'higher_better', 'numeric', TRUE, 30
    UNION ALL
    SELECT 'macro_etf', 'fact_crypto_features_hourly', 'total_etf_volume_weighted_return_1d', 'ETF Volume Weighted Return', 'pct', 'line', 'higher_better', 'numeric', TRUE, 40

    -- System signals (Overall risk score, Market status labels...).
    UNION ALL

    SELECT 'signal', 'fact_crypto_features_hourly', 'overall_risk_score', 'Overall Risk Score', 'score', 'gauge', 'higher_riskier', 'numeric', TRUE, 10
    UNION ALL
    SELECT 'signal', 'fact_crypto_features_hourly', 'core_signal', 'Core Signal', 'category', 'table', 'neutral', 'category', TRUE, 20
    UNION ALL
    SELECT 'signal', 'fact_crypto_features_hourly', 'market_regime', 'Market Regime', 'category', 'table', 'neutral', 'category', TRUE, 30

)

-- Final table with the standardized metric catalog
SELECT
    -- The unique identifier of the metric
    TO_HEX(MD5(CONCAT(dashboard_section, '|', source_model, '|', metric_name))) AS metric_catalog_sk,

    -- The section of the dashboard where the metric is displayed
    dashboard_section,
    source_model,
    metric_name,
    display_name,
    unit,
    default_chart_type,
    higher_is,
    value_type,
    is_default_visible,
    sort_order,

    -- The time when the metric catalog was loaded
    CURRENT_TIMESTAMP() AS mart_loaded_at

FROM metric_catalog
ORDER BY dashboard_section, sort_order