# Video Interview Assessment System: Comprehensive Technical Documentation

**Version:** 2.0.0
**Last Updated:** November 2025
**Author:** AI Engineering Team

---

## 1. Executive Summary

The **Video Interview Assessment System** is a state-of-the-art, AI-powered platform designed to automate the preliminary rounds of candidate interviewing. By leveraging a sophisticated multi-agent architecture, the system evaluates candidates not just on what they say, but on how they say it, providing a holistic assessment of technical knowledge, communication skills, and behavioral traits.

Traditional hiring processes are often bottlenecked by the manual review of initial screening videos. This system eliminates that bottleneck by providing instant, objective, and deep analysis of candidate responses. It employs a **3-Tier Architecture** comprising a responsive Frontend, a robust Node.js Middleware, and a high-performance Python AI Assessment Agent.

### Key Capabilities
*   **Automated Identity Verification:** Uses advanced facial recognition (ArcFace/DeepFace) to ensure the candidate in the video matches their profile picture across all interview responses.
*   **Technical Content Evaluation:** Analyzes the semantic depth of answers against specific technical criteria using Large Language Models (Gemini 2.5 Flash).
*   **Behavioral Profiling:** Assesses soft skills, confidence, and communication clarity using psychological markers.
*   **Video Quality Assurance:** Automatically checks for lighting, resolution, and audio clarity to ensure assessment validity.
*   **Optimized Performance:** Features a parallel processing pipeline that reduces assessment time from 5 minutes to under 45 seconds per candidate.

### Business Value
*   **90% Reduction in Screening Time:** Recruiters receive a finalized report with Pass/Fail recommendations instantly.
*   **Standardized Evaluation:** Removes human bias by applying consistent scoring rubrics across all candidates.
*   **Scalability:** Built on Google Cloud Run (Serverless), the system can handle thousands of concurrent interviews without performance degradation.

---

## 2. System Architecture (Deep Dive)

The system follows a **Microservices-based 3-Tier Architecture**, ensuring separation of concerns, scalability, and maintainability.

### 2.1 High-Level Architecture Diagram

```mermaid
graph TD
    User[Candidate] -->|HTTPS| Frontend[Frontend Application]
    Frontend -->|REST API| Middleware[Node.js Middleware]
    
    subgraph "Tier 1: Client Layer"
        Frontend
    end
    
    subgraph "Tier 2: Orchestration Layer"
        Middleware -->|Uploads| GCS[Google Cloud Storage]
        Middleware -->|Stores Data| SQLite[(SQLite Database)]
        Middleware -->|Triggers| AIAgent[Python AI Assessment Agent]
    end
    
    subgraph "Tier 3: Intelligence Layer"
        AIAgent -->|Retrieves Media| GCS
        AIAgent -->|LLM Calls| Gemini[Google Gemini 2.5 Flash]
        AIAgent -->|Speech-to-Text| STT[Google Speech-to-Text]
        AIAgent -->|Vision API| Vision[Google Cloud Vision]
    end
```

### 2.2 Component Breakdown

#### Tier 1: Frontend (Client Layer)
*   **Location:** `interview-frontend-app/frontend/`
*   **Port:** 3000
*   **Technology:** HTML5, CSS3, Vanilla JavaScript (ES6+)
*   **Responsibility:**
    *   **User Interface:** Provides a clean, responsive interface for candidates to enter details and record videos.
    *   **Media Capture:** Utilizes the browser's `MediaRecorder` API to capture video and audio streams.
    *   **State Management:** Manages the interview flow (Profile -> Instructions -> Questions 1-5 -> Submission).
    *   **Data Transmission:** Sends `FormData` payloads (videos, images, text) to the Middleware.
*   **Key Files:**
    *   `index.html`: The main entry point and layout structure.
    *   `script.js`: Handles logic for camera access, recording timers (10s minimum), and API calls.
    *   `style.css`: Contains the visual styling and responsive design rules.

