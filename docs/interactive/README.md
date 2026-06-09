# Interactive Project Explorer

This folder contains a static documentation page for recruiters and reviewers:

- `index.html` is the entrypoint.
- `styles.css` contains the light portfolio-style layout.
- `app.js` renders tabs, cards, flows, warnings, links, and graceful diagram fallbacks.
- `project_map.json` is the curated project map used by the explorer.
- `architecture_map.json` is the curated data source for the interactive architecture map on the Overview tab.
- `understand_anything/` is the reviewed/published graph asset folder for the optional AI Codebase Map tab.

## Interactive Architecture Map

The Overview tab renders a curated, pipeline-oriented architecture map from `architecture_map.json`.
It uses plain HTML, CSS, and JavaScript:

- no backend
- no npm install
- no build step
- no graph library, canvas, framework, or CDN
- no ingestion, training, backfill, deploy, GCS write, BigQuery write, or registry action

The map is organized as a guided platform pipeline:

- `Sources`
- `Ingestion`
- `Storage`
- `Transform`
- `ML / Outputs`
- `Monitoring / Dashboard`

The primary row shows the trusted batch path from external sources through validation, storage, dbt, ML, monitoring, and dashboards. A second row shows the streaming branch through producers, Kafka/Redpanda, Flink, dead-letter handling, BigQuery, dbt, and monitoring. A separate control plane rail shows Kestra, GKE, Artifact Registry, Workload Identity, Terraform, and CI/CD gates.

Flow filters highlight related paths for Batch, Streaming, dbt, ML/MLOps, and Infra/Runtime. Clicking a node opens a sticky detail panel with what it does, where it lives, why it matters, production/research boundaries, docs links, GitHub source path pills, upstream nodes, downstream nodes, and connected flow context.

The left Project Explorer sidebar has a desktop collapse/expand toggle and remembers its state in local storage when available. The pipeline canvas uses short node titles and compact summaries; full explanations stay in the detail panel. The detail panel can also be hidden from the map controls when reviewers want maximum canvas width.

## AI Codebase Map

The AI Codebase Map is a secondary deep-dive layer generated from Understand-Anything when a reviewed graph asset is available. The curated architecture map remains the primary visual guide and source of truth.

The static viewer looks for graph assets in this order:

- `docs/interactive/understand_anything/knowledge-graph.public.json`
- `docs/interactive/understand_anything/knowledge-graph.json`

To regenerate and publish a safe graph asset:

1. Run `/understand --language en` in an environment where Understand-Anything is available.
2. Review `.understand-anything/knowledge-graph.json` for secrets, local absolute paths, oversized source detail, Terraform state, `.tfvars`, `.env`, service account keys, and other sensitive data.
3. Copy the safe graph or a reduced sanitized graph into `docs/interactive/understand_anything/`.
4. Prefer `knowledge-graph.public.json` for reduced output.
5. Run `mkdocs build --strict`.

Do not commit `.understand-anything/intermediate/`, `.understand-anything/diff-overlay.json`, unreviewed local cache, or secrets.

## Reference Assets

The draw.io files are compact reference assets only. They are not embedded as the primary UI:

- `docs/interactive/reference/architecture-main.drawio`
- `docs/interactive/reference/architecture-main.drawio.svg`

The current SVG export in this worktree is named `architecture-main.drawio.svg`; there is no separate `architecture-main.svg` file at this time. The UI keeps these links plus `architecture_map.json` in a small collapsible `Reference assets and data source` section after the pipeline.

## MkDocs Preview

After the MkDocs migration, Markdown docs are rendered as clean routes.
Open docs routes like:

- `/docs/`
- `/docs/architecture/`
- `/docs/repository_map/`

Do not open Markdown source routes on GitHub Pages:

- `/docs/architecture.md`
- `/docs/repository_map.md`

Preview the MkDocs site locally:

```bash
cd /home/thanh/crypto-analysis-project
mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000/
```

## Full Pages Artifact Preview

Build the same `/docs/` artifact shape used by GitHub Pages:

```bash
cd /home/thanh/crypto-analysis-project
mkdocs build --strict
python3 -m http.server 8000 --directory site
```

Then open:

```text
http://localhost:8000/docs/
http://localhost:8000/docs/interactive/
```

This mode enables:

- clean MkDocs docs links
- `project_map.json`
- GitHub source links for code and folder path pills

## Direct UI-Only Preview

```bash
cd /home/thanh/crypto-analysis-project
python3 -m http.server 8000 --directory docs/interactive
```

Then open:

```text
http://localhost:8000/
```

Direct mode only serves the `docs/interactive` folder. `project_map.json` works locally. Clean MkDocs docs links point to routes such as `../architecture/`, so use the MkDocs preview or full Pages artifact preview for route-accurate link testing. Source and folder path pills use GitHub links when configured.

Open directly from the filesystem:

```bash
/home/thanh/crypto-analysis-project/docs/interactive/index.html
```

No backend, npm install, build step, training run, backfill, deploy, GCS write, BigQuery write, or registry update is required.

Some browsers block `fetch("project_map.json")` for pages opened through `file://`. The app includes the same curated data as a bundled fallback so the page still works when opened directly. If served through any static file server, it will load `project_map.json`.

The page complements:

- `README.md`
- `docs/architecture.md`
- `docs/repository_map.md`
- `docs/batch_pipeline.md`
- `docs/streaming_pipeline.md`
- `docs/dbt_models.md`
- `docs/ml_mLOps.md`
- `docs/kestra_orchestration.md`
- `docs/k8s_gke_runtime.md`
- `docs/terraform_infrastructure.md`
- `docs/ci_cd_gates.md`
- `docs/production_boundaries.md`
- `docs/codebase_knowledge_graph.md`

## Published GitHub Pages Layout

When deployed by the GitHub Pages workflow:

- `/` opens the root project documentation landing page.
- `/docs/` opens the MkDocs-rendered documentation site.
- `/docs/interactive/` opens this static interactive explorer.
- `/dbt/` opens generated dbt documentation.

Understand-Anything is optional and not required for project operation. The AI Codebase Map tab parses only a reviewed/published static docs asset when available.
