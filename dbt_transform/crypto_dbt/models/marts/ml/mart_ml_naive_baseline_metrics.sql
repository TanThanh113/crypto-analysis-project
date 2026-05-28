{{ config(
    materialized='table',
    cluster_by=['symbol', 'split_name', 'baseline_name']
) }}

-- This model evaluates simple baseline strategies before training real ML models.
-- The goal is to create a benchmark that LightGBM/XGBoost must beat.
--
-- Baseline 1: naive_momentum_4h
--   If past 4h return is positive enough, predict UP.
--   If past 4h return is negative enough, predict DOWN.
--   Otherwise predict FLAT.
--
-- Baseline 2: naive_core_signal_4h
--   Convert rule-based core_signal into UP/DOWN/FLAT prediction.

-- Define two simple baseline strategies.
WITH dataset AS (

    SELECT
        symbol,
        split_name,
        hour_ts,

        future_direction_4h AS actual_direction_4h,

        -- Baseline 1: Predicting cash flow by momentum
        CASE
            WHEN return_4h > 0.003 THEN 'UP'
            WHEN return_4h < -0.003 THEN 'DOWN'
            ELSE 'FLAT'
        END AS naive_momentum_prediction_4h,

        -- Baseline 2: Predicting based on available technical signals.
        CASE
            WHEN core_signal = 'BULLISH' THEN 'UP'
            WHEN core_signal IN ('BEARISH', 'REDUCE_RISK') THEN 'DOWN'
            ELSE 'FLAT'
        END AS naive_signal_prediction_4h

    FROM {{ ref('mart_ml_training_dataset_hourly') }}
    WHERE future_direction_4h IN ('UP', 'DOWN', 'FLAT')

),

-- Combine flat data
baseline_predictions AS (

    -- Explode multiple baseline predictions into one normalized table.
    SELECT
        symbol,
        split_name,
        hour_ts,
        actual_direction_4h,
        baseline.baseline_name,
        baseline.predicted_direction_4h

    FROM dataset,
    UNNEST([
        STRUCT(
            'naive_momentum_4h' AS baseline_name,
            naive_momentum_prediction_4h AS predicted_direction_4h
        ),
        STRUCT(
            'naive_core_signal_4h' AS baseline_name,
            naive_signal_prediction_4h AS predicted_direction_4h
        )
    ]) AS baseline

),

agg AS (

    SELECT
        symbol,
        split_name,
        baseline_name,

        COUNT(*) AS row_count,

        -- Count the number of rows with UP/DOWN/FLAT predictions.
        COUNTIF(actual_direction_4h = 'UP') AS actual_up_count,
        COUNTIF(actual_direction_4h = 'DOWN') AS actual_down_count,
        COUNTIF(actual_direction_4h = 'FLAT') AS actual_flat_count,

        -- Count the number of predicted UP/DOWN/FLAT predictions.
        COUNTIF(predicted_direction_4h = 'UP') AS predicted_up_count,
        COUNTIF(predicted_direction_4h = 'DOWN') AS predicted_down_count,
        COUNTIF(predicted_direction_4h = 'FLAT') AS predicted_flat_count,

        -- Count the number of correct predictions.
        COUNTIF(predicted_direction_4h = actual_direction_4h) AS correct_count,

        -- Count the number of correct UP/DOWN predictions.
        COUNTIF(predicted_direction_4h = 'UP' AND actual_direction_4h = 'UP') AS true_up_count,
        COUNTIF(predicted_direction_4h = 'DOWN' AND actual_direction_4h = 'DOWN') AS true_down_count,
        COUNTIF(predicted_direction_4h = 'FLAT' AND actual_direction_4h = 'FLAT') AS true_flat_count,

        -- Count the number of non-FLAT predictions.
        COUNTIF(predicted_direction_4h != 'FLAT') AS non_flat_prediction_count,
        COUNTIF(actual_direction_4h != 'FLAT') AS non_flat_actual_count,

        -- Count the number of correct non-FLAT directions.
        COUNTIF(
            predicted_direction_4h != 'FLAT'
            AND actual_direction_4h != 'FLAT'
            AND predicted_direction_4h = actual_direction_4h
        ) AS correct_non_flat_direction_count,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS evaluated_at

    FROM baseline_predictions
    GROUP BY
        symbol,
        split_name,
        baseline_name

),

-- Here we will create the final table.
final AS (

    SELECT
        -- Here we will create a unique key for each row.
        TO_HEX(
            MD5(
                CONCAT(
                    symbol,
                    '|',
                    split_name,
                    '|',
                    baseline_name,
                    '|baseline_eval_v1'
                )
            )
        ) AS ml_baseline_metric_sk,

        symbol,
        split_name,
        baseline_name,

        row_count,

        actual_up_count,
        actual_down_count,
        actual_flat_count,

        predicted_up_count,
        predicted_down_count,
        predicted_flat_count,

        correct_count,

        SAFE_DIVIDE(correct_count, row_count) AS accuracy,

        -- Precision answers:
        -- "When baseline predicts UP, how often is it actually UP?"
        SAFE_DIVIDE(true_up_count, NULLIF(predicted_up_count, 0)) AS up_precision,
        SAFE_DIVIDE(true_down_count, NULLIF(predicted_down_count, 0)) AS down_precision,
        SAFE_DIVIDE(true_flat_count, NULLIF(predicted_flat_count, 0)) AS flat_precision,

        -- Recall answers:
        -- "Of all actual UP rows, how many did baseline catch?"
        SAFE_DIVIDE(true_up_count, NULLIF(actual_up_count, 0)) AS up_recall,
        SAFE_DIVIDE(true_down_count, NULLIF(actual_down_count, 0)) AS down_recall,
        SAFE_DIVIDE(true_flat_count, NULLIF(actual_flat_count, 0)) AS flat_recall,

        -- Balanced accuracy is better than raw accuracy when labels are imbalanced.
        (
            COALESCE(SAFE_DIVIDE(true_up_count, NULLIF(actual_up_count, 0)), 0)
            + COALESCE(SAFE_DIVIDE(true_down_count, NULLIF(actual_down_count, 0)), 0)
            + COALESCE(SAFE_DIVIDE(true_flat_count, NULLIF(actual_flat_count, 0)), 0)
        ) / 3.0 AS balanced_accuracy_3class,

        -- Coverage means how often the baseline gives a directional UP/DOWN call.
        SAFE_DIVIDE(non_flat_prediction_count, row_count) AS directional_prediction_coverage,

        -- Directional accuracy ignores FLAT predictions and focuses only on UP/DOWN calls.
        SAFE_DIVIDE(
            correct_non_flat_direction_count,
            NULLIF(non_flat_prediction_count, 0)
        ) AS directional_accuracy_when_predicting,

        true_up_count,
        true_down_count,
        true_flat_count,
        non_flat_prediction_count,
        non_flat_actual_count,
        correct_non_flat_direction_count,

        evaluated_at

    FROM agg

)

SELECT *
FROM final