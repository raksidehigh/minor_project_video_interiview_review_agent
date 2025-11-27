#!/bin/bash
# Deploy Video Interview Assessment API to Google Cloud Run (Mumbai Region)

set -e

echo "======================================================================"
echo "🚀 Deploying Video Interview Assessment API to Google Cloud Run"
echo "   Region: Mumbai (asia-south1)"
echo "   Company Account"
echo "======================================================================"

# Load environment variables from .env
if [ -f .env ]; then
    echo "📝 Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ Error: .env file not found. Please create it first."
    exit 1
fi

# Configuration
PROJECT_ID="${PROJECT_ID:-your-project-id}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-video-interview-api}"
BUCKET_NAME="${BUCKET_NAME:-virtual-interview-agent}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Verify required variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "❌ Error: GOOGLE_API_KEY not found in .env file"
    exit 1
fi

if [ "$PROJECT_ID" == "your-project-id" ]; then
    echo "❌ Error: Please set PROJECT_ID in .env file"
    exit 1
fi

echo ""
echo "📋 Configuration:"
echo "   Project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo "   Service: ${SERVICE_NAME}"
echo "   Bucket: ${BUCKET_NAME}"
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

# Check for service account key first
if [ -f "service-account-key.json" ]; then
    echo "🔑 Found service-account-key.json, authenticating..."
    gcloud auth activate-service-account --key-file=service-account-key.json
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || echo "")
    echo "✅ Logged in as service account: ${ACTIVE_ACCOUNT}"
else
    # Fallback to user authentication
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || echo "")
    if [ -z "$ACTIVE_ACCOUNT" ]; then
        echo "❌ Not logged in. Running: gcloud auth login"
        gcloud auth login
    else
        echo "✅ Logged in as: ${ACTIVE_ACCOUNT}"
    fi
fi

# Set project
echo "📦 Setting project: ${PROJECT_ID}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo ""
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable \
    vision.googleapis.com \
    speech.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    storage-api.googleapis.com \
    --project=${PROJECT_ID} \
    --quiet

echo "✅ APIs enabled"

# Verify bucket exists (region-agnostic check)
echo ""
echo "🪣 Verifying Cloud Storage bucket..."
if gsutil ls -b gs://${BUCKET_NAME} &> /dev/null; then
    echo "✅ Bucket exists: gs://${BUCKET_NAME}"
else
    echo "❌ Error: Bucket gs://${BUCKET_NAME} not found"
    echo "   Create it with: gsutil mb -l us-east1 gs://${BUCKET_NAME}"
    exit 1
fi

# Build container image
echo ""
echo "🏗️  Building container image (with --no-cache for fresh build)..."
echo "   This may take 5-10 minutes..."
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions _IMAGE_NAME=${IMAGE_NAME} \
    --project=${PROJECT_ID} \
    .

# Deploy to Cloud Run with crash fixes
echo ""
echo "🚀 Deploying to Cloud Run (Mumbai region) with crash fixes..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --service-account virtual-interview@${PROJECT_ID}.iam.gserviceaccount.com \
    --memory ${MEMORY:-8Gi} \
    --cpu ${CPU:-4} \
    --timeout ${TIMEOUT:-600} \
    --concurrency ${CONCURRENCY:-2} \
    --min-instances ${MIN_INSTANCES:-0} \
    --max-instances ${MAX_INSTANCES:-5} \
    --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-env-vars "BUCKET_NAME=${BUCKET_NAME}" \
    --set-env-vars "GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json" \
    --set-env-vars "MALLOC_ARENA_MAX=2" \
    --set-env-vars "OMP_NUM_THREADS=1" \
    --set-env-vars "MKL_NUM_THREADS=1" \
    --set-env-vars "OPENBLAS_NUM_THREADS=1" \
    --set-env-vars "NUMEXPR_NUM_THREADS=1" \
    --set-env-vars "VECLIB_MAXIMUM_THREADS=1" \
    --set-env-vars "TF_NUM_INTRAOP_THREADS=1" \
    --set-env-vars "TF_NUM_INTEROP_THREADS=1" \
    --set-env-vars "TF_CPP_MIN_LOG_LEVEL=2" \
    --set-env-vars "PYTHONHASHSEED=0" \
    --set-env-vars "USE_OPTIMIZED=true" \
    --project=${PROJECT_ID} \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --project=${PROJECT_ID} \
    --format 'value(status.url)')

