#!/bin/bash

echo "🚀 Starting Local Development Environment..."
echo ""

# Kill any existing services
echo "🧹 Cleaning up existing services..."
pkill -f "node server.js" 2>/dev/null
pkill -f "python.*3000" 2>/dev/null
sleep 2

# Check prerequisites
if [ ! -f "../service-account-key.json" ]; then
    echo "❌ Error: service-account-key.json not found in project root"
    exit 1
fi

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS="../service-account-key.json"

# Use deployed Cloud Run endpoint for assessment
export ASSESSMENT_API_URL="https://video-interview-api-wm2yb4fdna-uc.a.run.app/api/v1/assess"
echo "📡 Using Cloud Run endpoint: $ASSESSMENT_API_URL"
echo ""

# Start Node.js backend
echo "📦 Starting Node.js Backend (port 8080)..."
cd backend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "   Installing dependencies..."
    npm install
fi

node server.js &
NODE_PID=$!
echo "   PID: $NODE_PID"

# Wait for backend to start
sleep 3

# Start frontend
echo "📦 Starting Frontend (port 3000)..."
cd ../frontend

echo ""
echo "✅ All services started!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔗 Backend API:  http://localhost:8080"
echo "🔗 Frontend:     http://localhost:3000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start frontend (this will block)
python3 -m http.server 3000

# Cleanup on exit
echo ""
echo "🛑 Stopping services..."
kill $NODE_PID 2>/dev/null
echo "✅ All services stopped"
