-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['price_date'],
    partition_by={"field": "price_date", "data_type": "date", "granularity": "day"}
) }}

-- Filter the columns you need to extract data from, using the data from the previous fourteen days as a reference point.
WITH prices AS (

    SELECT
        price_date,
        UPPER(symbol) AS symbol,
        UPPER(ticker) AS ticker,

        close_price,
        adj_close_price,
        volume,
        ingestion_time,

        TIMESTAMP(DATETIME(price_date, TIME '22:30:00'), 'UTC') AS available_at

    FROM {{ ref('stg_etf_indicators') }}
    WHERE price_date IS NOT NULL
      AND close_price > 0
      AND adj_close_price > 0
      AND volume >= 0

    {% if is_incremental() %}
      AND price_date >= DATE_SUB(
            COALESCE(
                (SELECT MAX(price_date) FROM {{ this }}),
                DATE '1970-01-01'
            ),
            INTERVAL 14 DAY
          )
    {% endif %}

),

with_returns AS (

    SELECT
        *,

        -- Calculate the percentage increase in adj close price compared to yesterday.
        SAFE_DIVIDE(
            adj_close_price
                - LAG(adj_close_price) OVER (PARTITION BY symbol ORDER BY price_date),
            NULLIF(
                LAG(adj_close_price) OVER (PARTITION BY symbol ORDER BY price_date),
                0
            )
        ) AS return_1d,

        -- Calculate the percentage increase in adj close price compared to 5 days ago.
        SAFE_DIVIDE(
            adj_close_price
                - LAG(adj_close_price, 5) OVER (PARTITION BY symbol ORDER BY price_date),
            NULLIF(
                LAG(adj_close_price, 5) OVER (PARTITION BY symbol ORDER BY price_date),
                0
            )
        ) AS return_5d,

        -- Classify the ETF group based on the symbol.
        CASE
            WHEN symbol IN ('ETHA', 'FETH', 'ETHE', 'ETHW') THEN 'ETH_ETF'
            ELSE 'BTC_ETF'
        END AS etf_group

    FROM prices

),

aggregated AS (

    SELECT
        price_date,

        -- Count the number of ETFs reporting.
        COUNT(*) AS etf_count,
        COUNTIF(etf_group = 'BTC_ETF') AS btc_etf_count,
        COUNTIF(etf_group = 'ETH_ETF') AS eth_etf_count,

        -- Calculate the sum based on certain conditions(volume).
        SUM(volume) AS total_etf_volume,
        SUM(IF(etf_group = 'BTC_ETF', volume, 0)) AS btc_etf_volume,
        SUM(IF(etf_group = 'ETH_ETF', volume, 0)) AS eth_etf_volume,

        -- Calculate the ratio of BTC ETF volume to total volume.
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'BTC_ETF', volume, 0)),
            NULLIF(SUM(volume), 0)
        ) AS btc_etf_volume_share,

        -- Calculate the ratio of ETH ETF volume to total volume.
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'ETH_ETF', volume, 0)),
            NULLIF(SUM(volume), 0)
        ) AS eth_etf_volume_share,

        -- Calculate the btc - etf volumn return 1d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'BTC_ETF', return_1d * volume, 0)),
            NULLIF(SUM(IF(etf_group = 'BTC_ETF', volume, 0)), 0)
        ) AS btc_etf_volume_weighted_return_1d,

        -- Calculate the eth - etf volumn return 1d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'ETH_ETF', return_1d * volume, 0)),
            NULLIF(SUM(IF(etf_group = 'ETH_ETF', volume, 0)), 0)
        ) AS eth_etf_volume_weighted_return_1d,

        -- Calculate the total etf volumn return 1d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(return_1d * volume),
            NULLIF(SUM(volume), 0)
        ) AS total_etf_volume_weighted_return_1d,

        -- Calculate the btc - etf volumn return 5d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'BTC_ETF', return_5d * volume, 0)),
            NULLIF(SUM(IF(etf_group = 'BTC_ETF', volume, 0)), 0)
        ) AS btc_etf_volume_weighted_return_5d,

        -- Calculate the eth - etf volumn return 5d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(IF(etf_group = 'ETH_ETF', return_5d * volume, 0)),
            NULLIF(SUM(IF(etf_group = 'ETH_ETF', volume, 0)), 0)
        ) AS eth_etf_volume_weighted_return_5d,

        -- Calculate the total etf volumn return 5d on sum of weighted sentiment by weighted volumn
        SAFE_DIVIDE(
            SUM(return_5d * volume),
            NULLIF(SUM(volume), 0)
        ) AS total_etf_volume_weighted_return_5d,

        -- Not real ETF flows. This is a market action proxy using price return * volume.
        SUM(IF(etf_group = 'BTC_ETF', return_1d * volume, 0)) AS btc_etf_flow_proxy,
        SUM(IF(etf_group = 'ETH_ETF', return_1d * volume, 0)) AS eth_etf_flow_proxy,
        SUM(return_1d * volume) AS total_etf_flow_proxy,

        -- Find the maximum close price based on the symbol.
        MAX(IF(symbol = 'IBIT', close_price, NULL)) AS ibit_close,
        MAX(IF(symbol = 'FBTC', close_price, NULL)) AS fbtc_close,
        MAX(IF(symbol = 'GBTC', close_price, NULL)) AS gbtc_close,
        MAX(IF(symbol = 'ETHA', close_price, NULL)) AS etha_close,
        MAX(IF(symbol = 'FETH', close_price, NULL)) AS feth_close,
        MAX(IF(symbol = 'ETHE', close_price, NULL)) AS ethe_close,

        -- Find the maximum return 1 based on the symbol.
        MAX(IF(symbol = 'IBIT', return_1d, NULL)) AS ibit_return_1d,
        MAX(IF(symbol = 'FBTC', return_1d, NULL)) AS fbtc_return_1d,
        MAX(IF(symbol = 'GBTC', return_1d, NULL)) AS gbtc_return_1d,
        MAX(IF(symbol = 'ETHA', return_1d, NULL)) AS etha_return_1d,
        MAX(IF(symbol = 'FETH', return_1d, NULL)) AS feth_return_1d,
        MAX(IF(symbol = 'ETHE', return_1d, NULL)) AS ethe_return_1d,

        -- Find the maximum volume based on the symbol.
        MAX(IF(symbol = 'IBIT', volume, NULL)) AS ibit_volume,
        MAX(IF(symbol = 'FBTC', volume, NULL)) AS fbtc_volume,
        MAX(IF(symbol = 'GBTC', volume, NULL)) AS gbtc_volume,
        MAX(IF(symbol = 'ETHA', volume, NULL)) AS etha_volume,
        MAX(IF(symbol = 'FETH', volume, NULL)) AS feth_volume,
        MAX(IF(symbol = 'ETHE', volume, NULL)) AS ethe_volume,

        -- Find the most active ETF based on the volume.
        ARRAY_AGG(
            symbol IGNORE NULLS
            ORDER BY volume DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS most_active_etf,

        -- Find the most active ETF group based on the volume.
        ARRAY_AGG(
            etf_group IGNORE NULLS
            ORDER BY volume DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS most_active_etf_group,

        -- Find the most active return 1 day based on the volume.
        ARRAY_AGG( 
            return_1d IGNORE NULLS
            ORDER BY volume DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS most_active_etf_return_1d,

        MAX(volume) AS most_active_etf_volume,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    symbol,
                    ticker,
                    etf_group,
                    close_price,
                    adj_close_price,
                    volume,
                    return_1d,
                    return_5d
                )
                ORDER BY volume DESC
            )
        ) AS etf_snapshot_json,

        -- Calculate the latest loaded_at and available_at.
        MAX(ingestion_time) AS loaded_at,
        MAX(available_at) AS available_at

    FROM with_returns
    GROUP BY price_date

),

