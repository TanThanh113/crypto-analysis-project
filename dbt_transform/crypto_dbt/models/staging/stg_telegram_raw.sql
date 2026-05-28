{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'telegram_sentiment_raw') }}

),

cleaned AS (

    SELECT
        SAFE_CAST(message_id AS INT64) AS message_id,
        SAFE_CAST(date AS DATE) AS message_date,
        SAFE_CAST(datetime AS TIMESTAMP) AS message_at,

        LOWER(CAST(channel AS STRING)) AS channel,
        NULLIF(CAST(text AS STRING), '') AS text,

        SAFE_CAST(nlp_compound AS FLOAT64) AS nlp_compound,
        SAFE_CAST(weighted_sentiment AS FLOAT64) AS weighted_sentiment,
        UPPER(CAST(signal_type AS STRING)) AS signal_type,
        UPPER(CAST(coin_focus AS STRING)) AS coin_focus,
        UPPER(CAST(topic AS STRING)) AS topic,

        SAFE_CAST(views AS INT64) AS views,
        SAFE_CAST(forwards AS INT64) AS forwards,
        SAFE_CAST(replies AS INT64) AS replies,
        SAFE_CAST(reactions AS INT64) AS reactions,
        SAFE_CAST(engagement_score AS FLOAT64) AS engagement_score,
        UPPER(CAST(importance AS STRING)) AS importance,

        SAFE_CAST(word_count AS INT64) AS word_count,
        SAFE_CAST(financial_mentions_count AS INT64) AS financial_mentions_count,
        SAFE_CAST(hour_of_day AS INT64) AS hour_of_day,
        CAST(day_of_week AS STRING) AS day_of_week,
        SAFE_CAST(is_weekend AS BOOL) AS is_weekend,

        NULLIF(CAST(cashtags AS STRING), '') AS cashtags,
        NULLIF(CAST(hashtags AS STRING), '') AS hashtags,
        NULLIF(CAST(urls AS STRING), '') AS urls,
        SAFE_CAST(has_media AS BOOL) AS has_media,
        UPPER(CAST(media_type AS STRING)) AS media_type,
        SAFE_CAST(is_forward AS BOOL) AS is_forward,
        NULLIF(CAST(message_url AS STRING), '') AS message_url,

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
            PARTITION BY channel, message_id
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE message_id IS NOT NULL
      AND channel IS NOT NULL
      AND text IS NOT NULL
      AND nlp_compound BETWEEN -1 AND 1
      AND signal_type IN ('BULLISH', 'BEARISH', 'NEUTRAL')
      AND views >= 0
      AND engagement_score >= 0.99

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1