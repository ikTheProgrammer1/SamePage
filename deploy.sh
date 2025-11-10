#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="samepage-477714"
REGION="us-east1"
REPO="samepage"
SERVICE="samepage"

echo "Setting project…"
gcloud config set project "$PROJECT_ID"

echo "Enabling required APIs (idempotent)…"
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

echo "Ensure Artifact Registry repo exists…"
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="SamePage containers"
fi

echo "Compute service accounts…"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Grant IAM to Cloud Build…"
gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --location="$REGION" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"

echo "Determine Cloud Run runtime service account…"
RUNTIME_SA="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)"
if [[ -z "$RUNTIME_SA" ]]; then
  RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi
echo "Runtime SA: ${RUNTIME_SA}"

echo "Grant IAM to runtime SA…"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/artifactregistry.reader"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/datastore.user"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/aiplatform.user"

echo "Build and deploy via Cloud Build…"
gcloud builds submit \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_SERVICE="$SERVICE"

echo "Service URL:"
gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)'

# Optional: enable Vertex features in the app
# gcloud run services update "$SERVICE" --region="$REGION" --set-env-vars=ENABLE_VERTEX=1

