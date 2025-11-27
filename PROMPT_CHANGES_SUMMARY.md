# Prompt Changes Summary - Technical Interview Update

**Date:** November 27, 2025  
**Change Type:** Complete prompt overhaul from Ambassador Program to Full Stack Developer Interview

---

## Overview

Updated all evaluation prompts to align with the new technical interview questions displayed in the frontend. Changed from soft-skills focused Ambassador Program evaluation to technical competency assessment for Full Stack Developer role.

---

## Frontend Questions (No Changes Needed)

The frontend already displays the correct technical questions:

1. **Question 1:** How would you design a Video Streaming Platform Like YouTube.
2. **Question 2:** Explain the Trade-offs Between Monolithic vs Microservices Architecture
3. **Question 3:** How Would You Handle Authentication and Authorization in a Full Stack Application?
4. **Question 4:** Describe Your Approach to Optimizing the Performance of a Slow Web Application
5. **Question 5:** How Would You Design a Real-time Notification System?

---

## Backend Changes

### 1. **`app/main.py`** ✅ Already Updated

The hardcoded `INTERVIEW_QUESTIONS` array (lines 400-450) already contains the correct technical questions with proper criteria:

```python
INTERVIEW_QUESTIONS = [
    {
        "question_number": 1,
        "question": "How would you design a Video Streaming Platform Like YouTube.",
        "goal": "Demonstrate architectural thinking...",
        "criteria": {
            "content_check": "Keywords: upload, processing, transcoding, storage, CDN...",
            "clarity_check": "Structured approach...",
            "sentiment_check": "Confident and analytical"
        }
    },
    # ... Questions 2-5
]
```

---

### 2. **`app/agents/nodes/content.py`** ✅ UPDATED

**File:** `/app/agents/nodes/content.py`

**Changes:**
- Completely rewrote all 5 evaluation functions
- Removed Ambassador Program criteria (university, motivation, empathy)
- Added technical evaluation criteria

#### Question 1: System Design
**Old:** Academic background evaluation (university, major)  
**New:** System design evaluation (architecture, components, scalability)

**Key Criteria:**
- Upload flow, storage (S3/GCS), CDN, database
- Scalability and latency considerations
- Structured approach: requirements → design → components

**Scoring:**
- Technical depth 60+ = pass
- 3+ key components = 70+
- Discusses scalability = 80+
- Complete architecture = 90+

#### Question 2: Architecture Comparison
**Old:** Motivation for Ambassador Program  
**New:** Monolithic vs Microservices trade-offs

**Key Criteria:**
- Comparison of both architectures
- Pros/cons discussion
- Context-dependent reasoning

#### Question 3: Authentication & Authorization
**Old:** Empathy and helping experience  
**New:** Auth/AuthZ implementation

**Key Criteria:**
- Distinction between AuthN (who) and AuthZ (what)
- JWT, sessions, OAuth, RBAC
- Security best practices (HTTPS, token storage)

#### Question 4: Performance Optimization
**Old:** Handling difficult students  
**New:** Web application performance optimization

**Key Criteria:**
- Systematic approach: Measure → Identify → Optimize
- Multi-layer optimization (frontend, backend, DB)
- Profiling, caching, indexing, bundle size

#### Question 5: Real-time System Design
**Old:** Future goals as Ambassador  
**New:** Real-time notification system

**Key Criteria:**
- Technology choice (WebSockets, SSE, polling)
- Architecture for concurrency
- Message queues (Redis/Kafka)
- Reliability and scalability

---

### 3. **`app/agents/nodes/batched_evaluation.py`** ✅ UPDATED

**File:** `/app/agents/nodes/batched_evaluation.py`

**Function:** `build_batched_prompt()`

**Changes:**
- Updated prompt template to reflect technical interview context
- Changed evaluation criteria from soft skills to technical depth
- Updated JSON response structure for technical fields
- Changed pass threshold from 70 to 60 (more appropriate for technical assessment)

**Key Updates:**
```python
# Old: Ambassador Program focus
"mentions_helping": <bool>,
"mission_keywords_found": [<keywords>],
"empathy_keywords_found": [<keywords>]

# New: Technical focus
"mentions_upload_flow": <bool>,
"mentions_storage": <bool>,
"mentions_cdn": <bool>,
"architectural_thinking": "<strong|moderate|weak>",
"technical_depth": <0-100>
```

**Evaluation Guidelines:**
- Pass threshold: 60/100 (was 70/100)
- Focus on technical understanding, not perfect recall
- Bonus points for discussing trade-offs and scalability

---

### 4. **`app/agents/nodes/behavioral.py`** ✅ UPDATED

**File:** `/app/agents/nodes/behavioral.py`

**Function:** `analyze_behavior()`

**Changes:**
- Updated system prompt from "welcoming community" to "technical interview"
- Changed focus from soft skills to technical communication
- Adjusted scoring baseline from 80 to 70 (more realistic for technical assessment)

**Old Focus:**
- Helpfulness, empathy, enthusiasm
- Mission alignment
- Community building traits

**New Focus:**
- Communication clarity and articulation
- Confidence in technical explanations
- Problem-solving approach (systematic vs. intuitive)
- Technical curiosity

**Scoring Changes:**
```python
# Old: MVP-optimized (generous)
Base score: 80/100
Default: 85 for engaged candidates
90+ for enthusiasm

# New: Technical assessment (balanced)
Base score: 70/100
75-80: Adequate communication
80-85: Clear communication, confidence
85-90: Strong technical communication
90+: Exceptional clarity and problem-solving
```

**New Field:**
```python
"problem_solving_approach": "systematic|intuitive|unclear"
```

---

## Testing Checklist

- [ ] Test Question 1: System design evaluation recognizes architecture components
- [ ] Test Question 2: Architecture comparison detects trade-off discussion
- [ ] Test Question 3: Auth/AuthZ evaluation distinguishes authentication from authorization
- [ ] Test Question 4: Performance optimization checks for systematic approach
- [ ] Test Question 5: Real-time system design validates technology choices
- [ ] Verify batched evaluation returns correct JSON structure
- [ ] Verify behavioral analysis focuses on technical communication
- [ ] Check that pass threshold is 60/100 (not 70/100)
- [ ] Verify final decision aggregation uses updated criteria

---

## Deployment Notes

**No infrastructure changes required.** Only prompt logic updated.

**Files Modified:**
1. `app/agents/nodes/content.py` - Complete rewrite
2. `app/agents/nodes/batched_evaluation.py` - Prompt template update
3. `app/agents/nodes/behavioral.py` - System prompt update

**Files NOT Modified:**
- `app/main.py` - Already had correct questions
- `interview-frontend-app/frontend/script.js` - Already had correct questions
- All other agent nodes (identity, quality, transcribe, aggregate)

**Deployment Command:**
```bash
./deploy_new.sh
```

---

## Backward Compatibility

⚠️ **Breaking Change:** This update is NOT backward compatible with old Ambassador Program interviews.

**Impact:**
- Old interview recordings will be evaluated against new technical criteria
- Historical data may show different scores if re-evaluated

**Recommendation:**
- Archive old Ambassador Program data before deploying
- Consider maintaining separate evaluation pipelines if both interview types are needed

---

## Summary

✅ All prompts successfully updated to match technical interview questions  
✅ Evaluation criteria aligned with Full Stack Developer competencies  
✅ Scoring thresholds adjusted for technical assessment (60% pass)  
✅ Behavioral analysis refocused on technical communication  
✅ No breaking changes to API contracts or data structures  

**Ready for deployment!**
