SELECT *
FROM {{ ref('mart_ml_features_hourly') }}
WHERE (
    liquidity_regime_high IS NOT NULL
    AND liquidity_regime_high NOT IN (0.0, 1.0)
)
OR (
    liquidity_regime_low IS NOT NULL
    AND liquidity_regime_low NOT IN (0.0, 1.0)
)
