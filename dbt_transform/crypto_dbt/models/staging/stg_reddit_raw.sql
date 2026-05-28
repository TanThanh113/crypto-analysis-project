{{ config(materialized='view') }}

WITH source_data AS (

    SELECT *
    FROM {{ source('raw_crypto', 'reddit_sentiment_raw') }}

),

cleaned AS (

    SELECT
        CAST(post_id AS STRING) AS post_id,
        LOWER(CAST(subreddit AS STRING)) AS subreddit,

        NULLIF(CAST(title AS STRING), '') AS title,
        NULLIF(CAST(body AS STRING), '') AS body,
        NULLIF(CAST(full_text AS STRING), '') AS full_text,
        NULLIF(CAST(author AS STRING), '') AS author,

        SAFE_CAST(created_utc AS TIMESTAMP) AS created_at,

        SAFE_CAST(score AS INT64) AS score,
        SAFE_CAST(comments AS INT64) AS comments,
        SAFE_CAST(engagement_velocity AS FLOAT64) AS engagement_velocity,
        SAFE_CAST(interaction_weight AS FLOAT64) AS interaction_weight,
        SAFE_CAST(final_weight AS FLOAT64) AS final_weight,

        SAFE_CAST(sentiment_compound AS FLOAT64) AS sentiment_compound,
        SAFE_CAST(weighted_sentiment AS FLOAT64) AS weighted_sentiment,

        UPPER(CAST(asset AS STRING)) AS asset,
        NULLIF(CAST(event_tags AS STRING), '') AS event_tags,
        SAFE_CAST(is_viral AS BOOL) AS is_viral,
        NULLIF(CAST(url AS STRING), '') AS url,

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
            PARTITION BY post_id
            ORDER BY ingestion_time DESC, run_id DESC
        ) AS rn
    FROM cleaned
    WHERE post_id IS NOT NULL
      AND full_text IS NOT NULL
      AND asset IN ('BTC', 'ETH', 'GENERAL')
      AND sentiment_compound BETWEEN -1 AND 1
      AND comments >= 0
      AND engagement_velocity >= 0

)

SELECT * EXCEPT(rn)
FROM deduped
WHERE rn = 1