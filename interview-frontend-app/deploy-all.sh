#!/bin/bash
set -e

echo "🚀 Deploying Interview Application..."

# Deploy backend first
echo "📦 Step 1: Deploying Backend..."
chmod +x deploy-backend.sh
./deploy-backend.sh

BACKEND_URL=$(gcloud run services describe interview-backend --region asia-south1 --format 'value(status.url)')
echo "Backend URL: $BACKEND_URL"

# Update frontend API URL
echo "📝 Step 2: Updating Frontend API URL..."
sed -i.bak "s|const API_URL = '.*'|const API_URL = '$BACKEND_URL'|" frontend/script.js
rm -f frontend/script.js.bak

# Deploy frontend
echo "📦 Step 3: Deploying Frontend..."
chmod +x deploy-frontend.sh
./deploy-frontend.sh

FRONTEND_URL=$(gcloud run services describe interview-frontend --region asia-south1 --format 'value(status.url)')

echo ""
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Frontend: $FRONTEND_URL"
echo "🔧 Backend:  $BACKEND_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
