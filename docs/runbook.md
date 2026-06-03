# Operations Runbook

This runbook documents common operations for building, deploying, testing, and troubleshooting the crypto analytics pipeline.

---

## 1. Repository Setup

Clone the repository:

```bash
git clone https://github.com/TanThanh113/crypto-analysis-project.git
cd crypto-analysis-project
```

Check repository status:

```bash
git status
```

---

## 2. Docker Images

### Build images locally

```bash
docker build -t crypto-batch:local -f docker/batch.Dockerfile local_scripts
docker build -t crypto-dbt:local -f docker/dbt.Dockerfile dbt_transform
docker build -t crypto-ml:local -f docker/ml.Dockerfile ml
```

### Test images locally

```bash
docker run --rm crypto-batch:local python --version
docker run --rm crypto-dbt:local uv run dbt --version
docker run --rm crypto-ml:local python --version
```

### Configure Docker authentication for Artifact Registry

```bash
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
```

### Tag images

```bash
export PROJECT_ID="${GCP_PROJECT_ID}"
export REGION="${GCP_LOCATION:-asia-southeast1}"
export AR_REPO=crypto-docker
export AR_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"

docker tag crypto-batch:local ${AR_BASE}/crypto-batch:latest
docker tag crypto-dbt:local ${AR_BASE}/crypto-dbt:latest
docker tag crypto-ml:local ${AR_BASE}/crypto-ml:latest
```

### Push images

```bash
docker push ${AR_BASE}/crypto-batch:latest
docker push ${AR_BASE}/crypto-dbt:latest
docker push ${AR_BASE}/crypto-ml:latest
```

### Verify images

```bash
gcloud artifacts docker images list ${AR_BASE}
```

---

## 3. Terraform

### Initialize

```bash
cd terraform
terraform init
```

### Format and validate

```bash
terraform fmt
terraform validate
```

### Plan

```bash
terraform plan
```

### Apply

```bash
terraform apply
```

Important:

* Do not commit `terraform.tfstate`
* Do not commit `terraform.tfvars`
* Do not commit service account JSON keys

---

## 4. dbt

### Run dbt debug locally through Docker

```bash
docker run --rm \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/adc.json \
  -e GCP_PROJECT_ID="${GCP_PROJECT_ID}" \
  -e BQ_ANALYTICS_DATASET=dbt_quants_dev \
  -e BQ_ML_OUTPUTS_DATASET=ml_outputs \
  -e BQ_LOCATION=asia-southeast1 \
  -v "${GOOGLE_APPLICATION_CREDENTIALS}:/app/adc.json:ro" \
  crypto-dbt:local \
  uv run dbt debug
```

### Build selected dbt models

```bash
cd dbt_transform/crypto_dbt

uv run dbt build \
  --select mart_ml_model_metrics \
  --vars '{"enable_ml_outputs_marts": true}' \
  --no-partial-parse
```

### Common dbt notes

* `mart_ml_model_metrics` and prediction output marts require:

```bash
--vars '{"enable_ml_outputs_marts": true}'
```

* If source tables are empty, downstream marts may build successfully but return zero rows.
* Streaming-dependent marts should only be expected to return rows after the streaming pipeline has produced data.

---

## 5. ML Training

### Run ML training from Docker

```bash
docker run --rm \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/adc.json \
  -e GCP_PROJECT_ID="${GCP_PROJECT_ID}" \
  -e GCS_BUCKET_NAME="${GCS_BUCKET_NAME}" \
  -e BQ_ANALYTICS_DATASET=dbt_quants_dev \
  -e BQ_ML_OUTPUTS_DATASET=ml_outputs \
  -v "${GOOGLE_APPLICATION_CREDENTIALS}:/app/adc.json:ro" \
  crypto-ml:local \
  python train_model.py \
    --config feature_list.yml \
    --artifact-dir artifacts \
    --model-choice logistic \
    --artifact-storage both
```

### Expected result

Training should:

* Read `mart_ml_training_dataset_hourly`
* Train the model
* Write metrics to `ml_outputs.model_metrics`
* Upload `.joblib` model artifact to GCS
* Upload `latest_model.json` to GCS

### Verify artifact in GCS

