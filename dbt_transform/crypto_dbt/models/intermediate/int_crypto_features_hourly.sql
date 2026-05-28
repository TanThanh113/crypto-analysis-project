-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- MARKET
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
WITH market AS (

    SELECT *
    FROM {{ ref('int_market_trades_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),
-- FUNDING
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
funding AS (

    SELECT *
    FROM {{ ref('int_funding_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- LIQUIDATION
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
liquidation AS (

    SELECT *
    FROM {{ ref('int_liquidation_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- OPTIONS
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
options AS (

    SELECT *
    FROM {{ ref('int_options_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- SOCIAL
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
social AS (

    SELECT *
    FROM {{ ref('int_social_sentiment_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- STABLECOIN
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
stablecoin AS (

    SELECT *
    FROM {{ ref('int_stablecoin_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- RESERVE
-- Filter the columns you need to extract data from, using the data from the previous seven days as a reference point.
reserve AS (

    SELECT *
    FROM {{ ref('int_exchange_reserve_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 7 DAY
          )
    {% endif %}

),

-- MACRO_DAILY
macro_daily AS (

    SELECT *
    FROM {{ ref('int_macro_daily') }}

),

-- ETF_DAILY
etf_daily AS (

    SELECT *
    FROM {{ ref('int_etf_daily') }}

),

-- BASE_JOINED
base_joined AS (

    SELECT
        m.hour_ts,
        m.symbol,
        m.pair_symbol,

        -- Market
        m.open_price,
        m.high_price,
        m.low_price,
        m.close_price,
        m.vwap_price,
        m.trade_count,
        m.unique_trade_count,
        m.base_volume,
        m.quote_volume,
        m.taker_buy_quote_volume,
        m.taker_sell_quote_volume,
        m.taker_buy_quote_ratio,
        m.return_1h,
        m.log_return_1h,
        m.quote_volume_24h,
        m.avg_return_24h,
        m.realized_volatility_24h,
        m.quote_volume_zscore_24h,

        -- Funding
        f.exchanges_reporting,
        f.avg_mark_price AS funding_avg_mark_price,
        f.avg_spot_price AS funding_avg_spot_price,
        f.avg_basis_pct,
        f.max_abs_basis_pct,
        f.avg_funding_rate_coin,
        f.avg_funding_rate_usdt,
        f.avg_annualized_funding_coin,
        f.avg_annualized_funding_usdt,
        f.funding_dispersion_coin,
        f.avg_annualized_basis_coin,
        f.avg_annualized_basis_usdt,
        f.avg_arbitrage_spread,
        f.max_abs_arbitrage_spread,
        f.max_leverage_stress,
        f.avg_leverage_stress,
        f.dominant_funding_regime,
        f.dominant_arbitrage_opportunity,
        f.strongest_arbitrage_exchange,
        f.highest_stress_exchange,

        -- Liquidation
        l.liquidation_bucket_count,
        l.total_liq_usd,
        l.long_liq_sum,
        l.short_liq_sum,
        l.net_long_short_liq_usd,
        l.net_long_short_liq_ratio,
        l.liquidation_related_volume_usd,
        l.liquidation_hit_count,
        l.avg_open_interest,
        l.avg_weighted_liq_ratio,
        l.liq_weighted_liq_ratio,
        l.max_abs_weighted_liq_ratio,
        l.avg_money_flow,
        l.avg_panic,
        l.avg_panic_norm,
        l.max_panic_norm,
        l.avg_magnet_norm,
        l.max_magnet_norm,
        l.max_rank_score,
        l.top_liq_price_bucket,
        l.top_liq_distance_pct,
        l.top_squeeze_signal,
        l.dominant_side_by_liq,
        l.top_stress_level,
        l.short_squeeze_bucket_count,
        l.long_squeeze_bucket_count,
        l.high_stress_bucket_count,
        l.short_squeeze_bucket_ratio,
        l.long_squeeze_bucket_ratio,
        l.high_stress_bucket_ratio,

        -- Options
        o.option_instrument_count,
        o.call_instrument_count,
        o.put_instrument_count,
        o.atm_instrument_count,
        o.avg_mark_iv,
        o.avg_mid_iv,
        o.oi_weighted_mark_iv,
        o.oi_weighted_mid_iv,
        o.atm_avg_mark_iv,
        o.atm_avg_mid_iv,
        o.atm_oi_weighted_mark_iv,
        o.avg_iv_spread,
        o.max_iv_spread,
        o.put_call_iv_skew,
        o.oi_weighted_put_call_iv_skew,
        o.total_open_interest AS options_total_open_interest,
        o.call_open_interest,
        o.put_open_interest,
        o.put_call_oi_ratio,
        o.total_option_volume,
        o.total_option_volume_usd,
        o.call_volume_usd,
        o.put_volume_usd,
        o.put_call_volume_ratio,
        o.delta_exposure_proxy,
        o.gamma_exposure_proxy,
        o.vega_exposure_proxy,
        o.theta_exposure_proxy,
        o.rho_exposure_proxy,
        o.call_delta_exposure_proxy,
        o.put_delta_exposure_proxy,
        o.short_dated_option_count,
        o.mid_dated_option_count,
        o.long_dated_option_count,
        o.top_oi_instrument,
        o.top_oi_strike,
        o.top_oi_option_type,
        o.top_volume_instrument,
        o.top_volume_strike,
        o.top_volume_option_type,

        -- Social
        s.social_item_count,
        s.social_engagement_proxy,
        s.social_weighted_avg_sentiment,
        s.social_avg_sentiment,
        s.social_bullish_count,
        s.social_bearish_count,
        s.social_neutral_count,
        s.social_bullish_ratio,
        s.social_bearish_ratio,
        s.social_neutral_ratio,
        s.social_signal_state,
        s.reddit_telegram_sentiment_gap,
        s.social_etf_mentions,
        s.social_hack_scam_mentions,
        s.social_whale_mentions,
        s.social_liquidation_mentions,
        s.social_macro_mentions,
        s.social_regulation_mentions,
        s.has_reddit_signal,
        s.has_telegram_signal,

        s.reddit_post_count,
        s.reddit_weighted_avg_sentiment,
        s.reddit_etf_mentions,
        s.reddit_hack_mentions,
        s.reddit_whale_mentions,
        s.reddit_liquidation_mentions,
        s.reddit_fed_mentions,

        s.telegram_message_count,
        s.telegram_weighted_avg_sentiment,
        s.telegram_technical_topic_count,
        s.telegram_regulation_topic_count,
        s.telegram_hack_scam_topic_count,
        s.telegram_macro_topic_count,
        s.telegram_high_importance_count,

        -- Stablecoin liquidity
        st.stablecoin_count,
        st.total_stablecoin_market_cap_usd,
        st.total_stablecoin_fdv_usd,
        st.total_stablecoin_volume_24h_usd,
        st.total_stablecoin_circulating_supply,
        st.stablecoin_volume_to_mcap,
        st.mcap_weighted_peg_deviation_pct,
        st.mcap_weighted_depeg_risk_score,
        st.max_abs_peg_deviation_pct,
        st.max_depeg_risk_score,
        st.avg_depeg_risk_score,
        st.depeg_risk_coin_count,
        st.premium_coin_count,
        st.stable_peg_coin_count,
        st.peg_outlier_coin_count,
        st.volume_outlier_coin_count,
        st.usdt_dominance_pct,
        st.usdc_dominance_pct,
        st.dai_dominance_pct,
        st.fdusd_dominance_pct,
        st.tusd_dominance_pct,
        st.usdt_volume_share_pct,
        st.usdc_volume_share_pct,
        st.worst_peg_symbol,
        st.worst_peg_regime,
        st.worst_peg_price_usd,
        st.worst_peg_deviation_pct,
        st.highest_depeg_risk_symbol,
        st.highest_turnover_symbol,

        -- Exchange reserve
        r.exchange_count,
        r.tier_1_exchange_count,
        r.tier_2_exchange_count,
        r.tier_3_exchange_count,
        r.tier_4_exchange_count,
        r.total_exchange_reserve_usd,
        r.total_exchange_volume_24h_usd,
        r.total_exchange_volume_24h_usd_normalized,
        r.total_wash_trading_volume_usd,
        r.wash_trading_volume_ratio,
        r.system_reserve_utilization,
        r.normalized_system_reserve_utilization,
        r.avg_exchange_trust_score,
        r.reserve_weighted_trust_score,
        r.avg_reserve_utilization,
        r.max_reserve_utilization,
        r.reserve_weighted_utilization,
        r.reserve_hhi,
        r.high_bank_run_risk_exchange_count,
        r.moderate_bank_run_risk_exchange_count,
        r.safe_bank_run_risk_exchange_count,
        r.high_bank_run_risk_exchange_ratio,
        r.safe_bank_run_risk_exchange_ratio,
        r.top_reserve_exchange,
        r.top_reserve_exchange_reserve_usd,
        r.top_volume_exchange,
        r.highest_utilization_risk_label,
        r.highest_utilization_exchange,
        r.highest_whale_withdrawal_risk_exchange,
        r.highest_wash_trading_exchange,

        -- Get the latest date available.
        GREATEST(
            COALESCE(m.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(f.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(l.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(o.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(s.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(st.available_at, TIMESTAMP('1970-01-01')),
            COALESCE(r.available_at, TIMESTAMP('1970-01-01'))
        ) AS intraday_available_at,

        -- Get the latest date loaded.
        GREATEST(
            COALESCE(m.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(f.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(l.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(o.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(s.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(st.loaded_at, TIMESTAMP('1970-01-01')),
            COALESCE(r.loaded_at, TIMESTAMP('1970-01-01'))
        ) AS intraday_loaded_at

    FROM market AS m
    LEFT JOIN funding AS f
        ON m.hour_ts = f.hour_ts
       AND m.symbol = f.symbol
    LEFT JOIN liquidation AS l
        ON m.hour_ts = l.hour_ts
       AND m.symbol = l.symbol
    LEFT JOIN options AS o
        ON m.hour_ts = o.hour_ts
       AND m.symbol = o.symbol
    LEFT JOIN social AS s
        ON m.hour_ts = s.hour_ts
       AND m.symbol = s.symbol
    LEFT JOIN stablecoin AS st
        ON m.hour_ts = st.hour_ts
    LEFT JOIN reserve AS r
        ON m.hour_ts = r.hour_ts

),

-- MACRO_ASOF
macro_asof AS (

    SELECT
        b.hour_ts,
        b.symbol,

        md.price_date AS macro_price_date,
        md.sp500_return_1d,
        md.nasdaq_return_1d,
        md.gold_return_1d,
        md.vix_return_1d,
        md.oil_return_1d,
        md.sp500_return_5d,
        md.nasdaq_return_5d,
        md.gold_return_5d,
        md.vix_return_5d,
        md.oil_return_5d,
        md.sp500_return_10d,
        md.nasdaq_return_10d,
        md.gold_return_10d,
        md.vix_return_10d,
        md.oil_return_10d,
        md.nasdaq_sp500_ratio,
        md.nasdaq_sp500_relative_return_1d,
        md.safe_haven_bid_1d,
        md.safe_haven_bid_5d,
        md.oil_equity_relative_return_1d,
        md.macro_risk_regime,
        md.macro_risk_score_direction,
        md.macro_risk_appetite_score,
        md.macro_defensive_pressure_score,
        md.available_at AS macro_available_at

    FROM base_joined AS b
    LEFT JOIN macro_daily AS md
        ON md.available_at <= b.hour_ts
       AND md.price_date >= DATE_SUB(DATE(b.hour_ts), INTERVAL 21 DAY)

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY b.hour_ts, b.symbol
        ORDER BY md.available_at DESC
    ) = 1

),

-- ETF_ASOF
etf_asof AS (

    SELECT
        b.hour_ts,
        b.symbol,

        ed.price_date AS etf_price_date,
        ed.btc_etf_volume,
        ed.eth_etf_volume,
        ed.total_etf_volume,
        ed.btc_etf_volume_share,
        ed.eth_etf_volume_share,
        ed.btc_etf_volume_weighted_return_1d,
        ed.eth_etf_volume_weighted_return_1d,
        ed.total_etf_volume_weighted_return_1d,
        ed.btc_etf_volume_weighted_return_5d,
        ed.eth_etf_volume_weighted_return_5d,
        ed.total_etf_volume_weighted_return_5d,
        ed.btc_etf_flow_proxy,
        ed.eth_etf_flow_proxy,
        ed.total_etf_flow_proxy,
        ed.btc_eth_etf_return_spread_1d,
        ed.btc_eth_etf_flow_proxy_spread,
        ed.ibit_return_1d,
        ed.etha_return_1d,
        ed.feth_return_1d,
        ed.most_active_etf,
        ed.most_active_etf_group,
        ed.most_active_etf_return_1d,
        ed.crypto_etf_momentum_regime,
        ed.available_at AS etf_available_at

    FROM base_joined AS b
    LEFT JOIN etf_daily AS ed
        ON ed.available_at <= b.hour_ts
       AND ed.price_date >= DATE_SUB(DATE(b.hour_ts), INTERVAL 21 DAY)

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY b.hour_ts, b.symbol
        ORDER BY ed.available_at DESC
    ) = 1

),

-- FINAL
final AS (

    SELECT
        b.*,

        -- Macro as-of features
        ma.macro_price_date,
        ma.sp500_return_1d,
        ma.nasdaq_return_1d,
        ma.gold_return_1d,
        ma.vix_return_1d,
        ma.oil_return_1d,
        ma.sp500_return_5d,
        ma.nasdaq_return_5d,
        ma.gold_return_5d,
        ma.vix_return_5d,
        ma.oil_return_5d,
        ma.sp500_return_10d,
        ma.nasdaq_return_10d,
        ma.gold_return_10d,
        ma.vix_return_10d,
        ma.oil_return_10d,
        ma.nasdaq_sp500_ratio,
        ma.nasdaq_sp500_relative_return_1d,
        ma.safe_haven_bid_1d,
        ma.safe_haven_bid_5d,
        ma.oil_equity_relative_return_1d,
        ma.macro_risk_regime,
        ma.macro_risk_score_direction,
        ma.macro_risk_appetite_score,
        ma.macro_defensive_pressure_score,

        -- ETF as-of features
        ea.etf_price_date,
        ea.btc_etf_volume,
        ea.eth_etf_volume,
        ea.total_etf_volume,
        ea.btc_etf_volume_share,
        ea.eth_etf_volume_share,
        ea.btc_etf_volume_weighted_return_1d,
        ea.eth_etf_volume_weighted_return_1d,
        ea.total_etf_volume_weighted_return_1d,
        ea.btc_etf_volume_weighted_return_5d,
        ea.eth_etf_volume_weighted_return_5d,
        ea.total_etf_volume_weighted_return_5d,
        ea.btc_etf_flow_proxy,
        ea.eth_etf_flow_proxy,
        ea.total_etf_flow_proxy,
        ea.btc_eth_etf_return_spread_1d,
        ea.btc_eth_etf_flow_proxy_spread,
        ea.ibit_return_1d,
        ea.etha_return_1d,
        ea.feth_return_1d,
        ea.most_active_etf,
        ea.most_active_etf_group,
        ea.most_active_etf_return_1d,
        ea.crypto_etf_momentum_regime,

        -- Cross-domain features

        -- Volume pressure - emotional
        -- Meaning: The question is whether people will actually invest money when the news breaks.
        COALESCE(b.social_weighted_avg_sentiment, 0)
            * COALESCE(b.quote_volume_zscore_24h, 0) AS sentiment_volume_pressure,

        -- Compatibility between Funding Rate and Emotion
        -- Meaning: To examine whether online social media sentiment aligns with the behavior of derivative traders.
        COALESCE(b.avg_annualized_funding_coin, 0)
            * COALESCE(b.social_weighted_avg_sentiment, 0) AS funding_sentiment_alignment,

        -- Crypto System Pressure Points
        -- Meaning: A red alert for the entire market. This is the pure sum of the most dangerous risks: excessive 
        --          leverage easily leading to chain reactions, stablecoin devaluation, and exchanges losing liquidity.
        COALESCE(b.max_leverage_stress, 0)
            + COALESCE(b.max_depeg_risk_score, 0)
            + COALESCE(b.high_bank_run_risk_exchange_count, 0) AS systemic_crypto_stress_score,

        -- Derivative market risk score
        -- Meaning: Measures the level of risk and uncertainty specific to the Futures/Margin market.
        COALESCE(b.realized_volatility_24h, 0)
            + ABS(COALESCE(b.avg_funding_rate_coin, 0))
            + ABS(COALESCE(b.net_long_short_liq_ratio, 0)) AS derivatives_risk_score,

        -- Classify the risk signal based on the social sentiment, funding rate and taker buy ratio.
        CASE
            WHEN COALESCE(b.social_weighted_avg_sentiment, 0) > 0.1
                 AND COALESCE(b.avg_annualized_funding_coin, 0) > 2
                 AND COALESCE(b.taker_buy_quote_ratio, 0) > 0.55
                THEN 'BULLISH_MOMENTUM'

            WHEN COALESCE(b.social_weighted_avg_sentiment, 0) < -0.1
                 AND COALESCE(b.avg_annualized_funding_coin, 0) < -2
                 AND COALESCE(b.taker_buy_quote_ratio, 0) < 0.45
                THEN 'BEARISH_PRESSURE'

            -- Classify the risk signal based on the leverage stress, panic norm and high bank run risk exchange count.
            WHEN COALESCE(b.max_leverage_stress, 0) > 20
                 OR COALESCE(b.max_panic_norm, 0) > 0.8
                 OR COALESCE(b.high_bank_run_risk_exchange_count, 0) > 0
                THEN 'STRESS_RISK'

            -- Classify the risk signal based on the macro risk regime.
            WHEN ma.macro_risk_regime = 'RISK_OFF'
                 AND COALESCE(b.social_weighted_avg_sentiment, 0) < 0
                THEN 'MACRO_RISK_OFF'

            ELSE 'NEUTRAL'
        END AS composite_market_regime,

        -- Get the latest date available.
        GREATEST(
            b.intraday_available_at,
            COALESCE(ma.macro_available_at, TIMESTAMP('1970-01-01')),
            COALESCE(ea.etf_available_at, TIMESTAMP('1970-01-01'))
        ) AS feature_available_at,

        -- Get the latest date loaded.
        GREATEST(
            b.intraday_loaded_at,
            COALESCE(ma.macro_available_at, TIMESTAMP('1970-01-01')),
            COALESCE(ea.etf_available_at, TIMESTAMP('1970-01-01'))
        ) AS loaded_at

    FROM base_joined AS b
    LEFT JOIN macro_asof AS ma
        ON b.hour_ts = ma.hour_ts
       AND b.symbol = ma.symbol
    LEFT JOIN etf_asof AS ea
        ON b.hour_ts = ea.hour_ts
       AND b.symbol = ea.symbol

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM final

{% if is_incremental() %}
WHERE hour_ts >= TIMESTAMP_SUB(
    COALESCE(
        (SELECT MAX(hour_ts) FROM {{ this }}),
        TIMESTAMP('1970-01-01')
    ),
    INTERVAL 2 DAY
)
{% endif %}