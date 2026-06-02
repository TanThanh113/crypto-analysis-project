# Pull Request

## 1. Summary

Describe the main purpose of this Pull Request.

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

---

## 3. Motivation

Explain why this change is needed.

Include the problem, limitation, or improvement this PR addresses.

---

## 4. Main Changes

List the main changes in this PR.

*
*
*

---

## 5. Required GitHub Checks

These checks must pass before merge:

* [ ] Quality Check passed
* [ ] Docker preview image build passed
* [ ] Kestra preview flow deploy passed

---

## 6. PR Preview Environment

Preview namespace:

* `crypto.preview.pr_<number>`

Preview image tag:

* `pr-<number>`

Expected preview images:

* `crypto-batch:pr-<number>`
* `crypto-dbt:pr-<number>`
* `crypto-ml:pr-<number>`

---

## 7. Safe PR Flow Tests

Only safe PR validation flows should be executed in the preview namespace.

* [ ] `the_pr_raw_hourly_test_gke` passed
* [ ] `the_pr_dbt_test_gke` passed
* [ ] `the_pr_ml_predict_test_gke` passed
* [ ] `the_pr_quality_monitoring_test_gke` passed

Production-like flows must not be executed in the PR preview namespace unless output datasets and buckets are fully isolated.

---

## 8. Monitoring and Alerting Validation

Required if this PR changes monitoring, alerting, dashboard, GE audit, or health check code.

* [ ] Pipeline health check writes rows to BigQuery
* [ ] Health check creates a unique `run_id`
* [ ] Slack alert sends successfully
* [ ] Slack alert reads the correct `run_id`
* [ ] Slack alert does not duplicate old failures
* [ ] Production Monitoring dashboard still renders correctly

Evidence:

*

---

## 9. dbt Validation

Required if this PR changes dbt models.

* [ ] dbt parse passed
* [ ] Related dbt build passed
* [ ] dbt tests passed or expected failures are explained
* [ ] No unintended production table writes during PR testing

Notes:

*

---

## 10. Docker Validation

Required if this PR changes Dockerfiles or dependencies.

* [ ] `crypto-batch` image builds
* [ ] `crypto-dbt` image builds
* [ ] `crypto-ml` image builds
* [ ] Smoke tests passed

Notes:

*

---

## 11. Terraform Validation

Required if this PR changes Terraform.

* [ ] Terraform format check passed
* [ ] Terraform validate passed
* [ ] Terraform plan reviewed
* [ ] No destructive changes unless explicitly intended

Plan summary:

*

---

## 12. Dashboard Validation

Required if this PR changes dashboard or monitoring marts.

* [ ] KPI cards render correctly
* [ ] Failed Checks Table displays text fields correctly
* [ ] Data Freshness table displays stale sources correctly
* [ ] GE Audit cards render correctly
* [ ] Date range filter does not hide stale freshness rows unexpectedly

Evidence:

*

---

## 13. Safety Confirmation

* [ ] No secrets are committed
* [ ] No `.env` files are committed
* [ ] No service account JSON keys are committed
* [ ] No `.parquet` files are committed
* [ ] No local output files are committed
* [ ] No model artifacts are committed
* [ ] No production-like flows were executed in the PR preview namespace
* [ ] This PR does not write test data into production tables unless explicitly stated

---

## 14. Rollback Plan

Describe how to rollback this change if it breaks production.

Rollback summary:

*

---

## 15. Evidence

Attach relevant evidence if applicable:

* GitHub Actions result
* Kestra execution result
* Slack alert screenshot
* Dashboard screenshot
* BigQuery validation result
* Terraform plan summary

Evidence:

*

---

## 16. Final Checklist

* [ ] I reviewed my own changes
* [ ] I updated documentation if needed
* [ ] I tested the affected components
* [ ] I understand the production impact of this PR
* [ ] This PR is ready for review
