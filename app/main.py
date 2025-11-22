"""
FastAPI Application for Video Interview Assessment API
Deploy to Google Cloud Run
"""
# CRITICAL: Set environment variables BEFORE any other imports
# Thread-safe execution for face recognition operations
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['TF_NUM_INTRAOP_THREADS'] = '1'
os.environ['TF_NUM_INTEROP_THREADS'] = '1'

import gc
import psutil
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google.cloud import storage

from .agents.graph import run_assessment
from .agents.graph_optimized import run_assessment_optimized_with_fallback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== Helper Functions ==========

def check_memory_status():
    """Check and log current memory status"""
    try:
        memory = psutil.virtual_memory()
        available_gb = memory.available // (1024**3)
        total_gb = memory.total // (1024**3)
        used_percent = memory.percent
        
        print(f"💾 Memory Status: {available_gb}GB available / {total_gb}GB total ({used_percent:.1f}% used)")
        
        if available_gb < 2:
            print("⚠️  WARNING: Low memory available!")
            return False
        return True
    except Exception as e:
        print(f"⚠️  Could not check memory status: {e}")
        return True

def force_cleanup():
    """Force garbage collection and cleanup"""
    try:
        gc.collect()
        print("🧹 Forced garbage collection completed")
    except Exception as e:
        print(f"⚠️  Garbage collection warning: {e}")

