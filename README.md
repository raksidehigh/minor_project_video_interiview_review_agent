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
    User[Candidate] -->|HTTPS| Frontend[Frontend Application\n(Static Web App)]
    Frontend -->|REST API| Middleware[Node.js Middleware\n(Express.js)]
    
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
**End of Documentation**

