# Batch Pipeline

The batch pipeline collects and prepares crypto-related data for BigQuery/dbt transformations, dashboards, monitoring, and ML training. It is the most mature ingestion path in this repository.

## What It Does

- Collects raw and intermediate data from market, funding, macro, ETF, derivatives, liquidity, and sentiment sources.
- Supports daily snapshots, hourly snapshots, intraday shifts, and selected backfill loaders.
- Writes local files, GCS/parquet outputs, Iceberg/BigLake-oriented data, or BigQuery tables depending on the script and Kestra flow.
- Runs validation, quality audit, monitoring, and alerting utilities.

## Main Source Groups

| Source group | Example files | Coverage status |
| --- | --- | --- |
| Binance trades | `binance_trade_collector.py`, `backfill/binance_backfill_raw_trades_to_hourly_int_daily_window.py` | Reliable core backfill path |
| Funding | `funding_basis_collector.py`, `backfill/binance_backfill_funding_to_int.py` | Reliable core backfill path |
| ETF | `alpha_vantage_option/etf_flows_collector.py`, Tiingo backfill helpers | Reliable core backfill path |
| Macro | `alpha_vantage_option/macro_extractor.py`, Tiingo backfill helpers | Reliable core backfill path |
| Options/liquidation | `deribit_options_collector.py`, `liquidation_heatmap.py` | Partial or source-dependent |
| Stablecoin/reserve | `stablecoin_supply_collector.py`, `exchange_reserves_collector.py` | Partial or source-dependent |
| Sentiment | `reddit_sentiment.py`, `telegram_sentiment.py` | Partial or source-dependent |

The most trusted 5-year backfill currently centers on Binance trades, ETF, Macro, and Funding.

## Important Folders

| Path | Purpose |
| --- | --- |
| `local_scripts/batch` | Main batch collectors and utility modules |
| `local_scripts/batch/backfill` | Backfill-specific scripts |
| `local_scripts/batch/common` | Shared BigQuery/io helpers |
| `local_scripts/batch/validation` | Validation engine and rules |
| `local_scripts/batch/quality_audit` | Great Expectations-oriented audit utilities |
| `local_scripts/batch/monitoring` | Pipeline health checks |
| `local_scripts/batch/alerting` | Slack alert support |
| `kestra/flows-gke/raw` | GKE raw ingestion flows |
| `kestra/flows-gke/monitoring` | Health-check orchestration |
| `kestra/flows-gke/quality` | Quality/audit orchestration |

## Backfill vs Daily Snapshot

| Mode | Purpose | Typical behavior |
| --- | --- | --- |
| Backfill | Rebuild historical coverage over larger windows | Reads historical source ranges and loads intermediate or raw tables |
| Daily snapshot | Keep current source data fresh | Runs smaller scheduled extracts through Kestra |
| Hourly/intraday | Refresh near-current tables | Feeds more frequent mart updates and prediction readiness |

Backfill scripts should be run intentionally because they can read/write large volumes and incur cloud cost.

## Output Patterns

- Local development outputs may land under local output folders.
- Production-style ingestion can write to GCS, BigLake/Iceberg, or BigQuery.
- dbt consumes BigQuery raw/external/staging inputs and builds curated marts.
- Monitoring scripts write operational summaries when cloud targets are configured.

## Local Run and Debug Notes

Use a local virtual environment and dry or isolated output paths whenever possible. Do not run cloud write paths without explicitly configured project, dataset, bucket, and credentials.

Useful debug checks:

```bash
cd /home/thanh/crypto-analysis-project
python scripts/repo_guard.py
```

For individual collectors, inspect the script arguments and environment variables before running. Avoid committing `.env`, local output data, service account keys, or generated parquet files.

## Known Limitations

- Source coverage is uneven outside the trusted Binance/ETF/Macro/Funding backfill set.
- Some sources depend on third-party availability, rate limits, or incomplete historical APIs.
- Sentiment and liquidation-style inputs may be useful analytically but should not be assumed live-ready.
- Backfill quality should be verified through dbt tests, freshness checks, and monitoring marts.