#### Tier 2: Middleware (Orchestration Layer)
*   **Location:** `interview-frontend-app/backend/`
*   **Port:** 8080
*   **Technology:** Node.js, Express.js
*   **Responsibility:**
    *   **API Gateway:** Acts as the single entry point for the frontend, preventing direct exposure of the AI Agent.
    *   **File Management:** Receives multipart file uploads (videos, images) and streams them directly to Google Cloud Storage (GCS) using `@google-cloud/storage`.
    *   **Data Persistence:** Stores user metadata and assessment results in a local SQLite database (`interviews.db`) for record-keeping.
    *   **Service Orchestration:** Formats the assessment request and calls the Python AI Agent.
*   **Key Files:**
    *   `server.js`: The Express server definition, route handlers (`/submit-interview`, `/upload-video`), and GCS integration logic.
    *   `package.json`: Dependency definitions (`multer`, `axios`, `better-sqlite3`).

#### Tier 3: AI Assessment Agent (Intelligence Layer)
*   **Location:** `app/` (Root Directory)
*   **Port:** 8000
*   **Technology:** Python 3.11, FastAPI, LangGraph, Google Gemini
*   **Responsibility:**
    *   **Core Logic:** Executes the multi-agent workflow to analyze the interview.
    *   **AI Processing:** Interfaces with Google Gemini models for content and behavioral analysis.
    *   **Computer Vision:** Uses OpenCV and MediaPipe for face detection and quality analysis.
    *   **Workflow Management:** Uses LangGraph to orchestrate the 6-step assessment pipeline (Identity -> Quality -> Transcription -> Content -> Behavioral -> Decision).
*   **Key Files:**
    *   `app/main.py`: FastAPI entry point and endpoint definitions.
    *   `app/agents/graph_optimized.py`: The optimized, parallel execution graph.
    *   `app/agents/nodes/*.py`: Individual agent logic (Identity, Quality, etc.).

### 2.3 Data Flow

1.  **Initiation:** The user opens the Frontend and enters their details.
2.  **Capture:** The user records a profile picture and 5 video responses.
3.  **Upload:**
    *   As each video is recorded, the Frontend calls `POST /upload-video` on the Middleware.
    *   The Middleware streams the video to GCS bucket `virtual-interview-agent` under the path `user_id/interview_videos/`.
4.  **Submission:**
    *   Once all videos are uploaded, the Frontend calls `POST /submit-interview`.
    *   The Middleware saves the user record to SQLite.
    *   The Middleware triggers the AI Agent via `POST /api/v1/assess`.
5.  **Assessment:**
    *   The AI Agent downloads the media from GCS.
    *   It runs the 6-agent pipeline (Identity, Quality, Transcription, Content, Behavioral, Decision).
    *   It returns a comprehensive JSON object with scores and reasoning.
6.  **Result:** The Middleware stores the result and returns it to the Frontend for display.

---

## 3. Component Analysis

### 3.1 Frontend Application
The frontend is designed to be lightweight and dependency-free (Vanilla JS), ensuring fast load times and broad compatibility.

*   **Media Recording Logic (`script.js`):**
    *   **Constraint Enforcement:** The `stopRecording` function checks `recordedChunks` duration. If the video is < 10 seconds, it alerts the user and prevents submission.
    *   **Chunk Handling:** Video data is captured in 1-second chunks (`timeslice: 1000`) to ensure data safety.
    *   **Sequential Uploads:** The `nextVideoStep` function ensures the current video is successfully uploaded (awaiting the 200 OK response) before unlocking the next question.

### 3.2 Node.js Middleware
The middleware serves as the "glue" between the user and the AI.

*   **Storage Strategy:**
    *   It uses `multer` for handling `multipart/form-data`.
    *   Files are NOT stored locally on the container (which is ephemeral). Instead, they are streamed directly to GCS using `blob.createWriteStream()`.
    *   **Naming Convention:** Files are stored as `[user_id]/[file_type]/[filename]`.
        *   Example: `user_123/interview_videos/video_1.webm`
