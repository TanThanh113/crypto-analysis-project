{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'liquidation_raw') }}

),

cleaned AS (

    SELECT
        REGEXP_REPLACE(
            UPPER(CAST(symbol AS STRING)),
            r'(USDT_PERP\.A|USDT_PERP|USDT)$',
            ''
        ) AS symbol,

        SAFE_CAST(price_bucket AS FLOAT64) AS price_bucket,
        CAST(ROUND(SAFE_CAST(price_bucket AS FLOAT64), 2) AS STRING) AS price_bucket_key,
        SAFE_CAST(snapshot_timestamp AS TIMESTAMP) AS snapshot_at,

        SAFE_CAST(total_liq_usd_bucket AS FLOAT64) AS total_liq_usd_bucket,
        SAFE_CAST(long_sum AS FLOAT64) AS long_sum,
        SAFE_CAST(short_sum AS FLOAT64) AS short_sum,
        SAFE_CAST(oi_avg AS FLOAT64) AS oi_avg,
        SAFE_CAST(vol_sum AS FLOAT64) AS vol_sum,
        SAFE_CAST(hit_count AS INT64) AS hit_count,

        SAFE_CAST(avg_weighted_liq_ratio AS FLOAT64) AS avg_weighted_liq_ratio,
        SAFE_CAST(avg_panic AS FLOAT64) AS avg_panic,
        SAFE_CAST(avg_money_flow AS FLOAT64) AS avg_money_flow,
        SAFE_CAST(distance_pct AS FLOAT64) AS distance_pct,
        SAFE_CAST(weighted_liq_ratio AS FLOAT64) AS weighted_liq_ratio,
        SAFE_CAST(distance_decay AS FLOAT64) AS distance_decay,
        SAFE_CAST(magnet_score AS FLOAT64) AS magnet_score,
        SAFE_CAST(magnet_zscore AS FLOAT64) AS magnet_zscore,
        SAFE_CAST(magnet_norm AS FLOAT64) AS magnet_norm,

        UPPER(CAST(squeeze_signal AS STRING)) AS squeeze_signal,
        SAFE_CAST(panic_norm AS FLOAT64) AS panic_norm,
        SAFE_CAST(hit_norm AS FLOAT64) AS hit_norm,
        SAFE_CAST(rank_score AS FLOAT64) AS rank_score,
        UPPER(CAST(dominant_side AS STRING)) AS dominant_side,
        UPPER(CAST(stress_level AS STRING)) AS stress_level,

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
            PARTITION BY symbol, snapshot_at, price_bucket_key
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE symbol IN ('BTC', 'ETH')
      AND snapshot_at IS NOT NULL
      AND price_bucket > 0
      AND total_liq_usd_bucket >= 0
      AND hit_count >= 0
      AND weighted_liq_ratio BETWEEN -1 AND 1
      AND panic_norm BETWEEN 0 AND 1
      AND magnet_norm BETWEEN -1 AND 1
      AND squeeze_signal IN (
          'SHORT_SQUEEZE_SETUP',
          'LONG_SQUEEZE_SETUP',
          'NEUTRAL'
      )

)

SELECT * EXCEPT(rn, price_bucket_key)
FROM deduped
WHERE rn = 1