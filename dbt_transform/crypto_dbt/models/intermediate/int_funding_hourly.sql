-- The configuration allows for the intelligent addition of new data.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['hour_ts', 'symbol'],
    partition_by={"field": "hour_ts", "data_type": "timestamp", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- Filter the columns you need to extract data from, using the data from the previous two days as a reference point.
WITH source_data AS (

    SELECT
        TIMESTAMP_TRUNC(observed_at, HOUR) AS hour_ts,
        UPPER(symbol) AS symbol,
        LOWER(exchange) AS exchange,

        observed_at,
        mark_price,
        spot_price,
        basis_spread,
        basis_pct,
        funding_rate_coin,
        funding_rate_usdt,
        annualized_funding_coin,
        annualized_funding_usdt,
        annualized_basis_coin,
        annualized_basis_usdt,
        arbitrage_spread,
        funding_regime,
        arbitrage_opportunity,
        leverage_stress,
        ingestion_time

    FROM {{ ref('stg_funding_rates') }}
    WHERE observed_at IS NOT NULL
      AND symbol IN ('BTC', 'ETH')

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
latest_exchange AS (

    SELECT *
    FROM source_data
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY hour_ts, symbol, exchange
        ORDER BY observed_at DESC, ingestion_time DESC
    ) = 1

),

aggregated AS (

    SELECT
        hour_ts,
        symbol,

        -- Count the number of exchanges reporting
        COUNT(DISTINCT exchange) AS exchanges_reporting,

        -- Calculate the averages and max values (price, basis)
        AVG(mark_price) AS avg_mark_price,
        AVG(spot_price) AS avg_spot_price,
        AVG(basis_spread) AS avg_basis_spread,
        AVG(basis_pct) AS avg_basis_pct,
        MAX(ABS(basis_pct)) AS max_abs_basis_pct,

        -- Calculate the averages and standard deviation of funding rates
        AVG(funding_rate_coin) AS avg_funding_rate_coin,
        AVG(funding_rate_usdt) AS avg_funding_rate_usdt,
        AVG(annualized_funding_coin) AS avg_annualized_funding_coin,
        AVG(annualized_funding_usdt) AS avg_annualized_funding_usdt,
        STDDEV_SAMP(annualized_funding_coin) AS funding_dispersion_coin,

        -- Calculate the averages and max values (anualized basis)
        AVG(annualized_basis_coin) AS avg_annualized_basis_coin,
        AVG(annualized_basis_usdt) AS avg_annualized_basis_usdt,
        AVG(arbitrage_spread) AS avg_arbitrage_spread,
        MAX(ABS(arbitrage_spread)) AS max_abs_arbitrage_spread,

        -- Calculate the averages and max values (leverage stress)
        MAX(leverage_stress) AS max_leverage_stress,
        AVG(leverage_stress) AS avg_leverage_stress,

        -- Find the dominant funding regime based on the value of annualized funding rate
        ARRAY_AGG(
            funding_regime IGNORE NULLS
            ORDER BY ABS(annualized_funding_coin) DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS dominant_funding_regime,
        
        -- Find the dominant arbitrage opportunity based on the value of arbitrage spread
        ARRAY_AGG(
            arbitrage_opportunity IGNORE NULLS
            ORDER BY ABS(arbitrage_spread) DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS dominant_arbitrage_opportunity,

        -- Find the strongest arbitrage exchange based on the value of arbitrage spread
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY ABS(arbitrage_spread) DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS strongest_arbitrage_exchange,

        -- Find the highest stress exchange based on the value of leverage stress
        ARRAY_AGG(
            exchange IGNORE NULLS
            ORDER BY leverage_stress DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS highest_stress_exchange,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    exchange,
                    mark_price,
                    spot_price,
                    basis_pct,
                    annualized_funding_coin,
                    annualized_funding_usdt,
                    arbitrage_spread,
                    funding_regime,
                    arbitrage_opportunity,
                    leverage_stress
                )
                ORDER BY exchange
            )
        ) AS exchange_snapshot_json,

        -- Calculate max observed_at, ingestion_time, and 
        MAX(observed_at) AS latest_observed_at,
        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM latest_exchange
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