features AS (

    SELECT
        *,

        -- Calculate the relative return 1 day of BTC compared to ETH.
        COALESCE(btc_etf_volume_weighted_return_1d, 0)
            - COALESCE(eth_etf_volume_weighted_return_1d, 0) AS btc_eth_etf_return_spread_1d,

        -- Calculate the relative return 1 day of BTC compared to ETH.
        COALESCE(btc_etf_flow_proxy, 0)
            - COALESCE(eth_etf_flow_proxy, 0) AS btc_eth_etf_flow_proxy_spread,

        -- Classify the risk signal based on the relative return 1 day of BTC compared to ETH.
        CASE
            WHEN COALESCE(btc_etf_volume_weighted_return_1d, 0) > 0.01
                 AND COALESCE(eth_etf_volume_weighted_return_1d, 0) > 0.01
                THEN 'BROAD_CRYPTO_ETF_BID'

            WHEN COALESCE(btc_etf_volume_weighted_return_1d, 0) < -0.01
                 AND COALESCE(eth_etf_volume_weighted_return_1d, 0) < -0.01
                THEN 'BROAD_CRYPTO_ETF_SELL_PRESSURE'

            WHEN COALESCE(btc_etf_volume_weighted_return_1d, 0)
                 > COALESCE(eth_etf_volume_weighted_return_1d, 0)
                THEN 'BTC_ETF_LEADERSHIP'

            WHEN COALESCE(eth_etf_volume_weighted_return_1d, 0)
                 > COALESCE(btc_etf_volume_weighted_return_1d, 0)
                THEN 'ETH_ETF_LEADERSHIP'

            ELSE 'NEUTRAL'
        END AS crypto_etf_momentum_regime

    FROM aggregated

)

-- To be sure, here we will only consider events from the previous two days.
SELECT *
FROM features

{% if is_incremental() %}
WHERE price_date >= DATE_SUB(
    COALESCE(
        (SELECT MAX(price_date) FROM {{ this }}),
        DATE '1970-01-01'
    ),
    INTERVAL 7 DAY
)
{% endif %}