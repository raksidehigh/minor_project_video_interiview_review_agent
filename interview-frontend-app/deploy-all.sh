#!/bin/bash
set -e

echo "======================================================================"
echo "🚀 Deploying Complete Interview System to Cloud Run"
echo "======================================================================"
echo ""

# Step 1: Deploy Backend
echo "📦 Step 1/2: Deploying Backend..."
./deploy-backend.sh

# Get backend URL
BACKEND_URL=$(gcloud run services describe interview-backend --region us-central1 --format 'value(status.url)' --project interview-agent-479316)

echo ""
echo "======================================================================"
echo "⚠️  IMPORTANT: Updating frontend with backend URL..."
echo "======================================================================"

# Update frontend script.js with backend URL
cd frontend
sed -i.bak "s|const API_URL = '.*';|const API_URL = '$BACKEND_URL';|g" script.js
rm script.js.bak
cd ..

echo "✅ Frontend updated with backend URL: $BACKEND_URL"
echo ""

# Step 2: Deploy Frontend
echo "📦 Step 2/2: Deploying Frontend..."
./deploy-frontend.sh

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe interview-frontend --region us-central1 --format 'value(status.url)' --project interview-agent-479316)

echo ""
echo "======================================================================"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "======================================================================"
echo ""
echo "📍 Your Services:"
echo "   Frontend:  $FRONTEND_URL"
echo "   Backend:   $BACKEND_URL"
echo "   AI Agent:  https://video-interview-api-wm2yb4fdna-uc.a.run.app"
echo ""
echo "🔗 Open your interview platform:"
echo "   $FRONTEND_URL"
echo ""
echo "======================================================================"
