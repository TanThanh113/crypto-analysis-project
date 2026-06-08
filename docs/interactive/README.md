# Interactive Project Explorer

This folder contains a static documentation page for recruiters and reviewers:

- `index.html` is the entrypoint.
- `styles.css` contains the light portfolio-style layout.
- `app.js` renders tabs, cards, flows, warnings, links, and graceful diagram fallbacks.
- `project_map.json` is the curated project map used by the explorer.

Open directly in a browser:

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

Understand-Anything is documented only as an optional future exploration layer. This phase does not parse `.understand-anything/knowledge-graph.json`.
