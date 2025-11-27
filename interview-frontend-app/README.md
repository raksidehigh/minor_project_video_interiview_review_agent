# 🎯 Video Interview Application

Full-stack interview application with **Node.js/Express** backend, **Tailwind CSS** frontend, and **SQLite** database.

## 🏗️ Architecture

```
Frontend (Tailwind + Vanilla JS)
        ↓
Backend (Node.js + Express)
        ↓
├── SQLite Database (UUID-based users)
├── Google Cloud Storage (videos/images)
└── Assessment API (LangGraph agents)
```

## 🚀 Quick Deploy

```bash
# Deploy both frontend and backend to Cloud Run
./deploy-all.sh
```

## 📦 Features

- ✅ **UUID-based user management** with SQLite
- ✅ **Automatic result archiving** to `all-api-results/{uuid}-{timestamp}.json`
- ✅ **Node.js/Express** backend (replaced Python/FastAPI)
- ✅ **Tailwind CSS** frontend (replaced custom CSS)
- ✅ **Cloud Run deployment** for both services

## 🗄️ Database Schema

### Users Table
```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,           -- UUID v4
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  dob TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Assessments Table
```sql
CREATE TABLE assessments (
  id TEXT PRIMARY KEY,           -- UUID v4
  user_id TEXT NOT NULL,
  result JSON NOT NULL,
  gcs_path TEXT NOT NULL,        -- Path to all-api-results/{uuid}-{timestamp}.json
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## 🔧 Local Development

### Backend
```bash
cd backend
npm install
node server.js
# Runs on http://localhost:8080
```

### Frontend
```bash
cd frontend
python3 -m http.server 3000
# Open http://localhost:3000
```

## 📡 API Endpoints

### POST /submit-interview
Submit interview with videos and personal info.

**Request:** `multipart/form-data`
- `name`, `email`, `dob`
- `profile_photo`
- `video_intro`, `video_q1`, `video_q2`, `video_q3`, `video_q4`, `video_q5`

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "PASS",
  "final_score": 87.5,
  "result_path": "all-api-results/550e8400-e29b-41d4-a716-446655440000-2025-11-26T12-30-45-123Z.json",
  ...
}
```

### GET /users
List all users.

### GET /assessments/:userId
Get all assessments for a user.

## 📂 GCS Structure

```
virtual-interview-agent/
├── {uuid}/
│   ├── profile_pic.jpg
│   ├── video1.webm
│   ├── video2.webm
│   ├── video3.webm
│   ├── video4.webm
│   └── video5.webm
└── all-api-results/
    └── {uuid}-{timestamp}.json
```

## 🚀 Deployment

### Deploy Backend Only
```bash
./deploy-backend.sh
```

### Deploy Frontend Only
```bash
./deploy-frontend.sh
```

### Deploy Both
```bash
./deploy-all.sh
```

The script automatically:
1. Deploys backend to Cloud Run
2. Updates frontend API URL
3. Deploys frontend to Cloud Run
4. Outputs both service URLs

## 🔐 Environment Setup

Ensure `service-account-key.json` exists in project root:
```
interview-frontend-app/
├── backend/
├── frontend/
└── ../service-account-key.json
```

## 💰 Cost Estimate

- **Backend**: ~$0.15/assessment (includes GCS + API calls)
- **Frontend**: ~$0.001/request (static serving)
- **SQLite**: Free (local to container)

## 🛠️ Tech Stack

- **Backend**: Node.js 18, Express, better-sqlite3, @google-cloud/storage
- **Frontend**: Tailwind CSS, Vanilla JavaScript
- **Database**: SQLite (better-sqlite3)
- **Deployment**: Google Cloud Run
- **Storage**: Google Cloud Storage

---

**Built with** ❤️ **using Node.js, Express, Tailwind CSS, and Google Cloud**
