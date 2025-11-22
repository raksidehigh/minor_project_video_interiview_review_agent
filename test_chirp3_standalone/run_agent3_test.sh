#!/bin/bash
# Comprehensive Agent 3 Test - All Features

set -e

echo "======================================================================"
echo "AGENT 3 COMPREHENSIVE TEST - All Features"
echo "======================================================================"
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./run_test.sh first"
    exit 1
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check for credentials
if [ -f "../service-account-key.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="../service-account-key.json"
    echo "🔑 Using service account: ../service-account-key.json"
fi

echo ""
echo "======================================================================"
echo "🧪 RUNNING COMPREHENSIVE AGENT 3 TEST"
echo "======================================================================"
echo ""

# Run test
python test_agent3_full.py

echo ""
echo "======================================================================"
echo "✅ TEST COMPLETE"
echo "======================================================================"

