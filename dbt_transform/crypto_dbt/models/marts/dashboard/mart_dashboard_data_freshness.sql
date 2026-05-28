-- Dashboard Data Freshness Marting
{{ config(materialized='table') }}

-- Hardcoded. The data freshness thresholds for each data layer.
-- The logic classes of each table to check
WITH checks AS (
    -- Core Features
    SELECT
        'core_features' AS data_layer, -- Indicate which segment of the system this data belongs to.
        'fact_crypto_features_hourly' AS model_name, -- Name of the model that produces the data.
        'hourly' AS expected_cadence,
        120 AS freshness_threshold_minutes, -- The maximum time (in minutes) that the system will accept for late data arrivals.
        MAX(hour_ts) AS latest_data_ts,
        MAX(feature_available_at) AS latest_available_at,
        COUNT(*) AS row_count
    FROM {{ ref('fact_crypto_features_hourly') }}
    
    -- Data of Markets Trades (Binance)
    UNION ALL

    SELECT
        'intermediate',
        'int_market_trades_hourly',
        'daily_binance_0430_utc',
        1800,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_market_trades_hourly') }}

    -- Data of Funding Rates
    UNION ALL

    SELECT
        'intermediate',
        'int_funding_hourly',
        'hourly',
        120,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_funding_hourly') }}

    -- Data of Liquidation Buckets
    UNION ALL

    SELECT
        'intermediate',
        'int_liquidation_hourly',
        'hourly',
        120,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_liquidation_hourly') }}

    -- Data of Options
    UNION ALL

    SELECT
        'intermediate',
        'int_options_hourly',
        'hourly',
        120,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_options_hourly') }}

    -- Data of Stablecoins
    UNION ALL

    SELECT
        'intermediate',
        'int_stablecoin_hourly',
        'hourly',
        120,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_stablecoin_hourly') }}

    -- Data of Social Sentiment
    UNION ALL

    SELECT
        'intermediate',
        'int_social_sentiment_hourly',
        'four_times_daily',
        480,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_social_sentiment_hourly') }}

    -- Data of Exchange Reserves
    UNION ALL

    SELECT
        'intermediate',
        'int_exchange_reserve_hourly',
        'four_times_daily',
        480,
        MAX(hour_ts),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_exchange_reserve_hourly') }}

    -- Data of Macroeconomics
    UNION ALL

    SELECT
        'intermediate',
        'int_macro_daily',
        'daily_macro_2200_utc',
        1800,
        TIMESTAMP(MAX(price_date)),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_macro_daily') }}

    -- Data of ETFs
    UNION ALL

    SELECT
        'intermediate',
        'int_etf_daily',
        'daily_etf_2230_utc',
        1800,
        TIMESTAMP(MAX(price_date)),
        MAX(available_at),
        COUNT(*)
    FROM {{ ref('int_etf_daily') }}

),
-- Calculate how long ago the data was received to see if there is any congestion.
scored AS (

    SELECT
        *,
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            latest_available_at,
            MINUTE
        ) AS age_minutes

    FROM checks

),

-- Final table with the standardized data freshness data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(data_layer, '|', model_name))) AS dashboard_data_freshness_sk,

        -- The section of the dashboard where the metric is displayed
        data_layer,
        model_name,
        expected_cadence,
        freshness_threshold_minutes,

        latest_data_ts,
        latest_available_at,
        age_minutes,
        SAFE_DIVIDE(age_minutes, 60) AS age_hours,
        row_count,

        -- Labeling the freshness status
        CASE
            WHEN latest_available_at IS NULL OR row_count = 0 THEN 'MISSING'
            WHEN age_minutes <= freshness_threshold_minutes THEN 'FRESH'
            WHEN age_minutes <= freshness_threshold_minutes * 2 THEN 'STALE'
            ELSE 'OLD'
        END AS freshness_status,

        -- Labeling the freshness status
        CASE
            WHEN latest_available_at IS NULL OR row_count = 0 THEN FALSE
            WHEN age_minutes <= freshness_threshold_minutes THEN TRUE
            ELSE FALSE
        END AS is_fresh,

        -- Labeling the freshness sort order
        CASE
            WHEN latest_available_at IS NULL OR row_count = 0 THEN 4
            WHEN age_minutes <= freshness_threshold_minutes THEN 1
            WHEN age_minutes <= freshness_threshold_minutes * 2 THEN 2
            ELSE 3
        END AS freshness_sort_order,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM scored

)

SELECT *
FROM final
ORDER BY freshness_sort_order, data_layer, model_name