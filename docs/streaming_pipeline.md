# Streaming Pipeline

## What this part does

The streaming pipeline is a lower-latency, freshness-oriented path for market, on-chain, and sentiment signals. It is useful for experiments and future automation, but it is not the trusted full-history path yet.

The project remains an analytics and ML signal platform, not a trading bot.

## Where it lives

Streaming files live under `local_scripts/streaming`. Producers are under `local_scripts/streaming/producer`, while Flink/Kafka-oriented transformations live under `local_scripts/streaming/logic_crypto_streaming`.

## How it fits into the full platform

Streaming can provide more recent context than batch ingestion, but the current source coverage is partial. Batch remains the strongest historical path for Binance trades, ETF, macro, and funding. Streaming outputs should be validated before they influence automatic prediction workflows.

Runtime details for Kubernetes/GKE execution belong in [K8s / GKE Runtime](k8s_gke_runtime.md), and orchestration details belong in [Kestra Orchestration](kestra_orchestration.md).

## Main flow

1. Producers emit market, on-chain, and sentiment messages.
2. Kafka/Redpanda-style infrastructure can move messages between producers and processors.
3. Flink-oriented logic transforms raw events into freshness signals.
4. Sink specs prepare selected outputs for BigQuery-like destinations.
5. Downstream dbt and ML paths should consume streaming data only after freshness and completeness are understood.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `local_scripts/streaming/producer` | Streaming producers | Market, on-chain, and sentiment producers. |
| `local_scripts/streaming/producer/binance_full_producer.py` | Market producer | Recent market context. |
| `local_scripts/streaming/producer/onchain_producer.py` | On-chain producer | On-chain context. |
| `local_scripts/streaming/producer/sentiment_producer.py` | Sentiment producer | Sentiment context. |
| `local_scripts/streaming/logic_crypto_streaming/main.py` | Transformation entrypoint | Flink-oriented processing entrypoint. |
| `local_scripts/streaming/logic_crypto_streaming/transformations` | Transformation modules | Order-flow, breakout, liquidation, and related modules. |
| `local_scripts/streaming/scripts` | Sink specs and helpers | Avoid committing secrets or local key files. |
| `local_scripts/streaming/docker-compose.yaml` | Local streaming composition | Local-only support, not a deploy guarantee. |

## Production boundary

Streaming is partial and experimental compared with the batch path. It should not be the sole basis for historical model training coverage or automatic production prediction. Treat sink schemas, source freshness, and dead-letter handling as review points.

## Safety notes

- Do not commit `local_scripts/streaming/producer/.env`, `local_scripts/streaming/secrets`, generated logs, or connector keys.
- Validate topics, connector settings, sink schemas, and freshness before using streaming outputs downstream.
- Do not present the streaming path as complete production coverage.

## Read next

- [Batch Pipeline](batch_pipeline.md)
- [dbt Models](dbt_models.md)
- [Kestra Orchestration](kestra_orchestration.md)
- [K8s / GKE Runtime](k8s_gke_runtime.md)
