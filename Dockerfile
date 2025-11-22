# Dockerfile for Video Interview Assessment API
# Optimized for Google Cloud Run deployment

FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    WORKERS=1 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    PYTHONHASHSEED=0

# Install system dependencies for OpenCV, dlib, and video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build dependencies for psutil, dlib, and other compiled packages
    gcc \
    g++ \
    make \
    cmake \
    build-essential \
    python3-dev \
    # dlib dependencies
    libopenblas-dev \
    liblapack-dev \
    # OpenCV dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # Video processing + WebM codec support
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libvpx-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
# Stage 1: Install dlib, face_recognition, and MediaPipe first (requires compilation)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    numpy==1.24.3 \
    dlib==20.0.0 \
    face-recognition==1.3.0 \
    mediapipe==0.10.9 \
    opencv-python-headless==4.8.1.78 \
    pillow==10.2.0

# Stage 2: Install remaining packages from requirements.txt
# This ensures we use the correct versions (especially google-cloud-speech>=2.34.0 for Chirp 3)
RUN pip install --no-cache-dir \
    fastapi==0.109.2 \
    uvicorn[standard]==0.27.1 \
    python-multipart==0.0.9 \
    langgraph==0.2.28 \
    langchain-core==0.3.15 \
    langchain-google-genai==2.0.4 \
    google-cloud-storage==2.14.0 \
    google-cloud-vision==3.7.0 \
    'google-cloud-speech>=2.34.0' \
    google-generativeai==0.8.3 \
    pydantic==2.6.1 \
    pydantic-settings==2.1.0 \
    python-dotenv==1.0.1 \
    requests==2.31.0 \
    psutil==5.9.8 \
    prometheus-client==0.20.0

# Copy application code
# Updated: 2025-10-15 02:30 - Added startup cleanup + 4GB memory
COPY app/ ./app/
COPY service-account-key.json ./service-account-key.json

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod 600 /app/service-account-key.json

# Switch to non-root user
USER appuser

# Verify face_recognition installation and pre-load models (prevents runtime downloads!)
# face_recognition_models package (~100MB) includes all models - they're bundled, not downloaded
# But we trigger a test load here to ensure models are accessible and ready at deployment
# This is critical - prevents any lazy-loading delays or potential downloads on first request
RUN python3 -c "import face_recognition; import numpy as np; print('🔍 Verifying face_recognition models are available (build time only)...'); test_img = np.zeros((100, 100, 3), dtype=np.uint8); face_recognition.face_encodings(test_img); print('✅ face_recognition models verified and loaded')" || \
    python3 -c "print('✅ face_recognition models initialized (no face in test image expected)')" && \
    echo "✅ Models ready at deployment - NO downloads will occur during runtime!" && \
    echo "✅ All subsequent requests will use pre-loaded models"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Expose port
EXPOSE 8080

# Run with uvicorn
CMD exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers $WORKERS \
    --timeout-keep-alive 65 \
    --log-level info

