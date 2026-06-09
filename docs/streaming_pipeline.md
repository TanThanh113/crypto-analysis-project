# Streaming Pipeline

## What this part does

The streaming pipeline is a lower-latency, freshness-oriented path for market, on-chain, and sentiment signals. It is useful for experiments and future automation, but it is not the trusted full-history path yet.

The project remains an analytics and ML signal platform, <strong>not a trading bot</strong>.

## Where it lives

Streaming files live under `local_scripts/streaming`. Producers are under `local_scripts/streaming/producer`, while Flink/Kafka-oriented transformations live under `local_scripts/streaming/logic_crypto_streaming`.

## How it fits into the full platform

Streaming can provide more recent context than batch ingestion, but the current source coverage is partial. Batch remains the strongest historical path for Binance trades, ETF, macro, and funding. Streaming outputs should be validated before they influence automatic prediction workflows or ML marts.

Runtime details for Kubernetes/GKE execution belong in [K8s / GKE Runtime](k8s_gke_runtime.md), and orchestration details belong in [Kestra Orchestration](kestra_orchestration.md).

<div class="flow-grid">
  <div class="flow-step">
    <strong>Producers</strong>
    <span>Producer scripts emit recent market, on-chain, and sentiment messages for freshness experiments.</span>
  </div>
  <div class="flow-step">
    <strong>Kafka / Redpanda</strong>
    <span>Message infrastructure moves events between producers, transforms, dead-letter paths, and sink logic.</span>
  </div>
  <div class="flow-step">
    <strong>Flink transformations</strong>
    <span>Streaming logic shapes order-flow, breakout, liquidation, and related event signals.</span>
  </div>
  <div class="flow-step">
    <strong>Sink path</strong>
    <span>Sink specs and helpers describe where selected outputs would land; credentials must stay out of docs and commits.</span>
  </div>
  <div class="flow-step">
    <strong>Downstream review</strong>
    <span>dbt and ML should consume streaming context only after freshness, completeness, and schema health are understood.</span>
  </div>
</div>

## Main flow

1. Producers emit market, on-chain, and sentiment messages.
2. Kafka/Redpanda-style infrastructure can move messages between producers and processors.
3. Flink-oriented logic transforms raw events into freshness signals.
4. Sink specs prepare selected outputs for BigQuery-like destinations.
5. Downstream dbt and ML paths should consume streaming data only after freshness and completeness are understood.

## Local-to-cloud streaming runbook

!!! warning "Operational runbook"
    This workflow can start cloud resources and create cost. Run it only when intentionally operating the streaming environment. Do not run these commands during documentation validation.

The local streaming workspace is `local_scripts/streaming`. The local stack uses `local_scripts/streaming/Makefile` and `local_scripts/streaming/docker-compose.yaml`. Grafana infrastructure support lives under `terraform-grafana`. No clearly named Dataproc Terraform folder was found during docs inspection; use the Terraform path that owns your Dataproc resources if it differs from the main infrastructure modules.

### 1. Start cloud streaming infrastructure

From the Terraform module that provisions the streaming Dataproc resources, review the plan and apply only when you intend to create/update cloud infrastructure:

```bash
terraform apply
```

### 2. Start the local streaming stack

Start the local streaming services from the streaming workspace:

```bash
cd local_scripts/streaming
make up
```

Use `http://localhost:8080` to inspect the local streaming UI if the local compose profile exposes the Redpanda/streaming console on that port. If the compose configuration changes, use the UI endpoint exposed by the active local stack.

### 3. Start producers

Start the producer processes:

```bash
make start_bots
```

Open the producer logs in separate terminals as needed:

```bash
make log_binance
make log_onchain
make log_sentiment
```

### 4. Inspect Dataproc/YARN tracking UI

After the local producers and cloud streaming job are stable, inspect the cloud runtime from the GCP Console:

1. Open Cloud Console.
2. Go to Dataproc.
3. Select the cluster.
4. Open the VM or Web interfaces area.
5. Open YARN ResourceManager.
6. Select the relevant application and follow the Tracking URL to inspect the Flink-like job view.

### 5. Bring up Grafana

Provision Grafana support from the actual Grafana Terraform folder:

```bash
cd terraform-grafana
terraform apply
```

Use the output URL if Terraform prints one. In Grafana, choose the correct data source, open the dashboard, and use edit/save if panels need a refresh after the data source is attached.

### 6. Shut down local streaming jobs

Stop producers and clean up the local streaming stack when the run is finished:

```bash
cd local_scripts/streaming
make stop_bots
make down
```

## Key Files And What They Do

### Base path: `local_scripts/streaming`

#### Producers