*   **Database Schema (SQLite):**
    *   `users`: Stores `id`, `username`, `email`, `created_at`.
    *   `assessments`: Stores `user_id`, `scores` (JSON), `decision`, `timestamp`.

### 3.3 Python AI Agent (The Core)
This is the most complex component, built on **LangGraph**.

*   **Optimization Strategy:**
    *   **Original Flow:** Sequential execution (Agent 1 -> Agent 2 -> ... -> Agent 6). Time: ~4-5 minutes.
    *   **Optimized Flow:**
        *   **Phase 1 (Prep):** Parallel download of all assets.
        *   **Phase 2 (Parallel):** Runs Identity, Quality, and Transcription concurrently using `asyncio.gather`.
        *   **Phase 3 (Sequential):** Runs Content and Behavioral analysis (dependent on transcripts).
        *   **Phase 4 (Aggregation):** Combines scores.
    *   **Result:** Processing time reduced to **30-45 seconds**.

---

## 4. Agentic Workflow & Logic (Deep Dive)

The core intelligence of the system resides in its 6-agent workflow. Each agent is a specialized node in the LangGraph network.

### 4.1 Agent 1: Identity Verification
**Goal:** Prevent proxy interviewing by ensuring the person in the video matches the profile picture.

*   **Technology Stack:**
    *   **MediaPipe Face Detection:** Used first to robustly extract face crops from images (handling rotation/lighting better than dlib).
    *   **face_recognition (dlib):** Generates 128-dimensional face encodings for comparison.
    *   **Euclidean Distance:** Measures similarity between encodings.
*   **Process:**
    1.  **Extraction:** The agent extracts the face from the Profile Picture and the *best* frame from each of the 5 interview videos.
    2.  **Comparison:** It compares the Profile Picture encoding against each Video Frame encoding.
    3.  **Thresholding:**
        *   **Distance Threshold:** `0.6` (Lower is better).
        *   **Similarity Score:** Calculated as `100 - (distance * 100)`.
*   **Pass Criteria:**
    *   **Strict Mode:** The face must match in **>80%** of the videos.
    *   **Confidence Override:** If the average face confidence is **>75%**, it passes even if one video fails (accounting for bad lighting in a single clip).
*   **Output:** `verified` (Boolean), `confidence` (0-100%).

### 4.2 Agent 2: Video Quality Assurance
**Goal:** Ensure the video is technically sound for AI analysis.

*   **Technology Stack:** OpenCV (`cv2`), NumPy.
*   **Metrics Analyzed:**
    1.  **Resolution:** Checks width/height (Target: 720p+).
    2.  **FPS:** Checks frame rate (Target: 24fps+).
    3.  **Brightness:** Calculates average pixel intensity (0-255). Ideal range: 80-180.
    4.  **Sharpness:** Uses Laplacian Variance to detect blur.
    5.  **Face Visibility:** Checks what % of the video contains a detectable face.
*   **Scoring Formula:**
    ```python
    Quality Score = (Resolution_Score * 0.25) + 
                    (FPS_Score * 0.15) + 
                    (Brightness_Score * 0.20) + 
                    (Sharpness_Score * 0.20) + 
                    (Face_Visibility_Score * 0.20)
    ```
*   **Pass Threshold:** Overall Score >= **60/100**.

### 4.3 Agent 3: Audio Transcription
**Goal:** Convert speech to text for NLP analysis.

*   **Technology Stack:** Google Cloud Speech-to-Text API (v2).
*   **Process:**
    1.  Extracts audio track from video.
    2.  Uploads to GCS (if not already there).
    3.  Triggers `LongRunningRecognize` operation for high accuracy.
    4.  Returns full transcript with timestamps.
*   **Optimization:** Runs in parallel with Identity and Quality checks to minimize latency.

### 4.4 Agent 4: Technical Content Evaluation
**Goal:** Assess the *correctness* and *depth* of the candidate's answers.

