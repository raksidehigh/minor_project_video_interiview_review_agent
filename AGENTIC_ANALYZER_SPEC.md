## Agentic Video Interview Analyzer — Comprehensive Specification

This document explains the end‑to‑end flow, inputs/outputs, prompts, evaluation criteria, thresholds, weightages, decision logic, and expectations for the Agentic Video Interview Analyzer used for the Ambassador Program assessments.

Audience: Engineering, Product, and Leadership stakeholders. Use this to review design, tune thresholds/weights, and provide feedback.


## 1) High‑Level Overview

- **Goal**: Automatically assess candidate video interviews across identity verification, technical video quality, speech transcription, content quality, behavioral signals, and aggregate to a pass/review/fail decision with transparent reasoning.
- **Core Components (Agents)**:
  - Identity Verification (OCR + name match + face match)
  - Video Quality Assessment (OpenCV-based metrics)
  - Speech-to-Text Transcription (Google Cloud Speech-to-Text)
  - Batched Content + Behavioral Evaluation (single Gemini call)
  - Decision Aggregation (weighting + thresholds + LLM rationale)
- **Optimization**: Two execution modes
  - Sequential LangGraph workflow (`app/agents/graph.py`)
  - Optimized semi‑parallel workflow (`app/agents/graph_optimized.py`)


## 2) Execution Flow

### 2.1 Sequential Flow (default)
Order: Identity → Quality → Transcription → Batched Evaluation (Content + Behavioral) → Aggregation

```1:83:app/agents/graph.py
# START → verify_identity → check_quality → transcribe_videos → batched_evaluation → aggregate_decision → END
```

Notes:
- All agents run regardless of identity success to collect full evidence (fraud detection and transparency).
- Batched evaluation consolidates multiple LLM calls into a single call.

### 2.2 Optimized Flow (30–45s typical)
Phases: Preparation → Semi‑parallel processing → Batched evaluation → Aggregation → Cleanup

```81:150:app/agents/graph_optimized.py
# Phase 2: Quality + Transcription in parallel, then Identity; merge results; run batched evaluation; aggregate decision
```


## 3) Inputs — What the System Expects

Required per assessment (see `InterviewState`):
- `user_id` (string)
- `username` (string; candidate’s full name for name matching)
- `profile_pic_url` (GCS URL)
- `gov_id_url` (GCS URL)
- `video_urls` (list of 5 videos):
  - `video_0`: identity check video
  - `video_1`–`video_5`: interview question responses
- `interview_questions` (list of 5 dicts): each has `question_number`, `question`, `goal`, `criteria`

```30:83:app/agents/state.py
class InterviewState(TypedDict):
    # inputs, questions, and agent outputs schema
```

### 3.1 Detailed Data Contracts (InterviewState fields)

