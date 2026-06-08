# Interactive Project Explorer

This folder contains a static documentation page for recruiters and reviewers:

- `index.html` is the entrypoint.
- `styles.css` contains the light portfolio-style layout.
- `app.js` renders tabs, cards, flows, warnings, links, and graceful diagram fallbacks.
- `project_map.json` is the curated project map used by the explorer.

## Full Local Preview

```bash
cd /home/thanh/crypto-analysis-project
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/docs/interactive/
```

This serves the repository root, so parent links such as `../../README.md`, `../architecture.md`, and `../repository_map.md` work locally.

This mode enables:

- local README/docs links
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

Direct mode only serves the `docs/interactive` folder. `project_map.json` works locally. Parent README/docs links in the hero may be disabled, while card path pills can use GitHub links when configured. Full local README/docs links require repo-root mode.

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

Understand-Anything is documented only as an optional future exploration layer. This phase does not parse `.understand-anything/knowledge-graph.json`.