```bash
gcloud storage ls gs://${GCS_BUCKET_NAME}/ml-artifacts/crypto_direction_lgbm_v1/
gcloud storage cat gs://${GCS_BUCKET_NAME}/ml-artifacts/crypto_direction_lgbm_v1/latest_model.json
```

---

## 6. ML Prediction

### Run prediction from Docker

```bash
docker run --rm \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/adc.json \
  -e GCP_PROJECT_ID="${GCP_PROJECT_ID}" \
  -e GCS_BUCKET_NAME="${GCS_BUCKET_NAME}" \
  -e BQ_ANALYTICS_DATASET=dbt_quants_dev \
  -e BQ_ML_OUTPUTS_DATASET=ml_outputs \
  -v "${GOOGLE_APPLICATION_CREDENTIALS}:/app/adc.json:ro" \
  crypto-ml:local \
  python predict_latest.py \
    --config feature_list.yml \
    --artifact-dir artifacts \
    --artifact-storage gcs \
    --dry-run
```

### Expected behavior

Prediction should:

* Download `latest_model.json` from GCS
* Download the active model artifact
* Load the model successfully
* Read `mart_ml_prediction_input_latest`
* Write predictions if input rows exist

If the input table has zero rows, the prediction job will fail with:

```text
Prediction input returned 0 rows
```

This is expected when streaming/hourly input is not available yet.

---

## 7. Kestra

Kestra flows are stored in:

```text
kestra/flows/
```

Main groups:

```text
raw/
dbt/
ml/
master/
```

Production flows use Artifact Registry images:

```text
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-batch:latest
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-dbt:latest
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-ml:latest
```

### Recommended test order

1. Run `the_ml_train_daily`
2. Run a small dbt transform flow
3. Run raw ingestion flows
4. Enable scheduled triggers
5. Enable ML prediction only after prediction input has rows

---

## 8. BigQuery Validation Queries

### Check latest ML metrics

```sql
SELECT
  model_name,
  model_version,
  split_name,
  row_count,
  accuracy,
  f1_macro,
  auc_ovr,
  evaluated_at
FROM `${GCP_PROJECT_ID}.dbt_quants_dev.mart_ml_model_metrics`
ORDER BY evaluated_at DESC
LIMIT 20;
```

### Check prediction input

```sql
SELECT
  symbol,
  COUNT(*) AS rows
FROM `${GCP_PROJECT_ID}.dbt_quants_dev.mart_ml_prediction_input_latest`
GROUP BY symbol;
```

### Check prediction output

```sql
SELECT
  model_name,
  model_version,
  symbol,
  predicted_class,
  prob_up,
  prob_down,
  prob_flat,
  confidence_score,
  signal,
  predicted_at,
  hour_ts
FROM `${GCP_PROJECT_ID}.ml_outputs.model_predictions`
ORDER BY predicted_at DESC
LIMIT 20;
```

---

## 9. Common Troubleshooting

### Docker image not updating in Kestra

Use:

```yaml
pullPolicy: ALWAYS
```

Then rerun the flow.

### Prediction input returns zero rows

Check:

```sql
SELECT *
FROM `${GCP_PROJECT_ID}.dbt_quants_dev.mart_ml_prediction_input_latest`;
```

Usually this means streaming/hourly data is not available yet.

### BigQuery external table missing GCS metadata

This usually happens when raw GCS/Iceberg files were deleted but BigQuery metadata still points to them.

Fix:

* Rebuild the raw table
* Restore the missing files
* Recreate the external/Iceberg catalog table

### dbt source or mart not found

Run:

```bash
uv run dbt ls
uv run dbt build --select <model_name> --no-partial-parse
```

### Service account permission error

Check the service account has the required permissions for:

* BigQuery
* GCS
* Artifact Registry
* BigLake/Iceberg
* Kestra secrets

---

## 10. Public Repository Safety Checklist

Before making the repository public, verify:

```bash
git ls-files | grep -Ei '\.env|tfstate|tfvars|secret|secrets|key\.json|credential|credentials|joblib|artifacts|output_data|_state|\.success|\.parquet'
```

Expected result:

```text
No output
```

Run an additional scan:

```bash
git grep -nE 'BEGIN PRIVATE KEY|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z_]{20,}|sk-[0-9A-Za-z]{20,}|xox[baprs]-[0-9A-Za-z-]{20,}' || true
```

Expected result:

```text
No output
```