def discover_user_files(user_id: str, bucket_name: str = "edumentor-virtual-interview") -> Dict[str, Any]:
    """
    Automatically discover user files in GCS bucket
    
    Expected structure (supports nested subdirectories):
    gs://bucket_name/user_id/
        ├── profile_images/
        │   └── [UUID]/profile_pic.jpg (or .jpeg, .png)
        ├── documents/
        │   └── gov_id/
        │       └── [UUID]/gov_id.jpg (or .jpeg, .png)
        └── interview_videos/
            ├── video_0.webm (or .mp4, .avi, .mov)
            ├── video_1.webm
            ├── video_2.webm
            ├── video_3.webm
            ├── video_4.webm
            └── video_5.webm
    
    Also supports flat structure:
    gs://bucket_name/user_id/
        ├── profile_pic.jpg
        ├── gov_id.jpg
        └── video_*.webm
    
    Args:
        user_id: User ID to look up
        bucket_name: GCS bucket name (default: edumentor-virtual-interview)
    
    Returns:
        dict with profile_pic_url, gov_id_url, video_urls
    
    Raises:
        HTTPException if required files not found
    """
    try:
        # Initialize GCS client with explicit credentials if available
        import os
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            client = storage.Client(credentials=credentials)
        else:
            # Try default credentials (works in Cloud Run with service account)
            client = storage.Client()
        
        bucket = client.bucket(bucket_name)
        
        # List all files in user's folder
        prefix = f"{user_id}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Debug: Print all found files
        print(f"   🔍 DEBUG: Found {len(blobs)} blob(s) with prefix '{prefix}'")
        all_filenames = []
        for blob in blobs:
            filename = blob.name.replace(prefix, "").strip()
            if filename:  # Skip empty folder entries
                all_filenames.append(filename)
                print(f"      - {blob.name} (filename: '{filename}')")
        
        if not blobs or not all_filenames:
            raise HTTPException(
                status_code=404,
                detail=f"No files found for user_id={user_id} in bucket={bucket_name} with prefix '{prefix}'"
            )
        
        # Organize files by type
        # Based on actual structure: user_id/profile_images/, user_id/documents/gov_id/, user_id/interview_videos/
        profile_pic = None
        gov_id = None
        videos = []
        
        for blob in blobs:
            # Get relative path from user_id prefix
            relative_path = blob.name.replace(prefix, "").strip()
            
            # Skip if it's just the folder itself or empty
            if not relative_path:
                continue
            
            # Get filename and path parts
            path_parts = relative_path.lower().split('/')
            base_filename = path_parts[-1]
            
            # Skip if it's a directory (no extension)
            if '.' not in base_filename:
                continue
            
            # Check file extension
            has_image_ext = any(ext in base_filename for ext in ['.jpg', '.jpeg', '.png'])
            has_video_ext = any(ext in base_filename for ext in ['.webm', '.mp4', '.avi', '.mov'])
            
            # Profile picture: Look in profile_images/ subdirectory
            if has_image_ext:
                is_profile = False
                if ("profile_images" in relative_path.lower() or 
                    "profile_images/" in relative_path.lower()):
                    if not profile_pic:  # Take first match
                        profile_pic = f"gs://{bucket_name}/{blob.name}"
                        print(f"   ✅ Matched profile_pic: {blob.name}")
                        is_profile = True
                # Fallback: check filename pattern
                elif (base_filename.startswith("profile_pic") or 
                      base_filename.startswith("profile") or
                      ("profile" in base_filename and "pic" in base_filename)):
                    if not profile_pic:
                        profile_pic = f"gs://{bucket_name}/{blob.name}"
                        print(f"   ✅ Matched profile_pic (by filename): {blob.name}")
                        is_profile = True
                
                # If not a profile pic, check for gov_id
                if not is_profile:
                    if ("documents/gov_id" in relative_path.lower() or 
                        "documents/govt_id" in relative_path.lower() or
                        "/gov_id/" in relative_path.lower()):
                        if not gov_id:  # Take first match
                            gov_id = f"gs://{bucket_name}/{blob.name}"
                            print(f"   ✅ Matched gov_id: {blob.name}")
                    # Fallback: check filename pattern
                    elif (base_filename.startswith("gov_id") or 
                          base_filename.startswith("govt_id") or 
                          base_filename.startswith("government_id") or
                          (base_filename.startswith("id") and len(base_filename.split('_')[0]) <= 3) or
                          ("gov" in base_filename and "id" in base_filename)):
                        if not gov_id:
                            gov_id = f"gs://{bucket_name}/{blob.name}"
                            print(f"   ✅ Matched gov_id (by filename): {blob.name}")
                continue
            
            # Videos: Look in interview_videos/ subdirectory
            if has_video_ext:
                if ("interview_videos" in relative_path.lower() or 
                    "interview_videos/" in relative_path.lower()):
                    videos.append(f"gs://{bucket_name}/{blob.name}")
                    print(f"   ✅ Matched video: {blob.name}")
                # Fallback: check filename pattern
                elif (base_filename.startswith("video") or 
                      "video" in base_filename):
                    videos.append(f"gs://{bucket_name}/{blob.name}")
                    print(f"   ✅ Matched video (by filename): {blob.name}")
                continue
        
        # Debug: Print what was matched
        print(f"   📊 Summary: profile_pic={bool(profile_pic)}, gov_id={bool(gov_id)}, videos={len(videos)}")
        
        # Validate required files
        missing = []
        if not profile_pic:
            missing.append("profile_pic")
        if not gov_id:
            missing.append("gov_id")
        
        # NEW: Expect 6 videos (video_0 for identity + video_1-5 for interview)
        if len(videos) < 6:
            missing.append(f"videos (found {len(videos)}, need 6: video_0 + video_1-5)")
        
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required files for user_id={user_id}: {', '.join(missing)}"
            )
        
        # Sort videos by name (video_0, video_1, video_2, ..., video_5)
        videos.sort()
        
        # Take first 6 videos (video_0 for identity/quality, video_1-5 for interview)
        videos = videos[:6]
        
        return {
            "profile_pic_url": profile_pic,
            "gov_id_url": gov_id,
            "video_urls": videos
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to discover files for user_id={user_id}: {str(e)}"
        )


# ========== Pydantic Models ==========

class AssessmentRequest(BaseModel):
    """Request model for interview assessment - Simplified API"""
    user_id: str = Field(..., description="Unique identifier for the candidate (folder name in GCS)")
    username: str = Field(..., description="Candidate's full name (to verify against government ID)")
    bucket_name: Optional[str] = Field(
        "edumentor-virtual-interview",
        description="GCS bucket name (default: edumentor-virtual-interview)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_1",
                "username": "John Doe"
            }
        }


class ComponentScores(BaseModel):
    """Component scores from all agents"""
    identity: float = Field(..., ge=0, le=100)
    quality: float = Field(..., ge=0, le=100)
    content: float = Field(..., ge=0, le=100)
    behavioral: float = Field(..., ge=0, le=100)
    transcription: float = Field(..., ge=0, le=100)


