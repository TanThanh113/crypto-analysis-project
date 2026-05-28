{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'stablecoin_supply_raw') }}

),

cleaned AS (

    SELECT
        UPPER(CAST(symbol AS STRING)) AS symbol,
        LOWER(CAST(coin_id AS STRING)) AS coin_id,

        SAFE_CAST(timestamp AS TIMESTAMP) AS observed_at,
        SAFE_CAST(date AS DATE) AS observed_date,

        SAFE_CAST(price_usd AS FLOAT64) AS price_usd,
        SAFE_CAST(market_cap_usd AS FLOAT64) AS market_cap_usd,
        SAFE_CAST(fully_diluted_valuation_usd AS FLOAT64) AS fully_diluted_valuation_usd,
        SAFE_CAST(volume_24h_usd AS FLOAT64) AS volume_24h_usd,

        SAFE_CAST(circulating_supply AS FLOAT64) AS circulating_supply,
        SAFE_CAST(total_supply AS FLOAT64) AS total_supply,
        SAFE_CAST(max_supply AS FLOAT64) AS max_supply,
        SAFE_CAST(market_cap_rank AS INT64) AS market_cap_rank,

        SAFE_CAST(peg_deviation_pct AS FLOAT64) AS peg_deviation_pct,
        SAFE_CAST(utilization_ratio AS FLOAT64) AS utilization_ratio,
        SAFE_CAST(volume_to_marketcap AS FLOAT64) AS volume_to_marketcap,
        LOWER(CAST(peg_regime AS STRING)) AS peg_regime,
        SAFE_CAST(depeg_risk_score AS FLOAT64) AS depeg_risk_score,

        SAFE_CAST(market_cap_usd_log AS FLOAT64) AS market_cap_usd_log,
        SAFE_CAST(volume_24h_usd_log AS FLOAT64) AS volume_24h_usd_log,
        SAFE_CAST(circulating_supply_log AS FLOAT64) AS circulating_supply_log,

        SAFE_CAST(stablecoin_dominance_pct AS FLOAT64) AS stablecoin_dominance_pct,
        LOWER(CAST(liquidity_tier AS STRING)) AS liquidity_tier,
        SAFE_CAST(liquidity_score AS FLOAT64) AS liquidity_score,

        SAFE_CAST(timestamp_unix AS INT64) AS timestamp_unix,
        SAFE_CAST(hour AS INT64) AS hour,
        SAFE_CAST(day_of_week AS INT64) AS day_of_week,
        SAFE_CAST(hour_sin AS FLOAT64) AS hour_sin,
        SAFE_CAST(hour_cos AS FLOAT64) AS hour_cos,

        SAFE_CAST(is_peg_outlier AS INT64) AS is_peg_outlier,
        SAFE_CAST(is_volume_outlier AS INT64) AS is_volume_outlier,

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
            PARTITION BY symbol, observed_at
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE symbol IS NOT NULL
      AND coin_id IS NOT NULL
      AND observed_at IS NOT NULL
      AND price_usd BETWEEN 0.95 AND 1.05
      AND market_cap_usd > 0
      AND volume_24h_usd >= 0
      AND circulating_supply >= 0
      AND stablecoin_dominance_pct BETWEEN 0 AND 100
      AND peg_regime IN ('premium', 'depeg_risk', 'stable')
      AND liquidity_tier IN ('mega', 'large', 'medium', 'small')
      AND hour BETWEEN 0 AND 23
      AND day_of_week BETWEEN 0 AND 6
      AND is_peg_outlier IN (0, 1)
      AND is_volume_outlier IN (0, 1)

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1