-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"}
) }}

-- Filter the columns you need to extract data from, using the data from the previous two days as a reference point.
WITH source_data AS (

    SELECT
        TIMESTAMP_TRUNC(observed_at, HOUR) AS hour_ts,

        UPPER(symbol) AS symbol,
        LOWER(coin_id) AS coin_id,

        observed_at,
        price_usd,
        market_cap_usd,
        fully_diluted_valuation_usd,
        volume_24h_usd,
        circulating_supply,
        total_supply,
        peg_deviation_pct,
        utilization_ratio,
        volume_to_marketcap,
        peg_regime,
        depeg_risk_score,
        stablecoin_dominance_pct,
        liquidity_tier,
        liquidity_score,
        is_peg_outlier,
        is_volume_outlier,
        ingestion_time

    FROM {{ ref('stg_stablecoin_supply') }}
    WHERE observed_at IS NOT NULL
      AND symbol IS NOT NULL
      AND price_usd > 0
      AND market_cap_usd > 0

    {% if is_incremental() %}
      AND observed_at >= TIMESTAMP_SUB(
            COALESCE(
                (SELECT MAX(hour_ts) FROM {{ this }}),
                TIMESTAMP('1970-01-01')
            ),
            INTERVAL 2 DAY
          )
    {% endif %}

),

-- Filter out duplicate values.
latest_coin AS (

    SELECT *
    FROM source_data
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY hour_ts, symbol
        ORDER BY observed_at DESC, ingestion_time DESC
    ) = 1

),

