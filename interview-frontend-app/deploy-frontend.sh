#!/bin/bash
set -e

PROJECT_ID="interview-agent-479316"
REGION="us-central1"
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
  --port 8080 \
  --max-instances 5 \
  --project $PROJECT_ID

echo "✅ Frontend deployed!"
FRONTEND_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)
echo "Frontend URL: $FRONTEND_URL"
echo ""
echo "🎉 Your interview platform is live at: $FRONTEND_URL"
