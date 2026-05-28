-- Profiles of the 2 AIs about to be trained.
{{ config(materialized='table') }}

WITH model_registry AS (
    --- AI predicts price direction.
    SELECT
        'crypto_direction_lgbm_v1' AS model_name, -- The name of the model
        'v1' AS model_version, -- The version of the model
        'crypto_direction' AS model_family,
        'lightgbm' AS algorithm, -- The type of model
        'classification' AS problem_type,
        'future_direction_4h' AS primary_target, -- Solve the problem of predicting the direction of travel over the next 4 hours.
        'BTC/ETH 4h direction classifier using hourly market, derivatives, liquidity, social, macro, and ETF features' AS purpose, -- how to work the model
        'offline_train_local_or_kestra' AS training_mode, -- How to learn the model
        'mart_ml_training_dataset_hourly' AS training_table, -- Specify the data table that needs to be studied.
        'mart_ml_prediction_input_latest' AS inference_table, -- Specify the data table from which predictions need to be made.

        -- After completing its learning process, all of its intelligence is packaged into a secret text file stored on Google Cloud Storage.
        'gcs_or_local_artifacts/crypto_direction_lgbm_v1.txt' AS expected_artifact_path, 
        TRUE AS is_active
    -- AI measures the degree of price volatility.
    UNION ALL

    SELECT
        'crypto_volatility_baseline_v1' AS model_name,
        'v1' AS model_version,
        'crypto_volatility' AS model_family,
        'lightgbm_regressor' AS algorithm,
        'regression' AS problem_type,
        'future_volatility_24h' AS primary_target,
        'Baseline volatility risk model for 24h realized volatility' AS purpose,
        'offline_train_local_or_kestra' AS training_mode,
        'mart_ml_training_dataset_hourly' AS training_table,
        'mart_ml_prediction_input_latest' AS inference_table,
        'gcs_or_local_artifacts/crypto_volatility_baseline_v1.txt' AS expected_artifact_path,
        FALSE AS is_active

)

SELECT
    -- The unique identifier of the metric
    TO_HEX(MD5(CONCAT(model_name, '|', model_version))) AS model_registry_sk,

    model_name,
    model_version,
    model_family,
    algorithm,
    problem_type,
    primary_target,
    purpose,
    training_mode,
    training_table,
    inference_table,
    expected_artifact_path,
    is_active,

    -- The time when the metric was loaded
    CURRENT_TIMESTAMP() AS registered_at

FROM model_registry