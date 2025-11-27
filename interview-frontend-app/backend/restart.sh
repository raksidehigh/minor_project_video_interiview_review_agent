#!/bin/bash

echo "🔄 Restarting backend..."

# Kill existing process
pkill -f "node server.js" 2>/dev/null
sleep 1

# Start backend
echo "🚀 Starting backend on port 8080..."
node server.js
