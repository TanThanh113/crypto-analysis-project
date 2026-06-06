WITH expected AS (

    SELECT 'quote_volume_lag_1h' AS column_name UNION ALL
    SELECT 'quote_volume_24h_lag_1h' UNION ALL
    SELECT 'quote_volume_zscore_24h' UNION ALL
    SELECT 'volume_zscore_24h_lag_1h' UNION ALL
    SELECT 'liquidity_regime_high' UNION ALL
    SELECT 'liquidity_regime_low' UNION ALL
    SELECT 'liquidity_risk_score_lag_1h' UNION ALL
    SELECT 'is_eth_x_quote_volume_zscore_24h' UNION ALL
    SELECT 'return_4h_lag_1h' UNION ALL
    SELECT 'return_24h_lag_1h' UNION ALL
    SELECT 'return_24h_symbol_zscore' UNION ALL
    SELECT 'return_1h_rolling_mean_4h' UNION ALL
    SELECT 'return_1h_rolling_sum_4h' UNION ALL
    SELECT 'return_1h_rolling_mean_24h' UNION ALL
    SELECT 'return_1h_rolling_sum_24h' UNION ALL
    SELECT 'rolling_drawdown_24h'

),

actual AS (

    SELECT LOWER(column_name) AS column_name
    FROM `{{ target.database }}.{{ target.schema }}.INFORMATION_SCHEMA.COLUMNS`
    WHERE LOWER(table_name) = 'mart_ml_training_dataset_hourly'

)

SELECT expected.column_name
FROM expected
LEFT JOIN actual
    ON expected.column_name = actual.column_name
WHERE actual.column_name IS NULL