class AssessmentResponse(BaseModel):
    """Response model for interview assessment - Complete results for database storage"""
    user_id: str
    decision: str = Field(..., description="PASS, REVIEW, or FAIL")
    final_score: float = Field(..., ge=0, le=100)
    component_scores: ComponentScores
    reasoning: str
    recommendation: str
    strengths: List[str]
    concerns: List[str]
    processing_time_seconds: float
    completed_at: str
    
    # Complete agent results for database storage
    identity_verification_details: Optional[Dict[str, Any]] = Field(None, description="Full identity verification results")
    video_quality_details: Optional[Dict[str, Any]] = Field(None, description="Full video quality analysis")
    transcription_details: Optional[Dict[str, Any]] = Field(None, description="Full transcriptions with timestamps")
    content_evaluation_details: Optional[Dict[str, Any]] = Field(None, description="Full content evaluation breakdown")
    behavioral_analysis_details: Optional[Dict[str, Any]] = Field(None, description="Full behavioral analysis")
    
    # User form data (echo back for reference)
    user_form_data: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_001",
                "decision": "PASS",
                "final_score": 86.5,
                "component_scores": {
                    "identity": 92.0,
                    "quality": 85.0,
                    "content": 88.0,
                    "behavioral": 84.0,
                    "transcription": 90.0
                },
                "reasoning": "Strong candidate with excellent technical competence and clear communication",
                "recommendation": "PROCEED TO NEXT ROUND - Strong candidate",
                "strengths": ["Strong identity verification", "Excellent content quality"],
                "concerns": ["No major concerns identified"],
                "processing_time_seconds": 45.2,
                "completed_at": "2025-10-12T20:30:45.123456"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str


# ========== FastAPI App ==========

