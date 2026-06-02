{{ config(
    materialized='view'
) }}

WITH HEALTH_RESULTS AS (
    SELECT
        check_ts,
        run_id,
        check_id,
        check_type,
        severity,
        success,
        metric_value,
        threshold,
        message,
        details_json
    FROM `{{ env_var('GCP_PROJECT_ID') }}.{{ env_var('BQ_ML_OUTPUTS_DATASET', 'ml_outputs') }}.pipeline_health_check_results`
    WHERE run_id IS NOT NULL
),

LATEST_RUN AS (
    SELECT
        run_id
    FROM HEALTH_RESULTS
    QUALIFY ROW_NUMBER() OVER (
        ORDER BY check_ts DESC
    ) = 1
),

LATEST_RUN_RESULTS AS (
    SELECT
        h.*
    FROM HEALTH_RESULTS h
    INNER JOIN LATEST_RUN r
        ON h.run_id = r.run_id
),

SUMMARY AS (
    SELECT
        run_id,
        MAX(check_ts) AS latest_check_ts,
        COUNT(*) AS total_checks,
        COUNTIF(success = TRUE) AS passed_checks,
        COUNTIF(success = FALSE) AS failed_checks,
        COUNTIF(success = FALSE AND severity = 'critical') AS failed_critical_checks,
        COUNTIF(success = FALSE AND severity = 'warning') AS failed_warning_checks,
        ARRAY_AGG(
            IF(success = FALSE, CONCAT('[', severity, '] ', check_id, ': ', message), NULL)
            IGNORE NULLS
            ORDER BY severity, check_id
        ) AS failed_check_messages
    FROM LATEST_RUN_RESULTS
    GROUP BY run_id
)

SELECT
    run_id,
    latest_check_ts,
    total_checks,
    passed_checks,
    failed_checks,
    failed_critical_checks,
    failed_warning_checks,
    CASE
        WHEN failed_critical_checks > 0 THEN 'FAILED'
        WHEN failed_warning_checks > 0 THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS pipeline_health_status,
    failed_check_messages
FROM SUMMARY
