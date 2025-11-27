# 🎯 Video Interview Assessment API

AI-powered video interview evaluation system using **LangGraph** + **FastAPI** + **Google Cloud**.

Deployed on Google Cloud Run: [https://video-interview-api-urdy25bs2q-uc.a.run.app](https://video-interview-api-urdy25bs2q-uc.a.run.app)

---

## 🚀 Quick Start

```bash
# Set your API key
export GOOGLE_API_KEY="your_gemini_api_key"

# Deploy to Google Cloud Run
chmod +x deploy.sh
./deploy.sh

# Get your service URL
gcloud run services describe video-interview-api \
  --region us-central1 \
  --format 'value(status.url)'
```

**That's it!** Your API is live in ~10 minutes.

---

## 🏗️ Architecture

```
POST /api/v1/assess
        ↓
┌─────────────────────────────────────────────┐
│      LangGraph Multi-Agent System           │
│                                              │
│  1. Identity Verification (3-Layer)         │
│     • Name OCR from Government ID           │
│     • Face verification (profile + ID)      │
│     • 3/5 videos must pass                  │
│                                              │
│  2. [Video Quality + Transcription]         │
│     • Parallel processing                   │
│     • 5 videos per assessment               │
│                                              │
│  3. Content Evaluation                      │
│     • 5 hardcoded questions                 │
│     • Question-specific criteria            │
│     • Gemini LLM analysis                   │
│                                              │
│  4. Behavioral Analysis                     │
│     • Stress, confidence, engagement        │
│     • Red flag detection                    │
│                                              │
│  5. Decision Aggregation                    │
│     • Final Score = weighted sum            │
│     • PASS (≥75) | REVIEW (60-74) | FAIL    │
└─────────────────────────────────────────────┘
```

### Scoring Weights
- **Identity**: 25%
- **Quality**: 10%
- **Content**: 40%
- **Behavioral**: 15%
- **Transcription**: 10%

---

## 📡 API Usage

### ✨ Simplified API - Just Send user_id and username!

The API automatically discovers all files in your GCS bucket.

**Required GCS Structure:**
```
gs://virtual-interview-agent/
└── user_1/
    ├── profile_pic.jpg  (or .jpeg, .png)
    ├── gov_id.jpg       (or .jpeg, .png)
    ├── video1.webm      (or .mp4)
    ├── video2.webm
    ├── video3.webm
    ├── video4.webm
    └── video5.webm
```

### Request

```bash
curl -X POST "https://your-service-url.run.app/api/v1/assess" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_1",
    "username": "John Doe"
  }'
```

**That's it!** The API finds all files automatically.

### Response

```json
{
  "user_id": "user_001",
  "decision": "PASS",
  "final_score": 87.5,
  "component_scores": {
    "identity": 92.5,
    "quality": 88.0,
    "content": 86.0,
    "behavioral": 85.0,
    "transcription": 91.0
  },
  "reasoning": "Excellent candidate with strong academic background...",
  "recommendation": "PROCEED TO NEXT ROUND",
  "strengths": [
    "Strong identity verification: Name matched (98.5%), Face verified",
    "Excellent responses: 5/5 questions passed"
  ],
  "concerns": [],
  "red_flags": [],
  "processing_time_seconds": 45.2,
  "identity_verification_details": { },
  "content_evaluation_details": { }
}
```

### Check Files Before Assessment

```bash
# Verify files exist for a user
curl "https://your-service-url.run.app/api/v1/files/user_1"
```

**Response:**
```json
{
  "user_id": "user_1",
  "bucket": "virtual-interview-agent",
  "status": "ready",
  "files_found": {
    "profile_pic": "gs://virtual-interview-agent/user_1/profile_pic.jpeg",
    "gov_id": "gs://virtual-interview-agent/user_1/gov_id.jpeg",
    "videos": [
      "gs://virtual-interview-agent/user_1/video1.webm",
      "gs://virtual-interview-agent/user_1/video2.webm",
      "gs://virtual-interview-agent/user_1/video3.webm",
      "gs://virtual-interview-agent/user_1/video4.webm",
      "gs://virtual-interview-agent/user_1/video5.webm"
    ],
    "video_count": 5
  }
}
```

### Python Integration

```python
import requests

url = "https://your-service-url.run.app/api/v1/assess"

# Simple request - just user_id and name!
response = requests.post(url, json={
    "user_id": "user_1",
    "username": "John Doe"
}, timeout=600)

result = response.json()
print(f"{result['decision']}: {result['final_score']}/100")
```

---

## 📋 Interview Questions (Ambassador Program)

The system evaluates 5 specific questions:

### Question 1: Academic Background
**"Please introduce yourself and tell us about your academic background."**
- Must mention: Specific university + major/field
- Accepts any reputable university worldwide
- Clarity: <5% filler words

### Question 2: Motivation
**"What motivated you to apply for our Ambassador Program?"**
- Keywords: "help", "guide", "give back", "share"
- No self-centered reasons (money, resume)

### Question 3: Teaching Experience
**"Describe a time when you helped someone learn something new."**
- Must have: Problem → Action → Result
- Show empathy: "patience", "listened", "explained"

### Question 4: Handling Challenges
**"How do you handle challenging situations or difficult students?"**
- Positive actions: "listen", "understand", "solution"
- Red flags: No negative language

### Question 5: Mentor Goals
**"What are your goals as a mentor and how do you plan to achieve them?"**
- Action-oriented: "plan", "create", "organize"
- Specific plans: "weekly check-ins", etc.

---

## 💰 Cost Breakdown

### Per Assessment
| Service | Cost |
|---------|------|
| Cloud Run | $0.003 |
| Vision API (OCR) | $0.002 |
| Speech-to-Text | $0.120 |
| Cloud Storage | $0.000 |
| Gemini API | $0.000 |
| **Total** | **~$0.13** |

### Free Tier (Permanent)
- ✅ **Cloud Run**: 2M requests/month
- ✅ **Vision API**: 1,000 OCR calls/month
- ✅ **Speech-to-Text**: 60 minutes/month
- ✅ **Cloud Storage**: 5 GB/month
- ✅ **Gemini API**: 1,500 requests/day

### Monthly Costs
| Assessments | Cost |
|-------------|------|
| 100 | ~$10 |
| 500 | ~$60 |
| 2,000 | ~$240 |

**Note**: Speech-to-Text is 92% of costs. The first 12 assessments/month are FREE (60 min ÷ 5 min per assessment).

---

## 🛠️ Configuration

### Environment Variables

```bash
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

### Cloud Run Settings (Current)
- **Memory**: 8 GB
- **CPU**: 4 vCPUs
- **Timeout**: 600s (10 minutes)
- **Concurrency**: 2 requests per container
- **Max Concurrent Users**: 50 (2 per container × 25 containers)
- **Region**: asia-south1 (Mumbai)
- **Min Instances**: 0 (scales to zero)
- **Max Instances**: 25

### Modify Settings

```bash
gcloud run services update video-interview-api \
  --region us-central1 \
  --memory 4Gi \
  --cpu 4 \
  --timeout 600
```

---

## 📊 Monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail video-interview-api \
  --region us-central1

# Last 50 entries
gcloud run services logs read video-interview-api \
  --region us-central1 \
  --limit 50
```

### Cloud Console
- **Service Dashboard**: https://console.cloud.google.com/run
- **API Docs**: `https://your-service-url.run.app/docs`
- **Health Check**: `https://your-service-url.run.app/health`

---

## 🔧 Troubleshooting

### Timeout Errors
```bash
# Increase timeout to 10 minutes
gcloud run services update video-interview-api \
  --region us-central1 \
  --timeout 600
```

### Out of Memory
```bash
# Increase memory to 4GB
gcloud run services update video-interview-api \
  --region us-central1 \
  --memory 4Gi
```

### Environment Variable Issues
```bash
# Update API key
gcloud run services update video-interview-api \
  --region us-central1 \
  --set-env-vars "GOOGLE_API_KEY=your_key"
```

---

## 🔐 Security Best Practices

1. **Never commit secrets**
   - Add `.env` and `service-account-key.json` to `.gitignore`

2. **Use Secret Manager** (recommended)
   ```bash
   echo -n "your-api-key" | \
     gcloud secrets create gemini-api-key --data-file=-
   ```

3. **Add API authentication**
   ```python
   from fastapi import Header, HTTPException
   
   async def verify_api_key(x_api_key: str = Header(...)):
       if x_api_key != os.getenv("API_KEY"):
           raise HTTPException(401, "Invalid API Key")
   ```

4. **CORS Configuration**
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],
       allow_methods=["POST"],
       allow_headers=["Content-Type", "X-API-Key"]
   )
   ```

---

## 📚 Project Structure

```
video_interview_api/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   └── agents/
│       ├── __init__.py
│       ├── state.py               # State definitions
│       ├── graph.py               # LangGraph workflow
│       └── nodes/
│           ├── identity.py        # 3-layer identity verification
│           ├── quality.py         # Video quality assessment
│           ├── transcribe.py      # Speech-to-text
│           ├── content.py         # Question evaluation
│           ├── behavioral.py      # Behavioral analysis
│           └── aggregate.py       # Final decision
├── Dockerfile                     # Container definition
├── requirements.txt               # Python dependencies
├── deploy.sh                      # Deploy to Cloud Run
├── local_test.sh                  # Test locally
└── README.md                      # This file
```

---

## 🔄 Update & Redeploy

```bash
# Make changes to app/
# Then redeploy (rebuilds automatically)
./deploy.sh
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service video-interview-api --region us-central1

# Rollback
gcloud run services update-traffic video-interview-api \
  --region us-central1 \
  --to-revisions REVISION_NAME=100
```

---

## 🎉 What's Included

- ✅ **LangGraph** multi-agent orchestration
- ✅ **FastAPI** REST API with async support
- ✅ **3-Layer Identity Verification**
  - OCR name extraction from government ID
  - Dual reference face matching (profile + ID)
  - 3/5 video pass rate requirement
- ✅ **Question-Specific Evaluation**
  - 5 hardcoded Ambassador Program questions
  - LLM-based content analysis
  - Red flag detection
- ✅ **OpenCV + face_recognition** face matching (dlib-based)
- ✅ **Google Cloud Services**
  - Cloud Run (auto-scaling)
  - Vision API (OCR)
  - Speech-to-Text (transcription)
  - Cloud Storage (videos/images)
- ✅ **Cost-optimized** (~$0.13 per assessment)
- ✅ **Production-ready** with monitoring

---

## 📖 Further Reading

- **Deployment Guide**: See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed setup
- **API Documentation**: `https://your-service-url.run.app/docs`
- **Cloud Console**: https://console.cloud.google.com/run

---

**Built with** ❤️ **using LangGraph, FastAPI, and Google Cloud**
