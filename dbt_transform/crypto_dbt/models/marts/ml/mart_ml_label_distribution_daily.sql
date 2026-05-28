{{ config(
    materialized='table',
    partition_by={"field": "label_date", "data_type": "date", "granularity": "day"},
    cluster_by=['symbol']
) }}

-- This model monitors daily ML label quality by symbol.
-- It checks label availability, future return distribution, and class balance.
-- Useful before training classification/regression models.

-- Filter out the necessary columns and exclude rows with irrelevant data.
WITH labels AS (

    SELECT
        DATE(hour_ts) AS label_date,
        symbol,

        ml_label_sk,
        hour_ts,
        close_price,

        future_return_1h,
        future_return_4h,
        future_return_24h,
        future_volatility_24h,

        future_direction_1h,
        future_direction_4h,
        future_direction_24h,
        binary_direction_4h_excluding_flat,
        sample_weight_4h,

        is_label_1h_available,
        is_label_4h_available,
        is_label_24h_available,
        is_volatility_24h_available,
        is_label_available,
        label_available_at

    FROM {{ ref('mart_ml_labels_hourly') }}
    WHERE hour_ts IS NOT NULL
      AND symbol IN ('BTC', 'ETH')

),

agg AS (

    SELECT
        label_date,
        symbol,

        -- Count the number of rows.
        COUNT(*) AS label_rows,

        -- Count the columns that meet the filtering conditions.
        COUNTIF(is_label_1h_available = TRUE) AS available_label_1h_rows,
        COUNTIF(is_label_4h_available = TRUE) AS available_label_4h_rows,
        COUNTIF(is_label_24h_available = TRUE) AS available_label_24h_rows,
        COUNTIF(is_volatility_24h_available = TRUE) AS available_volatility_24h_rows,
        COUNTIF(is_label_available = TRUE) AS fully_available_label_rows,

        -- Calculate the ratio of available columns.
        SAFE_DIVIDE(COUNTIF(is_label_1h_available = TRUE), COUNT(*)) AS label_1h_available_ratio,
        SAFE_DIVIDE(COUNTIF(is_label_4h_available = TRUE), COUNT(*)) AS label_4h_available_ratio,
        SAFE_DIVIDE(COUNTIF(is_label_24h_available = TRUE), COUNT(*)) AS label_24h_available_ratio,
        SAFE_DIVIDE(COUNTIF(is_label_available = TRUE), COUNT(*)) AS fully_available_label_ratio,

        -- Calculate the average and standard deviation of future returns.
        AVG(future_return_1h) AS avg_future_return_1h,
        AVG(future_return_4h) AS avg_future_return_4h,
        AVG(future_return_24h) AS avg_future_return_24h,

        STDDEV_SAMP(future_return_1h) AS std_future_return_1h,
        STDDEV_SAMP(future_return_4h) AS std_future_return_4h,
        STDDEV_SAMP(future_return_24h) AS std_future_return_24h,

        -- Calculate the minimum and maximum of future returns.
        MIN(future_return_4h) AS min_future_return_4h,
        MAX(future_return_4h) AS max_future_return_4h,
        AVG(future_volatility_24h) AS avg_future_volatility_24h,

        -- Calculate the number of future returns with different directions.
        COUNTIF(future_direction_4h = 'UP') AS up_count_4h,
        COUNTIF(future_direction_4h = 'DOWN') AS down_count_4h,
        COUNTIF(future_direction_4h = 'FLAT') AS flat_count_4h,
        COUNTIF(future_direction_4h IS NULL) AS null_direction_4h_count,

        -- Calculate the number of future returns with binary directions.
        COUNTIF(binary_direction_4h_excluding_flat = 1) AS binary_up_count_4h,
        COUNTIF(binary_direction_4h_excluding_flat = 0) AS binary_down_count_4h,
        COUNTIF(binary_direction_4h_excluding_flat IS NULL) AS binary_excluded_flat_count_4h,

        -- Calculate the average and maximum sample weights.
        AVG(sample_weight_4h) AS avg_sample_weight_4h,
        MIN(sample_weight_4h) AS min_sample_weight_4h,
        MAX(sample_weight_4h) AS max_sample_weight_4h,

        MAX(label_available_at) AS latest_label_available_at,

        -- The time when the metric was loaded
        CURRENT_TIMESTAMP() AS mart_loaded_at

    FROM labels
    GROUP BY
        label_date,
        symbol

),

-- Here we will create the final table.
final AS (

    SELECT
        -- Here we will create a unique key for each row.
        TO_HEX(
            MD5(
                CONCAT(
                    CAST(label_date AS STRING),
                    '|',
                    symbol,
                    '|ml_label_quality_daily'
                )
            )
        ) AS ml_label_quality_daily_sk,

        label_date,
        symbol,

        label_rows,

        available_label_1h_rows,
        available_label_4h_rows,
        available_label_24h_rows,
        available_volatility_24h_rows,
        fully_available_label_rows,

        label_1h_available_ratio,
        label_4h_available_ratio,
        label_24h_available_ratio,
        fully_available_label_ratio,

        avg_future_return_1h,
        avg_future_return_4h,
        avg_future_return_24h,

        std_future_return_1h,
        std_future_return_4h,
        std_future_return_24h,

        min_future_return_4h,
        max_future_return_4h,
        avg_future_volatility_24h,

        up_count_4h,
        down_count_4h,
        flat_count_4h,
        null_direction_4h_count,

        -- Calculate the ratio of up/down/flat counts.
        SAFE_DIVIDE(up_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)) AS up_ratio_4h,
        SAFE_DIVIDE(down_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)) AS down_ratio_4h,
        SAFE_DIVIDE(flat_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)) AS flat_ratio_4h,

        binary_up_count_4h,
        binary_down_count_4h,
        binary_excluded_flat_count_4h,

        -- Calculate the ratio of binary up/down counts.
        SAFE_DIVIDE(binary_up_count_4h, NULLIF(binary_up_count_4h + binary_down_count_4h, 0)) AS binary_up_ratio_4h,
        SAFE_DIVIDE(binary_down_count_4h, NULLIF(binary_up_count_4h + binary_down_count_4h, 0)) AS binary_down_ratio_4h,

        avg_sample_weight_4h,
        min_sample_weight_4h,
        max_sample_weight_4h,

        latest_label_available_at,

        -- Label availability status.
        CASE
            WHEN label_rows = 0 THEN 'NO_LABELS'
            WHEN fully_available_label_ratio >= 0.90 THEN 'GOOD'
            WHEN fully_available_label_ratio >= 0.70 THEN 'ACCEPTABLE'
            WHEN fully_available_label_ratio >= 0.50 THEN 'WEAK'
            ELSE 'BAD'
        END AS label_availability_status,

        -- Direction availability status.
        CASE
            WHEN up_count_4h + down_count_4h + flat_count_4h = 0 THEN 'NO_DIRECTION_LABELS'
            WHEN LEAST(
                SAFE_DIVIDE(up_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)),
                SAFE_DIVIDE(down_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)),
                SAFE_DIVIDE(flat_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0))
            ) < 0.10 THEN 'HIGHLY_IMBALANCED'
            WHEN LEAST(
                SAFE_DIVIDE(up_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)),
                SAFE_DIVIDE(down_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0)),
                SAFE_DIVIDE(flat_count_4h, NULLIF(up_count_4h + down_count_4h + flat_count_4h, 0))
            ) < 0.20 THEN 'MODERATELY_IMBALANCED'
            ELSE 'BALANCED'
        END AS direction_4h_balance_status,

        mart_loaded_at

    FROM agg

)

SELECT *
FROM final