*   **Technology Stack:** Google Gemini 2.5 Flash.
*   **Input:** Transcripts + Question Context + Ideal Answer Criteria.
*   **Logic:**
    *   The agent evaluates each answer against specific **Keywords**, **Clarity**, and **Relevance**.
    *   **Scoring:** 0-100 scale per question.
    *   **MVP Optimization:** The prompt is engineered to be "welcoming," avoiding harsh penalties for minor phrasing issues.
*   **Weightage:** Contributes **70%** to the Final Score.

### 4.5 Agent 5: Behavioral Analysis
**Goal:** Evaluate soft skills and cultural fit.

*   **Technology Stack:** Google Gemini 2.5 Flash.
*   **Input:** Transcripts + Tone/Sentiment Analysis.
*   **Dimensions Analyzed:**
    1.  **Communication Clarity:** Is the candidate articulate?
    2.  **Confidence:** Do they speak with conviction?
    3.  **Structure:** Is the answer logically organized (STAR method)?
    4.  **Enthusiasm:** Do they show genuine interest?
*   **Weightage:** Contributes **30%** to the Final Score.

### 4.6 Agent 6: Decision Aggregation
**Goal:** Synthesize all data into a final hiring recommendation.

*   **Formula:**
    ```python
    Final Score = (Content_Score * 0.70) + (Behavioral_Score * 0.30)
    ```
*   **Decision Logic:**
    *   **PASS:** Final Score >= **70** AND Identity Verified AND Quality Passed.
    *   **REVIEW:** Final Score between **50-70** OR Identity/Quality Warning.
    *   **FAIL:** Final Score < **50**.
*   **Output:** Generates a human-readable "Reasoning" paragraph explaining the decision.

---

## 5. Installation & Setup (Step-by-Step)

### 5.1 Prerequisites
Before running the system locally, ensure you have the following installed:
*   **Python 3.11+** (for AI Agent)
*   **Node.js 18+** (for Middleware)
*   **Docker** (optional, for containerized testing)
*   **Google Cloud SDK** (`gcloud`)
*   **FFmpeg** (required for audio extraction)

### 5.2 Environment Configuration
You need to configure environment variables for both the Backend and Middleware.

1.  **AI Agent (`app/.env`):**
    ```bash
    GOOGLE_API_KEY=your_gemini_api_key
    GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
    GCS_BUCKET_NAME=virtual-interview-agent
    USE_OPTIMIZED=true
    ```

2.  **Middleware (`interview-frontend-app/backend/.env`):**
    ```bash
    PORT=8080
    ASSESSMENT_API_URL=http://localhost:8000/api/v1/assess
    GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
    ```

### 5.3 Local Development
To start the entire stack locally, use the provided helper script:

```bash
cd interview-frontend-app
./start-local.sh
```

This script performs the following actions:
1.  Starts the **Python AI Agent** on `http://localhost:8000`.
2.  Starts the **Node.js Middleware** on `http://localhost:8080`.
3.  Starts the **Frontend** on `http://localhost:3000`.

**Access the Application:** Open your browser and navigate to `http://localhost:3000`.

---

## 6. Deployment Guide

The system is designed to be deployed on **Google Cloud Run** as three separate services.

### 6.1 Deploying the AI Agent
Use the `deploy_new.sh` script to deploy the Python backend.

```bash
./deploy_new.sh
```
*   **Service Name:** `video-interview-api`
*   **Configuration:** 2 CPUs, 4GB Memory (Required for Face Recognition).
*   **Concurrency:** 80 (High concurrency allowed due to async I/O).

### 6.2 Deploying the Middleware
Use the `deploy-backend.sh` script.

```bash
cd interview-frontend-app
./deploy-backend.sh
```
*   **Service Name:** `interview-backend`
*   **Configuration:** 1 CPU, 512MB Memory.

### 6.3 Deploying the Frontend
Use the `deploy-frontend.sh` script.

```bash
cd interview-frontend-app
./deploy-frontend.sh
```
*   **Service Name:** `interview-frontend`
*   **Configuration:** Static file serving (Nginx/Python http.server).

---

## 7. API Reference

### 7.1 AI Agent Endpoints

