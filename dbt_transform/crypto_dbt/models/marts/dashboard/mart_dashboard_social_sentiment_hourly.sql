-- Dashboard Social Sentiment & NLP Analytics Data Marting
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dashboard_social_sentiment_sk',
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Specify data from the previous 14 days to avoid data errors, delayed data, etc.
WITH fact AS (

    SELECT *
    FROM {{ ref('fact_crypto_features_hourly') }}
    WHERE is_dashboard_ready = TRUE

    {% if is_incremental() %}
      AND hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 14 DAY
          )
    {% endif %}

),

prepared AS (

    SELECT
        *,

        -- Net psychological index
        -- Meaning: Subtract the number of negative (bearish) posts from the number of positive (bullish) posts 
        -- and divide by the total. This number ranges from -1 to 1.
        SAFE_DIVIDE(
            COALESCE(social_bullish_count, 0) - COALESCE(social_bearish_count, 0),
            NULLIF(COALESCE(social_bullish_count, 0) + COALESCE(social_bearish_count, 0), 0)
        ) AS social_net_bullish_bearish_ratio,

        -- Total number of Reddit posts divided by total number of social media posts.
        SAFE_DIVIDE(
            COALESCE(reddit_post_count, 0),
            NULLIF(COALESCE(social_item_count, 0), 0)
        ) AS reddit_item_share,

        -- Total number of Telegram posts divided by total number of social media posts.
        SAFE_DIVIDE(
            COALESCE(telegram_message_count, 0),
            NULLIF(COALESCE(social_item_count, 0), 0)
        ) AS telegram_item_share

    FROM fact

),

-- Final table with the standardized social sentiment data
final AS (

    SELECT
        -- The unique identifier of the metric
        TO_HEX(MD5(CONCAT(CAST(hour_ts AS STRING), '|', symbol, '|social_sentiment'))) AS dashboard_social_sentiment_sk,

        -- The section of the dashboard where the metric is displayed
        crypto_feature_sk,
        hour_ts,
        feature_date,
        symbol_key,
        symbol,
        pair_symbol,
        feature_available_at,
        feature_latency_minutes,

        social_item_count,
        social_engagement_proxy,
        social_weighted_avg_sentiment,
        social_bullish_count,
        social_bearish_count,
        social_bullish_ratio,
        social_bearish_ratio,
        social_net_bullish_bearish_ratio,
        social_sentiment_score,

        reddit_post_count,
        reddit_item_share,
        reddit_weighted_avg_sentiment,
        reddit_etf_mentions,
        reddit_hack_mentions,
        reddit_whale_mentions,
        reddit_liquidation_mentions,
        reddit_fed_mentions,

        telegram_message_count,
        telegram_item_share,
        telegram_weighted_avg_sentiment,
        telegram_technical_topic_count,
        telegram_regulation_topic_count,
        telegram_hack_scam_topic_count,
        telegram_macro_topic_count,
        telegram_high_importance_count,

        -- Labeling the sentiment score
        CASE
            WHEN COALESCE(social_sentiment_score, 0) >= 35 THEN 'EUPHORIC'
            WHEN COALESCE(social_sentiment_score, 0) >= 15 THEN 'BULLISH'
            WHEN COALESCE(social_sentiment_score, 0) <= -35 THEN 'PANIC'
            WHEN COALESCE(social_sentiment_score, 0) <= -15 THEN 'BEARISH'
            ELSE 'NEUTRAL'
        END AS social_sentiment_regime,

        -- Labeling the Measuring coverage
        CASE
            WHEN COALESCE(social_item_count, 0) >= 100
                OR COALESCE(social_engagement_proxy, 0) >= 100000 THEN 'VIRAL_ATTENTION'
            WHEN COALESCE(social_item_count, 0) >= 40
                OR COALESCE(social_engagement_proxy, 0) >= 25000 THEN 'HIGH_ATTENTION'
            WHEN COALESCE(social_item_count, 0) >= 10 THEN 'NORMAL_ATTENTION'
            ELSE 'LOW_ATTENTION'
        END AS social_attention_level,

        -- Keyword-driven Flags
        -- Detecting security-related keywords such as Hack, Scam, Exploit on Reddit/Telegram.
        CASE
            WHEN COALESCE(reddit_hack_mentions, 0) > 0
                OR COALESCE(telegram_hack_scam_topic_count, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS has_security_risk_mentions,

        -- Check if the community is discussing regulatory policies or ETF fund flows.
        CASE
            WHEN COALESCE(reddit_etf_mentions, 0) > 0
                OR COALESCE(telegram_regulation_topic_count, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS has_policy_or_etf_mentions,

        -- Keywords related to Whale alerts, a sign that price movements are imminent due to large investors selling or accumulating shares.
        CASE
            WHEN COALESCE(reddit_whale_mentions, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS has_whale_mentions,

        -- The crowd was discussing account liquidation and account wipeouts.
        CASE
            WHEN COALESCE(reddit_liquidation_mentions, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS has_liquidation_mentions,

        -- The community discusses the Fed, interest rates, inflation, and macroeconomics.
        CASE
            WHEN COALESCE(reddit_fed_mentions, 0) > 0
                OR COALESCE(telegram_macro_topic_count, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS has_macro_mentions,

        -- The time when the metric dashboard was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM prepared

)

SELECT *
FROM final