aggregated AS (

    SELECT
        hour_ts,

        COUNT(*) AS stablecoin_count,

        -- Calculate the sum based on certain conditions.
        SUM(market_cap_usd) AS total_stablecoin_market_cap_usd,
        SUM(fully_diluted_valuation_usd) AS total_stablecoin_fdv_usd,
        SUM(volume_24h_usd) AS total_stablecoin_volume_24h_usd,
        SUM(circulating_supply) AS total_stablecoin_circulating_supply,

        -- Calculate the stablecoin volume to market cap ratio(volume 24h usd / market cap usd).
        SAFE_DIVIDE(
            SUM(volume_24h_usd),
            NULLIF(SUM(market_cap_usd), 0)
        ) AS stablecoin_volume_to_mcap,

        -- Calculate the mcap weighted peg devation pct based on sum of peg deviation pct by weighted market cap.
        SAFE_DIVIDE(
            SUM(peg_deviation_pct * market_cap_usd),
            NULLIF(SUM(market_cap_usd), 0)
        ) AS mcap_weighted_peg_deviation_pct,

        -- Calculate the mcap weighted depeg risk score based on sum of depeg risk score by weighted market cap.
        SAFE_DIVIDE(
            SUM(depeg_risk_score * market_cap_usd),
            NULLIF(SUM(market_cap_usd), 0)
        ) AS mcap_weighted_depeg_risk_score,
        
        -- Calculate the max and average depeg risk score and peg deviation pct.
        MAX(ABS(peg_deviation_pct)) AS max_abs_peg_deviation_pct,
        MAX(depeg_risk_score) AS max_depeg_risk_score,
        AVG(depeg_risk_score) AS avg_depeg_risk_score,

        -- Calculate the count based on certain conditions.
        COUNTIF(peg_regime = 'depeg_risk') AS depeg_risk_coin_count,
        COUNTIF(peg_regime = 'premium') AS premium_coin_count,
        COUNTIF(peg_regime = 'stable') AS stable_peg_coin_count,

        COUNTIF(is_peg_outlier = 1) AS peg_outlier_coin_count,
        COUNTIF(is_volume_outlier = 1) AS volume_outlier_coin_count,

        -- Calculate the sum based on certain conditions.
        SUM(IF(symbol = 'USDT', market_cap_usd, 0)) AS usdt_market_cap_usd,
        SUM(IF(symbol = 'USDC', market_cap_usd, 0)) AS usdc_market_cap_usd,
        SUM(IF(symbol = 'DAI', market_cap_usd, 0)) AS dai_market_cap_usd,
        SUM(IF(symbol = 'FDUSD', market_cap_usd, 0)) AS fdusd_market_cap_usd,
        SUM(IF(symbol = 'TUSD', market_cap_usd, 0)) AS tusd_market_cap_usd,

        -- Calculate the ratio of USDT market cap to total market cap.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'USDT', market_cap_usd, 0)),
            NULLIF(SUM(market_cap_usd), 0)
        ) * 100 AS usdt_dominance_pct,

        -- Calculate the ratio of USDC market cap to total market cap.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'USDC', market_cap_usd, 0)),
            NULLIF(SUM(market_cap_usd), 0)
        ) * 100 AS usdc_dominance_pct,

        -- Calculate the ratio of DAI market cap to total market cap.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'DAI', market_cap_usd, 0)),
            NULLIF(SUM(market_cap_usd), 0)
        ) * 100 AS dai_dominance_pct,

        -- Calculate the ratio of FDUSD market cap to total market cap.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'FDUSD', market_cap_usd, 0)),
            NULLIF(SUM(market_cap_usd), 0)
        ) * 100 AS fdusd_dominance_pct,

        -- Calculate the ratio of TUSD market cap to total market cap.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'TUSD', market_cap_usd, 0)),
            NULLIF(SUM(market_cap_usd), 0)
        ) * 100 AS tusd_dominance_pct,

        -- Calculate the ratio of USDT volume to 24h volume.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'USDT', volume_24h_usd, 0)),
            NULLIF(SUM(volume_24h_usd), 0)
        ) * 100 AS usdt_volume_share_pct,

        -- Calculate the ratio of USDC volume to 24h volume.
        SAFE_DIVIDE(
            SUM(IF(symbol = 'USDC', volume_24h_usd, 0)),
            NULLIF(SUM(volume_24h_usd), 0)
        ) * 100 AS usdc_volume_share_pct,
        
        -- Find the top peg symbol based on the peg deviation pct and depeg risk score.
        ARRAY_AGG(
            symbol IGNORE NULLS
            ORDER BY ABS(peg_deviation_pct) DESC, depeg_risk_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_symbol,

        -- Find the top peg regime based on the peg deviation pct and depeg risk score.
        ARRAY_AGG(
            peg_regime IGNORE NULLS
            ORDER BY ABS(peg_deviation_pct) DESC, depeg_risk_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_regime,

        -- Find the top peg price usd based on the peg deviation pct and depeg risk score.
        ARRAY_AGG(
            price_usd IGNORE NULLS
            ORDER BY ABS(peg_deviation_pct) DESC, depeg_risk_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_price_usd,

        -- Find the top peg deviation pct based on the peg deviation pct and depeg risk score.
        ARRAY_AGG(
            peg_deviation_pct IGNORE NULLS
            ORDER BY ABS(peg_deviation_pct) DESC, depeg_risk_score DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS worst_peg_deviation_pct,

        -- Find the highest depeg risk symbol based on the depeg risk score and peg deviation pct.
        ARRAY_AGG(
            symbol IGNORE NULLS
            ORDER BY depeg_risk_score DESC, ABS(peg_deviation_pct) DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_depeg_risk_symbol,

        -- Find the highest turnover symbol based on the volume to market cap.
        ARRAY_AGG(
            symbol IGNORE NULLS
            ORDER BY volume_to_marketcap DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_turnover_symbol,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    symbol,
                    coin_id,
                    price_usd,
                    market_cap_usd,
                    volume_24h_usd,
                    peg_deviation_pct,
                    peg_regime,
                    depeg_risk_score,
                    stablecoin_dominance_pct,
                    liquidity_tier,
                    liquidity_score,
                    is_peg_outlier,
                    is_volume_outlier
                )
                ORDER BY market_cap_usd DESC
            )
        ) AS stablecoin_snapshot_json,

        MAX(observed_at) AS latest_observed_at,
        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM latest_coin
    GROUP BY hour_ts

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