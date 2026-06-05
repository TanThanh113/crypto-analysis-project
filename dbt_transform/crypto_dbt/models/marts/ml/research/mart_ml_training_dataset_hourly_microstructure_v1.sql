{{ config(materialized='view') }}

-- Scratch-only research model for microstructure feature parity.
-- This model does not replace mart_ml_training_dataset_hourly and should not be
-- used by production prediction flows. It mirrors the research Python features
-- from local_feature_engineering_research.py using leakage-safe SQL windows.

WITH base AS (

    SELECT *
    FROM {{ ref('mart_ml_training_dataset_hourly') }}

),

lagged AS (

    SELECT
        *,

        LAG(quote_volume, 1) OVER symbol_time AS quote_volume_lag_1h,
        LAG(quote_volume_24h, 1) OVER symbol_time AS quote_volume_24h_lag_1h,
        LAG(volume_zscore_24h, 1) OVER symbol_time AS volume_zscore_24h_lag_1h,
        LAG(liquidity_risk_score, 1) OVER symbol_time AS liquidity_risk_score_lag_1h,

        LAG(taker_buy_quote_ratio, 1) OVER symbol_time AS taker_buy_quote_ratio_lag_1h,
        LAG(taker_buy_quote_ratio, 5) OVER symbol_time AS _taker_buy_quote_ratio_lag_5h,
        LAG(taker_buy_quote_ratio, 13) OVER symbol_time AS _taker_buy_quote_ratio_lag_13h,

        LAG(return_1h, 1) OVER symbol_time AS _return_1h_lag_1h_for_window,
        LAG(return_4h, 1) OVER symbol_time AS return_4h_lag_1h,
        LAG(return_24h, 1) OVER symbol_time AS return_24h_lag_1h,

        SUM(COALESCE(log_return_1h, 0.0)) OVER (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS _cumulative_log_return

    FROM base
    WINDOW symbol_time AS (
        PARTITION BY symbol
        ORDER BY hour_ts
    )

),

lagged_again AS (

    SELECT
        *,
        LAG(_cumulative_log_return, 1) OVER symbol_time AS _cumulative_log_return_lag_1h
    FROM lagged
    WINDOW symbol_time AS (
        PARTITION BY symbol
        ORDER BY hour_ts
    )

),

windowed AS (

    SELECT
        *,

        COUNT(_return_1h_lag_1h_for_window) OVER window_4h AS _return_1h_count_4h,
        AVG(_return_1h_lag_1h_for_window) OVER window_4h AS _return_1h_avg_4h,
        SUM(_return_1h_lag_1h_for_window) OVER window_4h AS _return_1h_sum_4h,

        COUNT(_return_1h_lag_1h_for_window) OVER window_24h AS _return_1h_count_24h,
        AVG(_return_1h_lag_1h_for_window) OVER window_24h AS _return_1h_avg_24h,
        SUM(_return_1h_lag_1h_for_window) OVER window_24h AS _return_1h_sum_24h,

        COUNT(quote_volume_lag_1h) OVER window_24h AS _quote_volume_count_24h,
        AVG(quote_volume_lag_1h) OVER window_24h AS _quote_volume_avg_24h,
        STDDEV_SAMP(quote_volume_lag_1h) OVER window_24h AS _quote_volume_std_24h,

        COUNT(return_24h_lag_1h) OVER expanding_symbol AS _return_24h_count_expanding,
        AVG(return_24h_lag_1h) OVER expanding_symbol AS _return_24h_avg_expanding,
        STDDEV_SAMP(return_24h_lag_1h) OVER expanding_symbol AS _return_24h_std_expanding,

        COUNT(_cumulative_log_return_lag_1h) OVER window_24h AS _drawdown_count_24h,
        MAX(_cumulative_log_return_lag_1h) OVER window_24h AS _rolling_peak_log_return_24h

    FROM lagged_again
    WINDOW
        window_4h AS (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
        window_24h AS (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ),
        expanding_symbol AS (
            PARTITION BY symbol
            ORDER BY hour_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )

),

scored AS (

    SELECT
        *,

        taker_buy_quote_ratio_lag_1h - _taker_buy_quote_ratio_lag_5h AS taker_buy_pressure_delta_4h,
        taker_buy_quote_ratio_lag_1h - _taker_buy_quote_ratio_lag_13h AS taker_buy_pressure_delta_12h,

        CASE
            WHEN _return_1h_count_4h >= 2 THEN _return_1h_avg_4h
        END AS return_1h_rolling_mean_4h,

        CASE
            WHEN _return_1h_count_4h >= 2 THEN _return_1h_sum_4h
        END AS return_1h_rolling_sum_4h,

        CASE
            WHEN _return_1h_count_24h >= 12 THEN _return_1h_avg_24h
        END AS return_1h_rolling_mean_24h,

        CASE
            WHEN _return_1h_count_24h >= 12 THEN _return_1h_sum_24h
        END AS return_1h_rolling_sum_24h,

        CASE
            WHEN _quote_volume_count_24h >= 6 THEN SAFE_DIVIDE(
                quote_volume_lag_1h - _quote_volume_avg_24h,
                NULLIF(_quote_volume_std_24h, 0)
            )
        END AS quote_volume_zscore_24h,

        CASE
            WHEN _return_24h_count_expanding >= 24 THEN SAFE_DIVIDE(
                return_24h_lag_1h - _return_24h_avg_expanding,
                NULLIF(_return_24h_std_expanding, 0)
            )
        END AS return_24h_symbol_zscore,

        CASE
            WHEN _drawdown_count_24h >= 6
                THEN _cumulative_log_return_lag_1h - _rolling_peak_log_return_24h
        END AS rolling_drawdown_24h

    FROM windowed

),

final AS (

    SELECT
        * EXCEPT (
            _taker_buy_quote_ratio_lag_5h,
            _taker_buy_quote_ratio_lag_13h,
            _return_1h_lag_1h_for_window,
            _cumulative_log_return,
            _cumulative_log_return_lag_1h,
            _return_1h_count_4h,
            _return_1h_avg_4h,
            _return_1h_sum_4h,
            _return_1h_count_24h,
            _return_1h_avg_24h,
            _return_1h_sum_24h,
            _quote_volume_count_24h,
            _quote_volume_avg_24h,
            _quote_volume_std_24h,
            _return_24h_count_expanding,
            _return_24h_avg_expanding,
            _return_24h_std_expanding,
            _drawdown_count_24h,
            _rolling_peak_log_return_24h
        ),

        CASE
            WHEN quote_volume_zscore_24h >= 1.0 THEN 1.0
            ELSE 0.0
        END AS liquidity_regime_high,

        CASE
            WHEN quote_volume_zscore_24h <= -1.0 THEN 1.0
            ELSE 0.0
        END AS liquidity_regime_low,

        CASE
            WHEN UPPER(symbol) = 'ETH' THEN quote_volume_zscore_24h
            ELSE 0.0
        END AS is_eth_x_quote_volume_zscore_24h

    FROM scored

)

SELECT *
FROM final
