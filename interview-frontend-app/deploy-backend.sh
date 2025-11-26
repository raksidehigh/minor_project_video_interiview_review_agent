#!/bin/bash
set -e

PROJECT_ID="virtual-interview-agent"
REGION="asia-south1"
SERVICE_NAME="interview-backend"

echo "🚀 Deploying Backend to Cloud Run..."

cd backend

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --set-env-vars "BUCKET_NAME=virtual-interview-agent" \
  --project $PROJECT_ID

echo "✅ Backend deployed!"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
