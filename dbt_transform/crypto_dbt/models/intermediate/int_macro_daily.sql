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

        TIMESTAMP(DATETIME(price_date, TIME '22:00:00'), 'UTC') AS available_at

    FROM {{ ref('stg_macro_indicators') }}
    WHERE price_date IS NOT NULL
      AND close_price > 0
      AND adj_close_price > 0

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

        -- Calculate the percentage increase in adj close price compared to 10 days ago.
        SAFE_DIVIDE(
            adj_close_price
                - LAG(adj_close_price, 10) OVER (PARTITION BY symbol ORDER BY price_date),
            NULLIF(
                LAG(adj_close_price, 10) OVER (PARTITION BY symbol ORDER BY price_date),
                0
            )
        ) AS return_10d

    FROM prices

),

pivoted AS (

    SELECT
        price_date,

        -- Find the maximum close price based on the symbol.
        MAX(IF(symbol = 'SP500', close_price, NULL)) AS sp500_close,
        MAX(IF(symbol = 'NASDAQ', close_price, NULL)) AS nasdaq_close,
        MAX(IF(symbol = 'GOLD', close_price, NULL)) AS gold_close,
        MAX(IF(symbol = 'VIX', close_price, NULL)) AS vix_close,
        MAX(IF(symbol = 'OIL', close_price, NULL)) AS oil_close,

        -- Find the maximum return 1 based on the symbol.
        MAX(IF(symbol = 'SP500', return_1d, NULL)) AS sp500_return_1d,
        MAX(IF(symbol = 'NASDAQ', return_1d, NULL)) AS nasdaq_return_1d,
        MAX(IF(symbol = 'GOLD', return_1d, NULL)) AS gold_return_1d,
        MAX(IF(symbol = 'VIX', return_1d, NULL)) AS vix_return_1d,
        MAX(IF(symbol = 'OIL', return_1d, NULL)) AS oil_return_1d,

        -- Find the maximum return 5 based on the symbol.
        MAX(IF(symbol = 'SP500', return_5d, NULL)) AS sp500_return_5d,
        MAX(IF(symbol = 'NASDAQ', return_5d, NULL)) AS nasdaq_return_5d,
        MAX(IF(symbol = 'GOLD', return_5d, NULL)) AS gold_return_5d,
        MAX(IF(symbol = 'VIX', return_5d, NULL)) AS vix_return_5d,
        MAX(IF(symbol = 'OIL', return_5d, NULL)) AS oil_return_5d,
        
        -- Find the maximum return 10 based on the symbol.
        MAX(IF(symbol = 'SP500', return_10d, NULL)) AS sp500_return_10d,
        MAX(IF(symbol = 'NASDAQ', return_10d, NULL)) AS nasdaq_return_10d,
        MAX(IF(symbol = 'GOLD', return_10d, NULL)) AS gold_return_10d,
        MAX(IF(symbol = 'VIX', return_10d, NULL)) AS vix_return_10d,
        MAX(IF(symbol = 'OIL', return_10d, NULL)) AS oil_return_10d,

        SUM(volume) AS total_macro_proxy_volume,

        -- Calculate the latest loaded_at and available_at.
        MAX(ingestion_time) AS loaded_at,
        MAX(available_at) AS available_at

    FROM with_returns
    GROUP BY price_date

),

features AS (

    SELECT
        *,

        -- Calculate the ratio of NASDAQ close to SP500 close.
        SAFE_DIVIDE(nasdaq_close, NULLIF(sp500_close, 0)) AS nasdaq_sp500_ratio,

        -- Calculate the relative return 1 day of NASDAQ compared to SP500.
        COALESCE(nasdaq_return_1d, 0)
            - COALESCE(sp500_return_1d, 0) AS nasdaq_sp500_relative_return_1d,

        -- Calculate the relative return 1 day of Gold compared to SP500.
        COALESCE(gold_return_1d, 0)
            - COALESCE(sp500_return_1d, 0) AS safe_haven_bid_1d,

        -- Calculate the relative return 5 day of Gold compared to SP500.
        COALESCE(gold_return_5d, 0)
            - COALESCE(sp500_return_5d, 0) AS safe_haven_bid_5d,

        -- Calculate the relative return 1 day of Oil compared to SP500.
        COALESCE(oil_return_1d, 0)
            - COALESCE(sp500_return_1d, 0) AS oil_equity_relative_return_1d,

        -- Classify the risk signal based on the relative return 1 day of Oil compared to SP500.
        CASE
            WHEN COALESCE(vix_return_1d, 0) > 0.05
                 AND COALESCE(sp500_return_1d, 0) < 0
                THEN 'RISK_OFF'

            WHEN COALESCE(vix_return_1d, 0) < -0.03
                 AND COALESCE(sp500_return_1d, 0) > 0
                THEN 'RISK_ON'

            WHEN COALESCE(gold_return_1d, 0) > COALESCE(sp500_return_1d, 0)
                 AND COALESCE(vix_return_1d, 0) > 0
                THEN 'DEFENSIVE'

            ELSE 'NEUTRAL'
        END AS macro_risk_regime,

        -- Classify the signal state based on the relative return 1 day of Nasdaq compared to SP500.
        CASE
            WHEN COALESCE(sp500_return_1d, 0) > 0
                 AND COALESCE(nasdaq_return_1d, 0) > 0
                 AND COALESCE(vix_return_1d, 0) < 0
                THEN 1

            WHEN COALESCE(sp500_return_1d, 0) < 0
                 AND COALESCE(nasdaq_return_1d, 0) < 0
                 AND COALESCE(vix_return_1d, 0) > 0
                THEN -1

            ELSE 0
        END AS macro_risk_score_direction,

        -- This index measures the level of "risk appetite" of investors (when the market is euphoric and they want to make money).
        SAFE_DIVIDE(
            COALESCE(sp500_return_1d, 0)
                + COALESCE(nasdaq_return_1d, 0)
                - COALESCE(vix_return_1d, 0),
            3
        ) AS macro_risk_appetite_score,

        -- This index is the complete opposite, measuring the level of "panic and defensiveness" (investors are fearful and want to seek safe haven).
        SAFE_DIVIDE(
            COALESCE(gold_return_1d, 0)
                + COALESCE(vix_return_1d, 0)
                - COALESCE(sp500_return_1d, 0),
            3
        ) AS macro_defensive_pressure_score

    FROM pivoted

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