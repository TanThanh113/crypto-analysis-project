{{ config(
    materialized='view',
    enabled=var('enable_ml_outputs_marts', false)
) }}

-- This model exposes the latest ML prediction per symbol and target.
-- Source table is written by Python/Kestra after loading the trained model artifact.
-- This model is disabled by default because the prediction output table may not exist yet.

WITH source_predictions AS (

    SELECT *
    FROM {{ source('ml_outputs', 'model_predictions') }}

),

active_models AS (

    -- Only expose predictions from active registered models.
    SELECT
        model_name,
        model_version,
        primary_target

    FROM {{ ref('dim_ml_model_registry') }}
    WHERE is_active = TRUE

),

-- Change the basic format for the output.
cleaned AS (

    SELECT
        CAST(prediction_id AS STRING) AS prediction_id,
        CAST(model_name AS STRING) AS model_name,
        CAST(model_version AS STRING) AS model_version,

        SAFE_CAST(predicted_at AS TIMESTAMP) AS predicted_at,
        SAFE_CAST(hour_ts AS TIMESTAMP) AS hour_ts,

        DATE(SAFE_CAST(hour_ts AS TIMESTAMP)) AS feature_date,

        UPPER(CAST(symbol AS STRING)) AS symbol,
        CONCAT(UPPER(CAST(symbol AS STRING)), 'USDT') AS pair_symbol,

        CAST(target_name AS STRING) AS target_name,

        UPPER(CAST(predicted_class AS STRING)) AS predicted_class,

        SAFE_CAST(prob_up AS FLOAT64) AS prob_up,
        SAFE_CAST(prob_down AS FLOAT64) AS prob_down,
        SAFE_CAST(prob_flat AS FLOAT64) AS prob_flat,

        SAFE_CAST(predicted_return_4h AS FLOAT64) AS predicted_return_4h,

        SAFE_CAST(confidence_score AS FLOAT64) AS raw_confidence_score,

        UPPER(CAST(signal AS STRING)) AS signal,

        CAST(model_artifact_uri AS STRING) AS model_artifact_uri,

        SAFE_CAST(feature_available_at AS TIMESTAMP) AS feature_available_at

    FROM source_predictions
    WHERE UPPER(CAST(symbol AS STRING)) IN ('BTC', 'ETH')
      AND SAFE_CAST(predicted_at AS TIMESTAMP) IS NOT NULL
      AND SAFE_CAST(hour_ts AS TIMESTAMP) IS NOT NULL
      AND CAST(target_name AS STRING) IS NOT NULL

),

validated AS (

    SELECT
        *,
        -- Confidence score of the prediction
        COALESCE(
            raw_confidence_score,
            GREATEST(
                COALESCE(prob_up, 0),
                COALESCE(prob_down, 0),
                COALESCE(prob_flat, 0)
            ) * 100
        ) AS confidence_score,

        -- Sum of the probability of each direction
        COALESCE(prob_up, 0)
            + COALESCE(prob_down, 0)
            + COALESCE(prob_flat, 0) AS probability_sum,

        -- That data shows how long it's actually been.
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            predicted_at,
            MINUTE
        ) AS prediction_age_minutes,

        -- That data shows how long ago it was received on the system.
        TIMESTAMP_DIFF(
            predicted_at,
            feature_available_at,
            MINUTE
        ) AS feature_to_prediction_latency_minutes,

        -- The predicted class is valid if it's not NULL.
        CASE
            WHEN predicted_class IN ('UP', 'DOWN', 'FLAT') THEN TRUE
            ELSE FALSE
        END AS is_valid_predicted_class,

        -- The probability output is valid if it's not NULL.
        CASE
            WHEN prob_up IS NULL
                AND prob_down IS NULL
                AND prob_flat IS NULL THEN FALSE
            ELSE TRUE
        END AS has_probability_output

    FROM cleaned

),

-- Logic join table
filtered_to_active_model AS (

    SELECT
        v.*

    FROM validated AS v
    INNER JOIN active_models AS m
        ON v.model_name = m.model_name
       AND v.model_version = m.model_version
       AND v.target_name = m.primary_target

),

-- Only retrieve the latest data.
ranked AS (

    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY symbol, target_name
            ORDER BY predicted_at DESC, hour_ts DESC
        ) AS rn

    FROM filtered_to_active_model
    WHERE is_valid_predicted_class = TRUE

),

-- Final table with the standardized ML prediction
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    symbol,
                    '|',
                    target_name,
                    '|',
                    model_name,
                    '|',
                    model_version,
                    '|latest_prediction'
                )
            )
        ) AS ml_latest_prediction_sk,

        prediction_id,

        model_name,
        model_version,
        target_name,

        predicted_at,
        hour_ts,
        feature_date,

        symbol,
        pair_symbol,

        predicted_class,
        prob_up,
        prob_down,
        prob_flat,
        probability_sum,

        predicted_return_4h,
        confidence_score,

        -- The confidence label is based on the confidence score.
        CASE
            WHEN confidence_score >= 80 THEN 'HIGH_CONFIDENCE'
            WHEN confidence_score >= 60 THEN 'MEDIUM_CONFIDENCE'
            ELSE 'LOW_CONFIDENCE'
        END AS confidence_label,

        -- The prediction direction is based on the predicted class.
        CASE
            WHEN predicted_class = 'UP' THEN 'BULLISH'
            WHEN predicted_class = 'DOWN' THEN 'BEARISH'
            WHEN predicted_class = 'FLAT' THEN 'NEUTRAL'
            ELSE 'UNKNOWN'
        END AS prediction_direction,

        signal,

        -- The signal is based on the signal column.
        CASE
            WHEN signal IS NOT NULL THEN signal
            WHEN predicted_class = 'UP' THEN 'BULLISH_SETUP'
            WHEN predicted_class = 'DOWN' THEN 'BEARISH_SETUP'
            WHEN predicted_class = 'FLAT' THEN 'NEUTRAL_WAIT'
            ELSE 'NO_SIGNAL'
        END AS dashboard_signal,

        model_artifact_uri,
        feature_available_at,

        prediction_age_minutes,
        feature_to_prediction_latency_minutes,

        has_probability_output,

        -- The prediction freshness status is based on the prediction age.
        CASE
            WHEN prediction_age_minutes <= 90 THEN 'FRESH'
            WHEN prediction_age_minutes <= 240 THEN 'STALE'
            ELSE 'OLD'
        END AS prediction_freshness_status,

        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM ranked
    WHERE rn = 1

)

SELECT *
FROM final