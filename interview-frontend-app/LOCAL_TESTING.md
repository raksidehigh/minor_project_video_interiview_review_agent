# 🧪 Local Testing Guide

Complete guide to test the entire stack locally: Frontend → Backend → Python Agent

---

## 📋 Prerequisites

1. **Service Account Key**
   ```bash
   # Ensure this file exists in project root
   ls ../service-account-key.json
   ```

2. **Environment Variables**
   ```bash
   # Set in your shell or create .env file
   export GOOGLE_APPLICATION_CREDENTIALS="../service-account-key.json"
   export GOOGLE_API_KEY="your_gemini_api_key"
   ```

---

## 🚀 Step 1: Start Python Agent API

```bash
# Terminal 1: Python Agent (Port 8000)
cd /Users/rakshit/Desktop/projects/minor_project_video_interiview_review_agent

# Install dependencies (if not done)
pip install -r requirements.txt

# Run the agent API
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Verify:** Open http://localhost:8000/docs

---

## 🔧 Step 2: Start Node.js Backend

```bash
# Terminal 2: Node.js Backend (Port 8080)
cd /Users/rakshit/Desktop/projects/minor_project_video_interiview_review_agent/interview-frontend-app/backend

# Install dependencies (first time only)
npm install

# Update API URL to local Python agent
# Edit server.js line 17:
# const ASSESSMENT_API_URL = 'http://localhost:8000/api/v1/assess';

# Start backend
node server.js
```

**Verify:** Backend should log "Server running on port 8080"

---

## 🎨 Step 3: Start Frontend

```bash
# Terminal 3: Frontend (Port 3000)
cd /Users/rakshit/Desktop/projects/minor_project_video_interiview_review_agent/interview-frontend-app/frontend

# Update API URL to local backend
# Edit script.js line 1:
# const API_URL = 'http://localhost:8080';

# Start simple HTTP server
python3 -m http.server 3000
```

**Verify:** Open http://localhost:3000

---

## 🧪 Step 4: Test the Flow

### Option A: Use the Web Interface

1. Open http://localhost:3000
2. Fill in personal info
3. Capture profile photo
4. Record 5 videos (intro + 4 questions)
5. Submit and wait for results

### Option B: Test Backend API Directly

```bash
# Create test files
mkdir -p /tmp/test-interview
# Add profile_photo.jpg and video files to /tmp/test-interview

# Test backend endpoint
curl -X POST http://localhost:8080/submit-interview \
  -F "name=John Doe" \
  -F "email=john@test.com" \
  -F "dob=1990-01-01" \
  -F "profile_photo=@/tmp/test-interview/profile.jpg" \
  -F "video_intro=@/tmp/test-interview/video1.webm" \
  -F "video_q1=@/tmp/test-interview/video2.webm" \
  -F "video_q2=@/tmp/test-interview/video3.webm" \
  -F "video_q3=@/tmp/test-interview/video4.webm" \
  -F "video_q4=@/tmp/test-interview/video5.webm"
```

### Option C: Test Python Agent Directly

```bash
# Test with existing GCS files
curl -X POST http://localhost:8000/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_123",
    "username": "John Doe"
  }'
```

---

## 🔍 Debugging Tips

### Check Logs

**Python Agent:**
```bash
# Watch logs in Terminal 1
# Logs show: Identity → Quality → Transcription → Content → Behavioral → Decision
```

**Node.js Backend:**
```bash
# Watch logs in Terminal 2
# Shows: File uploads → GCS upload → API call → Result save
```

**Frontend:**
```bash
# Open browser DevTools (F12)
# Check Console tab for errors
# Check Network tab for API calls
```

### Common Issues

**1. CORS Errors**
```bash
# Backend already has CORS enabled
# If issues persist, check browser console
```

**2. File Upload Fails**
```bash
# Check file sizes (videos should be < 100MB)
# Check GCS bucket permissions
```

**3. Python Agent Timeout**
```bash
# Assessment takes 30-60 seconds
# Increase timeout in backend server.js if needed
```

**4. Database Locked**
```bash
# Stop backend and delete interview.db
rm backend/interview.db
# Restart backend
```

---

## 📊 Check Results

### 1. SQLite Database
```bash
cd backend
sqlite3 interview.db

# View users
SELECT * FROM users;

# View assessments
SELECT id, user_id, created_at FROM assessments;

# Exit
.quit
```

### 2. GCS Bucket
```bash
# List uploaded files
gsutil ls gs://virtual-interview-agent/

# View specific user
gsutil ls gs://virtual-interview-agent/{user_id}/

# View results
gsutil ls gs://virtual-interview-agent/all-api-results/
```

### 3. API Response
Check the JSON response in browser DevTools or backend logs for:
- `decision`: PASS/REVIEW/FAIL
- `final_score`: 0-100
- `component_scores`: Identity, Quality, Content, Behavioral, Transcription
- `strengths`, `concerns`, `red_flags`

---

## 🛑 Stop All Services

```bash
# Terminal 1 (Python): Ctrl+C
# Terminal 2 (Node.js): Ctrl+C
# Terminal 3 (Frontend): Ctrl+C
```

---

## 🚀 Quick Start Script

Create `start-local.sh`:
```bash
#!/bin/bash

# Start Python agent in background
cd /Users/rakshit/Desktop/projects/minor_project_video_interiview_review_agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PYTHON_PID=$!

# Wait for Python to start
sleep 5

# Start Node.js backend in background
cd interview-frontend-app/backend
node server.js &
NODE_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
cd ../frontend
echo "🚀 All services started!"
echo "   Python Agent: http://localhost:8000/docs"
echo "   Backend API: http://localhost:8080"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services"
python3 -m http.server 3000

# Cleanup on exit
kill $PYTHON_PID $NODE_PID
```

```bash
chmod +x start-local.sh
./start-local.sh
```

---

**Happy Testing! 🎉**