app = FastAPI(
    title="Video Interview Assessment API",
    description="AI-powered video interview evaluation using LangGraph multi-agent system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== API Endpoints ==========

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Video Interview Assessment API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.post("/api/v1/assess", response_model=AssessmentResponse)
async def assess_interview(request: AssessmentRequest):
    """
    Run complete video interview assessment for Ambassador Program
    
    Simplified API: Just send user_id and username!
    The API automatically discovers files in GCS bucket.
    
    Executes 6-agent workflow:
    1. Identity Verification (face_recognition + OCR + Name matching)
    2. Video Quality Check (OpenCV)
    3. Speech-to-Text (Google Speech-to-Text)
    4. Content Evaluation (Question-specific criteria)
    5. Behavioral Analysis (Gemini LLM)
    6. Decision Aggregation (weighted scoring)
    
    Returns final decision: PASS, REVIEW, or FAIL
    """
    try:
        print(f"\n{'='*80}")
        print(f"📥 STEP 1: Request received for user_id={request.user_id}")
        print(f"   - username: {request.username}")
        print(f"   - bucket: {request.bucket_name}")
        
        # Discover user files in GCS bucket
        print(f"📥 STEP 2: Discovering files in GCS bucket...")
        logger.info(f"🔍 [MAIN] Discovering files for user_id={request.user_id} in bucket={request.bucket_name}")
        try:
            files = discover_user_files(request.user_id, request.bucket_name)
            logger.info(f"✅ [MAIN] File discovery successful:")
            logger.info(f"   - Profile pic found: {bool(files.get('profile_pic_url'))}")
            logger.info(f"   - Gov ID found: {bool(files.get('gov_id_url'))}")
            logger.info(f"   - Videos found: {len(files.get('video_urls', []))}")
            print(f"   ✅ Found files:")
            print(f"      - profile_pic: {files['profile_pic_url']}")
            print(f"      - gov_id: {files['gov_id_url']}")
            print(f"      - videos: {len(files['video_urls'])} files")
            for i, url in enumerate(files['video_urls'], 1):
                print(f"         {i}. {url}")
                logger.info(f"      Video {i}: {url}")
        except Exception as e:
            error_msg = f"File discovery failed: {str(e)}"
            print(f"   ❌ {error_msg}")
            logger.error(f"❌ [MAIN] {error_msg}")
            logger.error(f"   Exception type: {type(e).__name__}")
            raise
        
        # Validate environment
        print(f"📥 STEP 3: Validating environment...")
        if not os.getenv('GOOGLE_API_KEY'):
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY not configured"
            )
        print(f"   ✅ GOOGLE_API_KEY present")
        
        # Hardcoded interview questions for Ambassador Program
        INTERVIEW_QUESTIONS = [
            {
                "question_number": 1,
                "question": "Please introduce yourself and tell us about your academic background.",
                "goal": "The candidate must clearly state their name, a specific top-tier university, and their field of study in a confident manner.",
                "criteria": {
                    "content_check": "Specific university name from approved list and specific major",
                    "clarity_check": "Direct speech, free of excessive filler words",
                    "sentiment_check": "Professional and confident (neutral to positive)"
                }
            },
            {
                "question_number": 2,
                "question": "What motivated you to apply for our Ambassador Program?",
                "goal": "The candidate must express genuine, mission-aligned passion for helping students, not just personal gain.",
                "criteria": {
                    "content_check": "Keywords: help, guide, give back, share my experience",
                    "sentiment_check": "Highly positive and enthusiastic",
                    "sincerity_check": "Facial expressions align with positive words"
                }
            },
            {
                "question_number": 3,
                "question": "Describe a time when you helped someone learn something new.",
                "goal": "The candidate must demonstrate patience, empathy, and a structured approach to teaching.",
                "criteria": {
                    "content_check": "Clear process (Problem -> Action -> Result), empathy keywords: patience, listened, explained",
                    "sentiment_check": "Helpful and positive"
                }
            },
            {
                "question_number": 4,
                "question": "How do you handle challenging situations or difficult students?",
                "goal": "The candidate must show a mature, calm, and solution-oriented approach, not a blaming one.",
                "criteria": {
                    "content_check": "Positive actions: listen, understand, empathize, find a solution",
                    "red_flag_check": "No negative words: lazy, stupid, their fault",
                    "sentiment_check": "Calm and professional (neutral-to-positive)"
                }
            },
            {
                "question_number": 5,
                "question": "What are your goals as a mentor and how do you plan to achieve them?",
                "goal": "The candidate must show forward-looking, aspirational goals with concrete action plans.",
                "criteria": {
                    "content_check": "Action-oriented words: plan, create, organize, develop, implement, build, establish",
                    "specific_actions": "Specific actions: weekly, daily, monthly, check-in, meeting, resource, guide",
                    "sentiment_check": "Forward-looking, confident, aspirational with concrete plan"
                }
            }
        ]
        
        # Check memory before processing
        print(f"📥 STEP 4: Checking memory before assessment...")
        memory_ok = check_memory_status()
        if not memory_ok:
            print("⚠️  Low memory detected - forcing cleanup before assessment")
            force_cleanup()
        
        # Run assessment (with optimized pipeline)
        # Set USE_OPTIMIZED=false in environment to use original implementation
        use_optimized = os.getenv('USE_OPTIMIZED', 'true').lower() == 'true'
        
        print(f"📥 STEP 5: Calling {'OPTIMIZED' if use_optimized else 'ORIGINAL'} assessment pipeline...")
        try:
            logger.info(f"🚀 [MAIN] Starting assessment pipeline (optimized={use_optimized})")
            logger.info(f"   - User ID: {request.user_id}")
            logger.info(f"   - Username: {request.username}")
            logger.info(f"   - Profile Pic: {files['profile_pic_url']}")
            logger.info(f"   - Gov ID: {files['gov_id_url']}")
            logger.info(f"   - Videos: {len(files['video_urls'])} files")
            logger.info(f"   - Interview Questions: {len(INTERVIEW_QUESTIONS)}")
            
            result = await run_assessment_optimized_with_fallback(
                user_id=request.user_id,
                username=request.username,
                profile_pic_url=files['profile_pic_url'],
                gov_id_url=files['gov_id_url'],
                video_urls=files['video_urls'],
                interview_questions=INTERVIEW_QUESTIONS,
                use_optimized=use_optimized
            )
            
            logger.info(f"✅ [MAIN] Assessment pipeline completed")
            logger.info(f"   - Processing time: {result.get('processing_time_seconds', 0):.2f}s")
            logger.info(f"   - Completed at: {result.get('completed_at', 'N/A')}")
            print(f"   ✅ Assessment completed")
            
            # Force cleanup after assessment
            print(f"📥 STEP 6: Post-assessment cleanup...")
            logger.info(f"🧹 [MAIN] Running post-assessment cleanup")
            force_cleanup()
            logger.info(f"✅ [MAIN] Cleanup completed")
            
        except Exception as e:
            error_msg = f"ERROR in run_assessment(): {type(e).__name__}: {e}"
            print(f"   ❌ {error_msg}")
            logger.error(f"❌ [MAIN] {error_msg}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            traceback.print_exc()
            # Force cleanup even on error
            logger.info(f"🧹 [MAIN] Running cleanup after error")
            force_cleanup()
            raise
        
        # Check for errors
        if result.get('errors'):
            error_count = len(result['errors'])
            print(f"⚠️  Assessment completed with errors: {result['errors']}")
            logger.warning(f"⚠️  Assessment completed with {error_count} error(s) for user_id={request.user_id}")
            for idx, error in enumerate(result['errors'], 1):
                logger.warning(f"   Error {idx}: {error}")
        
        # Extract final decision
        final_decision = result.get('final_decision', {})
        
        logger.info(f"📋 [MAIN] Extracting final decision for user_id={request.user_id}")
        logger.info(f"   - Final decision available: {bool(final_decision)}")
        
        if not final_decision:
            error_msg = "Assessment failed to produce final decision"
            logger.error(f"❌ [MAIN] {error_msg} for user_id={request.user_id}")
            logger.error(f"   Available keys in result: {list(result.keys())}")
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
        
        logger.info(f"✅ [MAIN] Final decision extracted:")
        logger.info(f"   - Decision: {final_decision.get('decision')}")
        logger.info(f"   - Final Score: {final_decision.get('final_score')}")
        logger.info(f"   - Reasoning: {final_decision.get('reasoning', '')[:100]}...")
        
        # Build response
        component_scores = final_decision.get('component_scores', {})
        
        # Log what we're storing in the response
        logger.info(f"📦 BUILDING RESPONSE for user_id={result['user_id']}")
        logger.info(f"   ✅ Decision: {final_decision.get('decision')}")
        logger.info(f"   ✅ Final Score: {final_decision.get('final_score')}")
        logger.info(f"   ✅ Component Scores: {component_scores}")
        logger.info(f"   ✅ Processing Time: {result.get('processing_time_seconds', 0):.2f}s")
        
        # Log agent results availability
        has_identity = result.get('identity_verification') is not None
        has_quality = result.get('video_quality') is not None
        has_transcription = result.get('transcriptions') is not None
        has_content = result.get('content_evaluation') is not None
        has_behavioral = result.get('behavioral_analysis') is not None
        
        logger.info(f"   📊 Agent Results Status:")
        logger.info(f"      - Identity Verification: {'✅' if has_identity else '❌'}")
        logger.info(f"      - Video Quality: {'✅' if has_quality else '❌'}")
        logger.info(f"      - Transcription: {'✅' if has_transcription else '❌'}")
        logger.info(f"      - Content Evaluation: {'✅' if has_content else '❌'}")
        logger.info(f"      - Behavioral Analysis: {'✅' if has_behavioral else '❌'}")
        
        # Log detailed agent results
        if has_identity:
            identity_data = result.get('identity_verification', {})
            logger.info(f"   🔍 Identity Details:")
            logger.info(f"      - Verified: {identity_data.get('verified', False)}")
            logger.info(f"      - Confidence: {identity_data.get('confidence', 0):.1f}%")
            logger.info(f"      - Name Match: {identity_data.get('name_match', False)}")
            logger.info(f"      - Face Verified: {identity_data.get('face_verified', False)}")
            if not identity_data.get('verified', False):
                logger.warning(f"      ⚠️  Identity verification FAILED for user_id={result['user_id']}")
        
        if has_quality:
            quality_data = result.get('video_quality', {})
            logger.info(f"   📹 Quality Details:")
            logger.info(f"      - Quality Passed: {quality_data.get('quality_passed', False)}")
            logger.info(f"      - Overall Score: {quality_data.get('overall_score', 0):.1f}/100")
            issues = quality_data.get('video_analyses', [{}])[0].get('issues', [])
            if issues:
                logger.warning(f"      ⚠️  Quality Issues: {', '.join(issues)}")
        
        if has_content:
            content_data = result.get('content_evaluation', {})
            logger.info(f"   📊 Content Details:")
            logger.info(f"      - Overall Score: {content_data.get('overall_score', 0):.1f}/100")
            logger.info(f"      - Questions Passed: {content_data.get('questions_passed', 0)}/4")
            failed_questions = [q for q in content_data.get('question_evaluations', []) if not q.get('passed', False)]
            if failed_questions:
                logger.warning(f"      ⚠️  Failed Questions: {[q.get('question_number') for q in failed_questions]}")
        
        if has_behavioral:
            behavioral_data = result.get('behavioral_analysis', {})
            logger.info(f"   🎭 Behavioral Details:")
            logger.info(f"      - Behavioral Score: {behavioral_data.get('behavioral_score', 0):.1f}/100")
        
        # Log errors if any
        if result.get('errors'):
            logger.error(f"   ❌ ERRORS DETECTED: {len(result['errors'])} error(s)")
            for idx, error in enumerate(result['errors'], 1):
                logger.error(f"      Error {idx}: {error}")
        
        response = AssessmentResponse(
            user_id=result['user_id'],
            decision=final_decision['decision'],
            final_score=final_decision['final_score'],
            component_scores=ComponentScores(**component_scores),
            reasoning=final_decision.get('reasoning', ''),
            recommendation=final_decision.get('recommendation', ''),
            strengths=final_decision.get('strengths', []),
            concerns=final_decision.get('concerns', []),
            processing_time_seconds=result.get('processing_time_seconds', 0),
            completed_at=result.get('completed_at', datetime.utcnow().isoformat()),
            # Include ALL agent results for database storage
            identity_verification_details=result.get('identity_verification'),
            video_quality_details=result.get('video_quality'),
            transcription_details=result.get('transcriptions'),
            content_evaluation_details=result.get('content_evaluation'),
            behavioral_analysis_details=result.get('behavioral_analysis'),
            user_form_data={"username": request.username}
        )
        
        logger.info(f"✅ Response built successfully for user_id={result['user_id']}")
        logger.info(f"   📤 Response size: ~{len(str(response.dict()))} characters")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Assessment error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Assessment failed: {str(e)}"
        )


