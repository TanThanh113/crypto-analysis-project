{{ config(materialized='view') }}

-- This model keeps only the latest prediction-ready row per symbol.
-- Python/Kestra should read this view for live inference.
-- It must not contain labels or future returns.

WITH ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY symbol
            ORDER BY hour_ts DESC, feature_available_at DESC
        ) AS rn

    FROM {{ ref('mart_ml_prediction_input_hourly') }}
    WHERE is_prediction_row = TRUE -- Only take rows that are ready for prediction
      AND feature_available_at <= CURRENT_TIMESTAMP() -- Only take rows that are available at the current time
      AND symbol IN ('BTC', 'ETH') -- Only take rows for BTC and ETH

)

SELECT * EXCEPT(rn)
FROM ranked
WHERE rn = 1