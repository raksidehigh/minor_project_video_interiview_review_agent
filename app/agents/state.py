"""
LangGraph State Definition
Defines the shared state structure for all agents
"""
from typing import TypedDict, List, Dict, Optional, Literal
from typing_extensions import Annotated
import operator


class VideoAnalysis(TypedDict):
    """Single video analysis result"""
    video_url: str
    resolution: tuple[int, int]
    fps: float
    duration: float
    quality_score: float
    issues: List[str]


class TranscriptionResult(TypedDict):
    """Single video transcription"""
    video_url: str
    transcript: str
    confidence: float
    word_count: int
    speaking_rate: float
    filler_words: int
    # New Chirp 3 fields (optional for backward compatibility)
    word_timestamps: Optional[List[Dict]]  # Word-level timestamps and confidence
    detected_language: Optional[str]  # Auto-detected language code
    duration: Optional[float]  # Audio duration in seconds


class InterviewState(TypedDict):
    """
    Complete state for video interview assessment.
    This state is passed through all agents in the workflow.
    """
    # ========== INPUT (Required) ==========
    user_id: str
    username: str  # Candidate's full name (to verify against government ID)
    profile_pic_url: str  # GCS URL: gs://bucket/user_id/profile_pic.jpg
    gov_id_url: str  # GCS URL to government ID photo: gs://bucket/user_id/gov_id.jpg
    video_urls: List[str]  # List of video GCS URLs (video_0 for identity + video_1-5 for interview)
    
    # ========== INTERVIEW QUESTIONS (Hardcoded) ==========
    interview_questions: List[Dict]  # 5 hardcoded questions with criteria
    # [
    #   {
    #     "question_number": 1,
    #     "question": "Please introduce yourself...",
    #     "goal": "...",
    #     "criteria": {"content_check": "...", "sentiment_check": "..."}
    #   },
    #   ...
    # ]
    
    # ========== AGENT OUTPUTS ==========
    
    # Agent 1: Identity Verification (with name verification)
    identity_verification: Optional[Dict]
    # {
    #   "verified": bool,
    #   "confidence": float,
    #   "name_match": bool,
    #   "extracted_name": str,
    #   "expected_name": str,
    #   "face_verification": {...},
    #   "video_results": [...],
    #   "red_flags": [...]
    # }
    
    # Agent 2: Video Quality
    video_quality: Optional[Dict]
    # {
    #   "quality_passed": bool,
    #   "overall_score": float,
    #   "video_analyses": [VideoAnalysis, ...]
    # }
    
    # Agent 3: Speech-to-Text
    transcriptions: Optional[Dict]
    # {
    #   "transcription_complete": bool,
    #   "transcriptions": [TranscriptionResult, ...],
    #   "avg_confidence": float
    # }
    
    # Agent 4: Content Evaluation (Question-specific)
    content_evaluation: Optional[Dict]
    # {
    #   "question_evaluations": [
    #     {
    #       "question_number": 1,
    #       "passed": bool,
    #       "score": float,
    #       "content_check_passed": bool,
    #       "sentiment_check_passed": bool,
    #       "feedback": str
    #     },
    #     ...
    #   ],
    #   "overall_score": float,
    #   "questions_passed": int,
    #   "questions_failed": int
    # }
    
    # Agent 5: Behavioral Analysis
    behavioral_analysis: Optional[Dict]
    # {
    #   "behavioral_score": float,
    #   "confidence_level": str,
    #   "emotional_consistency": float,
    #   "traits": [...]
    # }
    
    # Agent 6: Final Decision
    final_decision: Optional[Dict]
    # {
    #   "decision": "PASS" | "REVIEW" | "FAIL",
    #   "final_score": float,
    #   "component_scores": {...},
    #   "reasoning": str,
    #   "recommendation": str
    # }
    
    # ========== CONTROL FLOW ==========
    should_continue: bool  # If False, workflow stops early
    current_stage: str  # Track which stage we're in
    
    # ========== ERROR HANDLING ==========
    errors: List[str]  # Error messages
    
    # ========== DEPRECATED (Not used anymore) ==========
    user_form_data: Optional[Dict]  # Kept for backward compatibility
    
    # ========== METADATA ==========
    started_at: Optional[str]  # ISO timestamp
    completed_at: Optional[str]  # ISO timestamp
    processing_time_seconds: Optional[float]


class GraphConfig(TypedDict):
    """Configuration for the workflow"""
    enable_parallel: bool  # Enable parallel execution
    skip_on_identity_fail: bool  # Stop if identity verification fails
    llm_model: str  # Gemini model to use
    temperature: float  # LLM temperature
    max_retries: int  # Retry count for failures

