"""
Batched Evaluation Node
Single Gemini API call for all content + behavioral analysis
Replaces 6-7 separate calls with 1 batched call
"""
import os
import json
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import InterviewState


def extract_json_from_response(content: str) -> str:
    """
    Extract clean JSON from Gemini response that may have markdown formatting
    """
    # Remove markdown code blocks
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0]
    elif '```' in content:
        content = content.split('```')[1].split('```')[0]
    
    # Strip whitespace
    content = content.strip()
    
    return content


def batched_evaluation(state: InterviewState) -> InterviewState:
    """
    Single batched Gemini call for content + behavioral analysis
    
    Evaluates all 5 questions + behavioral patterns in ONE API call
    Returns structured JSON with all evaluations
    """
    print(f"\n📊🎭 Agent 4+5: Batched Content & Behavioral Evaluation (Single Gemini Call)")
    
    response = None
    try:
        # Get all required data
        transcriptions = state.get('transcriptions', {})
        interview_questions = state.get('interview_questions', [])
        identity_data = state.get('identity_verification', {})
        
        if not transcriptions.get('transcription_complete'):
            raise ValueError("Transcriptions not complete")
        
        # Prepare transcripts
        transcripts_list = transcriptions.get('transcriptions', [])
        
        # Log what batched evaluation receives from Agent 3
        print(f"\n   📥 AGENT 4+5 INPUT (from Agent 3):")
        avg_confidence = transcriptions.get('avg_confidence', 0)
        total_words = transcriptions.get('total_words', 0)
        print(f"      Overall Stats:")
        print(f"         - Total Words: {total_words}")
        print(f"         - Avg Confidence: {avg_confidence*100:.1f}%")
        print(f"      Transcripts:")
        for idx, transcript_data in enumerate(transcripts_list, 1):
            transcript_text = transcript_data.get('transcript', '')
            word_count = len(transcript_text.split()) if transcript_text else 0
            print(f"         Video {idx}:")
            print(f"            - Text: \"{transcript_text[:100]}{'...' if len(transcript_text) > 100 else ''}\"")
            print(f"            - Words: {word_count}, Confidence: {transcript_data.get('confidence', 0)*100:.1f}%")
            print(f"            - Language: {transcript_data.get('detected_language', 'N/A')}, Rate: {transcript_data.get('speaking_rate', 0):.1f} wpm")
            print(f"            - Filler words: {transcript_data.get('filler_words', 0)}")
        
        # Build comprehensive prompt
        prompt = build_batched_prompt(transcripts_list, interview_questions, identity_data)
        
        # Single Gemini API call
        print(f"   🤖 Making single batched Gemini API call...")
        # Use service account credentials (ADC) instead of API key
        # API keys are not supported - must use OAuth2/service account
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            # Uses Application Default Credentials (service account) automatically
        )
        
        response = llm.invoke([
            SystemMessage(content="You are an expert interview evaluator. Return ONLY valid JSON, no markdown."),
            HumanMessage(content=prompt)
        ])
        
        # Clean and parse JSON response
        cleaned_content = extract_json_from_response(response.content)
        result = json.loads(cleaned_content)
        
        print(f"   ✅ Batched evaluation complete!")
        print(f"      - Content Score: {result['content_evaluation']['overall_score']:.1f}/100")
        print(f"      - Behavioral Score: {result['behavioral_analysis']['behavioral_score']:.1f}/100")
        print(f"      - Questions Passed: {result['content_evaluation']['questions_passed']}/5")
        
        # Update state with parsed results
        state['content_evaluation'] = result['content_evaluation']
        state['behavioral_analysis'] = result['behavioral_analysis']
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {str(e)}"
        print(f"   ❌ {error_msg}")
        if response:
            print(f"   🔍 Raw response preview: {response.content[:500]}...")
    except Exception as e:
        error_msg = f"Batched evaluation error: {str(e)}"
        print(f"   ❌ {error_msg}")
        
        # Fallback: set default values
        state['content_evaluation'] = {
            "overall_score": 50.0,
            "questions_passed": 0,
            "questions_failed": 4,
            "question_evaluations": [],
            "error": error_msg
        }
        state['behavioral_analysis'] = {
            "behavioral_score": 50.0,
            "error": error_msg
        }
        state['errors'].append(error_msg)
    
    return state