<div class="file-card-grid">
  <div class="file-card">
    <h4>Producer Area</h4>
    <p><strong>Folder:</strong> <code>producer</code></p>
    <p><strong>Role:</strong> Groups market, on-chain, and sentiment producers for freshness-oriented streaming experiments.</p>
    <p><strong>Why it matters:</strong> This is the entry point for lower-latency context, but it does not replace trusted batch history.</p>
    <p><strong>Review note:</strong> Treat producer `.env` files, connector keys, and source credentials as sensitive.</p>
  </div>
  <div class="file-card">
    <h4>Binance Full Producer</h4>
    <p><strong>File:</strong> <code>producer/binance_full_producer.py</code></p>
    <p><strong>Role:</strong> Emits recent market events for low-latency market context.</p>
    <p><strong>Why it matters:</strong> It helps test streaming freshness and market-signal flow before downstream marts use the output.</p>
    <p><strong>Review note:</strong> Do not treat it as complete historical ML coverage; batch remains the trusted path.</p>
  </div>
  <div class="file-card">
    <h4>On-chain Producer</h4>
    <p><strong>File:</strong> <code>producer/onchain_producer.py</code></p>
    <p><strong>Role:</strong> Emits on-chain context that can complement market data.</p>
    <p><strong>Why it matters:</strong> It provides experimental context for future signal research.</p>
    <p><strong>Review note:</strong> Validate schema and freshness before downstream use.</p>
  </div>
  <div class="file-card">
    <h4>Sentiment Producer</h4>
    <p><strong>File:</strong> <code>producer/sentiment_producer.py</code></p>
    <p><strong>Role:</strong> Emits sentiment context for research and freshness experiments.</p>
    <p><strong>Why it matters:</strong> Sentiment can enrich analysis, but source coverage is partial and noisy.</p>
    <p><strong>Review note:</strong> Keep sentiment clearly marked as experimental unless promoted through validation.</p>
  </div>
</div>

#### Flink-Oriented Transformation Logic

<div class="file-card-grid">
  <div class="file-card">
    <h4>Streaming Entrypoint</h4>
    <p><strong>File:</strong> <code>logic_crypto_streaming/main.py</code></p>
    <p><strong>Role:</strong> Coordinates Flink-oriented processing from incoming events to derived signals.</p>
    <p><strong>Why it matters:</strong> This is the first file to inspect when reviewing how streaming events become transformed outputs.</p>
    <p><strong>Review note:</strong> Inspect source assumptions, topic names, and dead-letter behavior before production use.</p>
  </div>
  <div class="file-card">
    <h4>Transformation Modules</h4>
    <p><strong>Folder:</strong> <code>logic_crypto_streaming/transformations</code></p>
    <p><strong>Role:</strong> Holds order-flow, breakout, liquidation, and related signal transformation modules.</p>
    <p><strong>Why it matters:</strong> This folder contains the actual streaming signal logic reviewers should inspect for schema and freshness assumptions.</p>
    <p><strong>Review note:</strong> Streaming context remains experimental and should not be the sole ML input surface.</p>
  </div>
</div>

#### Sink And Local Support

<div class="file-card-grid">
  <div class="file-card">
    <h4>Sink Specs and Helpers</h4>
    <p><strong>Folder:</strong> <code>scripts</code></p>
    <p><strong>Role:</strong> Describes BigQuery-like sink behavior and local helper scripts.</p>
    <p><strong>Why it matters:</strong> Sink specs determine how streaming outputs would land for later dbt or analytics use.</p>
    <p><strong>Review note:</strong> Never commit connector secrets, key files, or local credentials.</p>
  </div>
  <div class="file-card">
    <h4>Local Streaming Composition</h4>
    <p><strong>File:</strong> <code>docker-compose.yaml</code></p>
    <p><strong>Role:</strong> Supports local streaming experiments.</p>
    <p><strong>Why it matters:</strong> It helps reviewers understand the intended local topology without implying live production readiness.</p>
    <p><strong>Review note:</strong> Do not run Docker as part of docs work; local composition is not a deploy guarantee.</p>
  </div>
</div>

## Production boundary

Streaming is partial and experimental compared with the batch path. It should not be the sole basis for historical model training coverage or automatic production prediction. Treat sink schemas, source freshness, dead-letter handling, and connector identity as review points.

## Safety notes

- Do not commit `local_scripts/streaming/producer/.env`, `local_scripts/streaming/secrets`, generated logs, or connector keys.
- Validate topics, connector settings, sink schemas, and freshness before using streaming outputs downstream.
- Do not present the streaming path as complete production coverage.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../batch_pipeline/">Batch Pipeline</a>
<a class="read-next-card" href="../dbt_models/">dbt Models</a>
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
</div>
</div>
