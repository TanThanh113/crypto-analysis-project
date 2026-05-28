{{ config(
    materialized='view',
    enabled=var('enable_ml_outputs_marts', false)
) }}

-- This model exposes ML model evaluation metrics written by Python/Kestra.
-- It is disabled by default because the ml_outputs.model_metrics table may not exist yet.
-- Use this for model monitoring, dashboarding, and comparing model versions.

-- Extract the metrics from the source table.
WITH source_metrics AS (

    SELECT *
    FROM {{ source('ml_outputs', 'model_metrics') }}

),

-- Extract the active model registry from the source table.
active_registry AS (

    SELECT
        model_name,
        model_version,
        model_family,
        algorithm,
        problem_type,
        primary_target,
        is_active

    FROM {{ ref('dim_ml_model_registry') }}

),

-- Change the basic format for the output.
cleaned AS (

    SELECT
        CAST(model_name AS STRING) AS model_name,
        CAST(model_version AS STRING) AS model_version,

        SAFE_CAST(trained_at AS TIMESTAMP) AS trained_at,
        SAFE_CAST(evaluated_at AS TIMESTAMP) AS evaluated_at,

        CAST(target_name AS STRING) AS target_name,
        LOWER(CAST(split_name AS STRING)) AS split_name,

        SAFE_CAST(row_count AS INT64) AS row_count,

        SAFE_CAST(accuracy AS FLOAT64) AS accuracy,
        SAFE_CAST(precision_macro AS FLOAT64) AS precision_macro,
        SAFE_CAST(recall_macro AS FLOAT64) AS recall_macro,
        SAFE_CAST(f1_macro AS FLOAT64) AS f1_macro,
        SAFE_CAST(auc_ovr AS FLOAT64) AS auc_ovr,
        SAFE_CAST(log_loss AS FLOAT64) AS log_loss,
        SAFE_CAST(brier_score AS FLOAT64) AS brier_score,

        CAST(feature_table AS STRING) AS feature_table,
        CAST(training_table AS STRING) AS training_table,
        CAST(model_artifact_uri AS STRING) AS model_artifact_uri,

        CAST(git_sha AS STRING) AS git_sha,
        CAST(run_id AS STRING) AS run_id

    FROM source_metrics
    WHERE CAST(model_name AS STRING) IS NOT NULL
      AND CAST(model_version AS STRING) IS NOT NULL
      AND CAST(target_name AS STRING) IS NOT NULL
      AND LOWER(CAST(split_name AS STRING)) IN ('train', 'validation', 'test')

),

-- Enrich the metrics with additional information.
enriched AS (

    SELECT
        c.*,

        r.model_family,
        r.algorithm,
        r.problem_type,
        r.primary_target,
        COALESCE(r.is_active, FALSE) AS is_active_model,

        1 - accuracy AS error_rate,

        CASE
            WHEN split_name = 'test' THEN TRUE
            ELSE FALSE
        END AS is_test_split,

        CASE
            WHEN target_name = primary_target THEN TRUE
            ELSE FALSE
        END AS is_primary_target_metric,

        -- Calculate the age of the metric in hours
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            evaluated_at,
            HOUR
        ) AS metric_age_hours
    
    FROM cleaned AS c
    -- Join the active registry to filter the metrics
    LEFT JOIN active_registry AS r
        ON c.model_name = r.model_name
       AND c.model_version = r.model_version

),

-- Rank the metrics by recency and target split
ranked AS (

    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY model_name, model_version, target_name, split_name
            ORDER BY evaluated_at DESC, trained_at DESC
        ) AS metric_recency_rank,

        ROW_NUMBER() OVER (
            PARTITION BY target_name, split_name
            ORDER BY evaluated_at DESC, trained_at DESC
        ) AS target_split_recency_rank

    FROM enriched

),

-- Final table with the standardized ML model metric
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    COALESCE(model_name, ''),
                    '|',
                    COALESCE(model_version, ''),
                    '|',
                    COALESCE(target_name, ''),
                    '|',
                    COALESCE(split_name, ''),
                    '|',
                    COALESCE(CAST(evaluated_at AS STRING), ''),
                    '|',
                    COALESCE(run_id, '')
                )
            )
        ) AS ml_model_metric_sk,

        model_name,
        model_version,
        model_family,
        algorithm,
        problem_type,

        target_name,
        primary_target,
        split_name,

        trained_at,
        evaluated_at,
        metric_age_hours,

        row_count,

        accuracy,
        error_rate,
        precision_macro,
        recall_macro,
        f1_macro,
        auc_ovr,
        log_loss,
        brier_score,

        -- The quality label is based on the model quality score.
        CASE
            WHEN row_count IS NULL OR row_count = 0 THEN 'NO_ROWS'
            WHEN f1_macro >= 0.60 THEN 'GOOD'
            WHEN f1_macro >= 0.50 THEN 'ACCEPTABLE'
            WHEN f1_macro >= 0.40 THEN 'WEAK'
            ELSE 'BAD'
        END AS model_quality_label,

        -- The auc quality label is based on the auc score.
        CASE
            WHEN auc_ovr IS NULL THEN 'AUC_NOT_AVAILABLE'
            WHEN auc_ovr >= 0.65 THEN 'GOOD_AUC'
            WHEN auc_ovr >= 0.55 THEN 'WEAK_AUC'
            ELSE 'POOR_AUC'
        END AS auc_quality_label,

        feature_table,
        training_table,
        model_artifact_uri,

        git_sha,
        run_id,

        is_active_model,
        is_test_split,
        is_primary_target_metric,

        metric_recency_rank = 1 AS is_latest_for_model_split,
        target_split_recency_rank = 1 AS is_latest_for_target_split,

        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM ranked

)

SELECT *
FROM final