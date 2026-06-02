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
    WHERE check_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),

RUN_SUMMARY AS (
    SELECT
        run_id,
        MAX(check_ts) AS latest_check_ts,
        COUNT(*) AS total_checks,
        COUNTIF(success = TRUE) AS passed_checks,
        COUNTIF(success = FALSE) AS failed_checks,
        COUNTIF(success = FALSE AND severity = 'critical') AS failed_critical_checks,
        COUNTIF(success = FALSE AND severity = 'warning') AS failed_warning_checks
    FROM HEALTH_RESULTS
    WHERE run_id IS NOT NULL
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
    END AS pipeline_health_status
FROM RUN_SUMMARY
