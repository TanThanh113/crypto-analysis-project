# Optional AI Codebase Map

## What this part does

This document explains the optional AI codebase map integration. Understand-Anything is not required to run, review, or understand this project. The primary documentation remains the README, architecture docs, repository map, MkDocs site, static diagrams where available, and the curated pipeline-oriented interactive explorer.

## Where it lives

The current static explorer lives under `docs/interactive`. Understand-Anything can generate local output at `.understand-anything/knowledge-graph.json`. When that output is reviewed and safe to publish, the docs site can expose a sanitized or reduced copy under `docs/interactive/understand_anything/`.

## How it fits into the full platform

The optional codebase map is an exploration layer on top of the documentation, not a runtime dependency. It should not affect ingestion, dbt, Kestra, Terraform, Docker, CI/CD, or ML behavior.

Use Understand-Anything only after the reviewer understands the curated architecture flow. It can help with AI-assisted codebase exploration, but it does not replace the README, MkDocs docs, interactive architecture map, production architecture notes, or repository map. The [AI Codebase Map tab](../interactive/#ai-codebase-map) loads the published graph asset when available and otherwise shows the exact next step.

<div class="note-card-grid">
  <div class="note-card">
    <strong>AI-assisted orientation</strong>
    <span>A generated codebase map can help a reviewer ask better questions, search files/layers/domains, and jump between related paths faster.</span>
  </div>
  <div class="note-card">
    <strong>Not source of truth</strong>
    <span>Generated graphs can be stale or incomplete. The README, MkDocs pages, static diagrams, and curated explorer remain canonical.</span>
  </div>
  <div class="note-card">
    <strong>No runtime dependency</strong>
    <span>The project does not require Understand-Anything for ingestion, dbt, ML, Kestra, Terraform, Docker, CI/CD, or deployment.</span>
  </div>
</div>

## Main flow

1. Read the normal documentation first.
2. Open `docs/interactive/index.html` for the curated static explorer and its `architecture_map.json`-backed architecture map.
3. Optionally generate `.understand-anything/knowledge-graph.json` in an environment where Understand-Anything is available.
4. Review the generated graph for secrets, local paths, and oversized code detail.
5. Publish a safe graph asset under `docs/interactive/understand_anything/`.
6. Use the AI Codebase Map tab as a secondary deep-dive only.
7. Keep the static docs as the canonical reviewer-facing documentation.

## Optional commands

These commands are optional and are not required for the docs site:

```text
/understand --language en
/understand-dashboard
```

No generated `.understand-anything` artifact is required to run this project or build the documentation. Do not commit generated local cache or large graph output unless it has been intentionally reviewed.

## Key Files And What They Do

<div class="file-card-grid">
  <div class="file-card">
    <h4>Static Explorer</h4>
    <p><strong>Path:</strong> <code>docs/interactive/index.html</code></p>
    <p><strong>Role:</strong> Curated visual map with no backend or build step.</p>
    <p><strong>Why it matters:</strong> Gives reviewers a stable exploration layer without generated graph dependency.</p>
    <p><strong>Review note:</strong> This remains primary reviewer-facing documentation.</p>
  </div>
  <div class="file-card">
    <h4>Curated Project Map</h4>
    <p><strong>Path:</strong> <code>docs/interactive/project_map.json</code></p>
    <p><strong>Role:</strong> Human-curated data used by the static explorer.</p>
    <p><strong>Why it matters:</strong> It stays readable even if no generated knowledge graph exists.</p>
    <p><strong>Review note:</strong> Do not put secrets or generated sensitive state into documentation data.</p>
  </div>
  <div class="file-card">
    <h4>Curated Architecture Map</h4>
    <p><strong>Path:</strong> <code>docs/interactive/architecture_map.json</code></p>
    <p><strong>Role:</strong> Human-curated node, edge, flow, and limitation data for the interactive architecture map.</p>
    <p><strong>Why it matters:</strong> It gives reviewers a stable architecture layer without requiring Understand-Anything output.</p>
    <p><strong>Review note:</strong> Treat generated AI maps as optional exploration, not as a replacement for this curated map.</p>
  </div>
  <div class="file-card">
    <h4>Canonical Docs</h4>
    <p><strong>Paths:</strong> <code>README.md</code>, <code>docs/architecture.md</code>, <code>docs/repository_map.md</code></p>
    <p><strong>Role:</strong> Primary overview, architecture reference, and folder-by-folder guide.</p>
    <p><strong>Why it matters:</strong> These documents are the source of truth for reviewer orientation.</p>
    <p><strong>Review note:</strong> Generated maps should not replace curated docs.</p>
  </div>
  <div class="file-card">
    <h4>Optional Future Graph</h4>
    <p><strong>Path:</strong> <code>.understand-anything/knowledge-graph.json</code></p>
    <p><strong>Role:</strong> Optional generated graph if the user runs Understand-Anything locally.</p>
    <p><strong>Why it matters:</strong> Can help AI-assisted codebase exploration and quick orientation.</p>
    <p><strong>Review note:</strong> Do not commit raw cache blindly; review for secrets, local paths, and size first.</p>
  </div>
  <div class="file-card">
    <h4>Published Graph Asset</h4>
    <p><strong>Path:</strong> <code>docs/interactive/understand_anything/</code></p>
    <p><strong>Role:</strong> Holds the reviewed docs asset loaded by the AI Codebase Map tab when available.</p>
    <p><strong>Why it matters:</strong> Lets the static docs site expose a safe graph without requiring Understand-Anything at runtime.</p>
    <p><strong>Review note:</strong> Prefer <code>knowledge-graph.public.json</code> for reduced/sanitized output.</p>
  </div>
  <div class="file-card">
    <h4>AI Codebase Map Tab</h4>
    <p><strong>Path:</strong> <code>docs/interactive/#ai-codebase-map</code></p>
    <p><strong>Role:</strong> Static viewer for published nodes, edges, filters, search, and node detail.</p>
    <p><strong>Why it matters:</strong> Gives technical reviewers a deeper exploration layer after the curated architecture map.</p>
    <p><strong>Review note:</strong> Generated graph content is secondary; curated docs remain the source of truth.</p>
  </div>
</div>

## Production boundary

Understand-Anything is optional and not part of the runtime, training, prediction, deployment, or infrastructure workflow. The published docs asset is static and reviewed; it does not run ingestion, dbt, ML, Kestra, Terraform, Docker, CI/CD, or cloud writes.

## Safety notes

- Do not put secrets, local credentials, generated artifacts, or sensitive state into codebase-map outputs.
- Do not treat generated maps as a substitute for curated docs.
- Review generated graph output before publishing it under `docs/interactive/understand_anything/`.
- Do not commit `.understand-anything/intermediate/`, `.understand-anything/diff-overlay.json`, `.env`, service account keys, local paths, Terraform state, or `.tfvars`.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../architecture/">Architecture</a>
<a class="read-next-card" href="../repository_map/">Repository Map</a>
<a class="read-next-card" href="../interactive/">Interactive Project Explorer</a>
</div>
</div>
