# Batch Pipeline

## What this part does

The batch pipeline is the most mature historical data path in the project. It collects trusted sources, supports selected backfills, validates outputs, and prepares data for dbt models, dashboards, monitoring, and ML datasets.

This is not a trading bot. Batch data supports analytics and ML signal research.

## Where it lives

Batch code lives mainly under `local_scripts/batch`, with validation rules, quality audit specs, monitoring utilities, and backfill scripts grouped into subfolders.

## How it fits into the full platform

Batch ingestion feeds the storage and warehouse layers that dbt transforms into marts. Those marts later support dashboards, monitoring, and ML training/prediction inputs. The trusted 5-year backfill coverage is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources remain partial, experimental, or not fully live-ready.

## Main flow

1. Main collectors gather source data for market, ETF, macro, funding, and other source areas.
2. Backfill scripts load selected historical windows when explicitly requested.
3. Validation rules and quality specs check schema, freshness, and expected values.
4. Curated data is prepared for storage/warehouse use.
5. dbt models transform data into analytics and ML marts.
6. Monitoring and quality audit paths help reviewers understand data health.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `local_scripts/batch` | Main collectors | Includes trusted and experimental source collectors. |
| `local_scripts/batch/binance_trade_collector.py` | Binance trade collector | Part of strongest reliable historical coverage. |
| `local_scripts/batch/funding_basis_collector.py` | Funding collector | Part of strongest reliable historical coverage. |
| `local_scripts/batch/alpha_vantage_option/etf_flows_collector.py` | ETF collector | Part of strongest reliable historical coverage. |
| `local_scripts/batch/alpha_vantage_option/macro_extractor.py` | Macro extractor | Part of strongest reliable historical coverage. |
| `local_scripts/batch/backfill` | Backfill scripts | Run intentionally only; can trigger cloud writes depending on script/config. |
| `local_scripts/batch/validation` | Validation engine | Includes rules, IO, engine, and rulesets. |
| `local_scripts/batch/validation/rulesets` | YAML validation rules | Source-specific validation rules. |
| `local_scripts/batch/quality_audit/specs` | Quality audit specs | Dashboard, ML, and freshness checks. |
| `local_scripts/batch/iceberg_loader.py` | Iceberg / BigLake path | Lakehouse-oriented loader path. |

## Production boundary

Batch ingestion is the strongest source path, but it is not automatically safe to run in every environment. Backfills and loaders can write to GCS or BigQuery when configured. Partial sources such as options, liquidation, stablecoin, exchange reserves, and sentiment should not be presented as equally reliable.

## Safety notes

- Do not run backfills casually.
- Do not commit `local_scripts/batch/.env`, service account keys, local output data, logs, or generated caches.
- Review cost and destination configuration before running cloud-connected loaders.
- Documentation updates should not trigger GCS, BigQuery, or Registry writes.

## Read next

- [Architecture](architecture.md)
- [dbt Models](dbt_models.md)
- [Kestra Orchestration](kestra_orchestration.md)
- [K8s / GKE Runtime](k8s_gke_runtime.md)
