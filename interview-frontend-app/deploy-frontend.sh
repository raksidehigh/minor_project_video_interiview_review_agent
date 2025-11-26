#!/bin/bash
set -e

PROJECT_ID="virtual-interview-agent"
REGION="asia-south1"
SERVICE_NAME="interview-frontend"

echo "🚀 Deploying Frontend to Cloud Run..."

cd frontend

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 5 \
  --project $PROJECT_ID

echo "✅ Frontend deployed!"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