#### `POST /api/v1/assess`
Triggers the full assessment pipeline.

**Request Body:**
```json
{
  "user_id": "user_12345",
  "username": "John Doe",
  "bucket_name": "virtual-interview-agent"
}
```

**Response Body:**
```json
{
  "user_id": "user_12345",
  "decision": "PASS",
  "final_score": 85.5,
  "component_scores": {
    "identity": 100.0,
    "quality": 90.0,
    "content": 82.0,
    "behavioral": 88.0,
    "transcription": 95.0
  },
  "reasoning": "Candidate demonstrated strong technical knowledge...",
  "processing_time_seconds": 42.5
}
```

### 7.2 Middleware Endpoints

#### `POST /upload-video`
Uploads a single video chunk or file.
*   **Form Data:** `video` (File), `user_id` (String), `index` (Integer).

#### `POST /submit-interview`
Finalizes the interview and triggers assessment.
*   **Form Data:** `user_id`, `username`, `email`.

---

## 8. Troubleshooting & Maintenance

### 8.1 Common Issues

| Issue | Probable Cause | Solution |
| :--- | :--- | :--- |
| **Memory Limit Exceeded** | Face recognition is memory-intensive. | Increase Cloud Run memory to 4GB or 8GB. |
| **Face Not Detected** | Poor lighting or extreme angles. | Ensure the candidate faces the camera directly with good lighting. |
| **GCS Permission Denied** | Service Account missing roles. | Grant `Storage Object Admin` and `Storage Object Creator` roles. |
| **Upload Timeout** | Slow internet connection. | The frontend handles retries, but ensure a stable connection (>5Mbps). |

### 8.2 Logging & Monitoring
The system integrates with **Google Cloud Logging**.
*   **Filter:** `resource.type="cloud_run_revision" AND severity>=WARNING`
*   **Key Metrics:** Look for "Processing time" logs to monitor performance.

---

## 9. Security Best Practices

1.  **Least Privilege Access:** The Service Account used by Cloud Run has only the permissions strictly necessary (GCS access, Vertex AI User).
2.  **Ephemeral Storage:** No sensitive candidate data is stored permanently on the application servers. All data resides in secure GCS buckets.
3.  **Signed URLs:** Video streaming uses short-lived Signed URLs to prevent unauthorized access to raw video files.
4.  **Input Validation:** The Middleware validates all file types and sizes before processing.

---

## 10. Future Roadmap

*   **Async Webhooks:** Decouple the assessment from the HTTP request to handle even higher loads.
*   **Real-time Feedback:** Provide instant feedback to candidates during the interview (e.g., "Please speak louder").
*   **Multi-language Support:** Add support for non-English interviews using Gemini's multilingual capabilities.
*   **Fraud Detection:** Enhance identity verification with liveness detection (blinking/movement checks).

---

## 11. Data Models & Schemas (TypedDict Spec)

### 11.1 InterviewState Schema
The core data structure passed through all agents in the LangGraph workflow is defined in `app/agents/state.py`:

```python
class InterviewState(TypedDict):
    # INPUT (Required)
    user_id: str
    username: str  
    profile_pic_url: str  # gs://bucket/user_id/profile_pic.jpg
    video_urls: List[str]  # [video_1.webm, ..., video_5.webm]
    interview_questions: List[Dict]  # 5 hardcoded questions
    
    # AGENT OUTPUTS
    identity_verification: Optional[Dict]  # Agent 1
    video_quality: Optional[Dict]  # Agent 2
    transcriptions: Optional[Dict]  # Agent 3
    content_evaluation: Optional[Dict]  # Agent 4
    behavioral_analysis: Optional[Dict]  # Agent 5
    final_decision: Optional[Dict]  # Agent 6
    
    # CONTROL FLOW
    should_continue: bool
    current_stage: str
    errors: List[str]
```

### 11.2 Google Cloud Storage (GCS) Bucket Structure

The system expects the following file structure in the `virtual-interview-agent` bucket:

