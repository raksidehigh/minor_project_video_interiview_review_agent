# Quick Deployment Guide - Prompt Changes

## What Changed?

Updated all evaluation prompts from **Ambassador Program** to **Full Stack Developer Technical Interview**.

## Files Modified

✅ `app/agents/nodes/content.py` - All 5 question evaluations  
✅ `app/agents/nodes/batched_evaluation.py` - Batched prompt template  
✅ `app/agents/nodes/behavioral.py` - Behavioral analysis prompt  

## Deploy to Cloud Run

```bash
# From project root
./deploy_new.sh
```

This will:
1. Build new Docker image with updated prompts
2. Deploy to Google Cloud Run (Mumbai region)
3. Update the running service with zero downtime

## Test Locally (Optional)

```bash
# Start local development environment
cd interview-frontend-app
./start-local.sh

# Access at http://localhost:3000
```

## Verify Deployment

```bash
# Check service health
curl https://YOUR_SERVICE_URL/health

# Check logs for prompt updates
gcloud run services logs read video-interview-api \
  --region asia-south1 \
  --limit 50 | grep "CONTENT\|BEHAVIORAL"
```

## Expected Behavior

### Question 1: System Design
- Should evaluate: architecture, components (upload, storage, CDN, database)
- Pass threshold: 60/100
- Looks for: scalability discussion, structured approach

### Question 2: Architecture Comparison
- Should evaluate: monolithic vs microservices trade-offs
- Pass threshold: 60/100
- Looks for: pros/cons, context-dependent reasoning

### Question 3: Auth/AuthZ
- Should evaluate: authentication vs authorization distinction
- Pass threshold: 60/100
- Looks for: JWT, sessions, RBAC, security practices

### Question 4: Performance Optimization
- Should evaluate: systematic approach (measure → optimize)
- Pass threshold: 60/100
- Looks for: profiling, caching, multi-layer optimization

### Question 5: Real-time System
- Should evaluate: technology choice (WebSockets/SSE)
- Pass threshold: 60/100
- Looks for: architecture, reliability, scalability

### Behavioral Analysis
- Base score: 70/100 (was 80/100)
- Focus: technical communication, problem-solving approach
- New field: `problem_solving_approach`

## Rollback (If Needed)

```bash
# List previous revisions
gcloud run revisions list --service video-interview-api --region asia-south1

# Rollback to previous revision
gcloud run services update-traffic video-interview-api \
  --region asia-south1 \
  --to-revisions PREVIOUS_REVISION=100
```

## Monitoring

```bash
# Watch for errors
gcloud logging read "severity>=ERROR AND resource.type=cloud_run_revision" \
  --project YOUR_PROJECT_ID \
  --limit 20 \
  --format json

# Monitor assessment results
gcloud logging read "textPayload:'CONTENT' OR textPayload:'BEHAVIORAL'" \
  --project YOUR_PROJECT_ID \
  --limit 50
```

## Support

For issues or questions, check:
- `PROMPT_CHANGES_SUMMARY.md` - Detailed change documentation
- `README.md` - Full system documentation
- Logs: `gcloud run services logs read video-interview-api --region asia-south1`

---

**Deployment Time:** ~5-10 minutes  
**Downtime:** Zero (rolling update)  
**Rollback Time:** ~30 seconds
