-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['snapshot_date'],
    partition_by={"field": "snapshot_date", "data_type": "date", "granularity": "day"}
) }}

-- Filter the columns you need to extract data from, using the data from the previous four days as a reference point.
WITH hourly AS (

    SELECT *
    FROM {{ ref('int_stablecoin_hourly') }}

    {% if is_incremental() %}
      WHERE hour_ts >= TIMESTAMP_SUB(
            TIMESTAMP(
                COALESCE(
                    (SELECT MAX(snapshot_date) FROM {{ this }}),
                    DATE '1970-01-01'
                )
            ),
            INTERVAL 4 DAY
          )
    {% endif %}

),

-- Filter out duplicate values.
daily_latest AS (

    SELECT *
    FROM hourly
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY DATE(hour_ts)
        ORDER BY hour_ts DESC, loaded_at DESC
    ) = 1

),

features AS (

    SELECT
        DATE(hour_ts) AS snapshot_date,
        hour_ts AS latest_hour_ts,

        stablecoin_count,

        total_stablecoin_market_cap_usd,
        total_stablecoin_fdv_usd,
        total_stablecoin_volume_24h_usd,
        total_stablecoin_circulating_supply,
        stablecoin_volume_to_mcap,

        mcap_weighted_peg_deviation_pct,
        mcap_weighted_depeg_risk_score,
        max_abs_peg_deviation_pct,
        max_depeg_risk_score,
        avg_depeg_risk_score,

        depeg_risk_coin_count,
        premium_coin_count,
        stable_peg_coin_count,
        peg_outlier_coin_count,
        volume_outlier_coin_count,

        usdt_market_cap_usd,
        usdc_market_cap_usd,
        dai_market_cap_usd,
        fdusd_market_cap_usd,
        tusd_market_cap_usd,

        usdt_dominance_pct,
        usdc_dominance_pct,
        dai_dominance_pct,
        fdusd_dominance_pct,
        tusd_dominance_pct,

        usdt_volume_share_pct,
        usdc_volume_share_pct,

        worst_peg_symbol,
        worst_peg_regime,
        worst_peg_price_usd,
        worst_peg_deviation_pct,
        highest_depeg_risk_symbol,
        highest_turnover_symbol,

        stablecoin_snapshot_json,

        -- Calculate the percentage increase in total stablecoin market cap usd compared to yesterday.
        SAFE_DIVIDE(
            total_stablecoin_market_cap_usd
                - LAG(total_stablecoin_market_cap_usd) OVER (ORDER BY DATE(hour_ts)),
            NULLIF(
                LAG(total_stablecoin_market_cap_usd) OVER (ORDER BY DATE(hour_ts)),
                0
            )
        ) AS stablecoin_mcap_return_1d,

        -- Calculate how much total stablecoin market cap usd has increased compared to yesterday.
        total_stablecoin_market_cap_usd
            - LAG(total_stablecoin_market_cap_usd) OVER (ORDER BY DATE(hour_ts))
            AS stablecoin_mcap_change_1d_usd,

        -- Calculate the percentage increase in total stablecoin volume 24h usd compared to yesterday.
        SAFE_DIVIDE(
            total_stablecoin_volume_24h_usd
                - LAG(total_stablecoin_volume_24h_usd) OVER (ORDER BY DATE(hour_ts)),
            NULLIF(
                LAG(total_stablecoin_volume_24h_usd) OVER (ORDER BY DATE(hour_ts)),
                0
            )
        ) AS stablecoin_volume_return_1d,

        -- Calculate how much usdt dominance pct has increased compared to yesterday.
        usdt_dominance_pct
            - LAG(usdt_dominance_pct) OVER (ORDER BY DATE(hour_ts))
            AS usdt_dominance_change_1d_pct,

        -- Calculate how much usdc dominance pct has increased compared to yesterday.
        usdc_dominance_pct
            - LAG(usdc_dominance_pct) OVER (ORDER BY DATE(hour_ts))
            AS usdc_dominance_change_1d_pct,

        -- Calculate how much mcap weighted peg deviation pct has increased compared to yesterday.
        mcap_weighted_peg_deviation_pct
            - LAG(mcap_weighted_peg_deviation_pct) OVER (ORDER BY DATE(hour_ts))
            AS peg_deviation_change_1d_pct,

        -- Calculate how much max depeg risk score has increased compared to yesterday.
        max_depeg_risk_score
            - LAG(max_depeg_risk_score) OVER (ORDER BY DATE(hour_ts))
            AS max_depeg_risk_change_1d,

        loaded_at,
        available_at

    FROM daily_latest

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM features

{% if is_incremental() %}
WHERE snapshot_date >= DATE_SUB(
    COALESCE(
        (SELECT MAX(snapshot_date) FROM {{ this }}),
        DATE '1970-01-01'
    ),
    INTERVAL 2 DAY
)
{% endif %}