@app.get("/api/v1/files/{user_id}")
async def check_user_files(user_id: str, bucket_name: str = "edumentor-virtual-interview"):
    """
    Check what files exist for a user in GCS bucket
    
    Useful for debugging and verifying file structure before assessment.
    
    Args:
        user_id: User ID to check
        bucket_name: GCS bucket name (default: edumentor-virtual-interview)
    
    Returns:
        Files found for the user
    """
    try:
        files = discover_user_files(user_id, bucket_name)
        return {
            "user_id": user_id,
            "bucket": bucket_name,
            "status": "ready",
            "files_found": {
                "profile_pic": files['profile_pic_url'],
                "gov_id": files['gov_id_url'],
                "videos": files['video_urls'],
                "video_count": len(files['video_urls'])
            }
        }
    except HTTPException as e:
        return {
            "user_id": user_id,
            "bucket": bucket_name,
            "status": "error",
            "error": e.detail
        }


@app.get("/api/v1/status/{user_id}")
async def get_assessment_status(user_id: str):
    """
    Get status of an assessment (for async workflows)
    
    Note: Current implementation is synchronous.
    This endpoint is a placeholder for future async support.
    """
    return {
        "user_id": user_id,
        "status": "synchronous_only",
        "message": "Current version processes assessments synchronously"
    }


