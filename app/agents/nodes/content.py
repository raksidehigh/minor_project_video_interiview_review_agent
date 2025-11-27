"""
Content Evaluation Node
Evaluates interview responses based on specific question criteria for Full Stack Developer Role
"""
import os
import re
import logging
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import InterviewState

logger = logging.getLogger(__name__)


def check_filler_words(text: str) -> tuple[int, bool]:
    """
    Count filler words and check if excessive
    
    Returns:
        (filler_count, is_excessive)
    """
    filler_words = ['um', 'uh', 'like', 'you know', 'basically', 'actually', 'sort of', 'kind of']
    text_lower = text.lower()
    
    filler_count = sum(text_lower.count(filler) for filler in filler_words)
    word_count = len(text.split())
    
    # Excessive if more than 30% of words are fillers
    is_excessive = (filler_count / word_count * 100) > 30 if word_count > 0 else False
    
    return filler_count, is_excessive


def check_keywords(text: str, keywords: List[str]) -> tuple[int, List[str]]:
    """
    Check for presence of specific keywords
    
    Returns:
        (count_found, found_keywords)
    """
    text_lower = text.lower()
    found = [kw for kw in keywords if kw.lower() in text_lower]
    return len(found), found


def evaluate_question_1(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 1: System Design: Design a Video Streaming Platform Like YouTube.
    
    Criteria:
    - Content Check: Architectural thinking, key components (upload, processing, storage, CDN, database)
    - Clarity Check: Structured approach (requirements -> design -> components)
    - Sentiment Check: Confident and analytical
    """
    filler_count, is_excessive = check_filler_words(transcript)
    
    prompt = f"""Analyze this system design answer for a Full Stack Developer interview.

"{transcript}"

EVALUATION CRITERIA:
1. Must demonstrate architectural thinking for a video streaming platform
2. Should mention key components: upload, processing/transcoding, storage (S3/GCS), CDN, database
3. Should discuss scalability and latency considerations
4. Structured approach: requirements -> high-level design -> components

Return ONLY a JSON object:
{{
  "mentions_upload_flow": true|false,
  "mentions_storage": true|false,
  "mentions_cdn": true|false,
  "mentions_database": true|false,
  "mentions_scalability": true|false,
  "architectural_thinking": "strong|moderate|weak",
  "structure_quality": "excellent|good|poor",
  "sentiment": "positive|neutral|negative",
  "confidence_level": "high|medium|low",
  "technical_depth": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation if failed, null if passed",
  "what_was_good": "Positive aspects of the answer"
}}

SCORING GUIDANCE:
- Mentions 3+ key components → technical_depth = 70+
- Discusses scalability → technical_depth = 80+
- Complete architecture with trade-offs → technical_depth = 90+"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"LLM Error in Q1: {str(e)}")
        analysis = {
            "technical_depth": 50,
            "passed": False,
            "sentiment": "neutral",
            "confidence_level": "medium"
        }
    
    technical_depth = analysis.get('technical_depth', 50)
    llm_passed = analysis.get('passed', False)
    
    # Scoring: Technical Content (70%) + Clarity (20%) + Communication (10%)
    content_score = min(70, technical_depth * 0.7)
    clarity_score = 20 if not is_excessive else 10
    communication_score = 10 if analysis.get('sentiment') != 'negative' else 5
    
    score = content_score + clarity_score + communication_score
    overall_passed = score >= 60 or llm_passed
    
    return {
        "question_number": 1,
        "passed": overall_passed,
        "score": round(score, 2),
        "content_check_passed": technical_depth >= 60,
        "clarity_check_passed": not is_excessive,
        "sentiment_check_passed": analysis.get('sentiment') != 'negative',
        "technical_depth": technical_depth,
        "filler_words_count": filler_count,
        "sentiment": analysis.get('sentiment', 'neutral'),
        "confidence_level": analysis.get('confidence_level', 'medium'),
        "why_failed": analysis.get('why_failed'),
        "what_was_good": analysis.get('what_was_good'),
        "feedback": f"{'✅' if overall_passed else '❌'} System Design - Technical Depth: {technical_depth}%, Score: {score}/100"
    }


def evaluate_question_2(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 2: Explain the Trade-offs Between Monolithic vs Microservices Architecture.
    
    Criteria:
    - Content Check: Comparison of pros/cons, organizational impact, context-dependent choice
    - Clarity Check: Clear comparison structure
    - Sentiment Check: Balanced and objective
    """
    filler_count, is_excessive = check_filler_words(transcript)
    
    prompt = f"""Analyze this architecture comparison answer.

"{transcript}"

EVALUATION CRITERIA:
1. Must compare monolithic vs microservices architectures
2. Should discuss: simplicity, deployment, scaling, complexity, team size, maintenance
3. Should explain that choice depends on context
4. Balanced view of both approaches

Return ONLY a JSON object:
{{
  "mentions_monolithic": true|false,
  "mentions_microservices": true|false,
  "discusses_pros_cons": true|false,
  "mentions_context_dependency": true|false,
  "comparison_quality": "excellent|good|poor",
  "sentiment": "positive|neutral|negative",
  "technical_depth": 0-100,
  "passed": true|false,
  "why_failed": "Explanation if failed, null if passed",
  "what_was_good": "Positive aspects"
}}

SCORING GUIDANCE:
- Mentions both architectures → technical_depth = 60+
- Discusses trade-offs → technical_depth = 75+
- Context-aware answer → technical_depth = 90+"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"LLM Error in Q2: {str(e)}")
        analysis = {"technical_depth": 50, "passed": False}
    
    technical_depth = analysis.get('technical_depth', 50)
    content_score = min(70, technical_depth * 0.7)
    clarity_score = 20 if not is_excessive else 10
    communication_score = 10 if analysis.get('sentiment') != 'negative' else 5
    
    score = content_score + clarity_score + communication_score
    overall_passed = score >= 60 or analysis.get('passed', False)
    
    return {
        "question_number": 2,
        "passed": overall_passed,
        "score": round(score, 2),
        "content_check_passed": technical_depth >= 60,
        "clarity_check_passed": not is_excessive,
        "sentiment_check_passed": analysis.get('sentiment') != 'negative',
        "technical_depth": technical_depth,
        "filler_words_count": filler_count,
        "why_failed": analysis.get('why_failed'),
        "what_was_good": analysis.get('what_was_good'),
        "feedback": f"{'✅' if overall_passed else '❌'} Architecture Comparison - Depth: {technical_depth}%, Score: {score}/100"
    }


def evaluate_question_3(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 3: How Would You Handle Authentication and Authorization in a Full Stack Application?
    
    Criteria:
    - Content Check: Distinction between AuthN/AuthZ, JWT/session, OAuth, RBAC, security
    - Clarity Check: Clear distinction and explanation
    - Sentiment Check: Professional and knowledgeable
    """
    filler_count, is_excessive = check_filler_words(transcript)
    
    prompt = f"""Analyze this authentication/authorization answer.

"{transcript}"

EVALUATION CRITERIA:
1. Must distinguish between authentication (who) and authorization (what)
2. Should discuss: JWT, sessions, OAuth, RBAC, security best practices
3. Should mention HTTPS, token storage (cookies vs localStorage)
4. Security-conscious approach

Return ONLY a JSON object:
{{
  "distinguishes_authn_authz": true|false,
  "mentions_jwt_or_sessions": true|false,
  "mentions_security": true|false,
  "mentions_rbac": true|false,
  "security_awareness": "high|medium|low",
  "technical_depth": 0-100,
  "passed": true|false,
  "why_failed": "Explanation if failed, null if passed",
  "what_was_good": "Positive aspects"
}}

SCORING GUIDANCE:
- Distinguishes AuthN/AuthZ → technical_depth = 60+
- Mentions JWT/sessions + security → technical_depth = 75+
- Complete security strategy → technical_depth = 90+"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"LLM Error in Q3: {str(e)}")
        analysis = {"technical_depth": 50, "passed": False}
    
    technical_depth = analysis.get('technical_depth', 50)
    content_score = min(70, technical_depth * 0.7)
    clarity_score = 20 if not is_excessive else 10
    communication_score = 10 if analysis.get('sentiment', 'neutral') != 'negative' else 5
    
    score = content_score + clarity_score + communication_score
    overall_passed = score >= 60 or analysis.get('passed', False)
    
    return {
        "question_number": 3,
        "passed": overall_passed,
        "score": round(score, 2),
        "content_check_passed": technical_depth >= 60,
        "clarity_check_passed": not is_excessive,
        "sentiment_check_passed": True,
        "technical_depth": technical_depth,
        "filler_words_count": filler_count,
        "why_failed": analysis.get('why_failed'),
        "what_was_good": analysis.get('what_was_good'),
        "feedback": f"{'✅' if overall_passed else '❌'} Auth/AuthZ - Depth: {technical_depth}%, Score: {score}/100"
    }


def evaluate_question_4(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 4: Describe Your Approach to Optimizing the Performance of a Slow Web Application.
    
    Criteria:
    - Content Check: Systematic approach (measure -> identify -> optimize), multi-layer optimization
    - Clarity Check: Logical flow
    - Sentiment Check: Problem-solving oriented
    """
    filler_count, is_excessive = check_filler_words(transcript)
    
    prompt = f"""Analyze this performance optimization answer.

"{transcript}"

EVALUATION CRITERIA:
1. Must describe systematic approach: Measure -> Identify -> Optimize
2. Should mention: profiling, caching, database indexing, bundle size, CDN, lazy loading
3. Multi-layer optimization (frontend, backend, database)
4. Problem-solving mindset

Return ONLY a JSON object:
{{
  "mentions_measurement": true|false,
  "mentions_profiling": true|false,
  "mentions_caching": true|false,
  "mentions_database_optimization": true|false,
  "mentions_frontend_optimization": true|false,
  "systematic_approach": "excellent|good|poor",
  "technical_depth": 0-100,
  "passed": true|false,
  "why_failed": "Explanation if failed, null if passed",
  "what_was_good": "Positive aspects"
}}

SCORING GUIDANCE:
- Mentions measurement/profiling → technical_depth = 60+
- Multi-layer optimization → technical_depth = 75+
- Complete systematic approach → technical_depth = 90+"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"LLM Error in Q4: {str(e)}")
        analysis = {"technical_depth": 50, "passed": False}
    
    technical_depth = analysis.get('technical_depth', 50)
    content_score = min(70, technical_depth * 0.7)
    clarity_score = 20 if not is_excessive else 10
    communication_score = 10
    
    score = content_score + clarity_score + communication_score
    overall_passed = score >= 60 or analysis.get('passed', False)
    
    return {
        "question_number": 4,
        "passed": overall_passed,
        "score": round(score, 2),
        "content_check_passed": technical_depth >= 60,
        "clarity_check_passed": not is_excessive,
        "sentiment_check_passed": True,
        "technical_depth": technical_depth,
        "filler_words_count": filler_count,
        "why_failed": analysis.get('why_failed'),
        "what_was_good": analysis.get('what_was_good'),
        "feedback": f"{'✅' if overall_passed else '❌'} Performance Optimization - Depth: {technical_depth}%, Score: {score}/100"
    }


def evaluate_question_5(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 5: How Would You Design a Real-time Notification System?
    
    Criteria:
    - Content Check: Technology choice (WebSockets/SSE), architecture, reliability
    - Clarity Check: Technical justification
    - Sentiment Check: Confident in technical choices
    """
    filler_count, is_excessive = check_filler_words(transcript)
    
    prompt = f"""Analyze this real-time system design answer.

"{transcript}"

EVALUATION CRITERIA:
1. Must choose appropriate technology: WebSockets, Socket.io, SSE, or polling
2. Should discuss: concurrency, message queues (Redis/Kafka), reliability
3. Architectural components and scalability
4. Technical justification for choices

Return ONLY a JSON object:
{{
  "mentions_websockets_or_sse": true|false,
  "mentions_message_queue": true|false,
  "mentions_reliability": true|false,
  "mentions_scalability": true|false,
  "technical_choice_justified": true|false,
  "technical_depth": 0-100,
  "passed": true|false,
  "why_failed": "Explanation if failed, null if passed",
  "what_was_good": "Positive aspects"
}}

SCORING GUIDANCE:
- Mentions WebSockets/SSE → technical_depth = 60+
- Discusses architecture + reliability → technical_depth = 75+
- Complete system with trade-offs → technical_depth = 90+"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"LLM Error in Q5: {str(e)}")
        analysis = {"technical_depth": 50, "passed": False}
    
    technical_depth = analysis.get('technical_depth', 50)
    content_score = min(70, technical_depth * 0.7)
    clarity_score = 20 if not is_excessive else 10
    communication_score = 10 if analysis.get('sentiment', 'neutral') != 'negative' else 5
    
    score = content_score + clarity_score + communication_score
    overall_passed = score >= 60 or analysis.get('passed', False)
    
    return {
        "question_number": 5,
        "passed": overall_passed,
        "score": round(score, 2),
        "content_check_passed": technical_depth >= 60,
        "clarity_check_passed": not is_excessive,
        "sentiment_check_passed": True,
        "technical_depth": technical_depth,
        "filler_words_count": filler_count,
        "why_failed": analysis.get('why_failed'),
        "what_was_good": analysis.get('what_was_good'),
        "feedback": f"{'✅' if overall_passed else '❌'} Real-time System - Depth: {technical_depth}%, Score: {score}/100"
    }


def evaluate_content(state: InterviewState) -> InterviewState:
    """
    Main content evaluation node - evaluates all 5 interview questions
    """
    logger.info("🎯 [CONTENT] Starting content evaluation...")
    
    transcriptions = state.get('transcriptions', {})
    if not transcriptions or not transcriptions.get('transcription_complete'):
        logger.error("❌ [CONTENT] No transcriptions available")
        state['errors'].append("Content evaluation failed: No transcriptions")
        return state
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.3,
        google_api_key=os.getenv('GOOGLE_API_KEY')
    )
    
    # Evaluate each question
    transcription_list = transcriptions.get('transcriptions', [])
    question_evaluations = []
    
    # Map video indices to questions (video_1 -> Q1, video_2 -> Q2, etc.)
    for i, trans_result in enumerate(transcription_list[1:6], 1):  # Skip video_0 (identity)
        transcript = trans_result.get('transcript', '')
        
        if i == 1:
            result = evaluate_question_1(transcript, llm)
        elif i == 2:
            result = evaluate_question_2(transcript, llm)
        elif i == 3:
            result = evaluate_question_3(transcript, llm)
        elif i == 4:
            result = evaluate_question_4(transcript, llm)
        elif i == 5:
            result = evaluate_question_5(transcript, llm)
        
        question_evaluations.append(result)
        logger.info(f"   Q{i}: {'✅ PASS' if result['passed'] else '❌ FAIL'} - Score: {result['score']}/100")
    
    # Calculate overall score
    total_score = sum(q['score'] for q in question_evaluations)
    overall_score = total_score / len(question_evaluations)
    questions_passed = sum(1 for q in question_evaluations if q['passed'])
    questions_failed = len(question_evaluations) - questions_passed
    
    state['content_evaluation'] = {
        "question_evaluations": question_evaluations,
        "overall_score": round(overall_score, 2),
        "questions_passed": questions_passed,
        "questions_failed": questions_failed
    }
    
    logger.info(f"✅ [CONTENT] Evaluation complete - Overall: {overall_score:.1f}/100, Passed: {questions_passed}/5")
    
    return state
