{{ config(
    materialized='view'
) }}

WITH AUDIT_RESULTS AS (
    SELECT
        audit_ts,
        project_id,
        table_name,
        suite_name,
        expectation_type,
        success,
        severity,
        result_json,
        expectation_json
    FROM `{{ env_var('GCP_PROJECT_ID') }}.{{ env_var('BQ_ML_OUTPUTS_DATASET', 'ml_outputs') }}.data_quality_audit_results`
    WHERE audit_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),

LATEST_AUDIT_TS AS (
    SELECT
        MAX(audit_ts) AS latest_audit_ts
    FROM AUDIT_RESULTS
),

LATEST_RESULTS AS (
    SELECT
        a.*
    FROM AUDIT_RESULTS a
    CROSS JOIN LATEST_AUDIT_TS l
    WHERE a.audit_ts = l.latest_audit_ts
)

SELECT
    MAX(audit_ts) AS latest_audit_ts,
    COUNT(*) AS total_expectations,
    COUNTIF(success = TRUE) AS passed_expectations,
    COUNTIF(success = FALSE) AS failed_expectations,
    COUNTIF(success = FALSE AND severity = 'critical') AS failed_critical_expectations,
    COUNTIF(success = FALSE AND severity = 'warning') AS failed_warning_expectations,
    CASE
        WHEN COUNTIF(success = FALSE AND severity = 'critical') > 0 THEN 'FAILED'
        WHEN COUNTIF(success = FALSE AND severity = 'warning') > 0 THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS ge_audit_status
FROM LATEST_RESULTS
