#!/bin/bash
# Test actual transcription with Chirp 3 on real GCS video

set -e

echo "======================================================================"
echo "CHIRP 3 TRANSCRIPTION TEST - Real Video (user_2/video_3)"
echo "======================================================================"
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./run_test.sh first"
    exit 1
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install additional dependencies
echo "⬇️  Installing google-cloud-storage..."
pip install -q google-cloud-storage 2>&1 || {
    echo "⚠️  pip install had warnings, continuing anyway..."
}

echo ""
echo "======================================================================"
echo "🧪 RUNNING TRANSCRIPTION TEST"
echo "======================================================================"
echo ""

# Check for credentials
if [ ! -f "../service-account-key.json" ]; then
    echo "⚠️  Warning: service-account-key.json not found in parent directory"
    echo "   Make sure GOOGLE_APPLICATION_CREDENTIALS is set or gcloud is authenticated"
fi

# Set credentials if available
if [ -f "../service-account-key.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="../service-account-key.json"
    echo "🔑 Using service account: ../service-account-key.json"
fi

# Run test
python test_transcribe_video.py

echo ""
echo "======================================================================"
echo "✅ TEST COMPLETE"
echo "======================================================================"

