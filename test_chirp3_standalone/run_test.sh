#!/bin/bash
# Simple test script for Chirp 3 DenoiserConfig

set -e

echo "======================================================================"
echo "CHIRP 3 DENOISER TEST - Standalone"
echo "======================================================================"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "⬇️  Installing google-cloud-speech..."
pip install -q --upgrade pip
pip install -r requirements.txt

echo ""
echo "======================================================================"
echo "🧪 RUNNING TEST"
echo "======================================================================"
echo ""

# Run test
python test_denoiser.py

echo ""
echo "======================================================================"
echo "✅ TEST COMPLETE"
echo "======================================================================"

