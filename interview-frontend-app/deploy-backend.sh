#!/bin/bash
set -e

PROJECT_ID="interview-agent-479316"
REGION="us-central1"
SERVICE_NAME="interview-backend"
ASSESSMENT_API_URL="https://video-interview-api-wm2yb4fdna-uc.a.run.app/api/v1/assess"
CLOUD_SQL_INSTANCE="interview-agent-479316:us-central1:interview-db"

echo "🚀 Deploying Backend to Cloud Run with Cloud SQL..."

cd backend

# Prompt for database password
read -sp "Enter PostgreSQL password: " DB_PASSWORD
echo ""

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --add-cloudsql-instances $CLOUD_SQL_INSTANCE \
  --set-env-vars "BUCKET_NAME=virtual-interview-agent,ASSESSMENT_API_URL=$ASSESSMENT_API_URL,DB_USER=postgres,DB_PASSWORD=$DB_PASSWORD,DB_NAME=interview_db,DB_HOST=/cloudsql/$CLOUD_SQL_INSTANCE" \
  --project $PROJECT_ID

echo "✅ Backend deployed!"
BACKEND_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)
echo "Backend URL: $BACKEND_URL"
echo ""
echo "⚠️  IMPORTANT: Update frontend script.js with this URL:"
echo "const API_URL = '$BACKEND_URL';"
