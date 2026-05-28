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
        UPPER(underlying) AS symbol,

        observed_at,
        instrument_name,
        expiry,
        SAFE.PARSE_DATE('%d%b%y', UPPER(expiry)) AS expiry_date,

        strike,
        option_type,
        underlying_price,
        index_price,
        mark_price,
        mark_iv,
        best_bid_price,
        best_ask_price,
        bid_iv,
        ask_iv,
        last_price,
        open_interest,
        volume,
        volume_usd,
        delta,
        gamma,
        vega,
        theta,
        rho,
        moneyness,
        is_atm,
        iv_spread,
        mid_iv,
        is_call,
        ingestion_time

    FROM {{ ref('stg_deribit_options') }}
    WHERE observed_at IS NOT NULL
      AND underlying IN ('BTC', 'ETH')
      AND instrument_name IS NOT NULL
      AND option_type IN ('C', 'P')

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
latest_instrument AS (

    SELECT *
    FROM source_data
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY hour_ts, symbol, instrument_name
        ORDER BY observed_at DESC, ingestion_time DESC
    ) = 1

),

aggregated AS (

    SELECT
        hour_ts,
        symbol,

        -- Calculate the sum based on certain conditions.
        COUNT(*) AS option_instrument_count,
        COUNTIF(option_type = 'C') AS call_instrument_count,
        COUNTIF(option_type = 'P') AS put_instrument_count,
        COUNTIF(is_atm) AS atm_instrument_count,

        -- Calculate the average based 
        AVG(underlying_price) AS avg_underlying_price,
        AVG(index_price) AS avg_index_price,

        AVG(mark_iv) AS avg_mark_iv,
        AVG(mid_iv) AS avg_mid_iv,

        -- Calculate the oi weighted mark iv based on sum of open interest.
        SAFE_DIVIDE(
            SUM(mark_iv * open_interest),
            NULLIF(SUM(open_interest), 0)
        ) AS oi_weighted_mark_iv,

        -- Calculate the oi weighted mid iv based on sum of open interest.
        SAFE_DIVIDE(
            SUM(mid_iv * open_interest),
            NULLIF(SUM(open_interest), 0)
        ) AS oi_weighted_mid_iv,

        -- Calculate the avg based on certain conditions.
        AVG(IF(is_atm, mark_iv, NULL)) AS atm_avg_mark_iv,
        AVG(IF(is_atm, mid_iv, NULL)) AS atm_avg_mid_iv,

        -- Calculate the atm oi weighted mark iv based on sum of open interest.
        SAFE_DIVIDE(
            SUM(IF(is_atm, mark_iv * open_interest, 0)),
            NULLIF(SUM(IF(is_atm, open_interest, 0)), 0)
        ) AS atm_oi_weighted_mark_iv,

        AVG(iv_spread) AS avg_iv_spread,
        MAX(iv_spread) AS max_iv_spread,

        -- Compare the difference mark iv between call and put.
        AVG(IF(option_type = 'P', mark_iv, NULL))
            - AVG(IF(option_type = 'C', mark_iv, NULL)) AS put_call_iv_skew,

        -- Calculate an index called IV Skew.(weighted by open interest)
        SAFE_DIVIDE(
            SUM(IF(option_type = 'P', mark_iv * open_interest, 0)),
            NULLIF(SUM(IF(option_type = 'P', open_interest, 0)), 0)
        )
        -
        SAFE_DIVIDE(
            SUM(IF(option_type = 'C', mark_iv * open_interest, 0)),
            NULLIF(SUM(IF(option_type = 'C', open_interest, 0)), 0)
        ) AS oi_weighted_put_call_iv_skew,


        SUM(open_interest) AS total_open_interest,
        SUM(IF(option_type = 'C', open_interest, 0)) AS call_open_interest,
        SUM(IF(option_type = 'P', open_interest, 0)) AS put_open_interest,

        -- Calculate the ratio of put open interest to call open interest.
        SAFE_DIVIDE(
            SUM(IF(option_type = 'P', open_interest, 0)),
            NULLIF(SUM(IF(option_type = 'C', open_interest, 0)), 0)
        ) AS put_call_oi_ratio,

        -- Calculate the sum based on certain conditions.
        SUM(volume) AS total_option_volume,
        SUM(volume_usd) AS total_option_volume_usd,
        SUM(IF(option_type = 'C', volume_usd, 0)) AS call_volume_usd,
        SUM(IF(option_type = 'P', volume_usd, 0)) AS put_volume_usd,

        -- Calculate the put call volume ratio based on sum of volume usd.
        SAFE_DIVIDE(
            SUM(IF(option_type = 'P', volume_usd, 0)),
            NULLIF(SUM(IF(option_type = 'C', volume_usd, 0)), 0)
        ) AS put_call_volume_ratio,

        -- Calculate the sum based on certain conditions.
        SUM(delta * open_interest * COALESCE(underlying_price, index_price)) AS delta_exposure_proxy,
        SUM(gamma * open_interest * COALESCE(underlying_price, index_price)) AS gamma_exposure_proxy,
        -- Note: Since the data is already in USD format, there's no need to multiply by the price.
        SUM(vega * open_interest) AS vega_exposure_proxy,
        SUM(theta * open_interest) AS theta_exposure_proxy,
        SUM(rho * open_interest) AS rho_exposure_proxy,

        -- Calculate the call delta exposure proxy based on sum of delta, open interest and underlying price.
        SUM(IF(option_type = 'C', delta * open_interest * COALESCE(underlying_price, index_price), 0)) AS call_delta_exposure_proxy,
        SUM(IF(option_type = 'P', delta * open_interest * COALESCE(underlying_price, index_price), 0)) AS put_delta_exposure_proxy,

        -- Classification by contract maturity date
        COUNTIF(
            expiry_date IS NOT NULL
            AND DATE_DIFF(expiry_date, DATE(hour_ts), DAY) BETWEEN 0 AND 7
        ) AS short_dated_option_count,

        COUNTIF(
            expiry_date IS NOT NULL
            AND DATE_DIFF(expiry_date, DATE(hour_ts), DAY) BETWEEN 8 AND 30
        ) AS mid_dated_option_count,

        COUNTIF(
            expiry_date IS NOT NULL
            AND DATE_DIFF(expiry_date, DATE(hour_ts), DAY) > 30
        ) AS long_dated_option_count,

        -- Find the top oi instrument based on the sum of open interest and volume usd.
        ARRAY_AGG(
            instrument_name IGNORE NULLS
            ORDER BY open_interest DESC, volume_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_oi_instrument,

        MAX(open_interest) AS top_instrument_open_interest,

        -- Find the top oi strike based on the sum of open interest and volume usd.
        ARRAY_AGG(
            strike IGNORE NULLS
            ORDER BY open_interest DESC, volume_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_oi_strike,

        -- Find the top oi option type based on the sum of open interest and volume usd.
        ARRAY_AGG(
            option_type IGNORE NULLS
            ORDER BY open_interest DESC, volume_usd DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_oi_option_type,

        -- Find the top volume instrument based on the sum of volume usd and open interest.
        ARRAY_AGG(
            instrument_name IGNORE NULLS
            ORDER BY volume_usd DESC, open_interest DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_volume_instrument,

        -- Find the top volume strike based on the sum of volume usd and open interest.
        ARRAY_AGG(
            strike IGNORE NULLS
            ORDER BY volume_usd DESC, open_interest DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_volume_strike,

        -- Find the top volume option type based on the sum of volume usd and open interest.
        ARRAY_AGG(
            option_type IGNORE NULLS
            ORDER BY volume_usd DESC, open_interest DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS top_volume_option_type,

        -- Create a data stream that summarizes all the data using JSON code.
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    instrument_name,
                    expiry,
                    strike,
                    option_type,
                    mark_iv,
                    mid_iv,
                    open_interest,
                    volume_usd,
                    delta,
                    gamma,
                    vega,
                    theta,
                    is_atm
                )
                ORDER BY open_interest DESC, volume_usd DESC
                LIMIT 20
            )
        ) AS top_20_options_by_oi_json,

        -- Calculate max latest_observed_at, loaded_at, and available_at.
        MAX(observed_at) AS latest_observed_at,
        MAX(ingestion_time) AS loaded_at,
        MAX(ingestion_time) AS available_at

    FROM latest_instrument
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