-- Create a checklist outlining the four core problems your AI must learn:
{{ config(materialized='table') }}

WITH target_catalog AS (

    -- Forecast of direction for the next hour
    SELECT
        'future_direction_1h' AS target_name, 
        'classification' AS target_type,
        1 AS horizon_hours, -- The timeframe in which AI needs to look to the future.
        0.001 AS up_threshold_return,
        -0.001 AS down_threshold_return,
        'UP if future_return_1h > 0.10%, DOWN if < -0.10%, otherwise FLAT' AS definition,
        FALSE AS primary_target,
        TRUE AS enabled -- Inform the system that this problem is being applied.

    -- Forecast of direction for the next 4 hours(The main goal of the AI ​​model)
    UNION ALL

    SELECT
        'future_direction_4h' AS target_name,
        'classification' AS target_type,
        4 AS horizon_hours,
        0.003 AS up_threshold_return,
        -0.003 AS down_threshold_return,
        'UP if future_return_4h > 0.30%, DOWN if < -0.30%, otherwise FLAT' AS definition,
        TRUE AS primary_target,
        TRUE AS enabled

    -- Forecast of direction for the next 24 hours
    UNION ALL

    SELECT
        'future_direction_24h' AS target_name,
        'classification' AS target_type,
        24 AS horizon_hours,
        0.010 AS up_threshold_return,
        -0.010 AS down_threshold_return,
        'UP if future_return_24h > 1.00%, DOWN if < -1.00%, otherwise FLAT' AS definition,
        FALSE AS primary_target,
        TRUE AS enabled

    -- Predicting the extent of price fluctuations
    UNION ALL

    SELECT
        'future_volatility_24h' AS target_name,
        'regression' AS target_type,
        24 AS horizon_hours,
        CAST(NULL AS FLOAT64) AS up_threshold_return,
        CAST(NULL AS FLOAT64) AS down_threshold_return,
        'Realized volatility of hourly log returns over the next 24 hours' AS definition,
        FALSE AS primary_target,
        TRUE AS enabled

)

SELECT
    -- The unique identifier of the metric
    TO_HEX(MD5(target_name)) AS target_catalog_sk,

    target_name,
    target_type,
    horizon_hours,
    up_threshold_return,
    down_threshold_return,
    definition,
    primary_target,
    enabled,

    -- The time when the metric catalog was loaded
    CURRENT_TIMESTAMP() AS created_at

FROM target_catalog