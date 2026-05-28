{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'options_raw') }}

),

cleaned AS (

    SELECT
        SAFE_CAST(timestamp AS TIMESTAMP) AS observed_at,
        SAFE_CAST(date AS DATE) AS observed_date,
        SAFE_CAST(hour AS INT64) AS observed_hour,

        CAST(instrument_name AS STRING) AS instrument_name,
        UPPER(CAST(underlying AS STRING)) AS underlying,
        CAST(expiry AS STRING) AS expiry,
        SAFE_CAST(strike AS FLOAT64) AS strike,
        UPPER(CAST(option_type AS STRING)) AS option_type,

        SAFE_CAST(underlying_price AS FLOAT64) AS underlying_price,
        SAFE_CAST(index_price AS FLOAT64) AS index_price,
        SAFE_CAST(mark_price AS FLOAT64) AS mark_price,
        SAFE_CAST(mark_iv AS FLOAT64) AS mark_iv,

        SAFE_CAST(best_bid_price AS FLOAT64) AS best_bid_price,
        SAFE_CAST(best_ask_price AS FLOAT64) AS best_ask_price,
        SAFE_CAST(bid_iv AS FLOAT64) AS bid_iv,
        SAFE_CAST(ask_iv AS FLOAT64) AS ask_iv,
        SAFE_CAST(last_price AS FLOAT64) AS last_price,

        SAFE_CAST(open_interest AS FLOAT64) AS open_interest,
        SAFE_CAST(volume AS FLOAT64) AS volume,
        SAFE_CAST(volume_usd AS FLOAT64) AS volume_usd,

        SAFE_CAST(delta AS FLOAT64) AS delta,
        SAFE_CAST(gamma AS FLOAT64) AS gamma,
        SAFE_CAST(vega AS FLOAT64) AS vega,
        SAFE_CAST(theta AS FLOAT64) AS theta,
        SAFE_CAST(rho AS FLOAT64) AS rho,

        SAFE_CAST(moneyness AS FLOAT64) AS moneyness,
        SAFE_CAST(is_atm AS BOOL) AS is_atm,
        SAFE_CAST(iv_spread AS FLOAT64) AS iv_spread,
        SAFE_CAST(mid_iv AS FLOAT64) AS mid_iv,
        SAFE_CAST(is_call AS BOOL) AS is_call,

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
            PARTITION BY instrument_name, observed_at
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE instrument_name IS NOT NULL
      AND observed_at IS NOT NULL
      AND underlying IN ('BTC', 'ETH')
      AND option_type IN ('C', 'P')
      AND strike > 0
      AND index_price > 0
      AND underlying_price > 0
      AND mark_price >= 0
      AND mark_iv >= 0
      AND mid_iv >= 0
      AND open_interest >= 0
      AND delta BETWEEN -1.05 AND 1.05

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1