{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'exchange_reserve_raw') }}

),

cleaned AS (

    SELECT
        LOWER(CAST(exchange AS STRING)) AS exchange,
        LOWER(CAST(coingecko_id AS STRING)) AS coingecko_id,

        SAFE_CAST(timestamp AS TIMESTAMP) AS observed_at,
        SAFE_CAST(date AS DATE) AS observed_date,

        SAFE_CAST(trust_score AS FLOAT64) AS trust_score,
        NULLIF(CAST(country AS STRING), '') AS country,
        NULLIF(CAST(year_established AS STRING), '') AS year_established,

        SAFE_CAST(trade_volume_24h_btc AS FLOAT64) AS trade_volume_24h_btc,
        SAFE_CAST(trade_volume_24h_btc_normalized AS FLOAT64) AS trade_volume_24h_btc_normalized,

        SAFE_CAST(llama_reserve_usd AS FLOAT64) AS llama_reserve_usd,
        SAFE_CAST(arkham_reserve_usd AS FLOAT64) AS arkham_reserve_usd,
        SAFE_CAST(actual_reserve_usd AS FLOAT64) AS actual_reserve_usd,
        CAST(data_source AS STRING) AS data_source,

        SAFE_CAST(live_btc_price_usd AS FLOAT64) AS live_btc_price_usd,
        SAFE_CAST(trade_volume_24h_usd AS FLOAT64) AS trade_volume_24h_usd,
        SAFE_CAST(trade_volume_24h_usd_normalized AS FLOAT64) AS trade_volume_24h_usd_normalized,

        SAFE_CAST(reserve_utilization AS FLOAT64) AS reserve_utilization,
        UPPER(CAST(bank_run_risk AS STRING)) AS bank_run_risk,
        SAFE_CAST(wash_trading_volume_usd AS FLOAT64) AS wash_trading_volume_usd,

        SAFE_CAST(reserve_dominance_pct AS FLOAT64) AS reserve_dominance_pct,
        SAFE_CAST(concentration_risk_score AS FLOAT64) AS concentration_risk_score,
        SAFE_CAST(liquidity_score AS FLOAT64) AS liquidity_score,
        LOWER(CAST(exchange_tier AS STRING)) AS exchange_tier,
        SAFE_CAST(whale_withdrawal_risk AS FLOAT64) AS whale_withdrawal_risk,

        CAST(source AS STRING) AS source,
        CAST(run_id AS STRING) AS run_id,
        SAFE_CAST(ingestion_time AS TIMESTAMP) AS ingestion_time,

        CAST(year AS STRING) AS year,
        CAST(month AS STRING) AS month,
        CAST(day AS STRING) AS day

    FROM source_data

),

deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY exchange, observed_at
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE exchange IS NOT NULL
      AND coingecko_id IS NOT NULL
      AND observed_at IS NOT NULL
      AND actual_reserve_usd >= 0
      AND trade_volume_24h_usd >= 0
      AND reserve_dominance_pct BETWEEN 0 AND 100
      AND trust_score BETWEEN 0 AND 10
      AND bank_run_risk IN ('SAFE', 'MODERATE', 'HIGH_RISK')
      AND exchange_tier IN ('tier_1', 'tier_2', 'tier_3', 'tier_4')

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1