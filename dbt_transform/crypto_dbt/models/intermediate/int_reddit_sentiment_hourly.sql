-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous three days as a reference point.
WITH posts AS (

    SELECT
        TIMESTAMP_TRUNC(created_at, HOUR) AS hour_ts,
        UPPER(asset) AS symbol,

        subreddit,
        post_id,
        title,
        score,
        comments,
        engagement_velocity,
        interaction_weight,
        final_weight,
        sentiment_compound,
        weighted_sentiment,
        event_tags,
        is_viral,
        ingestion_time

    FROM {{ ref('stg_reddit_raw') }}
    WHERE created_at IS NOT NULL
      AND asset IN ('BTC', 'ETH', 'GENERAL')
      AND post_id IS NOT NULL

    {% if is_incremental() %}
      AND created_at >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 3 DAY
          )
    {% endif %}

),

aggregated AS (

    SELECT
        hour_ts,
        symbol,

        -- Calculate the count based on certain conditions.
        COUNT(*) AS reddit_post_count,
        COUNT(DISTINCT subreddit) AS reddit_subreddit_count,

        -- Calculate the sum based on certain conditions.
        SUM(score) AS reddit_score_sum,
        SUM(comments) AS reddit_comment_sum,
        SUM(interaction_weight) AS reddit_interaction_weight_sum,
        SUM(final_weight) AS reddit_weight_sum,
        SUM(weighted_sentiment) AS reddit_sentiment_weight_sum,

        -- Calculate the reddit weighted average sentiment based on sum of weighted sentiment and final weight.
        SAFE_DIVIDE(
            SUM(weighted_sentiment),
            NULLIF(SUM(final_weight), 0)
        ) AS reddit_weighted_avg_sentiment,

        AVG(sentiment_compound) AS reddit_avg_sentiment,
        
        -- Calculate the reddit interaction weighted average sentiment based by weighted interaction weight.
        SAFE_DIVIDE(
            SUM(sentiment_compound * interaction_weight),
            NULLIF(SUM(interaction_weight), 0)
        ) AS reddit_interaction_weighted_avg_sentiment,

        MAX(engagement_velocity) AS reddit_max_engagement_velocity,
        AVG(engagement_velocity) AS reddit_avg_engagement_velocity,

        COUNTIF(is_viral) AS reddit_viral_post_count,

        -- Calculate the count based on certain conditions.
        COUNTIF(sentiment_compound > 0.05) AS reddit_bullish_post_count,
        COUNTIF(sentiment_compound < -0.05) AS reddit_bearish_post_count,
        COUNTIF(sentiment_compound BETWEEN -0.05 AND 0.05) AS reddit_neutral_post_count,

        -- Calculate the ratio of reddit bullish post count to reddit post count.
        SAFE_DIVIDE(
            COUNTIF(sentiment_compound > 0.05),
            NULLIF(COUNT(*), 0)
        ) AS reddit_bullish_ratio,

        -- Calculate the ratio of reddit bearish post count to reddit post count.
        SAFE_DIVIDE(
            COUNTIF(sentiment_compound < -0.05),
            NULLIF(COUNT(*), 0)
        ) AS reddit_bearish_ratio,

        -- Calculate the ratio of reddit neutral post count to reddit post count.
        SAFE_DIVIDE(
            COUNTIF(sentiment_compound BETWEEN -0.05 AND 0.05),
            NULLIF(COUNT(*), 0)
        ) AS reddit_neutral_ratio,

        -- Calculate the count based on certain conditions.
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'ETF')) AS reddit_etf_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'HACK')) AS reddit_hack_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'WHALE')) AS reddit_whale_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'LIQUIDATION')) AS reddit_liquidation_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'FED')) AS reddit_fed_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'SEC')) AS reddit_sec_mentions,
        COUNTIF(REGEXP_CONTAINS(COALESCE(event_tags, ''), r'BLACKROCK')) AS reddit_blackrock_mentions,

        -- Find the top reddit title based on the engagement velocity, score and comments.
        ARRAY_AGG(
            title IGNORE NULLS
            ORDER BY engagement_velocity DESC, score DESC, comments DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reddit_title,

        -- Find the top reddit subreddit based on the engagement velocity, score and comments.
        ARRAY_AGG(
            subreddit IGNORE NULLS
            ORDER BY engagement_velocity DESC, score DESC, comments DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reddit_subreddit,

        -- Find the top reddit post id based on the engagement velocity, score and comments.
        ARRAY_AGG(
            post_id IGNORE NULLS
            ORDER BY engagement_velocity DESC, score DESC, comments DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_reddit_post_id,

        -- Create a data stream that summarizes all the data using JSON code.(top 10 reddit posts)
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    post_id,
                    subreddit,
                    title,
                    score,
                    comments,
                    engagement_velocity,
                    sentiment_compound,
                    weighted_sentiment,
                    event_tags,
                    is_viral
                )
                ORDER BY engagement_velocity DESC, score DESC, comments DESC
                LIMIT 10
            )
        ) AS top_10_reddit_posts_json,

        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM posts
    GROUP BY hour_ts, symbol

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