```
gs://virtual-interview-agent/
├── user_123/
│   ├── profile_images/
│   │   └── profile_pic.jpg
│   └── interview_videos/
│       ├── video_0.webm  # Optional identity check
│       ├── video_1.webm  # Question 1
│       ├── video_2.webm  # Question 2
│       ├── video_3.webm  # Question 3
│       ├── video_4.webm  # Question 4
│       └── video_5.webm  # Question 5
└── temp_transcriptions/
    └── user_123/
        └── <uuid>.flac  # Temporary audio files (auto-deleted)
```

---

## 12. Prompt Engineering & LLM Configuration

### 12.1 Model Selection
*   **Content Evaluation (Agent 4):** `gemini-2.5-flash-exp` (Temperature: 0.3)
*   **Behavioral Analysis (Agent 5):** `gemini-2.5-flash` (Temperature: 0.3)
*   **Decision Reasoning (Agent 6):** `gemini-2.5-flash` (Temperature: 0.3)

### 12.2 MVP Philosophy: "Generous Scoring"
The prompts are **MVP-optimized** to be **extremely welcoming and encouraging**. Key principles:
*   **Default to PASS:** Automatic 100 score if ANY positive keywords detected.
*   **Normal motivations are POSITIVE:** Monetization, career growth, opportunities are **NOT red flags**.
*   **Slight nervousness shows they care:** Do NOT penalize nervous candidates.
*   **Focus on POTENTIAL:** Assume positive intent always.

### 12.3 Content Evaluation Prompts (Agent 4 - `content.py`)

#### Question 1: "Introduce yourself and tell us about your academic background"
**LLM Prompt (Excerpt from code):**
```
BE EXTREMELY WELCOMING - we want to encourage candidates who show ANY positive intent.

CRITICAL MVP RULES:
1. If they mention ANYTHING about education, university, college → AUTOMATIC PASS
2. If they mention their name and ANY academic-related word → AUTOMATIC PASS
3. Vague references like "I studied", "my college" → ALL ACCEPTABLE
4. Even if they just say their name and mention being a student → PASS
5. Only FAIL if completely irrelevant with zero educational context

GENEROUS INTERPRETATION:
- "I'm studying" = mentions field of study ✓
- "I go to university" = mentions institution ✓
- Any subject name (math, science, etc.) = field of study ✓

SCORING GUIDANCE:
- ANY educational context → intent_positive_percentage = 75+
- Mentions university OR field → intent = 85+
- Only completely off-topic → intent < 50
```

**Scoring Logic (from `content.py`):**
```python
# Answer Relevance (70%)
answer_relevance_score = 70 if passed else 65

# Clarity (30%): Filler threshold = 30 (very lenient)
clarity_score = 35 if filler_count < 30 else 30

# Keywords (10%): Sentiment not negative
keywords_score = 12 if sentiment != 'negative' else 10

# MVP Override: If answer shows 40% intent → FULL MARKS (100)
if minimal_relevance and intent >= 40:
    score = 100
    overall_passed = True
```

#### Question 2: "What motivated you to apply?"
**Ultra-Lenient MVP Rules (from `content.py`):**
```
🎯 ULTRA-LENIENT MVP RULES (MANDATORY):
1. **ANY MENTION OF HELPING = AUTOMATIC 100**: "help", "assist" → INSTANT PASS
2. **MONETIZATION IS EXCELLENT**: "get paid", "earn" → POSITIVE, NEVER red flags
3. **COMBINATION = PERFECT**: Helping + Money = IDEAL (realistic!)
4. **ANY PROGRAM INTEREST = PASS**: Vague interest → 90+ score
5. **GIVE 100 BY DEFAULT**: Unless hostile or off-topic

🚫 NEVER FLAG AS RED FLAGS:
- "monetize", "get monetized", "earn money", "financial benefit"
- Any realistic motivations - HEALTHY and NORMAL

✅ AUTOMATIC 100 IF:
- Mentions helping words (help, assist, support, contribute)
- Shows interest in program
- Mentions ANY positive motivation

❌ ONLY FAIL IF:
- Explicitly hostile
- Completely off-topic
- Refuses to answer
```

