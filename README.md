# 🎯 Video Interview Assessment System

A complete 3-tier video interview application featuring a **Frontend**, a **Node.js Middleware**, and an **AI Assessment Agent**.

---

## 🏗️ Architecture

The system consists of three main components:

1.  **Frontend (`/interview-frontend-app/frontend`)**
    *   **Tech**: HTML, CSS, Vanilla JS
    *   **Port**: 3000
    *   **Role**: User interface for recording videos and submitting interviews.

2.  **Middleware (`/interview-frontend-app/backend`)**
    *   **Tech**: Node.js, Express, SQLite
    *   **Port**: 8080
    *   **Role**: Handles video uploads to GCS, manages user data in SQLite, and communicates with the AI Agent.

3.  **AI Assessment Agent (`/app`)**
    *   **Tech**: Python, FastAPI, LangGraph, Google Gemini
    *   **Port**: 8000
    *   **Role**: Performs deep analysis of the interview (Identity, Content, Behavioral) and returns a pass/fail decision.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
*   Python 3.9+
*   Node.js 16+
*   Google Cloud SDK (`gcloud`)
*   `ffmpeg` (required for audio processing)

### 1. Setup Environment
Create a `.env` file in the root directory:
```bash
GOOGLE_API_KEY="your_gemini_api_key"
PROJECT_ID="your-project-id"
```

Ensure you have your service account key at `./service-account-key.json`.

### 2. Start All Services
We have a helper script to start all three services locally:

```bash
cd interview-frontend-app
./start-local.sh
```

This will launch:
*   🐍 **Python Agent**: http://localhost:8000/docs
*   📦 **Node Backend**: http://localhost:8080
*   💻 **Frontend**: http://localhost:3000

---

## ☁️ Deployment

### 1. Deploy AI Assessment Agent (Python)
Deploys the core analysis engine to Cloud Run.

```bash
./deploy_new.sh
```

### 2. Deploy Middleware (Node.js)
Deploys the Express backend that handles uploads.

```bash
cd interview-frontend-app
./deploy-backend.sh
```

### 3. Deploy Frontend (Static)
Deploys the user interface.

```bash
cd interview-frontend-app
./deploy-frontend.sh
```

---

## 📚 Project Structure

```
.
├── app/                        # Python AI Agent (FastAPI + LangGraph)
│   ├── main.py
│   └── agents/                 # Analysis logic (Identity, Content, etc.)
├── interview-frontend-app/     # Web Application
│   ├── frontend/               # Static HTML/JS Frontend
│   ├── backend/                # Node.js Express Middleware
│   ├── start-local.sh          # Local development script
│   ├── deploy-frontend.sh      # Frontend deploy script
│   └── deploy-backend.sh       # Backend deploy script
├── deploy_new.sh               # Python Agent deploy script
├── Dockerfile                  # Python Agent Dockerfile
└── README.md                   # This file
```

---

## 📡 API Documentation

### AI Assessment Agent (Port 8000)
*   `POST /api/v1/assess`: Triggers the full assessment pipeline.
    *   Input: `{ "user_id": "...", "username": "..." }`
    *   Output: Full assessment report (JSON).

### Middleware (Port 8080)
*   `POST /upload-video`: Uploads a video chunk/file.
*   `POST /submit-interview`: Finalizes submission, uploads to GCS, and calls the AI Agent.
    *   Input: Multipart form data (videos + profile pic).

---

## 🔧 Configuration

### Environment Variables
| Variable | Description | Required By |
|----------|-------------|-------------|
| `GOOGLE_API_KEY` | Gemini API Key | Python Agent |
| `PROJECT_ID` | Google Cloud Project ID | Deployment Scripts |
| `BUCKET_NAME` | GCS Bucket for storage | All Components |
