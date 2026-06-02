# Pull Request

## 1. Summary

Describe the main purpose of this Pull Request.

Example:

* This PR adds, fixes, improves, or refactors ...

---

## 2. Type of Change

Select all that apply:

* [ ] Batch ingestion
* [ ] dbt models
* [ ] ML training or prediction
* [ ] Kestra flows
* [ ] Terraform or infrastructure
* [ ] Monitoring or alerting
* [ ] Dashboard
* [ ] Documentation
* [ ] CI/CD
* [ ] Bug fix
* [ ] Refactor
* [ ] Security
* [ ] Performance or cost optimization

---

## 3. Motivation

Explain why this change is needed.

Include the problem, limitation, bug, or improvement this PR addresses.

---

## 4. Main Changes

List the main changes in this PR.

* Change 1:
* Change 2:
* Change 3:

---

## 5. Production Impact

Select all that apply:

* [ ] No production impact
* [ ] Changes production Kestra flows
* [ ] Changes scheduled jobs or triggers
* [ ] Changes BigQuery models or schemas
* [ ] Changes GCS or BigLake/Iceberg outputs
* [ ] Changes ML training or prediction behavior
* [ ] Changes monitoring or alerting behavior
* [ ] Changes infrastructure resources
* [ ] Changes secrets or runtime configuration
* [ ] May affect cost, runtime, or resource usage

Impact summary:

* Describe the expected production impact.
* Write `N/A` if there is no production impact.

---

## 6. Data Impact

Select all that apply:

* [ ] No data write impact
* [ ] Writes to BigQuery
* [ ] Writes to GCS
* [ ] Writes to BigLake/Iceberg tables
* [ ] Writes ML artifacts
* [ ] Writes monitoring or audit results
* [ ] Changes table schema
* [ ] Changes partitioning or clustering
* [ ] Changes freshness expectations
* [ ] Changes dashboard output

Affected datasets, tables, or buckets:

* Dataset/table/bucket 1:
* Dataset/table/bucket 2:
* Write `N/A` if not applicable.

---

## 7. Required GitHub Checks

These checks must pass before merge:

* [ ] Quality Check passed
* [ ] Docker preview image build passed
* [ ] Kestra preview flow deploy passed

---

## 8. PR Preview Environment

Preview namespace:

* `crypto.preview.pr_<number>`

Preview image tag:

* `pr-<number>`

Expected preview images:

* `crypto-batch:pr-<number>`
* `crypto-dbt:pr-<number>`
* `crypto-ml:pr-<number>`

---

## 9. Safe PR Flow Tests

Only safe PR validation flows should be executed in the preview namespace.

* [ ] `the_pr_raw_hourly_test_gke` passed
* [ ] `the_pr_dbt_test_gke` passed
* [ ] `the_pr_ml_predict_test_gke` passed
* [ ] `the_pr_quality_monitoring_test_gke` passed

Production-like flows must not be executed in the PR preview namespace unless output datasets and buckets are fully isolated.

---

## 10. Kestra Validation

Required if this PR changes Kestra flows.

* [ ] Preview flows deployed successfully
* [ ] Flow namespace is correct
* [ ] PR preview triggers are disabled
* [ ] PR preview images use `pr-<number>` tags
* [ ] Production flows still use production image tags
* [ ] No accidental production-like execution happened in preview namespace

Affected flows:

* Flow 1:
* Flow 2:
* Write `N/A` if not applicable.

Notes:

* Add important Kestra validation notes here.
* Write `N/A` if not applicable.

---

## 11. dbt Validation

Required if this PR changes dbt models.

* [ ] dbt parse passed
* [ ] Related dbt build passed
* [ ] dbt tests passed or expected failures are explained
* [ ] Model dependencies were reviewed
* [ ] Incremental model behavior was reviewed if applicable
* [ ] No unintended production table writes during PR testing

Affected models:

* Model 1:
* Model 2:
* Write `N/A` if not applicable.

Notes:

* Add dbt validation notes here.
* Write `N/A` if not applicable.

---

## 12. Docker Validation

Required if this PR changes Dockerfiles, dependencies, Python packages, dbt packages, or ML packages.

* [ ] `crypto-batch` image builds
* [ ] `crypto-dbt` image builds
* [ ] `crypto-ml` image builds
* [ ] Smoke tests passed
* [ ] Runtime imports work inside the container
* [ ] Image tag was pushed correctly

Affected images:

* Image 1:
* Image 2:
* Write `N/A` if not applicable.

Notes:

* Add Docker validation notes here.
* Write `N/A` if not applicable.

---

## 13. Terraform Validation

Required if this PR changes Terraform.

* [ ] Terraform format check passed
* [ ] Terraform validate passed
* [ ] Terraform plan reviewed
* [ ] No destructive changes unless explicitly intended
* [ ] New resources are named consistently
* [ ] IAM changes follow least privilege
* [ ] BigQuery tables are managed by Terraform if production-owned

Plan summary:

* Add the Terraform plan summary here.
* Write `N/A` if not applicable.

---

## 14. Monitoring and Alerting Validation

