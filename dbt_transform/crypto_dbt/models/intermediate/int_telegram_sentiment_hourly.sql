-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous three days as a reference point.
WITH base AS (

    SELECT
        TIMESTAMP_TRUNC(message_at, HOUR) AS hour_ts,
        UPPER(coin_focus) AS coin_focus,

        channel,
        message_id,
        text,
        nlp_compound,
        weighted_sentiment,
        signal_type,
        topic,
        views,
        forwards,
        replies,
        reactions,
        engagement_score,
        importance,
        word_count,
        financial_mentions_count,
        has_media,
        is_forward,
        ingestion_time

    FROM {{ ref('stg_telegram_raw') }}
    WHERE message_at IS NOT NULL
      AND message_id IS NOT NULL
      AND channel IS NOT NULL
      AND text IS NOT NULL
      AND coin_focus IN ('BTC', 'ETH', 'GENERAL', 'BTC_ETH')

    {% if is_incremental() %}
      AND message_at >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 3 DAY
          )
    {% endif %}

),

expanded AS (

    SELECT
        hour_ts,
        coin_focus,
        coin_focus AS symbol,
        channel,
        message_id,
        text,
        nlp_compound,
        weighted_sentiment,
        signal_type,
        topic,
        views,
        forwards,
        replies,
        reactions,
        engagement_score,
        importance,
        word_count,
        financial_mentions_count,
        has_media,
        is_forward,
        ingestion_time

    FROM base
    WHERE coin_focus IN ('BTC', 'ETH', 'GENERAL')

    UNION ALL

    SELECT
        hour_ts,
        coin_focus,
        'BTC' AS symbol,
        channel,
        message_id,
        text,
        nlp_compound,
        weighted_sentiment,
        signal_type,
        topic,
        views,
        forwards,
        replies,
        reactions,
        engagement_score,
        importance,
        word_count,
        financial_mentions_count,
        has_media,
        is_forward,
        ingestion_time

    FROM base
    WHERE coin_focus = 'BTC_ETH'

    UNION ALL

    SELECT
        hour_ts,
        coin_focus,
        'ETH' AS symbol,
        channel,
        message_id,
        text,
        nlp_compound,
        weighted_sentiment,
        signal_type,
        topic,
        views,
        forwards,
        replies,
        reactions,
        engagement_score,
        importance,
        word_count,
        financial_mentions_count,
        has_media,
        is_forward,
        ingestion_time

    FROM base
    WHERE coin_focus = 'BTC_ETH'

),

