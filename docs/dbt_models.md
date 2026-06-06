# dbt Models

The dbt project lives in `dbt_transform/crypto_dbt` and organizes BigQuery transformations into source-normalized staging models, aligned intermediate models, reusable marts, dashboard marts, ML marts, and monitoring marts.

## Layers

| Layer | Path | Purpose |
| --- | --- | --- |
| Staging | `models/staging` | Normalize raw source tables, timestamps, symbols, and column names |
| Intermediate | `models/intermediate` | Build hourly/daily source-specific aggregates and features |
| Core marts | `models/marts/core` | Reusable dimensions and feature facts |
| Dashboard marts | `models/marts/dashboard` | Looker/dashboard-ready tables |
| ML marts | `models/marts/ml` | Features, labels, training data, prediction input/output, model metrics |
| ML research marts | `models/marts/ml/research` | Scratch/research model variants that are not production defaults |
| Monitoring marts | `models/marts/monitoring` | Pipeline health, GE audit, failed checks, and recent health views |

## Naming Convention

- `stg_*`: cleaned source-level staging models.
- `int_*`: intermediate aggregates, joins, and source-specific feature preparation.
- `dim_*`: dimensions.
- `fact_*`: reusable analytical facts.
- `mart_dashboard_*`: BI/dashboard tables.
- `mart_ml_*`: ML training, prediction, quality, and metric tables.
- `mart_monitoring_*`: operational monitoring views/tables.

## Important ML Marts

| Model | Role |
| --- | --- |
| `mart_ml_features_hourly` | ML feature table |
| `mart_ml_labels_hourly` | Label table |
| `mart_ml_training_dataset_hourly` | Training dataset consumed by `ml/train_model.py` |
| `mart_ml_prediction_input_hourly` | Prediction-ready hourly input |
| `mart_ml_prediction_input_latest` | Latest prediction input consumed by `ml/predict_latest.py` |
| `mart_ml_predictions_latest` | Latest prediction output mart |
| `mart_ml_model_metrics` | Model metrics mart |
| `mart_ml_feature_quality_daily` | Feature quality/completeness mart |
| `mart_ml_label_distribution_daily` | Label distribution monitoring |

## Additive Microstructure Feature Note

Some dbt mart columns can be added before the production ML contract uses them. This is intentional: dbt can expose additive feature candidates while `ml/feature_list.yml` remains conservative. The microstructure/subset9 candidate is still research/manual and is not the default production feature contract.

## Incremental and Partitioning Notes

Many model-specific materialization details are defined directly in dbt model SQL or schema YAML. When changing mart behavior, inspect the model-level `config(...)`, partition columns, clustering fields, and tests before editing. Do not assume a model is safe to rebuild at full scale without checking cost and freshness impact.

## Local dbt Commands

```bash
cd /home/thanh/crypto-analysis-project/dbt_transform/crypto_dbt
uv run dbt parse
uv run dbt build --select models/marts/ml
```

Run cloud-backed dbt commands only when the BigQuery profile, target dataset, and credentials are intentionally configured.

## Testing Guidance

- Add schema tests for new marts or important columns.
- Prefer additive column changes over breaking schema changes.
- Validate ML mart changes against the production feature contract before enabling them in `ml/feature_list.yml`.
- Avoid changing label logic without a separate leakage and target-quality review.
