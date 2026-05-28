-- Standardize time
{{ config(materialized='table') }}
 
-- Hardcoded. Set your own start and end times.
WITH bounds AS (

    SELECT
        TIMESTAMP_TRUNC(
            COALESCE(
                MIN(hour_ts),
                TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            ),
            HOUR
        ) AS start_hour,

        TIMESTAMP_TRUNC(
            COALESCE(
                MAX(hour_ts),
                CURRENT_TIMESTAMP()
            ),
            HOUR
        ) AS end_hour

    FROM {{ ref('int_crypto_features_hourly') }}

),

-- Automatically generate hours within the start and end time ranges.
hours AS (

    SELECT
        hour_ts

    FROM bounds,
        UNNEST(
            GENERATE_TIMESTAMP_ARRAY(
                start_hour,
                end_hour,
                INTERVAL 1 HOUR
            )
        ) AS hour_ts

),

-- Final table with the standardized time
final AS (

    SELECT
        -- Identifier Group and Basic Format
        hour_ts AS time_key,
        hour_ts,
        DATE(hour_ts) AS date_key,

        -- Time-splitting team
        EXTRACT(YEAR FROM hour_ts) AS year,
        EXTRACT(QUARTER FROM hour_ts) AS quarter,
        EXTRACT(MONTH FROM hour_ts) AS month,
        FORMAT_DATE('%Y-%m', DATE(hour_ts)) AS year_month,
        EXTRACT(ISOWEEK FROM hour_ts) AS iso_week,

        -- Group to find the first day of the cycle
        DATE_TRUNC(DATE(hour_ts), WEEK(MONDAY)) AS week_start_date,
        DATE_TRUNC(DATE(hour_ts), MONTH) AS month_start_date,
        DATE_TRUNC(DATE(hour_ts), QUARTER) AS quarter_start_date,
        DATE_TRUNC(DATE(hour_ts), YEAR) AS year_start_date,

        -- Time-splitting team
        EXTRACT(DAY FROM hour_ts) AS day_of_month,
        EXTRACT(DAYOFWEEK FROM hour_ts) AS day_of_week_num,
        FORMAT_TIMESTAMP('%A', hour_ts) AS day_of_week_name,

        EXTRACT(HOUR FROM hour_ts) AS hour_of_day,
        EXTRACT(MINUTE FROM hour_ts) AS minute_of_hour,

        -- Business Logic
        EXTRACT(DAYOFWEEK FROM hour_ts) IN (1, 7) AS is_weekend,

        CASE
            WHEN EXTRACT(HOUR FROM hour_ts) BETWEEN 0 AND 6 THEN 'asia_early'
            WHEN EXTRACT(HOUR FROM hour_ts) BETWEEN 7 AND 12 THEN 'asia_europe_overlap'
            WHEN EXTRACT(HOUR FROM hour_ts) BETWEEN 13 AND 18 THEN 'europe_us_overlap'
            ELSE 'us_late'
        END AS trading_session_utc,

        EXTRACT(HOUR FROM hour_ts) IN (0, 7, 13, 19) AS has_intraday_social_refresh_window,

        EXTRACT(HOUR FROM hour_ts) = 0 AS is_day_start_utc,

        -- Time loading data
        CURRENT_TIMESTAMP() AS dim_loaded_at

    FROM hours

)

SELECT *
FROM final
ORDER BY hour_ts