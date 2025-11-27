# 📚 Comprehensive Documentation: Video Interview Review Agent

**Version:** 1.0.0  
**Last Updated:** October 2025  
**System:** Video Interview Assessment for Ambassador Program

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Current Flow Architecture](#current-flow-architecture)
3. [Evaluation Criteria](#evaluation-criteria)
4. [Weightages & Scoring](#weightages--scoring)
5. [Prompts Used](#prompts-used)
6. [Decision Logic](#decision-logic)
7. [Technical Details](#technical-details)
8. [Agent Specifications](#agent-specifications)

---

## System Overview

This is an AI-powered video interview assessment system that evaluates candidates for an Ambassador Program using a multi-agent LangGraph workflow. The system processes:
- **Profile picture** (for identity verification)
- **Government ID** (for name extraction and face verification)
- **5 Interview videos** (video_0 for identity/quality check, video_1-5 for interview questions)

### Key Components
- **FastAPI REST API** - Main entry point
- **LangGraph Workflow** - Multi-agent orchestration
- **Google Cloud Services** - Vision API, Speech-to-Text, Cloud Storage
- **face_recognition** - Facial recognition (dlib-based)
- **OpenCV** - Video quality analysis
- **Gemini LLM** - Content and behavioral analysis

---

## Current Flow Architecture

### Two Implementation Versions

#### 1. **Optimized Version** (Default - `graph_optimized.py`)

**4-Phase Architecture:**
```
Phase 1: PREPARATION (Resource Download)
├── Download profile_pic, gov_id, videos to isolated workspace
└── Prepare local file paths for all agents

Phase 2: SEMI-PARALLEL PROCESSING
├── Batch 1 (Parallel):
│   ├── Video Quality Assessment (OpenCV)
│   └── Speech-to-Text Transcription (Google Speech-to-Text)
└── Batch 2 (Sequential):
    └── Identity Verification (face_recognition - lightweight and thread-safe)

Phase 3: AGGREGATION
├── Batched Evaluation (Single Gemini call for Content + Behavioral)
└── Decision Aggregation (Weighted scoring + LLM reasoning)

Phase 4: CLEANUP (Mandatory)
└── Delete workspace files and verify cleanup
```

**Performance:**
- Processing time: **30-45 seconds** (vs 4-5 minutes in original)
- Memory usage: **2.5-3.5 GB** (vs 4.3 GB)
- Cost reduction: **83% cheaper**

#### 2. **Original Version** (Fallback - `graph.py`)

**Sequential LangGraph Workflow:**
```
START
  ↓
Agent 1: Identity Verification
  ↓
Agent 2: Video Quality Assessment
  ↓
Agent 3: Speech-to-Text Transcription
  ↓
Agent 4+5: Batched Evaluation (Content + Behavioral)
  ↓
Agent 6: Decision Aggregation
  ↓
END
```

**Note:** The optimized version is used by default, with automatic fallback to original if errors occur.

---

## Evaluation Criteria

### Agent 1: Identity Verification

**Purpose:** Verify candidate identity using 3-layer verification

**Criteria:**

1. **Name Verification (OCR)**
   - Extract text from government ID using Google Cloud Vision API
   - Heuristic-based name extraction from OCR text
   - Name matching with provided username
   - **Threshold:** 70% similarity required

2. **Face Verification**
   - Extract faces from profile_pic and gov_id
   - Compare both reference faces with frames from all 5 videos
   - Uses face_recognition library (dlib with ResNet-based encodings)
   - **Threshold:** At least 3 out of 5 videos must pass (60% pass rate)
   - **Similarity threshold:** 60% minimum average face confidence

3. **Overall Verification**
   - **Requires BOTH:**
     - Name match (≥70% similarity)
     - Face verification (≥3/5 videos pass AND ≥60% avg confidence)

**Output:**
```json
{
  "verified": bool,
  "confidence": float (0-100),
  "name_match": bool,
  "name_similarity": float (0-100),
  "extracted_name": str,
  "expected_name": str,
  "face_verified": bool,
  "face_verification_rate": float (0-100),
  "videos_passed": int,
  "videos_total": int,
  "avg_face_confidence": float (0-100),
  "video_results": [
    {
      "video_url": str,
      "video_index": int,
      "verified": bool,
      "similarity": float (0-100),
      "profile_pic_similarity": float,
      "gov_id_similarity": float,
      "best_match_source": "profile_pic" | "gov_id"
    }
  ],
  "red_flags": [str]
}
```

---

### Agent 2: Video Quality Assessment

**Purpose:** Assess technical quality of all videos

**Metrics Evaluated:**

1. **Resolution** (25% weight in quality score)
   - Minimum: 640x480
   - Score: `(width * height) / (1920 * 1080) * 100` (capped at 100)

2. **Frame Rate** (15% weight)
   - Minimum: 24 FPS
   - Score: `(fps / 30) * 100` (capped at 100)

3. **Brightness** (20% weight)
   - Optimal range: 80-180
   - Score: 100 if in range, otherwise penalized

4. **Sharpness** (20% weight)
   - Uses Laplacian variance
   - Minimum threshold: 100
   - Score: `(sharpness / 500) * 100` (capped at 100)

5. **Face Visibility** (20% weight)
   - Uses Haar Cascade face detection
   - Checks at 5 sample positions (0.2, 0.4, 0.5, 0.6, 0.8 of video)
   - Score: `(faces_detected / samples) * 100`

**Quality Score Formula:**
```
quality_score = (
    resolution_score * 0.25 +
    fps_score * 0.15 +
    brightness_score * 0.20 +
    sharpness_score * 0.20 +
    face_score * 0.20
)
```

**Issues Detected:**
- Low resolution (<640x480)
- Low frame rate (<24 FPS)
- Video too short (<5s) or too long (>300s)
- Too dark (<50 brightness) or too bright (>200)
- Blurry/out of focus (<100 sharpness)
- Poor face visibility (<60% of samples)
- Multiple people detected

**Pass Threshold:** Overall score ≥ 60/100

**Output:**
```json
{
  "quality_passed": bool,
  "overall_score": float (0-100),
  "video_analyses": [
    {
      "video_url": str,
      "video_index": int,
      "resolution": "WxH",
      "width": int,
      "height": int,
      "fps": float,
      "duration": float,
      "quality_score": float (0-100),
      "brightness": float,
      "sharpness": float,
      "face_visibility": float (0-100),
      "multiple_people": bool,
      "issues": [str]
    }
  ]
}
```

---

### Agent 3: Speech-to-Text Transcription

**Purpose:** Convert speech in videos to text for content analysis

**Technology:** Google Cloud Speech-to-Text API

**Configuration:**
- **Encoding:** FLAC
- **Sample Rate:** 16kHz
- **Channels:** Mono
- **Language:** en-IN (English - India)
- **Model:** Enhanced model with automatic punctuation
- **Features:** Word-level confidence scores

**Metrics Calculated:**
- Transcript text
- Average confidence (0-1)
- Word count per video
- Filler words count
- Speaking rate (words per second)

**Output:**
```json
{
  "transcription_complete": bool,
  "transcriptions": [
    {
      "video_url": str,
      "video_index": int,
      "transcript": str,
      "confidence": float (0-1),
      "word_count": int,
      "speaking_rate": float,
      "filler_words": int
    }
  ],
  "avg_confidence": float (0-1),
  "total_words": int
}
```

---

### Agent 4: Content Evaluation

**Purpose:** Evaluate interview responses based on question-specific criteria

**Evaluation Method:** Gemini 2.0 Flash (temperature: 0.3)

**Scoring Breakdown for Each Question:**
- **Answer Relevance:** 60% weight
- **Clarity:** 30% weight
- **Keywords/Content:** 10% weight

**Pass Threshold:** Score ≥ 70/100 per question

#### Question 1: Academic Background
**Question:** "Please introduce yourself and tell us about your academic background."

**Criteria:**
- **Content Check:** 
  - Must mention SPECIFIC university name (not vague references)
  - Must mention field of study/major
  - LLM determines if university is reputable
- **Clarity Check:**
  - Direct speech, free of excessive filler words
  - Threshold: <5% of words are fillers
- **Sentiment Check:**
  - Professional and confident (neutral to positive)

**Scoring:**
- Answer Relevance (60%): 60 if both university + major mentioned, 30 if one, 0 if neither
- Clarity (30%): 30 if fillers <5%, 15 if fillers <10, else 0
- Keywords (10%): 10 if positive/neutral sentiment, 5 otherwise

#### Question 2: Motivation
**Question:** "What motivated you to apply for our Ambassador Program?"

**Criteria:**
- **Content Check:**
  - Mission-aligned keywords: "help", "guide", "give back", "share my experience", "mentor", "support", etc.
  - Red flags: Self-centered keywords (money, salary, resume, CV, "for myself", "career boost")
- **Sentiment Check:**
  - Highly positive or positive sentiment
  - High or medium enthusiasm
  - Appears genuine
- **Sincerity Check:**
  - No self-centered motives detected

**Scoring:**
- Answer Relevance (60%): 60 if positive/genuine AND no red flags, 40 if genuine but moderate, 20 otherwise
- Clarity (30%): 30 if high/medium enthusiasm, 15 otherwise
- Keywords (10%): 10 if ≥2 mission keywords, 5 if 1, else 0

#### Question 3: Teaching Experience
**Question:** "Describe a time when you helped someone learn something new."

**Criteria:**
- **Content Check:**
  - Clear structure: Problem → Action → Result
  - Empathy keywords: "patience", "listened", "explained", "understood", "empathy", "relate"
- **Sentiment Check:**
  - Helpful and positive tone

**Scoring:**
- Answer Relevance (60%): 60 if structure complete AND positive, 40 if structure complete, 20 otherwise
- Clarity (30%): 30 if structure complete, 15 if action present, 0 otherwise
- Keywords (10%): 10 if empathy keywords found OR LLM confirms empathy, 5 otherwise

#### Question 4: Handling Challenges
**Question:** "How do you handle challenging situations or difficult students?"

**Criteria:**
- **Content Check:**
  - Positive actions: "listen", "understand", "empathize", "solution", "resolve", "communicate", "patient", "calm"
- **Red Flag Check:**
  - NO negative words: "lazy", "stupid", "dumb", "their fault", "blame them", "hopeless", "give up"
- **Sentiment Check:**
  - Calm and professional (neutral to positive)

**Scoring:**
- Answer Relevance (60%): 60 if calm/professional AND solution-oriented AND no red flags, 40 if solution-oriented, 20 otherwise
- Clarity (30%): 30 if calm/professional, 15 otherwise
- Keywords (10%): 10 if ≥2 positive actions, 5 if 1, else 0

#### Question 5: Mentor Goals
**Question:** "What are your goals as a mentor and how do you plan to achieve them?"

**Criteria:**
- **Content Check:**
  - Action-oriented words: "plan", "create", "organize", "develop", "implement", "build", "establish"
  - Specific actions: "weekly", "daily", "monthly", "check-in", "meeting", "resource", "guide"
- **Sentiment Check:**
  - Forward-looking, confident, aspirational
  - Has concrete plan

**Scoring:**
- Answer Relevance (60%): 60 if concrete plan AND forward-looking AND confident, 40 if concrete plan, 20 otherwise
- Clarity (30%): 30 if high/medium confidence, 15 otherwise
- Keywords (10%): 10 if ≥2 action words AND ≥1 specific action, 5 if ≥1 action word, else 0

**Overall Content Score:**
- Average of all 5 question scores
- Overall pass if ≥80% of questions passed (4/5)

**Output:**
```json
{
  "overall_score": float (0-100),
  "questions_passed": int,
  "questions_failed": int,
  "pass_rate": float (0-100),
  "summary": str,
  "question_evaluations": [
    {
      "question_number": int (1-5),
      "passed": bool,
      "score": float (0-100),
      "answer_relevance_score": float (0-60),
      "clarity_score": float (0-30),
      "keywords_score": float (0-10),
      "answer_relevance_passed": bool,
      "clarity_passed": bool,
      "keywords_passed": bool,
      "feedback": str
    }
  ]
}
```

---

### Agent 5: Behavioral Analysis

**Purpose:** Analyze non-verbal cues, confidence, engagement, and authenticity

**Technology:** Gemini 2.0 Flash (temperature: 0.3)

**Factors Analyzed:**
1. **Transcription Quality Impact:**
   - Average transcription confidence (indicates audio/speaking clarity)
   - Total filler words count (indicates nervousness or poor preparation)
   - Average speaking rate (indicates confidence and fluency)

2. **Emotional Consistency** (0-100)
   - Consistency of emotional state across all responses

3. **Confidence Level** (High/Medium/Low)
   - Based on transcription confidence and speaking rate

4. **Stress/Nervousness Indicators** (0-10 scale)
   - Based on filler words count

5. **Engagement Level** (High/Medium/Low)
   - Overall engagement in the interview

6. **Authenticity Score** (0-100)
   - Genuineness of responses

7. **Communication Clarity** (0-100)
   - Based on transcription confidence

**Behavioral Score Calculation:**
LLM provides a 0-100 behavioral score considering all factors above.

**Output:**
```json
{
  "behavioral_score": float (0-100),
  "confidence_level": "High" | "Medium" | "Low",
  "engagement_level": "High" | "Medium" | "Low",
  "stress_indicators": int (0-10),
  "authenticity_score": float (0-100),
  "communication_clarity": float (0-100),
  "overall_impression": str,
  "strengths": [str],
  "concerns": [str],
  "red_flags": [str],
  "transcription_metrics": {
    "avg_confidence": float,
    "filler_words": int,
    "speaking_rate": float
  }
}
```

---

## Weightages & Scoring

### Final Score Calculation

**NEW Weight Distribution (As per CTO requirements):**

| Component | Weight | Role |
|-----------|--------|------|
| **Content** | **70%** | Primary evaluation |
| **Behavioral** | **30%** | Secondary evaluation |
| **Identity** | **0%** | Gatekeeper only (must pass) |
| **Quality** | **0%** | Gatekeeper only (must pass) |
| **Transcription** | **0%** | Integrated into behavioral analysis |

**Formula:**
```
final_score = (content_score * 0.70) + (behavioral_score * 0.30)
```

**Component Scores:**
- **Identity:** Combined confidence score (name similarity 50% + face confidence 50%)
- **Quality:** Average quality score across all videos
- **Content:** Average score across all 5 questions
- **Behavioral:** LLM-generated behavioral score (0-100)
- **Transcription:** Average confidence from Speech-to-Text (0-100)

**Note:** Identity and Quality are gatekeepers but don't contribute to final score. They must pass minimum thresholds but don't directly affect the weighted calculation.

---

## Prompts Used

### 1. Content Evaluation Prompts

#### Question 1 Prompt (Academic Background)
```
Analyze this academic introduction and determine if the candidate clearly states their educational background:

"{transcript}"

Check for:
1. Does the candidate mention a SPECIFIC university name (not just "a top college" or "my university")?
2. Does the candidate mention their field of study/major/degree (e.g., Computer Science, Engineering, Business, etc.)?
3. What is the sentiment and professionalism level?

Return ONLY a JSON object:
{
  "mentions_specific_university": true|false,
  "university_name": "exact university name mentioned or null",
  "mentions_field_of_study": true|false,
  "field_of_study": "exact major/field mentioned or null",
  "sentiment": "positive|neutral|negative",
  "confidence_level": "high|medium|low",
  "is_professional": true|false,
  "appears_reputable": true|false
}

Note: Only set mentions_specific_university to true if an actual university name is stated, not vague references.
```

#### Question 2 Prompt (Motivation)
```
Analyze the emotional tone and sincerity of this motivation statement:

"{transcript}"

Return ONLY a JSON object:
{
  "sentiment": "highly_positive|positive|neutral|negative",
  "enthusiasm_level": "high|medium|low",
  "appears_genuine": true|false
}
```

#### Question 3 Prompt (Teaching Experience)
```
Analyze if this teaching story shows empathy and has a positive outcome:

"{transcript}"

Return ONLY a JSON object:
{
  "shows_empathy": true|false,
  "tone": "positive|neutral|negative",
  "has_clear_structure": true|false
}
```

#### Question 4 Prompt (Handling Challenges)
```
Analyze if this response shows maturity and professionalism:

"{transcript}"

Return ONLY a JSON object:
{
  "is_solution_oriented": true|false,
  "tone": "calm|frustrated|angry|professional",
  "blames_others": true|false
}
```

#### Question 5 Prompt (Mentor Goals)
```
Analyze if this goal statement is proactive and aspirational:

"{transcript}"

Return ONLY a JSON object:
{
  "is_forward_looking": true|false,
  "confidence_level": "high|medium|low",
  "has_concrete_plan": true|false
}
```

---

### 2. Behavioral Analysis Prompt

```
You are an expert behavioral psychologist analyzing interview behavior.

Based on the transcripts, speaking metrics, and transcription quality, analyze the candidate's behavioral patterns.

IMPORTANT: The behavioral score now includes transcription quality factors:
- Transcription confidence (indicates audio/speaking clarity)
- Filler words count (indicates nervousness or poor preparation)
- Speaking rate (indicates confidence and fluency)

Rate the following on 0-100:
- Emotional consistency
- Confidence level (consider transcription confidence and speaking rate)
- Stress/nervousness indicators (consider filler words)
- Engagement level
- Authenticity
- Speaking clarity (based on transcription confidence)

Return ONLY a JSON object:
{
  "behavioral_score": 82,
  "confidence_level": "High|Medium|Low",
  "emotional_consistency": 85,
  "stress_level": 25,
  "engagement": 88,
  "speaking_clarity": 90,
  "transcription_quality_impact": 5,
  "traits": ["confident", "articulate", "prepared"],
  "concerns": ["Minor signs of nervousness"],
  "summary": "Brief behavioral summary including speaking quality"
}
```

---

### 3. Batched Evaluation Prompt (Optimized - Single Call)

```
You are evaluating an Ambassador Program interview. Analyze ALL 5 questions and behavioral patterns in ONE response.

Identity Verified: {identity_status}, Confidence: {confidence}%

## INTERVIEW QUESTIONS & CRITERIA:
[Full question text with goals and criteria for all 5 questions]

## CANDIDATE RESPONSES (Transcripts):
[All 5 transcripts]

## YOUR TASK:
Evaluate EACH of the 5 questions based on their specific criteria, AND analyze behavioral patterns.

Return ONLY this JSON structure (no markdown, no explanation):

{
  "content_evaluation": {
    "overall_score": <0-100, average of all question scores>,
    "questions_passed": <count of questions with score >= 70>,
    "questions_failed": <count of questions with score < 70>,
    "pass_rate": <percentage of questions passed>,
    "summary": "<2-3 sentence summary>",
    "question_evaluations": [
      {
        "question_number": 1,
        "passed": <true/false, pass if score >= 70>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "university_found": "<university name or null>",
        "field_of_study": "<field or null>",
        "major_mentioned": <bool>,
        "appears_reputable": <bool>,
        "filler_words_excessive": <bool>,
        "sentiment": "<positive/neutral/negative>",
        "confidence_level": "<high/medium/low>",
        "feedback": "<1 sentence feedback>"
      },
      ... [similar structure for questions 2-5]
    ]
  },
  "behavioral_analysis": {
    "behavioral_score": <0-100>,
    "confidence_level": "<high/medium/low>",
    "engagement_level": "<high/medium/low>",
    "stress_indicators": <0-10 scale>,
    "authenticity_score": <0-100>,
    "communication_clarity": <0-100>,
    "overall_impression": "<2-3 sentences>",
    "strengths": [<behavioral strengths>],
    "concerns": [<behavioral concerns>],
    "red_flags": [<any red flags>]
  }
}

IMPORTANT:
- Be strict in evaluation
- Score >= 70 = Pass for individual questions
- Look for specific evidence in transcripts
- Red flags: self-centered motives, negative language, lack of empathy
- Return ONLY valid JSON, no markdown formatting
```

---

### 4. Decision Aggregation Prompt

```
You are a hiring decision expert. Based on the assessment data, provide:
1. Clear reasoning for the decision
2. Key strengths of the candidate
3. Areas of concern (if any)
4. Final recommendation

Keep it professional and concise (3-4 sentences).
```

**Input Data:**
```json
{
  "decision": "PASS|REVIEW|FAIL",
  "final_score": float,
  "component_scores": {
    "identity": float,
    "quality": float,
    "content": float,
    "behavioral": float,
    "transcription": float
  },
  "identity_verified": bool,
  "content_summary": str,
  "behavioral_summary": str
}
```

---

## Decision Logic

### Decision Thresholds

| Final Score | Decision | Recommendation |
|-------------|----------|----------------|
| **≥ 70** | **PASS** | "PROCEED TO NEXT ROUND - Strong candidate" |
| **60-69** | **REVIEW** | "MANUAL REVIEW REQUIRED - Borderline case" |
| **< 60** | **FAIL** | "REJECT - Insufficient scores" |

### Gatekeeper Requirements

**Identity Verification:**
- **Must Pass:** Name match (≥70% similarity) AND Face verification (≥3/5 videos pass)
- **Impact:** Identity failure triggers webhook notification but doesn't auto-fail (decision based on score)
- **Red Flags Generated:** If failed, generates `IDENTITY_VERIFICATION_FAILED`, `NAME_MISMATCH`, `FACE_VERIFICATION_FAILED`

**Video Quality:**
- **Minimum Threshold:** Overall quality score ≥ 60/100
- **Impact:** Poor quality flagged but doesn't block decision (score-based)
- **Red Flags Generated:** If score < 50, generates `POOR_VIDEO_QUALITY`, `POOR_FACE_VISIBILITY`

### Red Flags System

**Identity Red Flags:**
- `IDENTITY_VERIFICATION_FAILED`
- `NAME_MISMATCH`
- `FACE_VERIFICATION_FAILED`
- `LOW_SIMILARITY_SCORE`
- `AGE_DISCREPANCY` (if detected)
- `GENDER_MISMATCH` (if detected)

**Content Red Flags:**
- `ALL_QUESTIONS_FAILED` (if 0/5 passed)
- `MOSTLY_FAILED_QUESTIONS` (if content score < 40)

**Behavioral Red Flags:**
- `INAPPROPRIATE_EMOTIONAL_STATE` (if behavioral score < 30)

**Quality Red Flags:**
- `POOR_VIDEO_QUALITY` (if score < 50)
- `POOR_FACE_VISIBILITY` (if face visibility < 50%)

### Strengths & Concerns Generation

**Strengths (Auto-generated):**
- Strong identity verification (if identity ≥ 80% and name + face verified)
- Excellent responses (if content ≥ 85 and questions_passed ≥ 4)
- High confidence and engagement (if behavioral ≥ 85)
- High-quality audio (if transcription ≥ 90%)

**Concerns (Auto-generated):**
- Name mismatch details (if identity failed)
- Face verification failure (if face verification failed)
- Poor responses (if content < 40 or questions_passed = 0)
- Inconsistent responses (if content < 70)
- Behavioral indicators below expectations (if behavioral < 70)
- Poor audio quality (if transcription < 70%)

---

## Technical Details

### File Structure Expected

**GCS Bucket Structure:**
```
gs://virtual-interview-agent/
└── {user_id}/
    ├── profile_images/
    │   └── [UUID]/profile_pic.jpg (or .jpeg, .png)
    ├── documents/
    │   └── gov_id/
    │       └── [UUID]/gov_id.jpg (or .jpeg, .png)
    └── interview_videos/
        ├── video_0.webm (for identity/quality check)
        ├── video_1.webm (Question 1)
        ├── video_2.webm (Question 2)
        ├── video_3.webm (Question 3)
        ├── video_4.webm (Question 4)
        └── video_5.webm (Question 5)
```

**Note:** Also supports flat structure (files directly under user_id/)

### Environment Variables

```bash
GOOGLE_API_KEY=<gemini-api-key>
GOOGLE_APPLICATION_CREDENTIALS=<path-to-service-account-key.json>
USE_OPTIMIZED=true  # Default: true (use optimized pipeline)
```

### API Configuration

**Model Used:**
- **Gemini 2.0 Flash Experimental** (`gemini-2.0-flash-exp`)
- **Temperature:** 0.3 (for consistency)
- **Language:** English (India) - `en-IN`

**Google Cloud Services:**
- **Vision API:** OCR text extraction from government ID
- **Speech-to-Text API:** Audio transcription with word-level confidence
- **Cloud Storage:** File storage and retrieval
- **Cloud Run:** Container hosting

**face_recognition Configuration:**
- **Model:** dlib ResNet (128-dimensional face encodings)
- **Detector:** HOG + Linear SVM (dlib)
- **Threshold:** 0.6 distance (with 2% tolerance = 0.612)
- **Anti-Spoofing:** False

**OpenCV Video Analysis:**
- **Face Detection:** Haar Cascade (`haarcascade_frontalface_default.xml`)
- **Sampling:** 5 positions per video (20%, 40%, 50%, 60%, 80%)
- **Sharpness:** Laplacian variance calculation

---

## Agent Specifications

### Agent 1: Identity Verification

**Input:**
- `profile_pic_url` (GCS URL)
- `gov_id_url` (GCS URL)
- `video_urls` (list of 5 GCS URLs)
- `username` (expected name)

**Process:**
1. Download profile_pic and gov_id
2. Extract text from gov_id using Vision API OCR
3. Extract name from OCR text using heuristics
4. Compare extracted name with username (≥70% similarity required)
5. Extract middle frame from each video (streams via signed URL)
6. Compare profile_pic face with each video frame (face_recognition)
7. Compare gov_id face with each video frame (face_recognition)
8. Take best match between profile_pic and gov_id for each video
9. Require ≥3/5 videos pass with ≥60% average confidence

**Output:** Identity verification results with confidence scores

---

### Agent 2: Video Quality Assessment

**Input:**
- `video_urls` (list of 5 GCS URLs)

**Process:**
1. Stream each video from signed URL (no download)
2. Extract properties: resolution, FPS, duration
3. Sample 5 frames at different positions
4. Calculate brightness, sharpness, face visibility per frame
5. Detect issues (low res, low FPS, blur, dark, bright, multiple people)
6. Calculate quality score per video (weighted formula)
7. Average scores across all videos

**Output:** Quality scores and issues per video

---

### Agent 3: Speech-to-Text Transcription

**Input:**
- `video_urls` (list of 5 GCS URLs)

**Process:**
1. Stream each video from signed URL
2. Extract audio using FFmpeg (converts to FLAC, 16kHz, mono)
3. Transcribe using Google Speech-to-Text API
4. Calculate metrics: confidence, word count, filler words, speaking rate
5. Aggregate across all videos

**Output:** Transcripts with confidence scores and metrics

---

### Agent 4: Content Evaluation

**Input:**
- `transcriptions` (all 5 transcripts)
- `interview_questions` (5 questions with criteria)

**Process:**
1. For each question:
   - Extract relevant transcript
   - Analyze using question-specific prompt
   - Calculate score: 60% answer relevance + 30% clarity + 10% keywords
   - Determine pass (≥70) or fail
2. Calculate overall score (average of all questions)
3. Count questions passed/failed

**Output:** Question-level and overall content evaluation

---

### Agent 5: Behavioral Analysis

**Input:**
- `transcriptions` (with confidence, filler words, speaking rate)
- `identity_verification` (confidence context)

**Process:**
1. Aggregate transcription metrics:
   - Average confidence
   - Total filler words
   - Average speaking rate
2. Analyze behavioral patterns using Gemini LLM
3. Generate behavioral score (0-100)
4. Identify strengths, concerns, red flags

**Output:** Behavioral analysis with score and insights

---

### Agent 6: Decision Aggregation

**Input:**
- All previous agent results

**Process:**
1. Calculate weighted final score:
   - Content: 70%
   - Behavioral: 30%
2. Determine decision (PASS/REVIEW/FAIL) based on thresholds
3. Generate reasoning using Gemini LLM
4. Collect strengths and concerns from all agents
5. Generate red flags list
6. Create recommendation

**Output:** Final decision with complete assessment details

---

## Performance Metrics

### Optimized Version
- **Processing Time:** 30-45 seconds per assessment
- **Memory Usage:** 2.5-3.5 GB
- **Cost:** ~$0.13 per assessment (83% reduction)
- **API Calls:** 1 Gemini call (batched) vs 6-7 in original

### Original Version
- **Processing Time:** 4-5 minutes per assessment
- **Memory Usage:** 4.3 GB
- **Cost:** ~$0.78 per assessment

---

## Error Handling

### Graceful Degradation
- If optimized version fails, automatic fallback to original
- Individual agent failures don't stop the workflow
- Missing data uses default/fallback values
- All errors collected in `state['errors']` array

### Cleanup
- Mandatory workspace cleanup before response
- Temporary files deleted after each agent
- Verified cleanup to prevent disk space issues

---

## Conclusion

This comprehensive documentation covers:
- ✅ Current flow architecture (optimized and original)
- ✅ All evaluation criteria for each agent
- ✅ Weightages and scoring formulas
- ✅ All prompts used in LLM evaluations
- ✅ Decision logic and thresholds
- ✅ Technical implementation details
- ✅ Agent specifications and processes

**For questions or updates, refer to the codebase or contact the development team.**

