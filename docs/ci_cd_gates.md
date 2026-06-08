# CI/CD and Deployment Gates

## What this part does

CI/CD uses GitHub Actions and helper scripts to run quality checks, plan deploy work, gate Docker builds, gate Kestra deployment, and aggregate required PR status. The goal is to keep docs-only changes lightweight while still protecting runtime paths.

## Where it lives

CI/CD files live under `.github/workflows` and `.github/scripts`. Repository guard logic lives under `scripts`.

## How it fits into the full platform

CI/CD sits between code changes and runtime work. It should validate code and docs, but it should not force cloud/runtime actions when a PR only changes documentation. Docker, Kestra, and deployment work are gated so reviewers can see why a path ran or skipped.

## Main flow

1. Quality checks run repository guard and static/test validations.
2. Deploy planning determines whether Docker images or Kestra flows need runtime work.
3. Docker build/push runs only when relevant files or deployable flows require it.
4. Kestra deploy runs only when the deploy plan allows selected flow groups.
5. Required-gate workflow aggregates status for PR review.
6. Cleanup workflows remove preview flows/images when appropriate.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `.github/workflows/quality-check.yml` | Quality workflow | Tests, repo guard, and static checks. |
| `.github/workflows/docker-build-push.yml` | Docker build gate | Gated image build and smoke workflow. |
| `.github/workflows/kestra-deploy-gke.yml` | Kestra deploy gate | Deploys selected GKE flows when plan allows it. |
| `.github/workflows/pr-required-gate.yml` | Required PR gate | Aggregates required status. |
| `.github/workflows/cleanup-kestra-preview-flows.yml` | Preview flow cleanup | Removes preview flow artifacts. |
| `.github/workflows/cleanup-pr-preview-images.yml` | Preview image cleanup | Removes preview images. |
| `.github/scripts/kestra_deploy_plan.py` | Deploy plan helper | Computes deploy/build gating outputs. |
| `.github/scripts/deploy_kestra_flows.py` | Flow deploy helper | Deploys selected flows from CI. |
| `scripts/repo_guard.py` | Repository guard | Safety checks for production repository behavior. |

## Production boundary

CI/CD can trigger expensive or operational actions, so deploy gates must remain explicit. Docs-only PRs should not require training, backfills, Docker builds, deploys, Registry writes, GCS writes, or BigQuery writes.

## Safety notes

- Do not loosen gates just to make a check green.
- Do not expose secrets, tokens, keys, or service account JSON in workflow logs or docs.
- Docker and Kestra deploy workflows should remain gated by actual runtime relevance.
- Terraform apply, training, backfill, and deploy actions are out of scope for docs-only work.

## Read next

- [K8s / GKE Runtime](k8s_gke_runtime.md)
- [Kestra Orchestration](kestra_orchestration.md)
- [Terraform Infrastructure](terraform_infrastructure.md)
- [Repository Map](repository_map.md)
