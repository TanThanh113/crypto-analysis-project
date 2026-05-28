-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous three days as a reference point(reddit).
WITH reddit AS (

    SELECT *
    FROM {{ ref('int_reddit_sentiment_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 3 DAY
          )
    {% endif %}

),

-- Filter the columns you need to extract data from, using the data from the previous three days as a reference point(telegram).
telegram AS (

    SELECT *
    FROM {{ ref('int_telegram_sentiment_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 3 DAY
          )
    {% endif %}

),

-- Combine the reddit and telegram data.
joined AS (

    SELECT
        COALESCE(r.hour_ts, t.hour_ts) AS hour_ts,
        COALESCE(r.symbol, t.symbol) AS symbol,

        -- Reddit metrics
        r.reddit_post_count,
        r.reddit_subreddit_count,
        r.reddit_score_sum,
        r.reddit_comment_sum,
        r.reddit_interaction_weight_sum,
        r.reddit_weight_sum,
        r.reddit_sentiment_weight_sum,
        r.reddit_weighted_avg_sentiment,
        r.reddit_avg_sentiment,
        r.reddit_interaction_weighted_avg_sentiment,
        r.reddit_max_engagement_velocity,
        r.reddit_avg_engagement_velocity,
        r.reddit_viral_post_count,

        r.reddit_bullish_post_count,
        r.reddit_bearish_post_count,
        r.reddit_neutral_post_count,
        r.reddit_bullish_ratio,
        r.reddit_bearish_ratio,
        r.reddit_neutral_ratio,

        r.reddit_etf_mentions,
        r.reddit_hack_mentions,
        r.reddit_whale_mentions,
        r.reddit_liquidation_mentions,
        r.reddit_fed_mentions,
        r.reddit_sec_mentions,
        r.reddit_blackrock_mentions,

        r.top_reddit_title,
        r.top_reddit_subreddit,
        r.top_reddit_post_id,
        r.top_10_reddit_posts_json,

        -- Telegram metrics
        t.telegram_message_count,
        t.telegram_channel_count,
        t.telegram_unique_message_count,
        t.telegram_view_sum,
        t.telegram_forward_sum,
        t.telegram_reply_sum,
        t.telegram_reaction_sum,
        t.telegram_engagement_sum,
        t.telegram_max_engagement_score,
        t.telegram_avg_engagement_score,
        t.telegram_sentiment_weight_sum,
        t.telegram_weighted_avg_sentiment,
        t.telegram_avg_sentiment,
        t.telegram_view_weighted_avg_sentiment,

        t.telegram_bullish_message_count,
        t.telegram_bearish_message_count,
        t.telegram_neutral_message_count,
        t.telegram_bullish_ratio,
        t.telegram_bearish_ratio,
        t.telegram_neutral_ratio,

        t.telegram_technical_topic_count,
        t.telegram_regulation_topic_count,
        t.telegram_hack_scam_topic_count,
        t.telegram_macro_topic_count,
        t.telegram_airdrop_topic_count,
        t.telegram_general_news_topic_count,

        t.telegram_high_importance_count,
        t.telegram_viral_importance_count,
        t.telegram_media_message_count,
        t.telegram_forwarded_message_count,
        t.telegram_financial_mentions_count,
        t.telegram_avg_word_count,
        t.telegram_max_word_count,

        t.top_telegram_text,
        t.top_telegram_channel,
        t.top_telegram_message_id,
        t.top_telegram_topic,
        t.top_telegram_signal_type,
        t.top_10_telegram_messages_json,

        -- Combined social activity
        -- Calculate the sum based on certain conditions.
        COALESCE(r.reddit_post_count, 0)
            + COALESCE(t.telegram_message_count, 0) AS social_item_count,

        COALESCE(r.reddit_score_sum, 0)
            + COALESCE(t.telegram_engagement_sum, 0) AS social_engagement_proxy,

        COALESCE(r.reddit_bullish_post_count, 0)
            + COALESCE(t.telegram_bullish_message_count, 0) AS social_bullish_count,

        COALESCE(r.reddit_bearish_post_count, 0)
            + COALESCE(t.telegram_bearish_message_count, 0) AS social_bearish_count,

        COALESCE(r.reddit_neutral_post_count, 0)
            + COALESCE(t.telegram_neutral_message_count, 0) AS social_neutral_count,

        -- Calculate the social weighted average sentiment based on sum of weighted sentiment by weighted engagement score.
        SAFE_DIVIDE(
            COALESCE(r.reddit_sentiment_weight_sum, 0)
                + COALESCE(t.telegram_sentiment_weight_sum, 0),
            NULLIF(
                COALESCE(r.reddit_weight_sum, 0)
                    + COALESCE(t.telegram_engagement_sum, 0),
                0
            )
        ) AS social_weighted_avg_sentiment,

        -- Calculate the social average sentiment based on sum of sentiment by post count.
        SAFE_DIVIDE(
            COALESCE(r.reddit_avg_sentiment, 0) * COALESCE(r.reddit_post_count, 0)
                + COALESCE(t.telegram_avg_sentiment, 0) * COALESCE(t.telegram_message_count, 0),
            NULLIF(
                COALESCE(r.reddit_post_count, 0)
                    + COALESCE(t.telegram_message_count, 0),
                0
            )
        ) AS social_avg_sentiment,

        -- Calculate the ratio of social bullish post count to social post count.
        SAFE_DIVIDE(
            COALESCE(r.reddit_bullish_post_count, 0)
                + COALESCE(t.telegram_bullish_message_count, 0),
            NULLIF(
                COALESCE(r.reddit_post_count, 0)
                    + COALESCE(t.telegram_message_count, 0),
                0
            )
        ) AS social_bullish_ratio,

        -- Calculate the ratio of social bearish post count to social post count.
        SAFE_DIVIDE(
            COALESCE(r.reddit_bearish_post_count, 0)
                + COALESCE(t.telegram_bearish_message_count, 0),
            NULLIF(
                COALESCE(r.reddit_post_count, 0)
                    + COALESCE(t.telegram_message_count, 0),
                0
            )
        ) AS social_bearish_ratio,

        -- Calculate the ratio of social neutral post count to social post count.
        SAFE_DIVIDE(
            COALESCE(r.reddit_neutral_post_count, 0)
                + COALESCE(t.telegram_neutral_message_count, 0),
            NULLIF(
                COALESCE(r.reddit_post_count, 0)
                    + COALESCE(t.telegram_message_count, 0),
                0
            )
        ) AS social_neutral_ratio,

        -- Cross-source agreement
        -- Add some features to the case statement
        CASE
            WHEN r.reddit_weighted_avg_sentiment > 0.05
                 AND t.telegram_weighted_avg_sentiment > 0.05
                THEN 'BULLISH_AGREEMENT'
            WHEN r.reddit_weighted_avg_sentiment < -0.05
                 AND t.telegram_weighted_avg_sentiment < -0.05
                THEN 'BEARISH_AGREEMENT'
            WHEN r.reddit_weighted_avg_sentiment IS NOT NULL
                 AND t.telegram_weighted_avg_sentiment IS NOT NULL
                 AND SIGN(r.reddit_weighted_avg_sentiment) != SIGN(t.telegram_weighted_avg_sentiment)
                THEN 'DIVERGENCE'
            WHEN r.reddit_weighted_avg_sentiment IS NULL
                 AND t.telegram_weighted_avg_sentiment IS NOT NULL
                THEN 'TELEGRAM_ONLY'
            WHEN r.reddit_weighted_avg_sentiment IS NOT NULL
                 AND t.telegram_weighted_avg_sentiment IS NULL
                THEN 'REDDIT_ONLY'
            ELSE 'NEUTRAL_OR_LOW_SIGNAL'
        END AS social_signal_state,

        -- Calculate the absolute value of the difference between the weighted average sentiment of reddit and telegram.
        ABS(
            COALESCE(r.reddit_weighted_avg_sentiment, 0)
                - COALESCE(t.telegram_weighted_avg_sentiment, 0)
        ) AS reddit_telegram_sentiment_gap,

        -- Combined topic/event signals
        COALESCE(r.reddit_etf_mentions, 0) AS social_etf_mentions,
        COALESCE(r.reddit_hack_mentions, 0)
            + COALESCE(t.telegram_hack_scam_topic_count, 0) AS social_hack_scam_mentions,

        COALESCE(r.reddit_whale_mentions, 0) AS social_whale_mentions,
        COALESCE(r.reddit_liquidation_mentions, 0) AS social_liquidation_mentions,
        COALESCE(r.reddit_fed_mentions, 0)
            + COALESCE(t.telegram_macro_topic_count, 0) AS social_macro_mentions,

        COALESCE(r.reddit_sec_mentions, 0)
            + COALESCE(t.telegram_regulation_topic_count, 0) AS social_regulation_mentions,

        COALESCE(r.reddit_blackrock_mentions, 0) AS social_blackrock_mentions,

        -- Source coverage flags
        r.reddit_post_count IS NOT NULL AS has_reddit_signal,
        t.telegram_message_count IS NOT NULL AS has_telegram_signal,

        -- Calculate the latest loaded_at and available_at.(Take the latest time)
        GREATEST(
            COALESCE(r.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(t.loaded_at, TIMESTAMP('1970-01-01'))
        ) AS loaded_at,

        GREATEST(
            COALESCE(r.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(t.available_at, TIMESTAMP('1970-01-01'))
        ) AS available_at

    FROM reddit AS r
    FULL OUTER JOIN telegram AS t
        ON r.hour_ts = t.hour_ts
       AND r.symbol = t.symbol

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM joined

{% if is_incremental() %}
WHERE hour_ts >= TIMESTAMP_SUB(
    COALESCE(
        (SELECT MAX(hour_ts) FROM {{ this }}),
        TIMESTAMP('1970-01-01')
    ),
    INTERVAL 2 DAY
)
{% endif %}