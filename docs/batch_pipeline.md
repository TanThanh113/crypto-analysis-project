# Batch Pipeline

!!! note "Coverage boundary"
    Reliable 5-year backfill is strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources remain partial, experimental, or not fully live-ready.

## What this part does

The batch pipeline is the most mature historical data path in the project. It collects trusted sources, supports selected backfills, validates outputs, and prepares data for dbt models, dashboards, monitoring, and ML datasets.

This is <strong>not a trading bot</strong>. Batch data supports analytics and ML signal research. The strongest reliable 5-year coverage currently comes from Binance trades, ETF, macro, and funding sources.

## Where it lives

Batch code lives mainly under `local_scripts/batch`, with validation rules, quality audit specs, monitoring utilities, and backfill scripts grouped into subfolders.

## How it fits into the full platform

Batch ingestion feeds the storage and warehouse layers that dbt transforms into marts. Those marts later support dashboards, monitoring, and ML training/prediction inputs. The trusted 5-year <strong>backfill</strong> coverage is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources remain partial, experimental, or not fully live-ready.

<div class="flow-grid">
  <div class="flow-step">
    <strong>Main collectors</strong>
    <span>Collectors gather source-specific data and prepare it for warehouse or storage landing.</span>
  </div>
  <div class="flow-step">
    <strong>Backfill scripts</strong>
    <span>Historical loaders fill selected windows and must be run intentionally because they can produce large cloud writes.</span>
  </div>
  <div class="flow-step">
    <strong>Validation rules</strong>
    <span>Rule sets check schema, freshness, and expected value constraints before data is trusted downstream.</span>
  </div>
  <div class="flow-step">
    <strong>Quality audit specs</strong>
    <span>Dashboard, ML, and freshness checks make data-health expectations visible to reviewers.</span>
  </div>
  <div class="flow-step">
    <strong>Iceberg / BigLake path</strong>
    <span>Lakehouse-oriented loading support is useful for curated storage workflows and needs careful destination config.</span>
  </div>
</div>

## Main flow

1. Main collectors gather source data for market, ETF, macro, funding, and other source areas.
2. Backfill scripts load selected historical windows when explicitly requested.
3. Validation rules and quality specs check schema, freshness, and expected values.
4. Curated data is prepared for storage/warehouse use.
5. dbt models transform data into analytics and ML marts.
6. Monitoring and quality audit paths help reviewers understand data health.

## Key Files And What They Do

### Base path: `local_scripts/batch`

#### Main Collectors

<div class="file-card-grid">
  <div class="file-card">
    <h4>Batch Collector Area</h4>
    <p><strong>Folder:</strong> <code>.</code></p>
    <p><strong>Role:</strong> Groups trusted and experimental batch collectors that prepare source data for warehouse, storage, dbt, and ML workflows.</p>
    <p><strong>Why it matters:</strong> This is the mature historical ingestion surface, so reviewers can separate strongest coverage from partial source experiments.</p>
    <p><strong>Review note:</strong> Check destination config before running collectors because some paths can create <strong>cloud writes</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Binance Trade Collector</h4>
    <p><strong>File:</strong> <code>binance_trade_collector.py</code></p>
    <p><strong>Role:</strong> Collects Binance trade data for core market history.</p>
    <p><strong>Why it matters:</strong> This is one of the strongest historical coverage sources and feeds downstream <strong>dbt marts</strong>.</p>
    <p><strong>Review note:</strong> Treat historical collection and destination writes carefully; this is not something to run casually.</p>
  </div>
  <div class="file-card">
    <h4>Funding Basis Collector</h4>
    <p><strong>File:</strong> <code>funding_basis_collector.py</code></p>
    <p><strong>Role:</strong> Collects funding and basis context for derivatives-aware analytics.</p>
    <p><strong>Why it matters:</strong> Funding is part of the strongest reliable coverage and can explain market regime behavior beyond spot trades.</p>
    <p><strong>Review note:</strong> Validate freshness and schema expectations before using it in ML features.</p>
  </div>
</div>

#### ETF and Macro Collectors