### 12.4 Behavioral Analysis Prompt (Agent 5 - `behavioral.py`)
```
BE VERY GENEROUS in your assessment - we're building a welcoming community.

MVP GUIDELINES:
- Normal career motivations (money, growth) are NOT red flags - HEALTHY!
- Slight nervousness is EXPECTED - shows they care!
- Any sign of helpfulness should be HEAVILY REWARDED
- Focus on POTENTIAL, not perfection

SCORING GUIDELINES (CRITICAL):
- **Base score: 80/100** (high baseline)
- **Default to 85** for engaged candidates
- **90+ for enthusiasm or relevant experience**
- Only reduce below 80 for serious issues

MANDATORY:
- behavioral_score must be 85+ for normal engaged candidates
- Only reduce below 80 for anger, rudeness, or refusal to participate
```

---

## 13. GCS Storage & Workspace Management

### 13.1 Signed URL Generation (`gcs_streaming.py`)
The system uses **signed URLs** to stream videos directly from GCS without downloading:

```python
def get_signed_url(gcs_url: str, expiration_minutes: int = 60) -> str:
    """
    Generate signed URL for direct GCS access
    
    Example:
        signed_url = get_signed_url("gs://bucket/video.mp4")
        cap = cv2.VideoCapture(signed_url)  # Stream directly! NO DOWNLOAD!
    """
    storage_client = storage.Client()
    bucket, blob_path = parse_gcs_url(gcs_url)
    blob = bucket.blob(blob_path)
    
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="GET"
    )
    return signed_url
```

**Memory Impact:** ✅ **Zero** - Videos are streamed, never stored on disk.

### 13.2 Workspace Isolation (`workspace.py`)
Each user gets an **isolated temporary workspace** to prevent file conflicts:

```python
class UserWorkspace:
    def __init__(self, user_id: str):
        # Create unique workspace
        self.workspace = tempfile.gettempdir() / f"video_assessments/{user_id}_{timestamp}/"
        self.videos_dir = self.workspace / "videos"
        self.audios_dir = self.workspace / "audios"
    
    def cleanup(self) -> Dict:
        """MANDATORY cleanup with verification"""
        shutil.rmtree(self.workspace)  # Delete ALL files
        verify_deletion(self.workspace)  # Ensure deleted
        gc.collect()  # Force garbage collection
        return {"deleted": True, "verified": True, "files_deleted": count}
```

**Cleanup Flow:**
1.  **Phase 1:** Download files to workspace
2.  **Phase 2-3:** Process assessment
3.  **Phase 4:** **MANDATORY** workspace deletion before response

**Safety Check:** `verify_cleanup_before_response()` blocks the API response if cleanup fails:
```python
if not cleanup_report.get("verified"):
    raise RuntimeError("CRITICAL: Workspace deletion failed")
```

---

## 14. Performance Optimization & Memory Management

### 14.1 Memory Usage Breakdown (from `LOGGING_MEMORY_IMPLICATIONS.md`)

| Component | Memory per Request | Notes |
| :--- | :--- | :--- |
| **In-Memory Logging** | 14 MB | Python logging buffers |
| **Application State** | 2-5 MB | InterviewState object |
| **Face Recognition** | 300-500 MB | dlib face encodings |
| **Video Frame Buffers** | 50-100 MB | OpenCV processing |
| **Total per Request** | **~400-650 MB** | **Peak memory** |

**Concurrent Requests:**
*   1 request: ~650 MB
*   10 concurrent: ~6.5 GB
*   **Cloud Run Config:** 4 GB memory → Safe for ~6 concurrent requests

### 14.2 Optimization Strategies

#### 1. Video Streaming (No Download)
```python
# ❌ OLD (Downloads 50 MB × 5 = 250 MB)
video_path = download_from_gcs(gcs_url)
cap = cv2.VideoCapture(video_path)

# ✅ NEW (Streams directly, 0 MB overhead)
signed_url = get_signed_url(gcs_url)
cap = cv2.VideoCapture(signed_url)  # Streams!
```

