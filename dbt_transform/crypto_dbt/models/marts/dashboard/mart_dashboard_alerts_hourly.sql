-- Dashboard Alert Marting
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_alert_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol', 'alert_severity']
) }}

-- Specify data from the previous 14 days to avoid data errors, delayed data, etc.
WITH fact AS (

    SELECT *
    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE

    {% if is_incremental() %}
      AND hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 14 DAY
          )
    {% endif %}

),

alert_rows AS (

    SELECT
        f.hour_ts,
        f.feature_date,
        f.symbol_key,
        f.symbol,
        f.pair_symbol,
        f.crypto_feature_sk,
        f.feature_available_at,
        f.feature_latency_minutes,

        alert.alert_type,
        alert.alert_category,
        alert.alert_severity,
        alert.alert_message,
        alert.alert_score,
        alert.recommended_action

    FROM fact AS f,
        UNNEST([
            --- System Risk Warning
            STRUCT(
                'SYSTEM_RISK' AS alert_type,
                'risk' AS alert_category,
                CASE
                    WHEN COALESCE(f.overall_risk_score, 0) >= 80 THEN 'CRITICAL'
                    WHEN COALESCE(f.overall_risk_score, 0) >= 65 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Overall risk score is ',
                    CAST(ROUND(COALESCE(f.overall_risk_score, 0), 2) AS STRING)
                ) AS alert_message,
                CAST(COALESCE(f.overall_risk_score, 0) AS FLOAT64) AS alert_score,
                'Reduce exposure and review all risk panels.' AS recommended_action
            ),

            --- Derivatives Crowding Warning
            STRUCT(
                'DERIVATIVES_CROWDING' AS alert_type,
                'derivatives' AS alert_category,
                CASE
                    WHEN COALESCE(f.derivatives_risk_score, 0) >= 80 THEN 'CRITICAL'
                    WHEN COALESCE(f.derivatives_risk_score, 0) >= 65 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Derivatives risk score is ',
                    CAST(ROUND(COALESCE(f.derivatives_risk_score, 0), 2) AS STRING)
                ) AS alert_message,
                CAST(COALESCE(f.derivatives_risk_score, 0) AS FLOAT64) AS alert_score,
                'Check funding, leverage stress, options positioning and liquidation clusters.' AS recommended_action
            ),

            --- Liquidation Squeeze Warning
            STRUCT(
                'LIQUIDATION_SQUEEZE' AS alert_type,
                'liquidation' AS alert_category,
                CASE
                    WHEN f.top_squeeze_signal IN ('SHORT_SQUEEZE_SETUP', 'LONG_SQUEEZE_SETUP') THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Top squeeze signal: ',
                    COALESCE(f.top_squeeze_signal, 'UNKNOWN'),
                    ', top bucket rank score: ',
                    CAST(ROUND(COALESCE(f.max_rank_score, 0), 4) AS STRING)
                ) AS alert_message,
                CAST(COALESCE(f.max_rank_score, 0) * 100 AS FLOAT64) AS alert_score,
                'Inspect liquidation heatmap around spot price.' AS recommended_action
            ),

            --- Stablecoin Depeg Warning
            STRUCT(
                'STABLECOIN_DEPEG' AS alert_type,
                'liquidity' AS alert_category,
                CASE
                    WHEN COALESCE(f.max_abs_peg_deviation_pct, 0) >= 2 THEN 'CRITICAL'
                    WHEN COALESCE(f.max_abs_peg_deviation_pct, 0) >= 0.5 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Worst peg symbol: ',
                    COALESCE(f.worst_peg_symbol, 'UNKNOWN'),
                    ', deviation: ',
                    CAST(ROUND(COALESCE(f.max_abs_peg_deviation_pct, 0), 4) AS STRING),
                    '%'
                ) AS alert_message,
                CAST(COALESCE(f.max_abs_peg_deviation_pct, 0) * 10 AS FLOAT64) AS alert_score,
                'Review stablecoin peg and liquidity risk panels.' AS recommended_action
            ),

            --- Exchange Bank Run Warning
            STRUCT(
                'EXCHANGE_BANK_RUN' AS alert_type,
                'exchange' AS alert_category,
                CASE
                    WHEN COALESCE(f.high_bank_run_risk_exchange_count, 0) >= 2 THEN 'CRITICAL'
                    WHEN COALESCE(f.high_bank_run_risk_exchange_count, 0) >= 1 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'High bank-run risk exchange count: ',
                    CAST(COALESCE(f.high_bank_run_risk_exchange_count, 0) AS STRING)
                ) AS alert_message,
                CAST(COALESCE(f.high_bank_run_risk_exchange_count, 0) * 50 AS FLOAT64) AS alert_score,
                'Check exchange reserve utilization and top risky exchange.' AS recommended_action
            ),

            --- Social Panic Warning
            STRUCT(
                'SOCIAL_PANIC' AS alert_type,
                'social' AS alert_category,
                CASE
                    WHEN COALESCE(f.social_sentiment_score, 0) <= -35 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Social sentiment score is ',
                    CAST(ROUND(COALESCE(f.social_sentiment_score, 0), 2) AS STRING)
                ) AS alert_message,
                CAST(ABS(COALESCE(f.social_sentiment_score, 0)) AS FLOAT64) AS alert_score,
                'Review social sentiment, security mentions and panic narratives.' AS recommended_action
            ),

            --- Macro Risk Off Warning
            STRUCT(
                'MACRO_RISK_OFF' AS alert_type,
                'macro' AS alert_category,
                CASE
                    WHEN COALESCE(f.macro_risk_score, 0) >= 75 THEN 'HIGH'
                END AS alert_severity,
                CONCAT(
                    'Macro risk regime: ',
                    COALESCE(f.macro_risk_regime, 'UNKNOWN'),
                    ', macro risk score: ',
                    CAST(ROUND(COALESCE(f.macro_risk_score, 0), 2) AS STRING)
                ) AS alert_message,
                CAST(COALESCE(f.macro_risk_score, 0) AS FLOAT64) AS alert_score,
                'Check macro and ETF dashboard before taking directional risk.' AS recommended_action
            )
        ]) AS alert

    WHERE alert.alert_severity IS NOT NULL

),

-- Final table with the standardized alert data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(hour_ts AS STRING),
                    '|',
                    symbol,
                    '|',
                    alert_type
                )
            )
        ) AS dashboard_alert_sk,

        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        crypto_feature_sk,
        feature_available_at,
        feature_latency_minutes,

        alert_type,
        alert_category,
        alert_severity,
        alert_message,
        alert_score,
        recommended_action,

        CASE alert_severity
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            ELSE 4
        END AS alert_severity_sort_order,

        TRUE AS is_active_alert,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM alert_rows

)

SELECT *
FROM final