# ========== Startup/Shutdown Events ==========

@app.on_event("startup")
async def startup_event():
    """Initialize on startup and cleanup temp files"""
    print("="*70)
    print("🚀 Video Interview Assessment API Starting...")
    print("="*70)
    
    # Check memory status
    memory_ok = check_memory_status()
    if not memory_ok:
        print("⚠️  Starting with low memory - monitoring closely")
    
    # Cleanup any leftover temp files from previous runs
    import tempfile
    import glob
    temp_dir = tempfile.gettempdir()
    
    try:
        # Delete old temp files (*.jpg, *.flac, *.mp4, etc.)
        patterns = ['*.jpg', '*.jpeg', '*.png', '*.flac', '*.mp4', '*.webm']
        deleted_count = 0
        
        for pattern in patterns:
            temp_files = glob.glob(os.path.join(temp_dir, pattern))
            for temp_file in temp_files:
                try:
                    # Only delete files older than 1 hour
                    if os.path.getmtime(temp_file) < (datetime.now().timestamp() - 3600):
                        os.unlink(temp_file)
                        deleted_count += 1
                except:
                    pass
        
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old temp files from {temp_dir}")
    except Exception as e:
        print(f"⚠️  Temp cleanup warning: {e}")
    
    # Force initial garbage collection
    force_cleanup()
    
    print(f"📝 Docs: http://localhost:8080/docs")
    print(f"🏥 Health: http://localhost:8080/health")
    print(f"🎯 Assess: POST http://localhost:8080/api/v1/assess")
    print("="*70)
    
    # Check environment
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  WARNING: GOOGLE_API_KEY not set!")
    else:
        print("✅ GOOGLE_API_KEY configured")
    
    # Check GCP credentials
    if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print("✅ GCP credentials configured")
    else:
        print("⚠️  WARNING: GOOGLE_APPLICATION_CREDENTIALS not set!")
    
    print("="*70 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("\n🛑 Video Interview Assessment API Shutting Down...")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        reload=True
    )