<div class="file-card-grid">
  <div class="file-card">
    <h4>ETF Flows Collector</h4>
    <p><strong>File:</strong> <code>alpha_vantage_option/etf_flows_collector.py</code></p>
    <p><strong>Role:</strong> Collects ETF flow indicators that add broader market context.</p>
    <p><strong>Why it matters:</strong> ETF data is part of the strongest reliable coverage and can be aligned with crypto analytics windows.</p>
    <p><strong>Review note:</strong> Source freshness and API behavior should be reviewed before treating it as live-ready.</p>
  </div>
  <div class="file-card">
    <h4>Macro Extractor</h4>
    <p><strong>File:</strong> <code>alpha_vantage_option/macro_extractor.py</code></p>
    <p><strong>Role:</strong> Collects macro indicators used as external market regime context.</p>
    <p><strong>Why it matters:</strong> Macro is one of the strongest reliable backfill sources and helps explain risk-on/risk-off regimes.</p>
    <p><strong>Review note:</strong> Macro cadence differs from crypto trades, so timestamp alignment belongs in dbt review.</p>
  </div>
</div>

#### Backfill Scripts

<div class="file-card-grid">
  <div class="file-card">
    <h4>Historical Backfill Loaders</h4>
    <p><strong>Folder:</strong> <code>backfill</code></p>
    <p><strong>Role:</strong> Loads selected historical windows for trusted sources when explicitly requested.</p>
    <p><strong>Why it matters:</strong> Backfills make 5-year coverage possible for Binance trades, ETF, Macro, and Funding.</p>
    <p><strong>Review note:</strong> Backfills can generate large <strong>cloud writes</strong> to <strong>GCS</strong> or <strong>BigQuery</strong>; do not run them casually.</p>
  </div>
</div>

#### Validation Rules and Quality Audit

<div class="file-card-grid">
  <div class="file-card">
    <h4>Validation Engine</h4>
    <p><strong>Folder:</strong> <code>validation</code></p>
    <p><strong>Role:</strong> Converts source expectations into repeatable schema, freshness, and value checks.</p>
    <p><strong>Why it matters:</strong> It catches broken source assumptions before dbt and ML consume bad data.</p>
    <p><strong>Review note:</strong> Rule changes should match source behavior, not just silence failing checks.</p>
  </div>
  <div class="file-card">
    <h4>Validation Rulesets</h4>
    <p><strong>Folder:</strong> <code>validation/rulesets</code></p>
    <p><strong>Role:</strong> Stores source-specific YAML rules for expected data shape and freshness.</p>
    <p><strong>Why it matters:</strong> Reviewers can see what makes each source acceptable before it reaches marts.</p>
    <p><strong>Review note:</strong> Keep rules precise enough to catch regressions without hiding real source gaps.</p>
  </div>
  <div class="file-card">
    <h4>Quality Audit Specs</h4>
    <p><strong>Folder:</strong> <code>quality_audit/specs</code></p>
    <p><strong>Role:</strong> Documents dashboard, ML, and freshness checks for data-health review.</p>
    <p><strong>Why it matters:</strong> These specs make pipeline health visible before issues become model inputs.</p>
    <p><strong>Review note:</strong> Failed quality expectations should trigger investigation, not blind bypasses.</p>
  </div>
</div>

#### Iceberg / BigLake Path

<div class="file-card-grid">
  <div class="file-card">
    <h4>Iceberg Loader</h4>
    <p><strong>File:</strong> <code>iceberg_loader.py</code></p>
    <p><strong>Role:</strong> Supports curated lakehouse-oriented loading for <strong>GCS / BigLake / Iceberg</strong> workflows.</p>
    <p><strong>Why it matters:</strong> It provides an alternate storage path for curated data beyond simple local output.</p>
    <p><strong>Review note:</strong> Confirm destination, partitioning, and write behavior before running cloud-connected loaders.</p>
  </div>
</div>

## Production boundary

Batch ingestion is the strongest source path, but it is not automatically safe to run in every environment. Backfills and loaders can write to GCS or BigQuery when configured. Partial sources such as options, liquidation, stablecoin, exchange reserves, and sentiment should not be presented as equally reliable.

## Operational handoff

Batch jobs are commonly orchestrated through Kestra in the GKE-oriented runtime. For the operator-facing cloud workflow, see the [Batch and Kestra on GKE runbook](kestra_orchestration.md#batch-and-kestra-on-gke-runbook). That runbook covers infrastructure provisioning, cloud secrets, Kubernetes/Helm access, Kestra secret sync, pod health checks, and opening the Kestra webserver locally.

## Safety notes

- Do not run backfills casually.
- Do not commit `local_scripts/batch/.env`, service account keys, local output data, logs, or generated caches.
- Review cost and destination configuration before running cloud-connected loaders.
- Documentation updates should not trigger GCS, BigQuery, or Registry writes.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../architecture/">Architecture</a>
<a class="read-next-card" href="../dbt_models/">dbt Models</a>
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
</div>
</div>
