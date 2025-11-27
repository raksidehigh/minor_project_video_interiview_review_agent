# 🔧 Troubleshooting Guide

## Issue 1: Files Not Uploading to GCS

### Test GCS Connection
```bash
cd backend
node test-gcs.js
```

**Expected output:**
```
✅ Credentials file found
✅ Storage client initialized
✅ Bucket virtual-interview-agent exists
✅ Test file uploaded
✅ Test file read
✅ Test file deleted
🎉 All GCS tests passed!
```

### Common Fixes

**1. Missing Credentials**
```bash
# Check file exists
ls ../../service-account-key.json

# If missing, download from Google Cloud Console:
# IAM & Admin → Service Accounts → Create Key (JSON)
```

**2. Wrong Bucket Name**
```bash
# Check bucket exists
gsutil ls gs://virtual-interview-agent/

# If not, create it:
gsutil mb -l asia-south1 gs://virtual-interview-agent/
```

**3. Permissions Issue**
```bash
# Grant Storage Admin role to service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

**4. Check Backend Logs**
```bash
# Start backend and watch logs
node server.js

# You should see:
# 📤 Uploading {userId}/profile_pic.jpg...
# ✅ Uploaded {userId}/profile_pic.jpg
# 📤 Uploading {userId}/video1.webm...
# ✅ Uploaded {userId}/video1.webm
```

---

## Issue 2: Questions Mismatch

### ✅ Fixed!

Frontend now shows the correct 5 questions:
1. How would you design a Video Streaming Platform Like YouTube.
2. Explain the Trade-offs Between Monolithic vs Microservices Architecture
3. How Would You Handle Authentication and Authorization in a Full Stack Application?
4. Describe Your Approach to Optimizing the Performance of a Slow Web Application
5. How Would You Design a Real-time Notification System?

These match exactly with the Python agent evaluation criteria.

---

## Issue 3: Assessment API Not Responding

### Check Python Agent is Running
```bash
# Should return 200 OK
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs
```

### Check Backend Can Reach Python Agent
```bash
# In backend server.js, check ASSESSMENT_API_URL
# For local testing: http://localhost:8000/api/v1/assess
# For production: https://your-cloud-run-url/api/v1/assess
```

### Test Direct API Call
```bash
# Test Python agent directly (requires files in GCS)
curl -X POST http://localhost:8000/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "username": "John Doe"
  }'
```

---

## Issue 4: Database Errors

### Reset Database
```bash
cd backend
rm interview.db
node server.js  # Will recreate tables
```

### Check Database Contents
```bash
sqlite3 interview.db

# View users
SELECT * FROM users;

# View assessments
SELECT id, user_id, created_at FROM assessments;

# Exit
.quit
```

---

## Issue 5: Frontend Not Sending Files

### Check Browser Console
1. Open DevTools (F12)
2. Go to Console tab
3. Look for errors during submission

### Check Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Submit interview
4. Look for `/submit-interview` request
5. Check:
   - Request payload has all files
   - Response status is 200
   - Response has `user_id` and `decision`

### Common Issues

**Video not recording:**
- Check camera permissions in browser
- Try different browser (Chrome recommended)
- Check MediaRecorder support

**File too large:**
- Videos should be < 100MB each
- Reduce recording time if needed

---

## Issue 6: CORS Errors

### Backend Already Has CORS Enabled
```javascript
// In server.js
app.use(cors());
```

### If Still Getting CORS Errors
1. Check frontend API_URL matches backend URL
2. Restart backend after changes
3. Clear browser cache

---

## Debug Checklist

### Before Testing
- [ ] Python agent running on port 8000
- [ ] Backend running on port 8080
- [ ] Frontend running on port 3000
- [ ] service-account-key.json exists
- [ ] GOOGLE_API_KEY set in environment
- [ ] GCS bucket exists and accessible

### During Testing
- [ ] Profile photo captured successfully
- [ ] All 5 videos recorded
- [ ] Backend logs show file uploads
- [ ] Python agent logs show assessment progress
- [ ] Results displayed in frontend

### After Testing
- [ ] Check SQLite database for user entry
- [ ] Check GCS bucket for uploaded files
- [ ] Check GCS all-api-results/ for JSON result

---

## Quick Verification Commands

```bash
# 1. Check all services running
lsof -i :8000  # Python agent
lsof -i :8080  # Backend
lsof -i :3000  # Frontend

# 2. Check GCS files for a user
gsutil ls gs://virtual-interview-agent/{user_id}/

# 3. Check assessment results
gsutil ls gs://virtual-interview-agent/all-api-results/

# 4. Download and view result
gsutil cat gs://virtual-interview-agent/all-api-results/{uuid}-{timestamp}.json | jq .

# 5. Check database
sqlite3 backend/interview.db "SELECT COUNT(*) FROM users;"
sqlite3 backend/interview.db "SELECT COUNT(*) FROM assessments;"
```

---

## Still Having Issues?

1. Check all logs (Python agent, Backend, Browser console)
2. Run `node backend/test-gcs.js` to verify GCS access
3. Test each component individually
4. Check firewall/network settings
5. Verify all environment variables are set

---

**Need Help?** Check the logs first - they usually tell you exactly what's wrong!
