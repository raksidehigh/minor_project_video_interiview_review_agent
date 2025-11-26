import os
import uuid
import json
import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from typing import List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BUCKET_NAME = "virtual-interview-agent" 
ASSESSMENT_API_URL = "https://video-interview-api-wm2yb4fdna-uc.a.run.app/api/v1/assess"
# Path to service account key in the root directory
CREDENTIALS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../service-account-key.json"))

# Initialize GCS Client
if os.path.exists(CREDENTIALS_PATH):
    print(f"Loading credentials from: {CREDENTIALS_PATH}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
    storage_client = storage.Client.from_service_account_json(CREDENTIALS_PATH)
else:
    print(f"Warning: service-account-key.json not found at {CREDENTIALS_PATH}, using default credentials")
    storage_client = storage.Client()

@app.post("/submit-interview")
async def submit_interview(
    name: str = Form(...),
    dob: str = Form(...),
    email: str = Form(...),
    profile_photo: UploadFile = File(...),
    video_intro: UploadFile = File(...),
    video_q1: UploadFile = File(...),
    video_q2: UploadFile = File(...),
    video_q3: UploadFile = File(...),
    video_q4: UploadFile = File(...),
    video_q5: UploadFile = File(...)
):
    try:
        # Generate User ID (using sanitized email or UUID)
        sanitized_email = email.split('@')[0].replace('.', '_')
        user_id = f"{sanitized_email}_{uuid.uuid4().hex[:8]}"
        
        print(f"Processing submission for {name} ({user_id})")

        bucket = storage_client.bucket(BUCKET_NAME)

        # Helper to upload file
        async def upload_to_gcs(file: UploadFile, destination_blob_name: str):
            blob = bucket.blob(destination_blob_name)
            # Reset file pointer just in case
            await file.seek(0)
            # Read content
            content = await file.read()
            blob.upload_from_string(content, content_type=file.content_type)
            print(f"Uploaded {destination_blob_name}")

        # 1. Upload Profile Photo
        # Structure: {user_id}/profile_pic.jpg
        await upload_to_gcs(profile_photo, f"{user_id}/profile_pic.jpg")

        # 2. Upload Videos
        # Structure: {user_id}/interview_videos/video_0.webm
        videos = [video_intro, video_q1, video_q2, video_q3, video_q4, video_q5]
        
        for idx, video in enumerate(videos):
            # Extension might vary, but let's assume webm from MediaRecorder or keep original
            filename = video.filename or "video.webm"
            ext = filename.split('.')[-1] if '.' in filename else 'webm'
            if ext not in ['webm', 'mp4', 'avi', 'mov']:
                ext = 'webm' 
            
            blob_name = f"{user_id}/interview_videos/video_{idx}.{ext}"
            await upload_to_gcs(video, blob_name)

        # 3. Call Assessment API
        payload = {
            "user_id": user_id,
            "username": name,
            "bucket_name": BUCKET_NAME
        }
        
        print(f"Calling Assessment API: {ASSESSMENT_API_URL} with payload: {payload}")
        response = requests.post(
            ASSESSMENT_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Assessment API Error: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Assessment API failed: {response.text}")
            
        return response.json()

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
