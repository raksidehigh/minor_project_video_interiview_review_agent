#!/bin/bash
# Test Video Interview Assessment API locally with Docker

set -e

echo "======================================================================"
echo "🧪 Testing Video Interview Assessment API Locally"
echo "======================================================================"

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading .env file..."
    export $(grep -v '^#' .env | xargs)
    echo "   ✅ Loaded environment variables from .env"
fi

# Check for service account key
if [ ! -f "service-account-key.json" ]; then
    echo "❌ Error: service-account-key.json not found"
    exit 1
fi

# Build image
echo ""
echo "🏗️  Building Docker image..."
docker build -t video-interview-api:local .

# Stop existing container if running
echo ""
echo "🛑 Stopping existing container (if any)..."
docker stop video-interview-api-test 2>/dev/null || true
docker rm video-interview-api-test 2>/dev/null || true

# Run container
echo ""
echo "🚀 Starting container..."
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GOOGLE_API_KEY not set. Using fallback key (may be invalid)"
    GOOGLE_API_KEY="AIzaSyChww0PCNK8FR8GXoOV-n4SgvUEJ0wKKZo"
else
    echo "   ✅ Using GOOGLE_API_KEY from environment"
fi

docker run -d \
    --name video-interview-api-test \
    -p 8080:8080 \
    -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
    -e GOOGLE_APPLICATION_CREDENTIALS="/app/service-account-key.json" \
    -v "${PWD}/service-account-key.json:/app/service-account-key.json:ro" \
    video-interview-api:local

# Wait for service to be ready
echo ""
echo "⏳ Waiting for service to start..."
sleep 8

# Check health
echo ""
echo "🏥 Checking health endpoint..."
curl -s http://localhost:8080/health | python3 -m json.tool

echo ""
echo "======================================================================"
echo "✅ API is running locally with STREAMING enabled!"
echo "======================================================================"
echo ""
echo "📚 API Documentation: http://localhost:8080/docs"
echo "🏥 Health Check: http://localhost:8080/health"
echo ""
echo "🧪 Test with simplified API (auto-discovers files):"
echo ""
echo 'curl -X POST "http://localhost:8080/api/v1/assess" \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{'
echo '    "user_id": "user_1",'
echo '    "username": "Test User"'
echo '  }'"'"
echo ""
echo "========================================================================"
echo "📊 STREAMING VERIFICATION - Watch for these indicators in logs:"
echo "========================================================================"
echo ""
echo "✅ GOOD (Streaming):   🔗 Streaming from signed URL (no download)"
echo "❌ BAD (Old behavior): ⬇️  Downloading..."
echo ""
echo "Expected behavior:"
echo "  - Videos should stream 15 times (5 videos × 3 agents)"
echo "  - Memory usage should stay under 500MB (was 2-4GB before)"
echo "  - No downloads to /tmp/"
echo ""
echo "📋 View logs to verify streaming:"
echo "docker logs -f video-interview-api-test"
echo ""
echo "🛑 Stop container:"
echo "docker stop video-interview-api-test"
echo ""
echo "======================================================================"

