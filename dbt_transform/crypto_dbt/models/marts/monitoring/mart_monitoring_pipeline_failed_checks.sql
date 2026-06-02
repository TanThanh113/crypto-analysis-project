{{ config(
    materialized='view'
) }}

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
WHERE success = FALSE
  AND check_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
