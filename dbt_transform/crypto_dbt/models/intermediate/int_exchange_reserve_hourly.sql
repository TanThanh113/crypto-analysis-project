-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"}
) }}

-- Filter the columns you need to extract data from, using the data from the previous three days as a reference point.
WITH source_data AS (

    SELECT
        TIMESTAMP_TRUNC(observed_at, HOUR) AS hour_ts,

        exchange,
        coingecko_id,
        observed_at,
        trust_score,
        trade_volume_24h_usd,
        trade_volume_24h_usd_normalized,
        actual_reserve_usd,
        data_source,
        reserve_utilization,
        bank_run_risk,
        wash_trading_volume_usd,
        reserve_dominance_pct,
        concentration_risk_score,
        liquidity_score,
        exchange_tier,
        whale_withdrawal_risk,
        ingestion_time

    FROM {{ ref('stg_exchange_reserve') }}
    WHERE observed_at IS NOT NULL
      AND exchange IS NOT NULL
      AND actual_reserve_usd >= 0
      AND trade_volume_24h_usd >= 0

    {% if is_incremental() %}
      AND observed_at >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 3 DAY
          )
    {% endif %}

),

-- Filter out duplicate values.
latest_exchange AS (

    SELECT *
    FROM source_data
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY hour_ts, exchange
        ORDER BY observed_at DESC, ingestion_time DESC
    ) = 1

),

