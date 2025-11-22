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
    Build comprehensive prompt for batched evaluation
    """
    
    # Build transcript section
    transcripts_text = ""
    for i, t in enumerate(transcripts, 1):
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
    
    prompt = f"""You are evaluating an Ambassador Program interview. Analyze ALL 4 questions and behavioral patterns in ONE response.

{identity_text}

## INTERVIEW QUESTIONS & CRITERIA:
{questions_text}

## CANDIDATE RESPONSES (Transcripts):
{transcripts_text}

## YOUR TASK:
Evaluate EACH of the 5 questions based on their specific criteria, AND analyze behavioral patterns.

Return ONLY this JSON structure (no markdown, no explanation):

{{
  "content_evaluation": {{
    "overall_score": <0-100, average of all question scores>,
    "questions_passed": <count of questions with score >= 70>,
    "questions_failed": <count of questions with score < 70>,
    "pass_rate": <percentage of questions passed>,
    "summary": "<2-3 sentence summary>",
    "question_evaluations": [
      {{
        "question_number": 1,
        "passed": <true/false, pass if score >= 70>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "clarity_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "university_found": "<university name or null>",
        "field_of_study": "<field or null>",
        "major_mentioned": <bool>,
        "appears_reputable": <bool>,
        "filler_words_excessive": <bool>,
        "sentiment": "<positive/neutral/negative>",
        "confidence_level": "<high/medium/low>",
        "feedback": "<1 sentence feedback>"
      }},
      {{
        "question_number": 2,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "sincerity_check_passed": <bool>,
        "mission_keywords_found": [<keywords>],
        "red_flags_found": [<red flags if any>],
        "enthusiasm_level": "<high/medium/low>",
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 3,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "has_structure": <bool, problem->action->result>,
        "shows_empathy": <bool>,
        "empathy_keywords_found": [<keywords>],
        "story_completeness": "<complete/partial/none>",
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 4,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "red_flag_check_passed": <bool, no negative words>,
        "sentiment_check_passed": <bool>,
        "positive_actions_found": [<actions>],
        "red_flags_found": [<red flags if any>],
        "tone": "<calm/professional/defensive>",
        "feedback": "<1 sentence>"
      }},
      {{
        "question_number": 5,
        "passed": <bool>,
        "score": <0-100>,
        "content_check_passed": <bool>,
        "sentiment_check_passed": <bool>,
        "action_keywords_found": [<action words>],
        "specific_actions_found": [<specific actions like weekly, daily>],
        "is_forward_looking": <bool>,
        "has_concrete_plan": <bool>,
        "confidence_level": "<high/medium/low>",
        "feedback": "<1 sentence>"
      }}
    ]
  }},
  "behavioral_analysis": {{
    "behavioral_score": <0-100>,
    "confidence_level": "<high/medium/low>",
    "engagement_level": "<high/medium/low>",
    "stress_indicators": <0-10 scale>,
    "authenticity_score": <0-100>,
    "communication_clarity": <0-100>,
    "overall_impression": "<2-3 sentences>",
    "strengths": [<behavioral strengths>],
    "concerns": [<behavioral concerns>],
    "red_flags": [<any red flags>]
  }}
}}

🎯 ULTRA-LENIENT MVP EVALUATION RULES (MANDATORY):

**Question 2 (Motivation):**
- ANY mention of "help", "assist", "support", "contribute" = AUTOMATIC 100, passed = true
- "get monetized" + "help students" = PERFECT (100 score) - monetization is NOT a red flag!
- Monetization/money mentions are POSITIVE motivations, NEVER red flags
- red_flags_found should be [] (empty) unless explicitly hostile
- If response exists and shows ANY interest = 100 score

**Question 4 (Handling Challenges):**
- Words like "difficult", "act difficult", "challenging" are NOT red flags - just describing situations!
- ANY approach mentioned (understand, listen, question, calm, time) = AUTOMATIC 100, passed = true
- Acknowledging challenges is POSITIVE (realistic awareness), not negative
- red_flags_found should be [] (empty) unless explicitly hostile
- red_flag_check_passed should ALWAYS be true

**Question 5 (Goals):**
- Action words like "ensure", "make sure", "be prepared", "be a good listener", "allow" COUNT AS concrete plans!
- has_concrete_plan = true if ANY action words present
- ANY goal/intention = AUTOMATIC 100, passed = true
- Don't require detailed step-by-step plans - aspirational goals are sufficient

**General Rules:**
- Give 100 score BY DEFAULT for all questions if ANY positive intent
- ONLY fail (score < 70) if: explicitly hostile, completely off-topic, or no response
- Focus on POSITIVE aspects, not finding flaws
- Return ONLY valid JSON, no markdown formatting
"""
    
    return prompt