aggregated AS (

    SELECT
        hour_ts,
        symbol,

        -- Calculate the count based on certain conditions.
        COUNT(*) AS telegram_message_count,
        COUNT(DISTINCT channel) AS telegram_channel_count,
        COUNT(DISTINCT message_id) AS telegram_unique_message_count,

        SUM(views) AS telegram_view_sum,
        SUM(forwards) AS telegram_forward_sum,
        SUM(replies) AS telegram_reply_sum,
        SUM(reactions) AS telegram_reaction_sum,
        SUM(engagement_score) AS telegram_engagement_sum,

        MAX(engagement_score) AS telegram_max_engagement_score,
        AVG(engagement_score) AS telegram_avg_engagement_score,

        SUM(weighted_sentiment) AS telegram_sentiment_weight_sum,

        -- Calculate the telegram weighted average sentiment based on sum of weighted sentiment and engagement score.
        SAFE_DIVIDE(
            SUM(weighted_sentiment),
            NULLIF(SUM(engagement_score), 0)
        ) AS telegram_weighted_avg_sentiment,

        AVG(nlp_compound) AS telegram_avg_sentiment,

        -- Calculate the telegram weighted average sentiment based on sum of nlp compound by weighted views.
        SAFE_DIVIDE(
            SUM(nlp_compound * views),
            NULLIF(SUM(views), 0)
        ) AS telegram_view_weighted_avg_sentiment,

        -- Calculate the count based on certain conditions.
        COUNTIF(signal_type = 'BULLISH') AS telegram_bullish_message_count,
        COUNTIF(signal_type = 'BEARISH') AS telegram_bearish_message_count,
        COUNTIF(signal_type = 'NEUTRAL') AS telegram_neutral_message_count,

        -- Calculate the ratio of telegram bullish message count to telegram message count.
        SAFE_DIVIDE(
            COUNTIF(signal_type = 'BULLISH'),
            NULLIF(COUNT(*), 0)
        ) AS telegram_bullish_ratio,

        --  Calculate the ratio of telegram bearish message count to telegram message count.
        SAFE_DIVIDE(
            COUNTIF(signal_type = 'BEARISH'),
            NULLIF(COUNT(*), 0)
        ) AS telegram_bearish_ratio,

        -- Calculate the ratio of telegram neutral message count to telegram message count.
        SAFE_DIVIDE(
            COUNTIF(signal_type = 'NEUTRAL'),
            NULLIF(COUNT(*), 0)
        ) AS telegram_neutral_ratio,

        -- Calculate the count based on certain conditions.
        COUNTIF(topic = 'TECH_ANALYSIS') AS telegram_technical_topic_count,
        COUNTIF(topic = 'REGULATION') AS telegram_regulation_topic_count,
        COUNTIF(topic = 'HACK_SCAM') AS telegram_hack_scam_topic_count,
        COUNTIF(topic = 'MACRO_POLITICS') AS telegram_macro_topic_count,
        COUNTIF(topic = 'AIRDROP_PROMO') AS telegram_airdrop_topic_count,
        COUNTIF(topic = 'GENERAL_NEWS') AS telegram_general_news_topic_count,

        COUNTIF(importance IN ('VIRAL', 'HIGH')) AS telegram_high_importance_count,
        COUNTIF(importance = 'VIRAL') AS telegram_viral_importance_count,

        -- Calculate the count, sum, average and max based on certain conditions.
        COUNTIF(has_media) AS telegram_media_message_count,
        COUNTIF(is_forward) AS telegram_forwarded_message_count,

        SUM(financial_mentions_count) AS telegram_financial_mentions_count,
        AVG(word_count) AS telegram_avg_word_count,
        MAX(word_count) AS telegram_max_word_count,

        -- Find the top telegram text based on the engagement score, views and reactions.
        ARRAY_AGG(
            text IGNORE NULLS
            ORDER BY engagement_score DESC, views DESC, reactions DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_telegram_text,

        -- Find the top telegram channel based on the engagement score, views and reactions.
        ARRAY_AGG(
            channel IGNORE NULLS
            ORDER BY engagement_score DESC, views DESC, reactions DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_telegram_channel,

        -- Find the top telegram message id based on the engagement score, views and reactions.
        ARRAY_AGG(
            message_id IGNORE NULLS
            ORDER BY engagement_score DESC, views DESC, reactions DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_telegram_message_id,

        -- Find the top telegram topic based on the engagement score, views and reactions.
        ARRAY_AGG(
            topic IGNORE NULLS
            ORDER BY engagement_score DESC, views DESC, reactions DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_telegram_topic,

        -- Find the top telegram signal type based on the engagement score, views and reactions.
        ARRAY_AGG(
            signal_type IGNORE NULLS
            ORDER BY engagement_score DESC, views DESC, reactions DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_telegram_signal_type,

        -- Create a data stream that summarizes all the data using JSON code.(top 10 telegram messages)
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    message_id,
                    channel,
                    text,
                    nlp_compound,
                    weighted_sentiment,
                    signal_type,
                    topic,
                    views,
                    forwards,
                    replies,
                    reactions,
                    engagement_score,
                    importance,
                    financial_mentions_count,
                    has_media,
                    is_forward
                )
                ORDER BY engagement_score DESC, views DESC, reactions DESC
                LIMIT 10
            )
        ) AS top_10_telegram_messages_json,

        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM expanded
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