def build_batched_prompt(transcripts: List[Dict], questions: List[Dict], identity_data: Dict) -> str:
    """
    Build comprehensive prompt for batched evaluation - Full Stack Developer Interview
    """
    
    # Build transcript section (skip video_0, use video_1-5)
    transcripts_text = ""
    for i, t in enumerate(transcripts[1:6], 1):  # Skip first video (identity), use next 5
        transcript = t.get('transcript', '')
        transcripts_text += f"\n**Question {i} Response:**\n{transcript}\n"
    
    # Build questions section
    questions_text = ""
    for q in questions:
        qnum = q['question_number']
        questions_text += f"\n**Question {qnum}:** {q['question']}\n"
        questions_text += f"**Goal:** {q['goal']}\n"
        questions_text += f"**Criteria:** {json.dumps(q['criteria'], indent=2)}\n"
    
    # Identity context
    identity_text = f"Identity Verified: {identity_data.get('verified', False)}, Confidence: {identity_data.get('confidence', 0):.1f}%"
    
    prompt = f"""You are evaluating a Full Stack Developer technical interview. Analyze ALL 5 questions and behavioral patterns in ONE response.

{identity_text}

## INTERVIEW QUESTIONS & CRITERIA:
{questions_text}

## CANDIDATE RESPONSES (Transcripts):
{transcripts_text}

## YOUR TASK:
Evaluate EACH of the 5 technical questions based on their specific criteria, AND analyze behavioral patterns.

Return ONLY this JSON structure (no markdown, no explanation):

{{
  "content_evaluation": {{
    "overall_score": <0-100, average of all question scores>,
    "questions_passed": <count of questions with score >= 60>,
    "questions_failed": <count of questions with score < 60>,
    "pass_rate": <percentage of questions passed>,
    "summary": "<2-3 sentence summary>",
    "question_evaluations": [
      {{
        "question_number": 1,
        "passed": <true/false, pass if score >= 60>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "mentions_upload_flow": <bool>,
        "mentions_storage": <bool>,
        "mentions_cdn": <bool>,
        "mentions_database": <bool>,
        "mentions_scalability": <bool>,
        "architectural_thinking": "<strong|moderate|weak>",
        "technical_depth": <0-100>,
        "feedback": "<1 sentence feedback>"
      }},
      {{
        "question_number": 2,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "mentions_monolithic": <bool>,
        "mentions_microservices": <bool>,
        "discusses_pros_cons": <bool>,
        "mentions_context_dependency": <bool>,
        "comparison_quality": "<excellent|good|poor>",
        "technical_depth": <0-100>,
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 3,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "distinguishes_authn_authz": <bool>,
        "mentions_jwt_or_sessions": <bool>,
        "mentions_security": <bool>,
        "mentions_rbac": <bool>,
        "security_awareness": "<high|medium|low>",
        "technical_depth": <0-100>,
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 4,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "mentions_measurement": <bool>,
        "mentions_profiling": <bool>,
        "mentions_caching": <bool>,
        "mentions_database_optimization": <bool>,
        "mentions_frontend_optimization": <bool>,
        "systematic_approach": "<excellent|good|poor>",
        "technical_depth": <0-100>,
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 5,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "mentions_websockets_or_sse": <bool>,
        "mentions_message_queue": <bool>,
        "mentions_reliability": <bool>,
        "mentions_scalability": <bool>,
        "technical_choice_justified": <bool>,
        "technical_depth": <0-100>,
        "feedback": "<1 sentence>"
      }}
    ]
  }},
  "behavioral_analysis": {{
    "behavioral_score": <0-100>,
    "confidence_level": "<high|medium|low>",
    "engagement_level": "<high|medium|low>",
    "stress_indicators": <0-10 scale>,
    "authenticity_score": <0-100>,
    "communication_clarity": <0-100>,
    "problem_solving_approach": "<systematic|intuitive|unclear>",
    "overall_impression": "<2-3 sentences>",
    "strengths": [<behavioral strengths>],
    "concerns": [<behavioral concerns>]
  }}
}}

🎯 EVALUATION GUIDELINES:

**Scoring:**
- Pass threshold: 60/100 per question
- Technical depth is key: 60+ = pass, 75+ = good, 90+ = excellent
- Focus on understanding of concepts, not perfect recall

**Question 1 (System Design):**
- Must mention 3+ key components (upload, storage, CDN, database, processing)
- Bonus for discussing scalability, latency, trade-offs

**Question 2 (Architecture Comparison):**
- Must compare both monolithic and microservices
- Bonus for context-dependent reasoning

**Question 3 (Auth/AuthZ):**
- Must distinguish authentication from authorization
- Bonus for security best practices (JWT, HTTPS, RBAC)

**Question 4 (Performance Optimization):**
- Must mention measurement/profiling first
- Bonus for multi-layer optimization (frontend, backend, DB)

**Question 5 (Real-time System):**
- Must choose appropriate technology (WebSockets/SSE)
- Bonus for discussing reliability and scalability

**Behavioral:**
- Assess communication clarity, confidence, problem-solving approach
- Look for systematic thinking and technical curiosity
- Return ONLY valid JSON, no markdown formatting
"""
    
    return prompt