Required if this PR changes monitoring, alerting, dashboard, GE audit, health check, or Slack logic.

* [ ] Pipeline health check writes rows to BigQuery
* [ ] Health check creates a unique `run_id`
* [ ] Slack alert sends successfully
* [ ] Slack alert reads the correct `run_id`
* [ ] Slack alert does not duplicate old failures
* [ ] Critical failures still fail the Kestra task after alerting
* [ ] Warning failures do not incorrectly fail production unless intended
* [ ] Production Monitoring dashboard still renders correctly

Evidence:

* Add Slack alert screenshot, Kestra log, dashboard screenshot, or BigQuery result.
* Write `N/A` if not applicable.

---

## 15. Great Expectations Validation

Required if this PR changes GE audit logic or expectations.

* [ ] GE audit runs successfully
* [ ] Audit results are written to BigQuery
* [ ] Critical and warning severities are correct
* [ ] Failed expectations are explainable
* [ ] Monitoring correctly reads GE audit results

Affected suites or tables:

* Suite/table 1:
* Suite/table 2:
* Write `N/A` if not applicable.

Notes:

* Add GE validation notes here.
* Write `N/A` if not applicable.

---

## 16. ML Validation

Required if this PR changes ML training, prediction, features, metrics, or artifacts.

* [ ] Training script runs successfully
* [ ] Prediction script runs successfully or expected missing input is explained
* [ ] Feature list changes were reviewed
* [ ] Model metrics output is valid
* [ ] Model artifact upload/download works
* [ ] Prediction output schema is still compatible

Affected ML components:

* Component 1:
* Component 2:
* Write `N/A` if not applicable.

Notes:

* Add ML validation notes here.
* Write `N/A` if not applicable.

---

## 17. Dashboard Validation

Required if this PR changes dashboard, monitoring marts, dashboard marts, or BI-facing tables.

* [ ] KPI cards render correctly
* [ ] Failed Checks Table displays text fields correctly
* [ ] Data Freshness table displays stale sources correctly
* [ ] GE Audit cards render correctly
* [ ] Date range filter does not hide stale freshness rows unexpectedly
* [ ] Dashboard still communicates the current production state clearly

Evidence:

* Add dashboard screenshot or validation notes here.
* Write `N/A` if not applicable.

---

## 18. Security and Secrets

* [ ] No secrets are committed
* [ ] No `.env` files are committed
* [ ] No service account JSON keys are committed
* [ ] No private keys are committed
* [ ] No API tokens are committed
* [ ] Secret Manager changes are documented if applicable
* [ ] Runtime secret mounts were tested if applicable

Secrets changed or added:

* Secret 1:
* Secret 2:
* Write `N/A` if not applicable.

---

## 19. Repository Hygiene

* [ ] No `.parquet` files are committed
* [ ] No local output files are committed
* [ ] No model artifacts are committed
* [ ] No temporary state files are committed
* [ ] No generated cache files are committed
* [ ] Documentation was updated if needed

---

## 20. Cleanup Expectations

Expected cleanup after PR close or merge:

* [ ] PR preview Docker images are cleaned up
* [ ] PR preview Kestra flows are cleaned up
* [ ] No stale preview namespace remains in Kestra UI
* [ ] No temporary test output remains in production tables or buckets

Notes:

* Add cleanup notes here.
* Write `N/A` if not applicable.

---

## 21. Rollback Plan

Describe how to rollback this change if it breaks production.

Rollback summary:

* Describe the rollback approach.
* Example: revert PR, retag previous image, redeploy previous flow, or disable trigger.

Rollback type:

* [ ] Revert PR
* [ ] Retag previous Docker image
* [ ] Redeploy previous Kestra flow
* [ ] Revert dbt model change
* [ ] Revert Terraform change
* [ ] Disable schedule or trigger temporarily
* [ ] Other:

---

## 22. Evidence

Attach relevant evidence if applicable:

* GitHub Actions result
* Kestra execution result
* Slack alert screenshot
* Dashboard screenshot
* BigQuery validation result
* Terraform plan summary
* dbt build result
* Docker build result

Evidence:

* Add links, screenshots, logs, or summaries here.
* Write `N/A` if not applicable.

---

## 23. Merge Criteria

This PR is ready to merge only when:

* [ ] Required GitHub checks passed
* [ ] Required manual PR validation passed
* [ ] Production impact is understood
* [ ] Rollback plan is clear
* [ ] No unsafe preview execution happened
* [ ] Reviewer concerns are resolved

---

## 24. Post-Merge Validation

After merging to `main`, verify if applicable:

* [ ] Production Docker images were built
* [ ] Production Kestra flows were deployed
* [ ] Production dashboard still works
* [ ] Slack alerting still works
* [ ] Affected production flow runs successfully
* [ ] Preview resources were cleaned up

Post-merge notes:

* Add post-merge validation notes here.
* Write `N/A` if not applicable.

---

## 25. Final Checklist

* [ ] I reviewed my own changes
* [ ] I updated documentation if needed
* [ ] I tested the affected components
* [ ] I understand the production impact of this PR
* [ ] This PR is ready for review
