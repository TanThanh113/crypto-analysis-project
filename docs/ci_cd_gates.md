# CI/CD and Deployment Gates

## What this part does

CI/CD uses GitHub Actions and helper scripts to run quality checks, plan deploy work, gate Docker builds, gate Kestra deployment, publish docs, and aggregate required PR status. The goal is to keep docs-only changes lightweight while still protecting runtime paths.

## Where it lives

CI/CD files live under `.github/workflows` and `.github/scripts`. Repository guard logic lives under `scripts`.

## How it fits into the full platform

CI/CD sits between code changes and runtime work. It should validate code and docs, but it should not force cloud/runtime actions when a PR only changes documentation. Docker, Kestra, and deployment work are gated so reviewers can see why a path ran or skipped.

<div class="flow-grid">
  <div class="flow-step">
    <strong>Repo guard</strong>
    <span>`scripts/repo_guard.py` checks production repository conventions before runtime changes move forward.</span>
  </div>
  <div class="flow-step">
    <strong>Diff and tests</strong>
    <span>Static checks, targeted tests, and diff hygiene catch regressions without triggering unnecessary cloud work.</span>
  </div>
  <div class="flow-step">
    <strong>Docker build gates</strong>
    <span>Image builds and pushes run only when relevant runtime files or deployable flows require them.</span>
  </div>
  <div class="flow-step">
    <strong>Kestra deploy gates</strong>
    <span>Deploy planning decides which flow groups are allowed to deploy and prevents accidental production triggers.</span>
  </div>
  <div class="flow-step">
    <strong>PR required gate</strong>
    <span>Aggregates required status so reviewers can see whether the change is safe to merge.</span>
  </div>
  <div class="flow-step">
    <strong>Pages docs deploy</strong>
    <span>Builds MkDocs, keeps `/docs/interactive/` static, and publishes generated dbt docs under `/dbt/`.</span>
  </div>
</div>

## Main flow

1. Quality checks run repository guard and static/test validations.
2. Deploy planning determines whether Docker images or Kestra flows need runtime work.
3. Docker build/push runs only when relevant files or deployable flows require it.
4. Kestra deploy runs only when the deploy plan allows selected flow groups.
5. Required-gate workflow aggregates status for PR review.
6. Cleanup workflows remove preview flows/images when appropriate.

## Key Files And What They Do

### Base path: `.github/workflows`

<div class="file-card-grid">
  <div class="file-card">
    <h4>Quality Check Workflow</h4>
    <p><strong>File:</strong> <code>quality-check.yml</code></p>
    <p><strong>Role:</strong> Runs tests, repo guard, and static checks.</p>
    <p><strong>Why it matters:</strong> This is the first place to inspect baseline safety and regression coverage.</p>
    <p><strong>Review note:</strong> Docs-only work should stay lightweight and avoid unnecessary runtime work.</p>
  </div>
  <div class="file-card">
    <h4>Docker Build Gate</h4>
    <p><strong>File:</strong> <code>docker-build-push.yml</code></p>
    <p><strong>Role:</strong> Builds and pushes images when relevant runtime files or deployable flows require it.</p>
    <p><strong>Why it matters:</strong> It protects <strong>Artifact Registry</strong> from unnecessary image writes.</p>
    <p><strong>Review note:</strong> Docker build/push should remain gated by real runtime relevance.</p>
  </div>
  <div class="file-card">
    <h4>Kestra Deploy Gate</h4>
    <p><strong>File:</strong> <code>kestra-deploy-gke.yml</code></p>
    <p><strong>Role:</strong> Deploys selected GKE flows when deploy planning allows the flow group.</p>
    <p><strong>Why it matters:</strong> It prevents accidental deployment of orchestration changes.</p>
    <p><strong>Review note:</strong> Do not deploy just to make checks green.</p>
  </div>
  <div class="file-card">
    <h4>Required PR Gate</h4>
    <p><strong>File:</strong> <code>pr-required-gate.yml</code></p>
    <p><strong>Role:</strong> Aggregates required status for PR review.</p>
    <p><strong>Why it matters:</strong> A PR should not appear safe simply because an optional path skipped.</p>
    <p><strong>Review note:</strong> Keep required-gate semantics clear and conservative.</p>
  </div>
  <div class="file-card">
    <h4>Pages Documentation Deploy</h4>
    <p><strong>File:</strong> <code>deploy-dbt-docs.yml</code></p>
    <p><strong>Role:</strong> Builds MkDocs under <code>/docs/</code>, keeps the static explorer under <code>/docs/interactive/</code>, and publishes generated dbt docs under <code>/dbt/</code>.</p>
    <p><strong>Why it matters:</strong> It gives reviewers one published documentation hub without requiring local setup.</p>
    <p><strong>Review note:</strong> This workflow may generate dbt docs in CI; do not run dbt docs generate locally for this polish task.</p>
  </div>
  <div class="file-card">
    <h4>Cleanup Workflows</h4>
    <p><strong>Files:</strong> <code>cleanup-kestra-preview-flows.yml</code>, <code>cleanup-pr-preview-images.yml</code></p>
    <p><strong>Role:</strong> Remove preview flows and preview images after PR work.</p>
    <p><strong>Why it matters:</strong> Cleanup reduces leftover operational artifacts and registry clutter.</p>
    <p><strong>Review note:</strong> Cleanup should target preview resources, not production assets.</p>
  </div>
</div>

### Base path: `.github/scripts` and `scripts`

<div class="file-card-grid">
  <div class="file-card">
    <h4>Kestra Deploy Plan Helper</h4>
    <p><strong>File:</strong> <code>.github/scripts/kestra_deploy_plan.py</code></p>
    <p><strong>Role:</strong> Computes deploy/build gating outputs.</p>
    <p><strong>Why it matters:</strong> It lets docs-only changes stay docs-only while runtime changes get the right gates.</p>
    <p><strong>Review note:</strong> Gating changes affect deployment behavior and should be reviewed carefully.</p>
  </div>
  <div class="file-card">
    <h4>Kestra Flow Deploy Helper</h4>
    <p><strong>File:</strong> <code>.github/scripts/deploy_kestra_flows.py</code></p>
    <p><strong>Role:</strong> Deploys selected Kestra flows from CI when gates allow it.</p>
    <p><strong>Why it matters:</strong> It is the operational bridge from CI decision to flow deployment.</p>
    <p><strong>Review note:</strong> Do not loosen this path just to make a check green.</p>
  </div>
  <div class="file-card">
    <h4>Repository Guard</h4>
    <p><strong>File:</strong> <code>scripts/repo_guard.py</code></p>
    <p><strong>Role:</strong> Protects production repository behavior and catches unsafe deploy/runtime patterns.</p>
    <p><strong>Why it matters:</strong> It gives reviewers a quick signal that production guardrails still hold.</p>
    <p><strong>Review note:</strong> Keep safety checks intact.</p>
  </div>
</div>

## Production boundary

CI/CD can trigger expensive or operational actions, so deploy gates must remain explicit. Docs-only PRs should not require training, backfills, Docker builds, deploys, Registry writes, GCS writes, or BigQuery writes.

## Safety notes

- Do not loosen gates just to make a check green.
- Do not expose secrets, tokens, keys, or service account JSON in workflow logs or docs.
- Docker and Kestra deploy workflows should remain gated by actual runtime relevance.
- Terraform apply, training, backfill, and deploy actions are out of scope for docs-only work.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../terraform_infrastructure/">Terraform Infrastructure</a>
<a class="read-next-card" href="../repository_map/">Repository Map</a>
</div>
</div>