**Memory Saved:** 250 MB per request

#### 2. Parallel Execution (`graph_optimized.py`)
```python
# Agents 1, 2, 3 run CONCURRENTLY
identity_state, quality_state, transcribe_state = await asyncio.gather(
    verify_identity_parallel(resources, state),
    check_quality_parallel(resources, state),
    transcribe_videos_parallel(resources, state)
)
```

**Time Saved:** 4-5 minutes → 30-45 seconds (**90% faster**)

#### 3. Mandatory Workspace Cleanup
```python
# BEFORE sending response:
cleanup_report = workspace.cleanup()
verify_cleanup_before_response(cleanup_report)  # Blocks if failed
```

Prevents memory leaks and disk exhaustion.

---

## 15. Speech-to-Text Configuration (`transcribe.py`)

### 15.1 Google Cloud Speech-to-Text V2 (Chirp 3)
```python
config = cloud_speech.RecognitionConfig(
    auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
    language_codes=["auto"],  # Auto-detect language
    model="chirp_3",  # Latest Chirp model
    features=cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True
    ),
    denoiser_config=cloud_speech.DenoiserConfig(
        denoise_audio=True,
        snr_threshold=20.0  # Medium sensitivity
    )
)
```

### 15.2 Synchronous vs. Batch Recognition
*   **Short audio (< 60s):** `recognize()` (synchronous)
*   **Long audio (≥ 60s):** `batch_recognize()` (long-running operation)

```python
duration = get_audio_duration(audio_path)

if duration >= 60:
    # Upload to GCS for batch
    temp_gcs_uri = upload_audio_to_gcs(audio_path, user_id)
    operation = client.batch_recognize(request)
    response = operation.result(timeout=300)  # 5min timeout
else:
    # Synchronous for short audio
    response = client.recognize(request)
```

### 15.3 Transcription Output
```python
{
  "transcript": "Full text of the answer...",
  "confidence": 0.95,  # 95% confidence
  "word_count": 127,
  "speaking_rate": 152.5,  # Words per minute
  "filler_words": 8,  # "um", "uh", "like" count
  "detected_language": "en-US",
  "word_timestamps": [  # Word-level timing
    {"word": "Hello", "start_time": 0.0, "end_time": 0.5},
    ...
  ]
}
```

---

## 16. Codebase Module Guide

### 16.1 Main Application
*   **`app/main.py`**: FastAPI entry point, `/api/v1/assess` endpoint, file discovery logic.

### 16.2 Agent Nodes (`app/agents/nodes/`)
*   **`identity.py`**: MediaPipe + face_recognition (dlib). Threshold: 0.6 Euclidean distance.
*   **`quality.py`**: OpenCV quality analysis (Resolution, FPS, Brightness, Sharpness, Face Visibility).
*   **`transcribe.py`**: Speech-to-Text V2 with Chirp 3, auto language detection.
*   **`content.py`**: LLM content evaluation with MVP-optimized prompts.
*   **`behavioral.py`**: Gemini behavioral profiling (engagement, confidence).
*   **`aggregate.py`**: Final decision (70% Content + 30% Behavioral).

### 16.3 Utilities (`app/utils/`)
*   **`gcs_streaming.py`**: Signed URL generation for streaming.
*   **`workspace.py`**: Isolated workspace with mandatory cleanup.
*   **`speech_client.py`**: Singleton Speech-to-Text client.
*   **`parallel.py`**: Parallel task manager.

### 16.4 State Management
*   **`app/agents/state.py`**: TypedDict definitions (`InterviewState`, `VideoAnalysis`).
*   **`app/agents/graph_optimized.py`**: 4-Phase optimized workflow (Prep → Parallel → Aggregate → Cleanup).

---

**End of Comprehensive Technical Documentation**

For questions or contributions, please refer to the source code in the `app/` directory or contact the project maintainers.