- Inputs
  - `user_id: str`
  - `username: str`
  - `profile_pic_url: str` (gs:// or signed URL)
  - `gov_id_url: str` (gs:// or signed URL)
  - `video_urls: List[str]` (index 0 = identity, 1–5 = interview)
  - `interview_questions: List[Dict]` (5 entries)

- Outputs
  - `identity_verification: Dict | None`
    - `verified: bool`, `confidence: float`, `name_match: bool`, `name_similarity: float`, `extracted_name: str`, `expected_name: str`, `face_verified: bool`, `face_verification_rate: float`, `videos_passed: int`, `videos_total: int`, `avg_face_confidence: float`, `video_results: List[Dict]`, `red_flags: List[str]`, `ocr_text: str(≤500)`
  - `video_quality: Dict | None`
    - `quality_passed: bool`, `overall_score: float`, `video_analyses: List[Dict]`
  - `transcriptions: Dict | None`
    - `transcription_complete: bool`, `transcriptions: List[TranscriptionResult]`, `avg_confidence: float`, `total_words: int`
  - `content_evaluation: Dict | None`
    - `overall_score: float`, `questions_passed: int`, `questions_failed: int`, `pass_rate: float?`, `summary: str?`, `question_evaluations: List[Dict]`
  - `behavioral_analysis: Dict | None`
    - `behavioral_score: float`, plus qualitative fields (confidence/engagement/stress/authenticity/clarity/strengths/concerns/red_flags/overall_impression)
  - `final_decision: Dict | None`
    - `decision: "PASS"|"REVIEW"|"FAIL"`, `final_score: float`, `confidence_level: str`, `component_scores: Dict`, `weighted_breakdown: Dict`, `reasoning: str`, `recommendation: str`, `strengths: List[str]`, `concerns: List[str]`, `red_flags: List[str]`
  - Control & meta: `should_continue: bool`, `current_stage: str`, `errors: List[str]`, `started_at: str`, `completed_at: str | None`, `processing_time_seconds: float | None`

### 3.2 Example interview_questions payload (5 items)

```json
[
  {
    "question_number": 1,
    "question": "Please introduce yourself and tell us about your academic background.",
    "goal": "Confirm presence of academic background and professionalism.",
    "criteria": {
      "content_check": "Mentions any educational institution and field of study (lenient).",
      "clarity_check": "Not excessive filler words.",
      "sentiment_check": "Neutral to positive, professional tone."
    }
  },
  {
    "question_number": 2,
    "question": "Why do you want to join the Ambassador Program?",
    "goal": "Assess motivation and alignment.",
    "criteria": {
      "content_check": "Genuine motivation; mission-aligned keywords helpful but lenient.",
      "clarity_check": "Coherent, reasonable pacing.",
      "sentiment_check": "Positive or neutral acceptable."
    }
  },
  {
    "question_number": 3,
    "question": "Describe a time you helped someone learn something difficult.",
    "goal": "Empathy and structure (problem-action-result).",
    "criteria": {
      "content_check": "Some structure or explicit action.",
      "clarity_check": "Story understandable.",
      "sentiment_check": "Neutral/positive acceptable."
    }
  },
  {
    "question_number": 4,
    "question": "How do you handle challenging situations or feedback?",
    "goal": "Solution-orientation and tone.",
    "criteria": {
      "content_check": "Positive actions; avoid negative/red-flag language.",
      "clarity_check": "Professional or calm tone acceptable.",
      "sentiment_check": "No blaming; red flags discouraged."
    }
  },
  {
    "question_number": 5,
    "question": "What specific steps would you take in your first month as an Ambassador?",
    "goal": "Forward-looking, concrete planning.",
    "criteria": {
      "content_check": "Action words and specific cadence (weekly/daily) helpful.",
      "clarity_check": "Coherent steps; feasibility.",
      "sentiment_check": "Neutral/positive; confidence reasonable."
    }
  }
]
```


## 4) Agent Nodes — Details, Criteria, Thresholds

### 4.1 Identity Verification
- Components:
  - OCR on government ID via Google Vision to extract text and heuristic name (`extract_text_from_image`, `extract_name_from_text`).
  - Name similarity to provided `username` with multi‑step matching.
    - Threshold: name similarity ≥ 50% considered match.
  - Face match using DeepFace (ArcFace) between `profile_pic` and a frame extracted from `video_0`.
    - Face verified if similarity ≥ 60% (lenient threshold logic).
  - Overall identity verified only if both name_match and face_verified are true.
- Confidence score: 50% name similarity + 50% face similarity.
- Failure does not block evaluation; it produces red flags and affects concerns in aggregation.

Key thresholds and logic:
- Name match threshold: 50% similarity.
- Face verified: average similarity ≥ 60% on `video_0` check.
- Combined identity confidence = 0.5 × name_similarity + 0.5 × avg_face_confidence.

```487:638:app/agents/nodes/identity.py
# Name similarity ≥ 50%; face verification on video_0; overall verified requires both
```

Red flags captured (examples):
- Name mismatch, low similarity, face verification failure, extraction errors.

Scoring & algorithm details:
- Name similarity (`calculate_name_similarity`):
  - Exact/substring match check against full OCR text → 100% if found.
  - Word-by-word truncated matching: each expected name word is truncated progressively; if truncated form appears in OCR text, it counts toward match ratio; match% = matched_words / total_words × 100; if > 50%, accept this as similarity.
  - Fallback: `difflib.SequenceMatcher` similarity with boost if one name is subset of the other.
- Face similarity (`verify_face_match`):
  - ArcFace distance compared against threshold; lenient check uses 1.02× threshold; similarity displayed as `(1 - distance/threshold) × 100`, normalized with floor/guard rails.
- Combined confidence = 0.5 × name_similarity + 0.5 × avg_face_confidence.

### 4.2 Video Quality Assessment
- Metrics (sampled frames via OpenCV): resolution, fps, duration, brightness, sharpness (Laplacian variance), face visibility ratio, multiple faces.
- Issues flagged only for: "Blurry/out of focus" and "Poor face visibility".
- Quality score (0–100) weighted:
  - Resolution 25%, FPS 15%, Brightness 20%, Sharpness 20%, Face visibility 20%.
- Pass criterion: overall quality score ≥ 60.

Formulas:
- Resolution score = min(100, width×height / (1920×1080) × 100)
- FPS score = min(100, fps/30 × 100)
- Brightness score = 100 if 80 ≤ avg_brightness ≤ 180 else max(0, 100 − |avg_brightness − 130|)
- Sharpness score = min(100, avg_laplacian_var/500 × 100)
- Face visibility = detected_face_frames/sample_frames × 100
- Overall quality = 0.25×resolution + 0.15×fps + 0.20×brightness + 0.20×sharpness + 0.20×face

```90:184:app/agents/nodes/quality.py
# Scoring weights; pass if overall_score ≥ 60
```

### 4.3 Speech-to-Text Transcription
- Google Cloud Speech-to-Text, FLAC 16kHz mono.
- Auto‑selects LongRunningRecognize for audio ≥ 60s, otherwise synchronous recognize.
- Outputs per video: transcript, confidence, word_count, filler_words, duration.
- Aggregates: `avg_confidence` across videos, `total_words`.

Important details:
- Language code: `en-IN`.
- Filler words counted: ["um", "uh", "like", "you know", "basically", "actually"].

Influence mapping:
- Low `avg_confidence` (< 70%) adds a concern in aggregation and can reduce perceived communication clarity in behavioral analysis.
- High filler words can signal stress/nervousness in behavioral prompts.

```124:200:app/agents/nodes/transcribe.py
# Config, long-running, confidence aggregation, filler words
```

### 4.4 Batched Content + Behavioral Evaluation (Single LLM Call)
- Consolidates analysis for all 5 questions and behavioral signals in a single Gemini call.
- System prompt enforces JSON‑only return.
- The batched prompt includes:
  - Identity summary (verified flag + confidence)
  - Full question text, goals, and criteria
  - All transcripts
  - Strict instructions and JSON schema for outputs

Per‑question pass threshold:
- Score ≥ 70 ⇒ pass
- `questions_passed`/`questions_failed` computed accordingly

Behavioral analysis output includes: `behavioral_score`, confidence/engagement levels, stress indicators (0–10), authenticity, communication clarity, strengths, concerns, red_flags, overall impression.

```130:242:app/agents/nodes/batched_evaluation.py
# JSON schema + IMPORTANT: Score ≥ 70 = pass for each question
```

Prompts (structure summary):
- System: "You are an expert interview evaluator. Return ONLY valid JSON, no markdown."
- Human: Includes identity context, questions/goals/criteria, transcripts, and the full JSON output schema with guidance:
  - Be strict
  - Score ≥ 70 = Pass
  - Look for specific evidence
  - Red flags: self‑centered motives, negative language, lack of empathy

Exact prompt template excerpt (batched):

```108:146:app/agents/nodes/batched_evaluation.py
# ... identity_text, questions_text, transcripts_text composed, followed by strict JSON schema and IMPORTANT notes ...
```

Scoring guidance within batched evaluation:
- Per‑question: `passed` if `score` ≥ 70.
- `overall_score`: average of question scores.
- Behavioral outputs include multi‑dimensional attributes; downstream aggregator uses only `behavioral_score` numerically (others feed narrative/flags).

### 4.5 Decision Aggregation
- Final score = 70% content overall score + 30% behavioral score.
- Identity and Quality are gatekeepers (0% weight). Their issues influence red flags/concerns but not numeric weighting.
- Decision thresholds:
  - PASS: final_score ≥ 70
  - REVIEW: 60 ≤ final_score < 70
  - FAIL: final_score < 60
- Identity failure does not auto‑fail; it adds red flags and concerns and is visible to reviewers.
- LLM reasoning: A concise 3–4 sentence rationale is generated to explain decision.

Decision table:

| Final Score | Identity Verified | Decision | Notes |
| --- | --- | --- | --- |
| ≥ 70 | Any | PASS | Identity affects red flags/concerns only |
| 60–69.99 | Any | REVIEW | Borderline; manual review suggested |
| < 60 | Any | FAIL | Insufficient scores |

Weight application:
- `final_score` = 0.70 × `content_evaluation.overall_score` + 0.30 × `behavioral_analysis.behavioral_score`.
- `identity`, `quality`, `transcription` are recorded in `component_scores` but have 0% numeric weight; they affect narrative, strengths/concerns, and red_flags.

```39:88:app/agents/nodes/aggregate.py
# PASS ≥ 70, REVIEW 60–69, FAIL < 60; weights Content 70% + Behavioral 30%
```


## 5) Weightages and Thresholds (Quick Reference)

- Identity
  - Name match: ≥ 50% similarity to pass name check
  - Face match: ≥ 60% average similarity on video_0
  - Overall verified: name_match AND face_verified
  - Confidence: 50% name + 50% face
  - Weight in final score: 0% (gatekeeper; impacts concerns/red flags)

- Quality
  - Resolution 25%, FPS 15%, Brightness 20%, Sharpness 20%, Face visibility 20%
  - Pass: overall quality ≥ 60 (used for concerns/red_flags)
  - Weight in final score: 0%

- Transcription
  - Avg confidence reported; influences behavioral signals and concerns
  - Language: en‑IN; LongRunningRecognize for ≥ 60s

- Content (per question in batched evaluation)
  - Pass threshold: score ≥ 70
  - Overall content score: average of 5 question scores
  - Weight in final score: 70%

- Behavioral
  - Outputs include behavioral_score (0–100), confidence/engagement, stress indicators 0–10, authenticity, clarity
  - Weight in final score: 30%

- Final Decision
  - PASS: final_score ≥ 70
  - REVIEW: 60–69
  - FAIL: < 60


## 6) Prompts — What We Ask the Model(s)

- Batched Evaluation System Prompt:
  - "You are an expert interview evaluator. Return ONLY valid JSON, no markdown."

- Batched Evaluation Human Prompt (structure):
  - Identity summary (verified + confidence)
  - Questions with goals and criteria
  - Candidate transcripts for Q1–Q5
  - Strict JSON schema for content_evaluation and behavioral_analysis
  - Guidance: be strict, score ≥ 70 passes, look for evidence, list red flags

- Aggregation Reasoning Prompt:
  - "You are a hiring decision expert. Based on the assessment data, provide: 1) reasoning; 2) strengths; 3) concerns; 4) final recommendation. Keep 3–4 sentences."


## 7) Outputs — What We Produce

`final_decision` object includes:
- `decision`: PASS | REVIEW | FAIL
- `final_score`: weighted (Content 70% + Behavioral 30%)
- `confidence_level`: heuristic based on distance from 75
- `component_scores`: identity, quality, content, behavioral, transcription(avg_confidence×100)
- `weighted_breakdown`: contributions (identity/quality/transcription = 0 weight)
- `reasoning`: 3–4 sentence LLM rationale
- `recommendation`: action string
- `strengths`, `concerns`, `red_flags`: lists compiled from all agents

```214:235:app/agents/nodes/aggregate.py
# final_decision structure with weights and narrative explanations
```


## 7.1 Full Output Schemas and Examples

- Transcriptions (produced by Speech-to-Text):

```json
{
  "transcriptions": {
    "transcription_complete": true,
    "transcriptions": [
      {
        "video_url": "gs://bucket/user/video_1.webm",
        "video_index": 1,
        "transcript": "...",
        "confidence": 0.86,
        "word_count": 215,
        "filler_words": 7,
        "duration": 78.2
      }
    ],
    "avg_confidence": 0.82,
    "total_words": 1015
  }
}
```

- Content + Behavioral (batched):

```json
{
  "content_evaluation": {
    "overall_score": 78.6,
    "questions_passed": 4,
    "questions_failed": 1,
    "pass_rate": 80.0,
    "summary": "Strong, specific answers with good clarity.",
    "question_evaluations": [
      {
        "question_number": 1,
        "passed": true,
        "score": 80,
        "content_check_passed": true,
        "clarity_check_passed": true,
        "sentiment_check_passed": true,
        "university_found": "IIT Bombay",
        "field_of_study": "Computer Science",
        "major_mentioned": true,
        "appears_reputable": true,
        "filler_words_excessive": false,
        "sentiment": "positive",
        "confidence_level": "high",
        "feedback": "Clear and specific academic intro."
      }
    ]
  },
  "behavioral_analysis": {
    "behavioral_score": 74,
    "confidence_level": "medium",
    "engagement_level": "high",
    "stress_indicators": 3,
    "authenticity_score": 80,
    "communication_clarity": 78,
    "overall_impression": "Confident and engaged; minor nervousness early on.",
    "strengths": ["confident", "structured"],
    "concerns": ["slight pacing inconsistency"],
    "red_flags": []
  }
}
```

- Final decision:

```json
{
  "final_decision": {
    "decision": "PASS",
    "final_score": 77.4,
    "confidence_level": "medium",
    "component_scores": {
      "identity": 92.3,
      "quality": 71.8,
      "content": 78.6,
      "behavioral": 74.0,
      "transcription": 82.0
    },
    "weighted_breakdown": {
      "identity_weighted": 0.0,
      "quality_weighted": 0.0,
      "content_weighted": 55.0,
      "behavioral_weighted": 22.2,
      "transcription_weighted": 0.0
    },
    "reasoning": "The candidate provided specific, structured answers...",
    "recommendation": "PROCEED TO NEXT ROUND - Strong candidate",
    "strengths": ["Excellent identity verification", "High engagement"],
    "concerns": ["Minor pacing issues"],
    "red_flags": []
  }
}
```


## 8) Red Flags and Concerns

- Identity: name mismatch, face verification failure, low similarity, OCR errors, age/gender discrepancy flags
- Quality: poor face visibility (< 50%), blurry/out‑of‑focus
- Transcription: low confidence (< 70%), no speech detected
- Content: most/all questions failed, low overall content score, specific red‑flag phrases
- Behavioral: very low behavioral_score (< 30) or indicators of stress/disengagement; inappropriate tone

Mappings and automation notes:
- Identity
  - `NAME_MISMATCH` when name similarity < 50%.
  - `FACE_VERIFICATION_FAILED` when average similarity < 60% on `video_0`.
  - `LOW_SIMILARITY_SCORE` when identity confidence markedly low (< 60%).
  - Additional flags from `identity_verification.red_flags` include age/gender discrepancies.
- Quality
  - `POOR_FACE_VISIBILITY` if any video’s computed face visibility < 50%.
  - Issues list includes "Blurry/out of focus" and "Poor face visibility" with thresholds as in §4.2.
- Transcription
  - Adds concern if `avg_confidence` < 70%.
  - "No speech detected" sets low word_count and triggers concern.
- Content
  - `ALL_QUESTIONS_FAILED` when `questions_passed` == 0.
  - `MOSTLY_FAILED_QUESTIONS` when content overall score < 40.
- Behavioral
  - `INAPPROPRIATE_EMOTIONAL_STATE` when behavioral score < 30.


## 9) Operational Notes

- Models
  - LLM: Gemini (gemini‑2.0‑flash‑exp for batched eval and reasoning; gemini‑2.5‑flash‑exp in content module)
  - Face: DeepFace with ArcFace backend
  - OCR: Google Cloud Vision
  - Transcription: Google Cloud Speech‑to‑Text (en‑IN)

- Performance
  - Optimized run: ~30–45 seconds typical (semi‑parallel)
  - Sequential run: 4–5 minutes historically

- Resilience
  - Every node has exception handling; on failures, defaults are set and errors appended to `state.errors`
  - Identity/Quality failures become red flags but do not block evaluation


## 9.3 Error Handling & Fallbacks (per node)

- Identity
  - OCR errors → empty text handled; name extraction returns empty; similarity falls back to sequence matching; errors recorded in `identity_verification.red_flags` and `state.errors`.
  - Frame extraction tries OpenCV; falls back to ffprobe+ffmpeg at middle time; last attempt extracts first frame; all attempts have timeouts to avoid hangs.
  - DeepFace verification guarded with try/except; any error yields `verified: false`, `similarity: 0.0`, and error captured.
- Quality
  - If a video cannot be opened, that entry receives `quality_score: 0` with `error` message; aggregation continues with available videos.
- Transcription
  - Auto‑switches to LongRunningRecognize for ≥ 60s; retries with long running if a "too long" error arises.
  - On failure, returns a minimal struct with `transcript: ""`, `confidence: 0.0`, `word_count: 0`, `error` set.
  - Temporary GCS audio is always deleted in `finally` if uploaded.
- Batched Evaluation
  - If JSON decoding fails, logs the raw truncated response; fallback sets `content_evaluation` and `behavioral_analysis` to default 50 scores and adds error to `state.errors`.
- Aggregation
  - If aggregation fails, sets `final_decision` to `REVIEW` with zeroed component scores and an explicit error message for manual review.


## 9.4 Test & Review Aids

- Quick sanity checks:
  - Identity: verify name similarity prints and thresholds; confirm frame extraction prints a success path.
  - Quality: check per‑video `quality_score` and issues list; ensure face visibility logic triggers at < 60% ratio.
  - Transcription: validate `avg_confidence` and `total_words` are populated; try a short (< 60s) and a long (≥ 60s) clip.
  - Batched evaluation: inspect `questions_passed` aligns with `score ≥ 70` per question; validate strict JSON return.
  - Aggregation: confirm `final_score = 0.7×content + 0.3×behavioral` and decision bins.


## 9.1 Configuration & Environment

- Required environment variables:
  - `GOOGLE_API_KEY`: for Gemini LLM via `langchain_google_genai`.
  - `GOOGLE_APPLICATION_CREDENTIALS`: path to service account JSON for GCP client libraries.
  - `GCS_BUCKET_NAME`: bucket for temporary audio uploads during long transcription.
- External services and versions (as used in code):
  - Gemini models: `gemini-2.0-flash-exp` (batched eval & reasoning), `gemini-2.5-flash-exp` (content module initialization).
  - DeepFace with `ArcFace` model, `opencv` detector backend.
  - GCP services: Vision (OCR), Speech-to-Text, Storage (temp file handling).
- Timeouts:
  - Transcription long-running op wait: 300 seconds.
  - FFmpeg/ffprobe steps: 10–60 seconds per segment (see node code for exact calls).

### 9.1.1 Required Cloud APIs and roles
- Enable: Vision API, Speech-to-Text API, Cloud Storage.
- Service Account permissions: `roles/storage.objectAdmin` (temp audio), `roles/visionai.user` (or Vision appropriate role), `roles/speech.client` (Speech).

### 9.1.2 Security & Privacy
- PII involved: Name, government ID text, face imagery, voice transcription.
- Storage: Temp audio uploaded to `GCS_BUCKET_NAME` under `temp_transcriptions/{user_id}/...` and deleted after long-running jobs.
- Retention: No persistent storage in code aside from process logs and transient temp files; ensure logs avoid full OCR text beyond 500-char debug sample.
- Keys: Use service accounts for GCP; API key for Gemini via environment.
- Network: Videos and images read via GCS signed URLs; avoid local persistence wherever possible.

### 9.1.3 Observability & Metrics
- Suggested counters: processing_time_seconds, num_videos_processed, speech_total_words, transcription_avg_confidence, quality_overall_score, identity_confidence, content_overall_score, behavioral_score, decision_bucket.
- Logging: prefer structured logs for each node stage, include user_id correlation ID.


## 9.2 Performance & Parallelism Details

- Optimized flow Phase 2 executes Quality and Transcription concurrently, then runs Identity to avoid DeepFace memory contention; results are merged before batched LLM evaluation.
- Typical optimized total: 30–45s; sequential legacy: ~4–5 minutes.
- Batched LLM call replaces 6–7 separate LLM calls, reducing latency and cost; strict JSON extraction routines handle markdown/code fencing.

### 9.2.1 Performance targets & SLOs (suggested)
- P50 end-to-end optimized: ≤ 45s; P95: ≤ 75s.
- Success rate: ≥ 99% without manual retry.
- JSON compliance from LLM: ≥ 98% (fallback handles remainder).

### 9.2.2 Cost guardrails (ballpark; tune per provider pricing)
- Speech-to-Text: Long running charged per minute; assume 5× ~1–2 min clips.
- LLM: Single `gemini-2.0-flash-exp` call for batched eval + one short reasoning call.
- Storage egress negligible with signed URLs; transient GCS writes for long-running audio.

## 9.5 Deployment & Runbooks
- Pre-flight:
  - Validate env vars present; service account has required roles; Cloud APIs enabled.
  - Smoke test with known 5-video set and 5-question payload.
- Rollout:
  - Start with optimized workflow in a canary; compare timings and decisions vs sequential.
  - Monitor error rates and JSON parsing fallback frequency.
- Incident response:
  - If LLM JSON failures spike, temporarily switch to sequential content+behavioral legacy (if wired) or increase retries.
  - If Speech long-running timeouts occur, reduce audio length or increase timeout; inspect GCS temp cleanup.
  - For DeepFace memory issues, run identity in isolation (already done in optimized flow) and reduce concurrency elsewhere.


## 10) What Feedback We’re Seeking

- Are the final decision thresholds appropriate? (PASS ≥ 70, REVIEW 60–69)
- Are weightages right for our hiring bar? (Content 70% / Behavioral 30%)
- Should identity/quality contribute a small numeric weight or remain gatekeepers only?
- Are per‑question pass thresholds (≥ 70) and "strict but evidence‑based" guidance correct?
- Should we tune name similarity (50%) or face similarity (60%) thresholds?
- Any additional red flags/concerns to auto‑detect at aggregation time?
- Is the LLM rationale sufficient for reviewers, or should we expand to include evidence snippets?


## 11) Appendix — State Schema (abridged)

```30:136:app/agents/state.py
# InterviewState contains: inputs, questions, agent outputs, control flow, errors, metadata
```


## 12) Change/Tuning Log (to track decisions)

- Weights updated per CTO direction: Content 70%, Behavioral 30%; Identity and Quality are gatekeepers (0 weight).
- Identity name similarity relaxed to ≥ 50%; face similarity pass at ≥ 60% on video_0.
- Batched evaluation consolidates content + behavioral into one call to reduce latency and cost.


— End —

## Appendix B — Consistency check against codebase

This section reconciles the document with current source code to ensure fidelity.

- Number of questions and videos
  - Canonical in code: 5 interview questions and 6 total videos (video_0 identity + video_1–video_5 interview). See `InterviewState.video_urls` and `state.py` comments, and `transcribe_parallel` slicing `[1:6]`.
  - Minor inconsistency: `graph.py:run_assessment` docstring mentions "video_1–4" and "4 hardcoded questions"; this appears outdated. The active logic (batched evaluation schema and content module) assumes 5 questions. This spec adopts 5 questions as canonical.

- Nodes used in current flows
  - Sequential graph uses: `verify_identity`, `check_quality`, `transcribe_videos`, `batched_evaluation`, `aggregate_decision`. Legacy `evaluate_content` and `analyze_behavior` exist but are superseded by `batched_evaluation` in the current graph.
  - Optimized flow uses: `check_quality_parallel`, `transcribe_videos_parallel`, `verify_identity_parallel`, then `batched_evaluation`, then `aggregate_decision`, with `prepare_user_resources` and `verify_cleanup_before_response` in `utils.workspace`.

- Transcription scope
  - Sequential `transcribe_videos` transcribes all provided videos (including `video_0`). This spec reflects that in §4.3.
  - Optimized `transcribe_videos_parallel` explicitly skips `video_0` and processes only `video_1–video_5`, matching the 5-question evaluation in `batched_evaluation`.

- Weights and thresholds
  - Final scoring weight: Content 70% + Behavioral 30% — matches `nodes/aggregate.py`.
  - Decision thresholds: PASS ≥ 70; REVIEW 60–69; FAIL < 60 — matches `nodes/aggregate.py`.
  - Identity: name ≥ 50% similarity and face ≥ 60% similarity on `video_0` — matches `nodes/identity.py`.
  - Quality pass threshold: overall ≥ 60 — matches `nodes/quality.py`.
  - Per-question pass: score ≥ 70 — matches `nodes/batched_evaluation.py` prompt.

- Prompts and models
  - Batched evaluation uses Gemini `gemini-2.0-flash-exp` with a strict JSON schema — matches code.
  - Aggregation reasoning uses Gemini `gemini-2.0-flash-exp` — matches code.
  - Content module references `gemini-2.5-flash-exp` (legacy path if used) — noted.

No further mismatches found. If desired, we can update `graph.py` docstrings to reflect 5 questions and `video_1–video_5` to avoid confusion.


