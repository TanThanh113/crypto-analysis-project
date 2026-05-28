{{ config(
    materialized='table',
    partition_by={"field": "feature_date", "data_type": "date", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- This model monitors daily ML feature quality by symbol.
-- It helps detect missing features, low completeness, and high feature latency before training.

WITH feature_quality AS (

    SELECT
        feature_date,
        symbol,

        COUNT(*) AS feature_rows,

        -- Caclulate the base completeness score.
        AVG(feature_completeness_score) AS avg_feature_completeness_score,
        MIN(feature_completeness_score) AS min_feature_completeness_score,
        MAX(feature_completeness_score) AS max_feature_completeness_score,

        -- Calculate the training completeness score.
        COUNTIF(is_training_feature_ready = TRUE) AS training_ready_rows,

        -- The total amount of data available for training compared to the overall amount
        SAFE_DIVIDE(
            COUNTIF(is_training_feature_ready = TRUE),
            COUNT(*)
        ) AS training_ready_ratio,

        -- The total amount of missing data compared to the overall amount
        COUNTIF(close_price IS NULL) AS missing_close_price_rows,
        COUNTIF(return_1h IS NULL) AS missing_return_1h_rows,
        COUNTIF(return_4h IS NULL) AS missing_return_4h_rows,
        COUNTIF(return_24h IS NULL) AS missing_return_24h_rows,
        COUNTIF(realized_volatility_24h IS NULL AND rolling_volatility_24h IS NULL) AS missing_volatility_rows,

        COUNTIF(avg_basis_pct IS NULL) AS missing_funding_rows,
        COUNTIF(avg_annualized_funding_coin IS NULL) AS missing_annualized_funding_rows,

        COUNTIF(avg_panic_norm IS NULL) AS missing_liquidation_rows,
        COUNTIF(max_rank_score IS NULL) AS missing_liquidation_rank_rows,

        COUNTIF(avg_mark_iv IS NULL) AS missing_options_rows,
        COUNTIF(put_call_oi_ratio IS NULL) AS missing_options_positioning_rows,

        COUNTIF(social_weighted_avg_sentiment IS NULL) AS missing_social_rows,
        COUNTIF(social_engagement_proxy IS NULL) AS missing_social_engagement_rows,

        COUNTIF(total_stablecoin_market_cap_usd IS NULL) AS missing_stablecoin_rows,
        COUNTIF(total_exchange_reserve_usd IS NULL) AS missing_exchange_reserve_rows,

        COUNTIF(sp500_return_1d IS NULL) AS missing_macro_rows,
        COUNTIF(btc_etf_flow_proxy IS NULL) AS missing_etf_rows,

        -- Calculate the average and maximum latency between the row and the latest available time.
        AVG(feature_latency_minutes) AS avg_feature_latency_minutes,
        MAX(feature_latency_minutes) AS max_feature_latency_minutes,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM {{ ref('mart_ml_features_hourly') }}
    WHERE feature_date IS NOT NULL
      AND symbol IN ('BTC', 'ETH')

    GROUP BY
        feature_date,
        symbol

),

-- Here we will create the final table.
final AS (

    SELECT
        -- Here we will create a unique key for each row.
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(feature_date AS STRING),
                    '|',
                    symbol,
                    '|ml_feature_quality_daily'
                )
            )
        ) AS ml_feature_quality_daily_sk,

        feature_date,
        symbol,

        feature_rows,

        avg_feature_completeness_score,
        min_feature_completeness_score,
        max_feature_completeness_score,

        training_ready_rows,
        training_ready_ratio,

        missing_close_price_rows,
        missing_return_1h_rows,
        missing_return_4h_rows,
        missing_return_24h_rows,
        missing_volatility_rows,

        missing_funding_rows,
        missing_annualized_funding_rows,
        missing_liquidation_rows,
        missing_liquidation_rank_rows,
        missing_options_rows,
        missing_options_positioning_rows,
        missing_social_rows,
        missing_social_engagement_rows,
        missing_stablecoin_rows,
        missing_exchange_reserve_rows,
        missing_macro_rows,
        missing_etf_rows,

        -- Calculate the ratio of missing data compared to the overall amount
        SAFE_DIVIDE(missing_close_price_rows, feature_rows) AS missing_close_price_ratio,
        SAFE_DIVIDE(missing_return_4h_rows, feature_rows) AS missing_return_4h_ratio,
        SAFE_DIVIDE(missing_funding_rows, feature_rows) AS missing_funding_ratio,
        SAFE_DIVIDE(missing_liquidation_rows, feature_rows) AS missing_liquidation_ratio,
        SAFE_DIVIDE(missing_options_rows, feature_rows) AS missing_options_ratio,
        SAFE_DIVIDE(missing_social_rows, feature_rows) AS missing_social_ratio,
        SAFE_DIVIDE(missing_stablecoin_rows, feature_rows) AS missing_stablecoin_ratio,
        SAFE_DIVIDE(missing_exchange_reserve_rows, feature_rows) AS missing_exchange_reserve_ratio,
        SAFE_DIVIDE(missing_macro_rows, feature_rows) AS missing_macro_ratio,
        SAFE_DIVIDE(missing_etf_rows, feature_rows) AS missing_etf_ratio,

        avg_feature_latency_minutes,
        max_feature_latency_minutes,

        -- Label the quality status based on the training completeness and completeness scores.
        CASE
            WHEN training_ready_ratio >= 0.90
                AND avg_feature_completeness_score >= 0.80 THEN 'GOOD'
            WHEN training_ready_ratio >= 0.70
                AND avg_feature_completeness_score >= 0.60 THEN 'ACCEPTABLE'
            WHEN training_ready_ratio >= 0.50 THEN 'WEAK'
            ELSE 'BAD'
        END AS feature_quality_status,

        -- Label the latency status based on the maximum latency.
        CASE
            WHEN max_feature_latency_minutes >= 1440 THEN 'HIGH_LATENCY'
            WHEN max_feature_latency_minutes >= 360 THEN 'MEDIUM_LATENCY'
            ELSE 'LOW_LATENCY'
        END AS feature_latency_status,

        mart_loaded_at

    FROM feature_quality

)

SELECT *
FROM final