# Post-Mortem: Crypto API Ingestion Failure & Data Freshness Lag

**Date of Incident:** 2026-05-28  
**Authors:** Lê Tấn Thành  
**Status:** Resolved  
**Severity:** SEV-2 (Critical Data Delay)

---

## 1. Summary
A sudden breaking change in the upstream Crypto Exchange API's JSON response payload caused the raw data ingestion pods to fail continuously. This resulted in a 4-hour data lag across the downstream analytics pipeline. The incident was detected by the automated Pipeline Health Check workflow, which triggered a Slack alert and updated the Looker Studio Production Dashboard to a `CRITICAL / STALE` status.

The issue was mitigated by patching the Python parsing logic, validating the fix in an isolated PR preview namespace via our `PR Required Gate`, and executing a historical backfill in Kestra to recover the missing hours.

## 2. Impact
- **Data Latency:** Downstream dbt marts (`dbt_quants_dev`) were stale for exactly 4 hours and 15 minutes.
- **ML Models:** The intraday price prediction model skipped 4 scheduled training loops due to missing raw data dependencies.
- **User Facing:** No direct user outage, but internal quantitative dashboards reported outdated metrics.

## 3. Timeline (UTC+7)
- **08:00 AM:** Upstream Crypto API deploys an unannounced update, wrapping the `volume_24h` metric inside a nested `metrics` object instead of the root level.
- **08:15 AM:** Kestra orchestrator triggers the scheduled `crypto_batch_ingestion` flow.
- **08:17 AM:** GKE extraction pod throws a `KeyError: 'volume_24h'` and crashes. Kubernetes attempts to restart the pod, eventually entering `CrashLoopBackOff` state.
- **09:00 AM - 11:00 AM:** Subsequent hourly Kestra schedules fail silently at the extraction phase.
- **12:15 PM:** The scheduled `pipeline_health_check` flow executes the dbt source freshness tests.
- **12:16 PM:** **[Detection]** BigQuery logs the failure. Slack Webhook fires a red alert: `CRITICAL: dbt_quants_dev.mart_dashboard_data_freshness is STALE (>4 hours lag)`. Looker Studio KPI cards turn red.
- **12:20 PM:** **[Triage]** Engineer acknowledges the Slack alert. Queries the `mart_monitoring_pipeline_failed_checks` table in Looker Studio and identifies the ingestion layer failure. GKE pod logs reveal the `KeyError`.
- **12:45 PM:** **[Resolution]** Python ingestion script is patched to handle the nested JSON structure safely using `.get('metrics', {}).get('volume_24h')`.
- **12:50 PM:** Pull Request is opened. The `PR Required Gate` dynamically triggers a Docker Build and deploys a preview flow (`crypto.preview.pr_14`) to the isolated GKE namespace.
- **01:00 PM:** Manual dry-run of `the_pr_raw_hourly_test_gke` in the preview namespace completes successfully.
- **01:10 PM:** PR is merged into `main`. Production Docker image is built and tagged.
- **01:15 PM:** Engineer initiates a **Backfill Execution** in Kestra for the time window `08:00:00` to `12:00:00`.
- **01:30 PM:** Backfill completes. BigQuery partitions are successfully overwritten/merged.
- **01:45 PM:** The next Health Check flow runs. Slack alert resolves automatically. Dashboard returns to `HEALTHY`.

## 4. Root Cause
The root cause was an unhandled schema evolution from the external REST API. Our Python extraction code strictly expected a flat JSON dictionary and did not implement fallback mechanisms or robust schema validation (like Pydantic models) at the ingestion boundary.

## 5. Action Items (Lessons Learned)
| Action Item | Type | Owner | Status |
| :--- | :--- | :--- | :--- |
| Implement Pydantic for strict input validation at the API extraction boundary. | Prevent | Data Engineering | To Do |
| Update `dbt_project.yml` to tighten the `warn_after` and `error_after` freshness thresholds from 4 hours down to 2 hours for critical crypto sources. | Detect | Data Engineering | Done |
| Add a dedicated Kestra alert for `CrashLoopBackOff` pod states before the downstream dbt freshness check catches it. | Detect | Infrastructure | To Do |
