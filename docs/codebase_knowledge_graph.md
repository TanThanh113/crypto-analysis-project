# Optional AI Codebase Map

## What this part does

This document explains the optional AI codebase map idea. Understand-Anything is not required to run, review, or understand this project. The primary documentation remains the README, architecture docs, repository map, and static interactive explorer.

## Where it lives

The current static explorer lives under `docs/interactive`. A future generated knowledge graph may live under `.understand-anything/knowledge-graph.json` if the user generates it, but that file may not exist in the repository today.

## How it fits into the full platform

The optional codebase map would be an exploration layer on top of the documentation, not a runtime dependency. It should not affect ingestion, dbt, Kestra, Terraform, Docker, CI/CD, or ML behavior.

## Main flow

1. Read the normal documentation first.
2. Open `docs/interactive/index.html` for the curated static explorer.
3. Optionally generate an Understand-Anything graph in an environment where that tool is available.
4. Use the optional dashboard for exploration only.
5. Keep the static docs as the canonical reviewer-facing documentation.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `docs/interactive/index.html` | Static explorer | No backend or build step required. |
| `docs/interactive/project_map.json` | Curated project map | Human-curated documentation data. |
| `README.md` | Primary overview | Start here before generated maps. |
| `docs/architecture.md` | Architecture reference | Canonical platform overview. |
| `docs/repository_map.md` | Repository map | Canonical folder-by-folder guide. |

## Production boundary

Understand-Anything is optional and not part of the runtime, training, prediction, deployment, or infrastructure workflow. Do not require it for normal project operation.

## Safety notes

- Do not put secrets, local credentials, generated artifacts, or sensitive state into codebase-map outputs.
- Do not treat generated maps as a substitute for curated docs.
- Do not implement a parser for `.understand-anything/knowledge-graph.json` in this phase.

## Read next

- [Architecture](architecture.md)
- [Repository Map](repository_map.md)
- [Interactive Explorer README](interactive/README.md)