aggregated AS (

    SELECT
        hour_ts,

        -- Count the number of exchanges reporting and their tier.
        COUNT(*) AS exchange_count,
        COUNTIF(exchange_tier = 'tier_1') AS tier_1_exchange_count,
        COUNTIF(exchange_tier = 'tier_2') AS tier_2_exchange_count,
        COUNTIF(exchange_tier = 'tier_3') AS tier_3_exchange_count,
        COUNTIF(exchange_tier = 'tier_4') AS tier_4_exchange_count,

        -- Calculate the sum based on certain conditions.
        SUM(actual_reserve_usd) AS total_exchange_reserve_usd,
        SUM(trade_volume_24h_usd) AS total_exchange_volume_24h_usd,
        SUM(trade_volume_24h_usd_normalized) AS total_exchange_volume_24h_usd_normalized,
        SUM(wash_trading_volume_usd) AS total_wash_trading_volume_usd,

        -- Calculate the wash trading volume ratio based on sum of wash trading volume usd and sum of trade volume 24h usd.
        SAFE_DIVIDE(
            SUM(wash_trading_volume_usd),
            NULLIF(SUM(trade_volume_24h_usd), 0)
        ) AS wash_trading_volume_ratio,

        -- Calculate the system reserve utilization based on sum of trade volume 24h usd and sum of actual reserve usd.
        SAFE_DIVIDE(
            SUM(trade_volume_24h_usd),
            NULLIF(SUM(actual_reserve_usd), 0)
        ) AS system_reserve_utilization,

        -- Calculate the normalized system reserve utilization based on sum of trade volume 24h usd normalized and sum of actual reserve usd.
        SAFE_DIVIDE(
            SUM(trade_volume_24h_usd_normalized),
            NULLIF(SUM(actual_reserve_usd), 0)
        ) AS normalized_system_reserve_utilization,

        -- Calculate the average based on certain conditions.
        AVG(trust_score) AS avg_exchange_trust_score,

        -- Calculate the reserve weighted trust score based on sum of trust score by weighted actual reserve.
        SAFE_DIVIDE(
            SUM(trust_score * actual_reserve_usd),
            NULLIF(SUM(actual_reserve_usd), 0)
        ) AS reserve_weighted_trust_score,

        AVG(reserve_utilization) AS avg_reserve_utilization,
        MAX(reserve_utilization) AS max_reserve_utilization,

        -- Calculate the reserve weighted utilization based on sum of utilization by weighted actual reserve.
        SAFE_DIVIDE(
            SUM(reserve_utilization * actual_reserve_usd),
            NULLIF(SUM(actual_reserve_usd), 0)
        ) AS reserve_weighted_utilization,

        AVG(concentration_risk_score) AS avg_concentration_risk_score,
        MAX(concentration_risk_score) AS max_concentration_risk_score,

        SUM(POW(reserve_dominance_pct / 100, 2)) AS reserve_hhi,

        SUM(whale_withdrawal_risk) AS total_whale_withdrawal_risk,
        MAX(whale_withdrawal_risk) AS max_whale_withdrawal_risk,

        -- Calculate the count based on certain conditions.
        COUNTIF(bank_run_risk = 'HIGH_RISK') AS high_bank_run_risk_exchange_count,
        COUNTIF(bank_run_risk = 'MODERATE') AS moderate_bank_run_risk_exchange_count,
        COUNTIF(bank_run_risk = 'SAFE') AS safe_bank_run_risk_exchange_count,

        -- Calculate the ratio of high bank run risk exchange count to total exchange count.
        SAFE_DIVIDE(
            COUNTIF(bank_run_risk = 'HIGH_RISK'),
            NULLIF(COUNT(*), 0)
        ) AS high_bank_run_risk_exchange_ratio,

        -- Calculate the ratio of safe bank run risk exchange count to total exchange count.
        SAFE_DIVIDE(
            COUNTIF(bank_run_risk = 'SAFE'),
            NULLIF(COUNT(*), 0)
        ) AS safe_bank_run_risk_exchange_ratio,

        -- Find the top reserve exchange based on the actual reserve usd and trade volume 24h usd.
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY actual_reserve_usd DESC, trade_volume_24h_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reserve_exchange,

        -- Find the top reserve exchange reserve usd based on the actual reserve usd and trade volume 24h usd.
        ARRAY_AGG(
            actual_reserve_usd IGNORE NULLS
            ORDER BY actual_reserve_usd DESC, trade_volume_24h_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reserve_exchange_reserve_usd,

        -- Find the top volume exchange based on the trade volume 24h usd and actual reserve usd.
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY trade_volume_24h_usd DESC, actual_reserve_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_volume_exchange,

        -- Find the highest utilization exchange based on the reserve utilization and actual reserve usd.
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY reserve_utilization DESC, actual_reserve_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_utilization_exchange,

        -- Find the highest utilization risk label based on the reserve utilization and actual reserve usd.
        ARRAY_AGG(
            bank_run_risk IGNORE NULLS
            ORDER BY reserve_utilization DESC, actual_reserve_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_utilization_risk_label,

        -- Find the highest whale withdrawal risk exchange based on the whale withdrawal risk and actual reserve usd.
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY whale_withdrawal_risk DESC, actual_reserve_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_whale_withdrawal_risk_exchange,

        -- Find the highest wash trading exchange based on the wash trading volume usd and trade volume 24h usd.
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY wash_trading_volume_usd DESC, trade_volume_24h_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_wash_trading_exchange,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    exchange,
                    coingecko_id,
                    trust_score,
                    actual_reserve_usd,
                    trade_volume_24h_usd,
                    trade_volume_24h_usd_normalized,
                    reserve_utilization,
                    reserve_dominance_pct,
                    concentration_risk_score,
                    liquidity_score,
                    bank_run_risk,
                    exchange_tier,
                    whale_withdrawal_risk,
                    wash_trading_volume_usd,
                    data_source
                )
                ORDER BY actual_reserve_usd DESC, trade_volume_24h_usd DESC
            )
        ) AS exchange_reserve_snapshot_json,

        -- Calculate max latest_observed_at, loaded_at, and available_at.
        MAX(observed_at) AS latest_observed_at,
        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM latest_exchange
    GROUP BY hour_ts

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM aggregated

{% if is_incremental() %}
WHERE hour_ts >= TIMESTAMP_SUB(
    COALESCE(
        (SELECT MAX(hour_ts) FROM {{ this }}),
        TIMESTAMP('1970-01-01')
    ),
    INTERVAL 2 DAY
)
{% endif %}