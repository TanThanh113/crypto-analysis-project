-- Standardize coins

{{ config(materialized='table') }}

-- Hardcoded. The coins that are allowed to exist, and they are standardized according to rules(BTC, ETH, USDT, etc.)
WITH hardcoded AS (

    SELECT
        'BTC' AS symbol,
        'BTCUSDT' AS pair_symbol,
        'Bitcoin' AS asset_name,
        'BTC' AS base_asset,
        'USDT' AS quote_asset,
        'crypto' AS asset_class,
        'bitcoin' AS coingecko_id,
        TRUE AS is_major_asset,
        TRUE AS dashboard_enabled,
        TRUE AS ml_enabled,
        1 AS sort_order,
        1 AS source_priority

    UNION ALL

    SELECT
        'ETH' AS symbol,
        'ETHUSDT' AS pair_symbol,
        'Ethereum' AS asset_name,
        'ETH' AS base_asset,
        'USDT' AS quote_asset,
        'crypto' AS asset_class,
        'ethereum' AS coingecko_id,
        TRUE AS is_major_asset,
        TRUE AS dashboard_enabled,
        TRUE AS ml_enabled,
        2 AS sort_order,
        1 AS source_priority

),

-- Observed. The currencies traded on that day
observed AS (

    SELECT DISTINCT
        UPPER(symbol) AS symbol,
        UPPER(COALESCE(pair_symbol, CONCAT(symbol, 'USDT'))) AS pair_symbol,

        CASE
            WHEN UPPER(symbol) = 'BTC' THEN 'Bitcoin'
            WHEN UPPER(symbol) = 'ETH' THEN 'Ethereum'
            ELSE UPPER(symbol)
        END AS asset_name,

        UPPER(symbol) AS base_asset,
        'USDT' AS quote_asset,
        'crypto' AS asset_class,

        CASE
            WHEN UPPER(symbol) = 'BTC' THEN 'bitcoin'
            WHEN UPPER(symbol) = 'ETH' THEN 'ethereum'
        END AS coingecko_id,

        UPPER(symbol) IN ('BTC', 'ETH') AS is_major_asset,
        TRUE AS dashboard_enabled,
        UPPER(symbol) IN ('BTC', 'ETH') AS ml_enabled,

        CASE
            WHEN UPPER(symbol) = 'BTC' THEN 1
            WHEN UPPER(symbol) = 'ETH' THEN 2
            ELSE 999
        END AS sort_order,

        2 AS source_priority

    FROM {{ ref('int_crypto_features_hourly') }}
    WHERE symbol IS NOT NULL

),

-- Unioned the two tables
unioned AS (

    SELECT * FROM hardcoded

    UNION ALL

    SELECT * FROM observed

),

-- Deduped. The final table with the standardized coins
deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY symbol
            ORDER BY
                source_priority ASC,
                dashboard_enabled DESC,
                ml_enabled DESC,
                sort_order ASC
        ) AS rn
    FROM unioned

)

-- Final table with the standardized coins
SELECT
    symbol AS symbol_key,
    symbol,
    pair_symbol,
    asset_name,
    base_asset,
    quote_asset,
    asset_class,
    coingecko_id,
    is_major_asset,
    dashboard_enabled,
    ml_enabled,
    sort_order,
    CURRENT_TIMESTAMP() AS dim_loaded_at

FROM deduped
WHERE rn = 1
ORDER BY sort_order ASC, symbol ASC