# Cleanup old container images to save storage costs
echo ""
echo "🧹 Cleaning up old container images (keeping 3 most recent)..."
OLD_IMAGE_COUNT=$(gcloud container images list-tags ${IMAGE_NAME} \
    --limit=999 --sort-by=~TIMESTAMP --format="get(digest)" | wc -l | tr -d ' ')

if [ "$OLD_IMAGE_COUNT" -gt 3 ]; then
    IMAGES_TO_DELETE=$((OLD_IMAGE_COUNT - 3))
    echo "   Found ${OLD_IMAGE_COUNT} images, deleting ${IMAGES_TO_DELETE} old images..."
    
    gcloud container images list-tags ${IMAGE_NAME} \
        --limit=999 --sort-by=~TIMESTAMP \
        --format="get(digest)" | tail -n +4 | \
        xargs -I {} gcloud container images delete "${IMAGE_NAME}@{}" --quiet 2>/dev/null || true
    
    echo "   ✅ Cleanup complete! Reduced storage costs."
else
    echo "   ✅ Only ${OLD_IMAGE_COUNT} images found, no cleanup needed."
fi

echo ""
echo "======================================================================"
echo "✅ Deployment Complete with Crash Fixes!"
echo "======================================================================"
echo ""
echo "🔧 Applied Crash Fixes:"
echo "   ✅ face_recognition library for face matching"
echo "   ✅ Proper OpenCV resource management"
echo "   ✅ Memory monitoring and garbage collection"
echo "   ✅ Enhanced error handling"
echo "   ✅ Memory-optimized environment variables"
echo ""
echo "🌐 Service URL: ${SERVICE_URL}"
echo "📍 Region: Mumbai (${REGION})"
echo "🪣 Bucket: gs://${BUCKET_NAME}"
echo ""
echo "📚 API Documentation: ${SERVICE_URL}/docs"
echo "🏥 Health Check: ${SERVICE_URL}/health"
echo ""
echo "🧪 Test the API:"
echo ""
echo "curl -X POST \"${SERVICE_URL}/api/v1/assess\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"user_id\": \"test_001\","
echo "    \"username\": \"Test User\","
echo "    \"profile_pic_url\": \"gs://${BUCKET_NAME}/test_001/profile_pic.jpg\","
echo "    \"gov_id_url\": \"gs://${BUCKET_NAME}/test_001/gov_id.jpg\","
echo "    \"video_urls\": ["
echo "      \"gs://${BUCKET_NAME}/test_001/video1.mp4\","
echo "      \"gs://${BUCKET_NAME}/test_001/video2.mp4\","
echo "      \"gs://${BUCKET_NAME}/test_001/video3.mp4\","
echo "      \"gs://${BUCKET_NAME}/test_001/video4.mp4\","
echo "      \"gs://${BUCKET_NAME}/test_001/video5.mp4\""
echo "    ]"
echo "  }'"
echo ""
echo "📊 Monitor logs:"
echo "gcloud run services logs read ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --limit 50"
echo ""
echo "🔍 Monitor for crashes:"
echo "gcloud logging read \"severity=ERROR AND resource.type=cloud_run_revision\" --project=${PROJECT_ID} --limit=20"
echo ""
echo "💾 Monitor memory usage:"
echo "gcloud logging read \"textPayload:'Memory Status'\" --project=${PROJECT_ID} --limit=10"
echo ""
echo "======================================================================"

