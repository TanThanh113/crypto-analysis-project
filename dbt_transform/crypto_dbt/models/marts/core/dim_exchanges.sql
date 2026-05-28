-- Standardize exchanges and funding rates
{{ config(materialized='table') }}

-- Hardcoded. Only use the exchanges you specify, and go hardcore first(Binance, Coinbase,...)
WITH hardcoded AS (

    SELECT
        'binance' AS exchange_key,
        'Binance' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'binance' AS exchange_family,
        'binance' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'coinbase' AS exchange_key,
        'Coinbase' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'coinbase' AS exchange_family,
        'gdax' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'kraken' AS exchange_key,
        'Kraken' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'kraken' AS exchange_family,
        'kraken' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'bitfinex' AS exchange_key,
        'Bitfinex' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'bitfinex' AS exchange_family,
        'bitfinex' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'okx' AS exchange_key,
        'OKX' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'okx' AS exchange_family,
        'okex' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'bybit' AS exchange_key,
        'Bybit' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'bybit' AS exchange_family,
        'bybit_spot' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'kucoin' AS exchange_key,
        'KuCoin' AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        'kucoin' AS exchange_family,
        'kucoin' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'binance_coin_m' AS exchange_key,
        'Binance COIN-M' AS exchange_name,
        'derivatives' AS exchange_type,
        'coin_m_perp' AS market_type,
        'binance' AS exchange_family,
        'binance' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'bybit_coin_m' AS exchange_key,
        'Bybit COIN-M' AS exchange_name,
        'derivatives' AS exchange_type,
        'coin_m_perp' AS market_type,
        'bybit' AS exchange_family,
        'bybit_spot' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'okx_coin_m' AS exchange_key,
        'OKX COIN-M' AS exchange_name,
        'derivatives' AS exchange_type,
        'coin_m_perp' AS market_type,
        'okx' AS exchange_family,
        'okex' AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

    UNION ALL

    SELECT
        'deribit' AS exchange_key,
        'Deribit' AS exchange_name,
        'derivatives' AS exchange_type,
        'options' AS market_type,
        'deribit' AS exchange_family,
        CAST(NULL AS STRING) AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        1 AS source_priority

),

-- Observed. Receive all the exchanges that the data returns.
reserve_observed AS (

    SELECT
        LOWER(exchange) AS exchange_key,
        INITCAP(REPLACE(LOWER(exchange), '_', ' ')) AS exchange_name,
        'cex' AS exchange_type,
        'spot' AS market_type,
        LOWER(exchange) AS exchange_family,
        ANY_VALUE(coingecko_id) AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        2 AS source_priority

    FROM {{ ref('stg_exchange_reserve') }}
    WHERE exchange IS NOT NULL
    GROUP BY
        exchange_key,
        exchange_name,
        exchange_type,
        market_type,
        exchange_family,
        is_cex,
        dashboard_enabled,
        source_priority

),

-- Observed. Receive all the funding rates that the data returns.
funding_observed AS (

    SELECT
        LOWER(exchange) AS exchange_key,
        INITCAP(REPLACE(LOWER(exchange), '_', ' ')) AS exchange_name,
        'derivatives' AS exchange_type,

        CASE
            WHEN LOWER(exchange) LIKE '%coin_m%' THEN 'coin_m_perp'
            WHEN LOWER(exchange) LIKE '%usdt%' THEN 'usdt_m_perp'
            ELSE 'perpetual'
        END AS market_type,

        SPLIT(LOWER(exchange), '_')[SAFE_OFFSET(0)] AS exchange_family,
        CAST(NULL AS STRING) AS coingecko_id,
        TRUE AS is_cex,
        TRUE AS dashboard_enabled,
        2 AS source_priority

    FROM {{ ref('stg_funding_rates') }}
    WHERE exchange IS NOT NULL
    GROUP BY
        exchange_key,
        exchange_name,
        exchange_type,
        market_type,
        exchange_family,
        coingecko_id,
        is_cex,
        dashboard_enabled,
        source_priority

),

-- Unioned the two tables

unioned AS (

    SELECT * FROM hardcoded

    UNION ALL

    SELECT * FROM reserve_observed

    UNION ALL

    SELECT * FROM funding_observed

),

-- Deduped. The final table with the standardized exchanges
deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY exchange_key
            ORDER BY
                source_priority ASC,
                dashboard_enabled DESC,
                coingecko_id IS NOT NULL DESC
        ) AS rn

    FROM unioned

)

-- Final table with the standardized exchanges and funding rates
SELECT
    exchange_key,
    exchange_name,
    exchange_type,
    market_type,
    exchange_family,
    coingecko_id,
    is_cex,
    dashboard_enabled,
    CURRENT_TIMESTAMP() AS dim_loaded_at

FROM deduped
WHERE rn = 1
ORDER BY exchange_type ASC, exchange_key ASC