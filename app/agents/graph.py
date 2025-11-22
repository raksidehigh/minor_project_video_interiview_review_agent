"""
LangGraph Workflow Definition
Orchestrates the 6-agent video interview assessment system
"""
from datetime import datetime
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .state import InterviewState
from .nodes import (
    verify_identity,
    check_quality,
    transcribe_videos,
    aggregate_decision
)
from .nodes.batched_evaluation import batched_evaluation


def create_workflow():
    """
    Create the LangGraph workflow for video interview assessment
    
    Flow (Sequential - ALL agents always run):
    1. Identity Verification
    2. Video Quality Analysis
    3. Speech-to-Text Transcription
    4. Batched Content + Behavioral Evaluation (SINGLE Gemini call)
    5. Decision Aggregation
    
    Note: All agents run regardless of identity verification result
    to gather comprehensive evidence for fraud detection.
    
    OPTIMIZATION: Batched evaluation replaces separate content + behavioral calls
    (6-7 Gemini calls reduced to 1 batched call)
    
    Returns:
        Compiled StateGraph
    """
    print("\n🏗️  Building LangGraph Workflow...")
    
    try:
        # Create graph with state
        workflow = StateGraph(InterviewState)
    except Exception as e:
        print(f"❌ ERROR creating StateGraph: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # Add nodes
    workflow.add_node("verify_identity", verify_identity)
    workflow.add_node("check_quality", check_quality)
    workflow.add_node("transcribe_videos", transcribe_videos)
    workflow.add_node("batched_evaluation", batched_evaluation)  # SINGLE call for content + behavioral
    workflow.add_node("aggregate_decision", aggregate_decision)
    
    # Define edges
    # Start with identity verification
    workflow.add_edge(START, "verify_identity")
    
    # ALWAYS continue to all agents regardless of identity result
    # This ensures we gather all evidence for fraud detection and comprehensive analysis
    workflow.add_edge("verify_identity", "check_quality")
    workflow.add_edge("check_quality", "transcribe_videos")
    workflow.add_edge("transcribe_videos", "batched_evaluation")
    
    # Batched evaluation directly to aggregator (no separate behavioral step)
    workflow.add_edge("batched_evaluation", "aggregate_decision")
    
    # Aggregator ends the workflow
    workflow.add_edge("aggregate_decision", END)
    
    # Compile with memory for state persistence
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    print("✅ Workflow compiled successfully!")
    print("\n📋 Execution Flow:")
    print("   START → verify_identity → check_quality → transcribe_videos")
    print("        → batched_evaluation (1 Gemini call) → aggregate_decision → END")
    print("   (Optimized: 6-7 Gemini calls reduced to 1 batched call)")
    
    return app


async def run_assessment(
    user_id: str,
    username: str,
    profile_pic_url: str,
    gov_id_url: str,
    video_urls: list[str],
    interview_questions: list[dict]
) -> dict:
    """
    Run complete video interview assessment for Ambassador Program
    
    Args:
        user_id: Unique identifier for the candidate
        username: Candidate's full name (to verify against government ID)
        profile_pic_url: GCS URL to profile picture
        gov_id_url: GCS URL to government ID photo
        video_urls: List of GCS URLs to videos (video_0 for identity + video_1-4 for interview)
        interview_questions: 4 hardcoded questions with evaluation criteria
    
    Returns:
        Complete assessment results with all agent outputs
    """
    print(f"\n{'='*70}")
    print(f"🎯 Starting Assessment for User: {user_id} ({username})")
    print(f"{'='*70}")
    
    # Initialize state
    initial_state: InterviewState = {
        "user_id": user_id,
        "username": username,
        "profile_pic_url": profile_pic_url,
        "gov_id_url": gov_id_url,
        "video_urls": video_urls,
        "interview_questions": interview_questions,
        "identity_verification": None,
        "video_quality": None,
        "transcriptions": None,
        "content_evaluation": None,
        "behavioral_analysis": None,
        "final_decision": None,
        "should_continue": True,
        "current_stage": "starting",
        "errors": [],
        "user_form_data": None,  # Deprecated
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "processing_time_seconds": None,
    }
    
    # Create workflow
    app = create_workflow()
    
    # Run workflow
    start_time = datetime.utcnow()
    
    try:
        config = {"configurable": {"thread_id": user_id}}
        print(f"📊 Initial state keys: {list(initial_state.keys())}")
        result = await app.ainvoke(initial_state, config=config)
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        result['completed_at'] = end_time.isoformat()
        result['processing_time_seconds'] = processing_time
        
        print(f"\n{'='*70}")
        print(f"✅ Assessment Complete!")
        print(f"⏱️  Processing Time: {processing_time:.1f}s")
        print(f"{'='*70}\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Assessment Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Test workflow creation
    app = create_workflow()
    print("\n✅ Workflow ready for deployment!")

