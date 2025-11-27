#!/bin/bash

echo "🚀 Starting Local Development Environment..."
echo ""

# Check prerequisites
if [ ! -f "../service-account-key.json" ]; then
    echo "❌ Error: service-account-key.json not found in project root"
    exit 1
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GOOGLE_API_KEY not set"
    echo "   Set it with: export GOOGLE_API_KEY='your_key'"
fi

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS="../service-account-key.json"

# Start Python agent
echo "📦 Starting Python Agent (port 8000)..."
cd ..
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PYTHON_PID=$!
echo "   PID: $PYTHON_PID"

# Wait for Python to start
sleep 5

# Start Node.js backend
echo "📦 Starting Node.js Backend (port 8080)..."
cd interview-frontend-app/backend

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
echo "🔗 Python Agent: http://localhost:8000/docs"
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
kill $PYTHON_PID $NODE_PID 2>/dev/null
echo "✅ All services stopped"
