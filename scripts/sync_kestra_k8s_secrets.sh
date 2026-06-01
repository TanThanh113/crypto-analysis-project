#!/usr/bin/env bash
set -Eeuo pipefail # Rules for Shell Scripts

PROJECT_ID="${PROJECT_ID:-project-lambda-crypto}"
NAMESPACE="${NAMESPACE:-kestra}"
K8S_SECRET_NAME="${K8S_SECRET_NAME:-kestra-runtime-secret}"
HELM_RELEASE="${HELM_RELEASE:-kestra}"
RESTART_DEPLOYMENTS="${RESTART_DEPLOYMENTS:-true}"

# Check if required commands are installed
require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "❌ Missing required command: $1"
    exit 1
  fi
}

# Function to read a secret from GCP Secret Manager
read_gcp_secret() {
  local secret_name="$1"

  echo "🔐 Reading Secret Manager secret: ${secret_name}" >&2

  gcloud secrets versions access latest \
    --project="${PROJECT_ID}" \
    --secret="${secret_name}"
}

# Function to check if a secret exists in GCP Secret Manager
require_command gcloud
require_command kubectl

echo "🚀 Syncing Kestra runtime secrets from GCP Secret Manager to Kubernetes..."
echo "Project: ${PROJECT_ID}"
echo "Namespace: ${NAMESPACE}"
echo "Kubernetes Secret: ${K8S_SECRET_NAME}"

# Read secrets from GCP Secret Manager
DB_PASSWORD="$(read_gcp_secret kestra-db-password)"
BASIC_AUTH_USERNAME="$(read_gcp_secret kestra-basic-auth-username)"
BASIC_AUTH_PASSWORD="$(read_gcp_secret kestra-basic-auth-password)"

# Check if secrets are empty
if [[ -z "${DB_PASSWORD}" || -z "${BASIC_AUTH_USERNAME}" || -z "${BASIC_AUTH_PASSWORD}" ]]; then
  echo "❌ One or more secrets are empty. Aborting."
  exit 1
fi

echo "📦 Applying Kubernetes Secret..."

# Create or update the Kubernetes Secret
kubectl create secret generic "${K8S_SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  --from-literal=KESTRA_DB_PASSWORD="${DB_PASSWORD}" \
  --from-literal=KESTRA_BASIC_AUTH_USERNAME="${BASIC_AUTH_USERNAME}" \
  --from-literal=KESTRA_BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD}" \
  --dry-run=client \
  -o yaml | kubectl apply -f -

# Label the Kubernetes Secret
kubectl label secret "${K8S_SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  app.kubernetes.io/name=kestra \
  app.kubernetes.io/managed-by=manual-secret-sync \
  --overwrite >/dev/null

echo "✅ Kubernetes Secret synced successfully."

if [[ "${RESTART_DEPLOYMENTS}" == "true" ]]; then
  echo "🔄 Restarting Kestra deployments so env vars are reloaded..."

  # Replace the old pods with new ones using the new secret library.
  kubectl rollout restart deployment \
    --namespace "${NAMESPACE}" \
    -l "app.kubernetes.io/instance=${HELM_RELEASE}"

  echo "⏳ Waiting for Kestra deployments rollout..."

  # Wait for the rollout to complete
  kubectl rollout status deployment \
    --namespace "${NAMESPACE}" \
    -l "app.kubernetes.io/instance=${HELM_RELEASE}" \
    --timeout=10m

  echo "✅ Kestra deployments restarted successfully."
else
  echo "ℹ️ Skipped deployment restart. Set RESTART_DEPLOYMENTS=true to restart automatically."
fi

echo "🎉 Secret sync completed."
