-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['snapshot_date'],
    partition_by={"field": "snapshot_date", "data_type": "date", "granularity": "day"}
) }}

 -- Filter the columns you need to extract data from, using the data from the previous five days as a reference point.
WITH hourly AS (

    SELECT *
    FROM {{ ref('int_exchange_reserve_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            TIMESTAMP(
                COALESCE(
                    (SELECT MAX(snapshot_date) FROM {{ this }}),
                    DATE '1970-01-01'
                )
            ),
            INTERVAL 5 DAY
          )
    {% endif %}

),

-- Filter out duplicate values.
daily_latest AS (

    SELECT *
    FROM hourly
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY DATE(hour_ts)
        ORDER BY hour_ts DESC, loaded_at DESC
    ) = 1

),

features AS (

    SELECT
        DATE(hour_ts) AS snapshot_date,
        hour_ts AS latest_hour_ts,

        exchange_count,
        tier_1_exchange_count,
        tier_2_exchange_count,
        tier_3_exchange_count,
        tier_4_exchange_count,

        total_exchange_reserve_usd,
        total_exchange_volume_24h_usd,
        total_exchange_volume_24h_usd_normalized,
        total_wash_trading_volume_usd,
        wash_trading_volume_ratio,

        system_reserve_utilization,
        normalized_system_reserve_utilization,

        avg_exchange_trust_score,
        reserve_weighted_trust_score,

        avg_reserve_utilization,
        max_reserve_utilization,
        reserve_weighted_utilization,

        avg_concentration_risk_score,
        max_concentration_risk_score,
        reserve_hhi,

        total_whale_withdrawal_risk,
        max_whale_withdrawal_risk,

        high_bank_run_risk_exchange_count,
        moderate_bank_run_risk_exchange_count,
        safe_bank_run_risk_exchange_count,
        high_bank_run_risk_exchange_ratio,
        safe_bank_run_risk_exchange_ratio,

        top_reserve_exchange,
        top_reserve_exchange_reserve_usd,
        top_volume_exchange,
        highest_utilization_exchange,
        highest_utilization_risk_label,
        highest_whale_withdrawal_risk_exchange,
        highest_wash_trading_exchange,

        exchange_reserve_snapshot_json,

        -- Calculate the percentage increase in total exchange reserve usd compared to yesterday.
        SAFE_DIVIDE(
            total_exchange_reserve_usd
                - LAG(total_exchange_reserve_usd) OVER (ORDER BY DATE(hour_ts)),
            NULLIF(
                LAG(total_exchange_reserve_usd) OVER (ORDER BY DATE(hour_ts)),
                0
            )
        ) AS exchange_reserve_return_1d,

        -- Calculate how much total exchange reserve usd has increased compared to yesterday.
        total_exchange_reserve_usd
            - LAG(total_exchange_reserve_usd) OVER (ORDER BY DATE(hour_ts))
            AS exchange_reserve_change_1d_usd,

        -- Calculate the percentage increase in total exchange volume 24h usd compared to yesterday.
        SAFE_DIVIDE(
            total_exchange_volume_24h_usd
                - LAG(total_exchange_volume_24h_usd) OVER (ORDER BY DATE(hour_ts)),
            NULLIF(
                LAG(total_exchange_volume_24h_usd) OVER (ORDER BY DATE(hour_ts)),
                0
            )
        ) AS exchange_volume_return_1d,

        -- Calculate how much total exchange volume 24h usd has increased compared to yesterday.
        total_exchange_volume_24h_usd
            - LAG(total_exchange_volume_24h_usd) OVER (ORDER BY DATE(hour_ts))
            AS exchange_volume_change_1d_usd,

        -- Calculate the percentage increase in system reserve utilization compared to yesterday.
        system_reserve_utilization
            - LAG(system_reserve_utilization) OVER (ORDER BY DATE(hour_ts))
            AS system_reserve_utilization_change_1d,

        -- Calculate how much normalized system reserve utilization has increased compared to yesterday.
        normalized_system_reserve_utilization
            - LAG(normalized_system_reserve_utilization) OVER (ORDER BY DATE(hour_ts))
            AS normalized_system_reserve_utilization_change_1d,

        -- Calculate how much reserve hhi has increased compared to yesterday.
        reserve_hhi
            - LAG(reserve_hhi) OVER (ORDER BY DATE(hour_ts))
            AS reserve_hhi_change_1d,

        -- Calculate how much high bank run risk exchange count has increased compared to yesterday.
        high_bank_run_risk_exchange_count
            - LAG(high_bank_run_risk_exchange_count) OVER (ORDER BY DATE(hour_ts))
            AS high_bank_run_risk_exchange_count_change_1d,

        -- Calculate how much total whale withdrawal risk has increased compared to yesterday.
        total_whale_withdrawal_risk
            - LAG(total_whale_withdrawal_risk) OVER (ORDER BY DATE(hour_ts))
            AS whale_withdrawal_risk_change_1d,

        -- Calculate how much wash trading volume ratio has increased compared to yesterday.
        wash_trading_volume_ratio
            - LAG(wash_trading_volume_ratio) OVER (ORDER BY DATE(hour_ts))
            AS wash_trading_volume_ratio_change_1d,

        loaded_at,
        available_at

    FROM daily_latest

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM features

{% if is_incremental() %}
WHERE snapshot_date >= DATE_SUB(
    COALESCE(
        (SELECT MAX(snapshot_date) FROM {{ this }}),
        DATE '1970-01-01'
    ),
    INTERVAL 2 DAY
)
{% endif %}