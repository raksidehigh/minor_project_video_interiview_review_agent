#!/bin/bash
# Deploy Video Interview Assessment API to Google Cloud Run

set -e

echo "======================================================================"
echo "🚀 Deploying Video Interview Assessment API to Google Cloud Run"
echo "======================================================================"

# Load environment variables from .env
if [ -f .env ]; then
    echo "📝 Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-cedar-kiln-459802-b6}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-video-interview-api}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Check for API key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "❌ Error: GOOGLE_API_KEY not found in environment or .env file"
    exit 1
fi

echo ""
echo "📋 Configuration:"
echo "   Project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo "   Service: ${SERVICE_NAME}"
echo "   Image: ${IMAGE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install it first."
    echo "   Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
echo "🔐 Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Not logged in. Running: gcloud auth login"
    gcloud auth login
fi

# Set project
echo "📦 Setting project: ${PROJECT_ID}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    aiplatform.googleapis.com \
    storage-api.googleapis.com \
    --quiet

# Build container image
echo ""
echo "🏗️  Building container image..."
echo "   This may take 5-10 minutes..."
gcloud builds submit --tag ${IMAGE_NAME} .

# Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 8Gi \
    --cpu 4 \
    --timeout 600 \
    --concurrency 2 \
    --min-instances 0 \
    --max-instances 25 \
    --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo ""
echo "======================================================================"
echo "✅ Deployment Complete!"
echo "======================================================================"
echo ""
echo "🌐 Service URL: ${SERVICE_URL}"
echo ""
echo "📚 API Documentation: ${SERVICE_URL}/docs"
echo "🏥 Health Check: ${SERVICE_URL}/health"
echo ""
echo "🧪 Test the API (Simplified - auto-discovers files):"
echo "curl -X POST \"${SERVICE_URL}/api/v1/assess\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"user_id\": \"user_1\","
echo "    \"username\": \"Test User\""
echo "  }'"
echo ""
echo "======================================================================"

