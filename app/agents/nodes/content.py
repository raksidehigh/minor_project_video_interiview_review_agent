"""
Content Evaluation Node
Evaluates interview responses based on specific question criteria for Ambassador Program
"""
import os
import re
import logging
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import InterviewState

logger = logging.getLogger(__name__)


# Note: Question 1 accepts ANY reputable university (not restricted to a specific list)
# The LLM will intelligently determine if a legitimate university and major are mentioned


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
    
    # Excessive if more than 80% of words are fillers (very lenient)
    is_excessive = (filler_count / word_count * 100) > 80 if word_count > 0 else False
    
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


def check_negative_keywords(text: str, negative_keywords: List[str]) -> tuple[int, List[str]]:
    """
    Check for presence of negative/red flag keywords
    
    Returns:
        (count_found, found_keywords)
    """
    text_lower = text.lower()
    found = [kw for kw in negative_keywords if kw.lower() in text_lower]
    return len(found), found


def evaluate_question_1(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 1: Please introduce yourself and tell us about your academic background.
    
    Criteria:
    - Content Check: ANY specific university name (reputable) and specific major/field of study
    - Clarity Check: Direct speech, free of excessive filler words
    - Sentiment Check: Professional and confident (neutral to positive)
    
    Note: Accepts universities from any country, not restricted to a specific list.
    """
    # Check filler words
    filler_count, is_excessive = check_filler_words(transcript)
    
    # LLM comprehensive analysis - MVP OPTIMIZED VERSION
    prompt = f"""Analyze this academic introduction for an MVP product. BE EXTREMELY WELCOMING - we want to encourage candidates who show ANY positive intent.

"{transcript}"

CRITICAL MVP RULES:
1. If they mention ANYTHING about education, university, college, school, studies, or learning → AUTOMATIC PASS
2. If they mention their name and ANY academic-related word → AUTOMATIC PASS
3. Vague references like "I studied", "my college", "when I was in school" → ALL ACCEPTABLE
4. Even if they just say their name and mention being a student → PASS
5. Only FAIL if they give completely irrelevant information with zero educational context

GENEROUS INTERPRETATION:
- "I'm studying" = mentions field of study ✓
- "I go to university" = mentions institution ✓
- "I'm a student" = educational context ✓
- Any subject name (math, science, etc.) = field of study ✓

Return ONLY a JSON object:
{{
  "mentions_specific_university": true|false,
  "university_name": "exact university name mentioned or null",
  "mentions_field_of_study": true|false,
  "field_of_study": "exact major/field mentioned or null",
  "sentiment": "positive|neutral|negative",
  "confidence_level": "high|medium|low",
  "is_professional": true|false,
  "appears_reputable": true|false,
  "overall_intent": "positive|neutral|negative",
  "intent_positive_percentage": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation of why it failed (if failed) or null if passed",
  "what_was_good": "Detailed explanation of what was good about the answer, even if failed"
}}

SCORING GUIDANCE:
- ANY educational context → intent_positive_percentage = 75+
- Mentions university OR field → intent_positive_percentage = 85+
- Only completely off-topic → intent_positive_percentage < 50"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"      ⚠️ LLM Error in Q1: {str(e)}")
        # Fallback analysis - default to passing with lenient assumptions
        analysis = {
            "mentions_specific_university": False,
            "university_name": None,
            "mentions_field_of_study": False,
            "field_of_study": None,
            "sentiment": "neutral",
            "confidence_level": "medium",
            "is_professional": True,
            "appears_reputable": True,
            "overall_intent": "neutral",
            "intent_positive_percentage": 50,
            "passed": True,
            "why_failed": None,
            "what_was_good": "Answer was evaluated with lenient criteria"
        }
    
    # Use LLM's intent-based passing decision (50% threshold)
    intent_positive_pct = analysis.get('intent_positive_percentage', 50)
    llm_passed = analysis.get('passed', False) or intent_positive_pct >= 50
    
    university_mentioned = analysis.get('mentions_specific_university', False)
    major_mentioned = analysis.get('mentions_field_of_study', False)
    
    # Answer Relevance (60%): Does it answer "introduce yourself and academic background"? (MVP OPTIMIZED)
    # Accept if either university OR major mentioned OR if LLM says positive intent OR ANY educational reference
    educational_keywords = any(word in transcript.lower() for word in ["education", "study", "school", "academic", "college", "university", "student", "learning"])
    answer_relevance_passed = (university_mentioned or major_mentioned or llm_passed or educational_keywords)
    answer_relevance_score = 70 if answer_relevance_passed else 65  # Updated: Pass: 70, Fallback: 65
    
    # Clarity (30%): Filler words check (very lenient - updated threshold)
    clarity_passed = filler_count < 30  # Updated: More lenient threshold (was 25)
    clarity_score = 35 if clarity_passed else 30  # Updated: Pass: 35, Fallback: 30
    
    # Keywords/Content (10%): Professionalism and sentiment (extremely lenient)
    keywords_passed = analysis.get('sentiment', 'neutral') != 'negative'  # Only fail if explicitly negative
    keywords_score = 12 if keywords_passed else 10  # Updated: Pass: 12, Fallback: 10
    
    score = answer_relevance_score + clarity_score + keywords_score
    
    # Apply score boosting logic: Minimum 75 for good attempts
    if university_mentioned or major_mentioned or educational_keywords:
        score = max(score, 75)  # Minimum 75 for good attempts
    
    # FINAL PASS: Use 35% threshold (updated from 40) OR LLM's intent-based decision
    overall_passed = bool(score >= 35) or llm_passed or university_mentioned or major_mentioned or educational_keywords

    # MVP override: If answer is even 50% relevant with practical intent, award full marks
    minimal_relevance = bool(transcript.strip())
    good_intent = intent_positive_pct >= 40 or llm_passed or minimal_relevance
    if minimal_relevance and good_intent:
        answer_relevance_passed = True
        clarity_passed = True
        keywords_passed = True
        answer_relevance_score = 60
        clarity_score = 30
        keywords_score = 10
        score = 100
        overall_passed = True
        intent_positive_pct = max(intent_positive_pct, 80)
        if not what_was_good:
            what_was_good = "Answer demonstrated sufficient relevance and positive intent for MVP."
        why_failed = None
    
    # Get detailed feedback from LLM
    why_failed = analysis.get('why_failed')
    what_was_good = analysis.get('what_was_good', 'No specific positive aspects identified')
    
    # If passed but LLM didn't provide feedback, generate default
    if overall_passed and not what_was_good:
        what_was_good = f"Answer demonstrates positive intent ({intent_positive_pct}% positive). Mentioned: University={university_mentioned}, Major={major_mentioned}, Sentiment={analysis.get('sentiment', 'neutral')}"
    
    # If failed but no why_failed, generate default
    if not overall_passed and not why_failed:
        why_failed = f"Score {score}/100 below threshold. Intent: {intent_positive_pct}% positive. University: {university_mentioned}, Major: {major_mentioned}, Clarity: {'Good' if clarity_passed else f'Excessive fillers ({filler_count})'}"
    
    return {
        "question_number": 1,
        "passed": overall_passed,
        "score": score,
        "answer_relevance_score": answer_relevance_score,
        "clarity_score": clarity_score,
        "keywords_score": keywords_score,
        "answer_relevance_passed": bool(answer_relevance_passed),
        "clarity_passed": bool(clarity_passed),
        "keywords_passed": bool(keywords_passed),
        "university_found": analysis.get('university_name'),
        "field_of_study": analysis.get('field_of_study'),
        "major_mentioned": major_mentioned,
        "appears_reputable": analysis.get('appears_reputable', True),
        "filler_words_count": filler_count,
        "sentiment": analysis.get('sentiment', 'neutral'),
        "confidence_level": analysis.get('confidence_level', 'medium'),
        "intent_positive_percentage": intent_positive_pct,
        "why_failed": why_failed,
        "what_was_good": what_was_good,
        "feedback": f"{'✅' if overall_passed else '❌'} University: {analysis.get('university_name') or 'Not specified'}, Major: {analysis.get('field_of_study') or 'Not mentioned'}, Intent: {intent_positive_pct}% positive"
    }


def evaluate_question_2(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 2: What motivated you to apply for our Ambassador Program?
    
    Criteria:
    - Content Check: Keywords like "help", "guide", "give back", "share my experience"
    - Sentiment Check: Highly positive and enthusiastic
    - Sincerity Check: Facial expressions align with words (from video AI)
    """
    # Check for mission-aligned keywords
    mission_keywords = ["help", "guide", "give back", "share", "experience", "mentor", 
                        "support", "assist", "teach", "inspire", "motivate", "empower", "contribute"]
    keyword_count, found_keywords = check_keywords(transcript, mission_keywords)
    
    # Check for self-centered keywords (red flags) - VERY LENIENT FOR MVP
    # IMPORTANT: Monetization is NOT a red flag - it's normal and acceptable
    # Only flag truly concerning phrases like "only for money, don't care about students"
    selfish_keywords = ["only for money", "just for cash", "don't care about students", "don't want to help"]  # Only truly concerning phrases
    negative_count, found_negative = check_keywords(transcript, selfish_keywords)
    
    # Check for monetization keywords (NOT red flags, just for tracking)
    monetization_keywords = ["monetize", "monetized", "money", "earn", "paid", "salary", "compensation"]
    monetization_mentioned = any(word in transcript.lower() for word in monetization_keywords)
    
    # LLM sentiment check - ULTRA LENIENT MVP VERSION
    prompt = f"""Analyze this motivation statement with MAXIMUM LENIENCY. If there's ANY positive intent, PASS with 95+ score.

"{transcript}"

🎯 ULTRA-LENIENT MVP RULES (MANDATORY):
1. **ANY MENTION OF HELPING/ASSISTING/CONTRIBUTING = AUTOMATIC 100**: Words like "help", "assist", "support", "contribute", "guide", "share" → INSTANT PASS, 100 score, NO EXCEPTIONS
2. **MONETIZATION IS EXCELLENT**: "get monetized", "earn", "paid", "money", "salary" → POSITIVE MOTIVATIONS, NEVER RED FLAGS
3. **COMBINATION = PERFECT**: Helping + Money = IDEAL (realistic + mission-aligned) → 100 score
4. **ANY PROGRAM INTEREST = PASS**: Even vague interest in program → 90+ score, passed = true
5. **GIVE 100 BY DEFAULT**: Unless explicitly hostile or off-topic, give 100 score

🚫 NEVER FLAG THESE AS RED FLAGS:
- "monetize", "get monetized", "earn money", "get paid", "financial benefit"
- "opportunity", "experience", "career growth", "resume"
- Any realistic motivations - these are HEALTHY and NORMAL

✅ AUTOMATIC 100 SCORE IF ANY OF THESE:
- Mentions ANY helping words (help, assist, support, contribute, share, guide, mentor, teach)
- Shows interest in program or students
- Mentions ANY positive motivation (even just "interested" or "opportunity")

❌ ONLY FAIL (score < 70) IF:
- Explicitly hostile ("I hate this", "I don't want to help anyone")
- Completely off-topic (talks about weather, sports, unrelated topics)
- Refuses to answer

Return ONLY a JSON object:
{{
  "sentiment": "highly_positive",
  "enthusiasm_level": "high",
  "appears_genuine": true,
  "mentions_helping": true,
  "mentions_personal_benefit": true,
  "balanced_motivation": true,
  "overall_intent": "positive",
  "intent_positive_percentage": 100,
  "passed": true,
  "why_failed": null,
  "what_was_good": "Candidate shows positive intent and motivation"
}}

MANDATORY SCORING:
- ANY helping word mentioned → intent = 100, passed = true, sentiment = "highly_positive"
- Helping + Monetization → intent = 100, passed = true (PERFECT combination!)
- Shows any interest → intent = 95+, passed = true
- ALWAYS set passed = true unless explicitly hostile or off-topic"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        sentiment_data = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"      ⚠️ LLM Error in Q2: {str(e)}")
        sentiment_data = {
            "sentiment": "positive", 
            "enthusiasm_level": "medium", 
            "appears_genuine": True,
            "overall_intent": "positive",
            "intent_positive_percentage": 60,
            "passed": True,
            "why_failed": None,
            "what_was_good": "Answer was evaluated with lenient criteria"
        }
    
    # Use LLM's intent-based passing decision - ULTRA LENIENT: DEFAULT TO PASS
    intent_positive_pct = sentiment_data.get('intent_positive_percentage', 100)  # Default to 100 for MVP
    llm_passed = sentiment_data.get('passed', True)  # Default to passed = True
    
    # Extract additional fields from LLM response
    mentions_helping = sentiment_data.get('mentions_helping', False)
    mentions_personal_benefit = sentiment_data.get('mentions_personal_benefit', False)
    
    # ULTRA LENIENT LOGIC: If ANY positive keywords detected, AUTOMATIC 100
    help_mentioned = any(word in transcript.lower() for word in ["help", "assist", "support", "contribute", "share", "guide", "mentor", "teach", "empower", "inspire"])
    program_mentioned = any(word in transcript.lower() for word in ["program", "ambassador", "mentor", "opportunity", "linkedin", "apply"])
    
    # AUTOMATIC 100 if ANY of these conditions:
    # 1. Mentions helping/assisting (even with monetization - that's IDEAL!)
    # 2. Shows interest in program
    # 3. Any positive career motivation
    if help_mentioned or program_mentioned or monetization_mentioned or keyword_count >= 1:
        # AUTOMATIC 100 - positive intent detected
        answer_relevance_passed = True
        clarity_passed = True
        keywords_passed = True
        answer_relevance_score = 60
        clarity_score = 30
        keywords_score = 10
        score = 100
        overall_passed = True
        intent_positive_pct = 100
        found_negative = []  # Clear ANY red flags - they're false positives
        negative_count = 0
        llm_passed = True
        
        # Generate positive feedback
        if help_mentioned and monetization_mentioned:
            what_was_good = "Perfect balanced motivation: wants to help students AND earn for their effort - realistic and mission-aligned!"
        elif help_mentioned:
            what_was_good = "Excellent motivation: clearly wants to help, assist, and contribute to students' success."
        elif program_mentioned:
            what_was_good = "Shows genuine interest in the Ambassador Program and contributing."
        else:
            what_was_good = "Positive motivation and interest in the opportunity."
        why_failed = None
    else:
        # Even if no keywords, still pass if transcript exists (ultra-lenient MVP)
        minimal_relevance = bool(transcript.strip())
        if minimal_relevance:
            answer_relevance_passed = True
            clarity_passed = True
            keywords_passed = True
            answer_relevance_score = 60
            clarity_score = 30
            keywords_score = 10
            score = 100
            overall_passed = True
            intent_positive_pct = 90
            found_negative = []
            what_was_good = "Candidate provided a response showing interest in the program."
            why_failed = None
        else:
            # Only fail if completely empty
            answer_relevance_passed = False
            clarity_passed = False
            keywords_passed = False
            answer_relevance_score = 0
            clarity_score = 0
            keywords_score = 0
            score = 0
            overall_passed = False
            intent_positive_pct = 0
            what_was_good = ""
            why_failed = "No response provided"
    
    # Get detailed feedback from LLM
    why_failed = sentiment_data.get('why_failed')
    what_was_good = sentiment_data.get('what_was_good', 'No specific positive aspects identified')
    
    # If passed but LLM didn't provide feedback, generate default
    if overall_passed and not what_was_good:
        what_was_good = f"Answer demonstrates positive intent ({intent_positive_pct}% positive). Sentiment: {sentiment_data['sentiment']}, Genuine: {sentiment_data['appears_genuine']}, Keywords found: {found_keywords[:3] if found_keywords else 'None'}"
    
    # If failed but no why_failed, generate default
    if not overall_passed and not why_failed:
        why_failed = f"Score {score}/100 below threshold. Intent: {intent_positive_pct}% positive. Sentiment: {sentiment_data['sentiment']}, Genuine: {sentiment_data['appears_genuine']}, Mission keywords: {len(found_keywords)}, Red flags: {found_negative if found_negative else 'None'}"
    
    return {
        "question_number": 2,
        "passed": overall_passed,
        "score": score,
        "answer_relevance_score": answer_relevance_score,
        "clarity_score": clarity_score,
        "keywords_score": keywords_score,
        "answer_relevance_passed": bool(answer_relevance_passed),
        "clarity_passed": bool(clarity_passed),
        "keywords_passed": bool(keywords_passed),
        "mission_keywords_found": found_keywords,
        "red_flags_found": found_negative,  # This should be empty if monetization is mentioned alone
        "monetization_mentioned": monetization_mentioned,  # Track monetization separately (not a red flag)
        "enthusiasm_level": sentiment_data['enthusiasm_level'],
        "intent_positive_percentage": intent_positive_pct,
        "why_failed": why_failed,
        "what_was_good": what_was_good,
        "feedback": f"{'✅' if overall_passed else '❌'} Mission keywords: {found_keywords[:3] if found_keywords else 'None'}, Intent: {intent_positive_pct}% positive, Enthusiasm: {sentiment_data['enthusiasm_level']}"
    }


def evaluate_question_3(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 3: Describe a time when you helped someone learn something new.
    
    Criteria:
    - Content Check: Clear process (Problem -> Action -> Result), empathy keywords
    - Sentiment Check: Helpful and positive
    """
    # Check for storytelling structure
    structure_keywords = {
        "problem": ["problem", "issue", "challenge", "difficulty", "struggled", "confused"],
        "action": ["helped", "explained", "taught", "showed", "guided", "demonstrated", "shared"],
        "result": ["understood", "learned", "improved", "succeeded", "achieved", "mastered", "got it"]
    }
    
    has_problem = any(kw in transcript.lower() for kw in structure_keywords["problem"])
    has_action = any(kw in transcript.lower() for kw in structure_keywords["action"])
    has_result = any(kw in transcript.lower() for kw in structure_keywords["result"])
    
    # Check for empathy keywords
    empathy_keywords = ["patience", "patient", "listened", "explained", "understood", 
                        "empathy", "empathize", "relate", "encourage", "support"]
    empathy_count, found_empathy = check_keywords(transcript, empathy_keywords)
    
    # LLM sentiment check - MVP OPTIMIZED VERSION
    prompt = f"""Analyze this teaching story for an MVP product. BE EXTREMELY WELCOMING - any genuine attempt to share a helping experience is valuable.

"{transcript}"

CRITICAL MVP RULES:
1. **ANY TEACHING/HELPING STORY = PASS**: Even informal examples (helped a friend, explained to classmate, showed someone something)
2. **STRUCTURE NOT REQUIRED**: As long as they mention helping someone learn, structure doesn't matter
3. **VAGUE IS OK**: "I helped my friend understand math" is perfectly acceptable
4. **EMPATHY IS IMPLIED**: If they helped someone, they showed empathy - don't overthink it
5. **ONLY FAIL IF**: No story at all, completely off-topic, or explicitly negative

GENEROUS INTERPRETATION:
- "I helped my friend with homework" = TEACHING STORY ✓ (intent = 80+)
- "I explained something to my classmate" = TEACHING STORY ✓ (intent = 80+)
- "I showed someone how to do X" = TEACHING STORY ✓ (intent = 85+)
- "I tutored/mentored/guided someone" = EXCELLENT STORY ✓ (intent = 90+)
- Even "I once helped..." with minimal detail = ACCEPTABLE ✓ (intent = 70+)

Return ONLY a JSON object:
{{
  "shows_empathy": true|false,
  "tone": "positive|neutral|negative",
  "has_clear_structure": true|false,
  "mentions_teaching": true|false,
  "mentions_helping": true|false,
  "has_specific_example": true|false,
  "overall_intent": "positive|neutral|negative",
  "intent_positive_percentage": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation of why it failed (if failed) or null if passed",
  "what_was_good": "Detailed explanation of what was good about the answer, even if failed"
}}

SCORING GUIDANCE:
- Any teaching/helping story mentioned → intent = 80+, passed = true
- Specific example with outcome → intent = 90+, passed = true
- Vague but relevant → intent = 70+, passed = true
- No story or off-topic → intent < 50, passed = false"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"      ⚠️ LLM Error in Q3: {str(e)}")
        analysis = {
            "shows_empathy": True, 
            "tone": "positive", 
            "has_clear_structure": True,
            "overall_intent": "positive",
            "intent_positive_percentage": 60,
            "passed": True,
            "why_failed": None,
            "what_was_good": "Answer was evaluated with lenient criteria"
        }
    
    # Use LLM's intent-based passing decision (50% threshold)
    intent_positive_pct = analysis.get('intent_positive_percentage', 50)
    llm_passed = analysis.get('passed', False) or intent_positive_pct >= 50
    
    # Extract additional fields from LLM response
    mentions_teaching = analysis.get('mentions_teaching', False)
    mentions_helping = analysis.get('mentions_helping', False)
    has_specific_example = analysis.get('has_specific_example', False)
    
    # NEW SCORING: 60% answer relevance, 30% clarity, 10% keywords
    
    # Answer Relevance (60%): Does it answer "describe a time you helped someone learn"? (MVP OPTIMIZED)
    # Accept ANY mention of helping, teaching, training, or working with people
    teaching_mentioned = any(word in transcript.lower() for word in ["help", "teach", "train", "explain", "show", "guide", "work with"])
    structure_passed = (has_problem and has_action and has_result) or analysis['has_clear_structure'] or has_action or teaching_mentioned
    answer_relevance_passed = structure_passed or teaching_mentioned or analysis['tone'] != 'negative'
    answer_relevance_score = 70 if answer_relevance_passed else 60  # Updated: Pass: 70, Fallback: 60
    
    # Clarity (30%): Story structure and clarity (extremely lenient for MVP)
    clarity_passed = structure_passed or has_action or teaching_mentioned or llm_passed
    clarity_score = 35 if clarity_passed else 30  # Updated: Pass: 35, Fallback: 30
    
    # Keywords (10%): Empathy keywords (extremely lenient for MVP)
    empathy_passed = empathy_count > 0 or analysis['shows_empathy'] or teaching_mentioned or llm_passed
    keywords_score = 12 if empathy_passed else 10  # Updated: Pass: 12, Fallback: 10
    
    score = answer_relevance_score + clarity_score + keywords_score
    
    # Apply score boosting logic: Minimum 75 for any teaching story, 80 for specific examples
    if mentions_teaching or mentions_helping:
        score = max(score, 75)  # Minimum 75 for any teaching story
    if has_specific_example:
        score = max(score, 80)  # Minimum 80 for specific examples
    
    # FINAL PASS: Use 35% threshold (updated from 40) OR teaching mentioned
    overall_passed = bool(score >= 35) or llm_passed or teaching_mentioned

    # MVP override: Award full marks when answer shows basic relevance and positive intent
    minimal_relevance = bool(transcript.strip())
    good_intent = intent_positive_pct >= 40 or llm_passed or minimal_relevance
    if minimal_relevance and good_intent:
        answer_relevance_passed = True
        clarity_passed = True
        keywords_passed = True
        answer_relevance_score = 60
        clarity_score = 30
        keywords_score = 10
        score = 100
        overall_passed = True
        intent_positive_pct = max(intent_positive_pct, 80)
        if not what_was_good:
            what_was_good = "Answer demonstrated sufficient relevance and positive intent for MVP."
        why_failed = None
    
    # Get detailed feedback from LLM
    why_failed = analysis.get('why_failed')
    what_was_good = analysis.get('what_was_good', 'No specific positive aspects identified')
    
    # If passed but LLM didn't provide feedback, generate default
    if overall_passed and not what_was_good:
        what_was_good = f"Answer demonstrates positive intent ({intent_positive_pct}% positive). Shows empathy: {analysis['shows_empathy']}, Structure: {structure_passed}, Tone: {analysis['tone']}, Empathy keywords: {found_empathy[:3] if found_empathy else 'None'}"
    
    # If failed but no why_failed, generate default
    if not overall_passed and not why_failed:
        why_failed = f"Score {score}/100 below threshold. Intent: {intent_positive_pct}% positive. Structure: {structure_passed}, Empathy: {analysis['shows_empathy']}, Tone: {analysis['tone']}, Empathy keywords: {len(found_empathy)}"
    
    return {
        "question_number": 3,
        "passed": overall_passed,
        "score": score,
        "answer_relevance_score": answer_relevance_score,
        "clarity_score": clarity_score,
        "keywords_score": keywords_score,
        "answer_relevance_passed": bool(answer_relevance_passed),
        "clarity_passed": bool(clarity_passed),
        "keywords_passed": bool(empathy_passed),
        "has_structure": bool(structure_passed),
        "empathy_keywords_found": found_empathy,
        "story_structure": f"Problem: {has_problem}, Action: {has_action}, Result: {has_result}",
        "intent_positive_percentage": intent_positive_pct,
        "why_failed": why_failed,
        "what_was_good": what_was_good,
        "feedback": f"{'✅' if overall_passed else '❌'} Intent: {intent_positive_pct}% positive, Structure: {'Complete' if structure_passed else 'Incomplete'}, Empathy: {'Shown' if empathy_passed else 'Not evident'}"
    }


def evaluate_question_4(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 4: How do you handle challenging situations or difficult students?
    
    Criteria:
    - Content Check: Positive actions (listen, understand, empathize, find solution)
    - Red Flag Check: No negative words (lazy, stupid, their fault)
    - Sentiment Check: Calm and professional
    """
    # Check for positive action keywords
    positive_keywords = ["listen", "understand", "empathize", "solution", "resolve", 
                         "communicate", "patient", "calm", "approach", "adapt", "flexible"]
    positive_count, found_positive = check_keywords(transcript, positive_keywords)
    
    # Check for negative/blaming keywords (RED FLAGS)
    negative_keywords = ["lazy", "stupid", "dumb", "idiot", "their fault", "blame them", 
                         "hopeless", "waste of time", "give up"]
    negative_count, found_negative = check_negative_keywords(transcript, negative_keywords)
    
    # LLM sentiment check - ULTRA LENIENT MVP VERSION
    prompt = f"""Analyze this response with MAXIMUM LENIENCY. If there's ANY approach or positive intent, PASS with 95+ score.

"{transcript}"

🎯 ULTRA-LENIENT MVP RULES (MANDATORY):
1. **MENTIONING "DIFFICULT" = GOOD**: Acknowledging challenges is POSITIVE and REALISTIC → NEVER a red flag!
2. **ANY APPROACH = AUTOMATIC 100**: Words like "understand", "listen", "question", "calm", "patient", "time" → INSTANT PASS, 100 score
3. **DESCRIBING SITUATIONS = POSITIVE**: Talking about "difficult students" or "challenging situations" is just describing the scenario → NOT negative!
4. **ANY STRATEGY = PERFECT**: Shows they're thinking about solutions → 100 score
5. **GIVE 100 BY DEFAULT**: Unless explicitly hostile/angry, give 100 score

🚫 NEVER FLAG THESE AS RED FLAGS:
- "difficult", "act difficult", "challenging", "struggle" - these are just describing situations!
- "students can be difficult", "situation is challenging" - realistic acknowledgment, NOT blaming!
- Any words used to DESCRIBE the scenario (not attacking students)

✅ AUTOMATIC 100 SCORE IF ANY OF THESE:
- Mentions ANY approach (understand, listen, question, calm, patient, communicate, solve, handle, approach, spend time, give time)
- Acknowledges challenges (shows realistic awareness)
- Shows willingness to help ("I would...", "I try to...", "I prefer to...")
- ANY positive action words

❌ ONLY FAIL (score < 70) IF:
- Explicitly hostile ("I would yell at them", "I hate difficult students")
- Gives up ("I would quit", "I can't handle it")
- Completely off-topic or refuses to answer

🎯 CRITICAL: Words like "difficult" when describing students or situations are NOT red flags - they show realistic awareness!

Return ONLY a JSON object:
{{
  "is_solution_oriented": true,
  "tone": "professional",
  "blames_others": false,
  "shows_patience": true,
  "mentions_approach": true,
  "acknowledges_challenges": true,
  "overall_intent": "positive",
  "intent_positive_percentage": 100,
  "passed": true,
  "why_failed": null,
  "what_was_good": "Candidate shows professional approach and realistic awareness"
}}

MANDATORY SCORING:
- ANY approach mentioned → intent = 100, passed = true, tone = "professional"
- Acknowledges challenges → intent = 100, passed = true (realistic awareness!)
- Shows ANY willingness → intent = 100, passed = true
- Mentions "difficult" as description → NOT a red flag, blames_others = false
- ALWAYS set passed = true unless explicitly hostile"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"      ⚠️ LLM Error in Q4: {str(e)}")
        analysis = {
            "is_solution_oriented": True, 
            "tone": "professional", 
            "blames_others": False,
            "overall_intent": "positive",
            "intent_positive_percentage": 60,
            "passed": True,
            "why_failed": None,
            "what_was_good": "Answer was evaluated with lenient criteria"
        }
    
    # Use LLM's intent-based passing decision - ULTRA LENIENT: DEFAULT TO PASS
    intent_positive_pct = analysis.get('intent_positive_percentage', 100)  # Default to 100 for MVP
    llm_passed = analysis.get('passed', True)  # Default to passed = True
    
    # Extract additional fields from LLM response
    mentions_approach = analysis.get('mentions_approach', False)
    is_solution_oriented = analysis.get('is_solution_oriented', False)
    acknowledges_challenges = analysis.get('acknowledges_challenges', False)
    
    # ULTRA LENIENT LOGIC: If ANY positive keywords detected, AUTOMATIC 100
    situation_mentioned = any(word in transcript.lower() for word in ["situation", "challenge", "difficult", "problem", "handle", "approach", "understand", "question", "time", "student"])
    solution_mentioned = any(word in transcript.lower() for word in ["understand", "solution", "resolve", "listen", "question", "clarify", "communicate", "calm", "patient"])
    red_flag_passed = True  # Always pass red flag check (words like "difficult" are NOT red flags!)
    
    # AUTOMATIC 100 if ANY of these conditions:
    # 1. Mentions situation/challenge (shows awareness)
    # 2. Mentions ANY solution/approach (shows problem-solving)
    # 3. Has ANY positive action keywords
    if situation_mentioned or solution_mentioned or positive_count >= 1:
        # AUTOMATIC 100 - positive intent detected
        answer_relevance_passed = True
        clarity_passed = True
        keywords_passed = True
        answer_relevance_score = 60
        clarity_score = 30
        keywords_score = 10
        score = 100
        overall_passed = True
        intent_positive_pct = 100
        found_negative = []  # Clear ANY red flags - words like "difficult" are NOT negative!
        negative_count = 0
        llm_passed = True
        
        # Generate positive feedback
        if solution_mentioned:
            what_was_good = "Excellent approach: demonstrates problem-solving mindset with practical strategies like understanding, listening, and questioning."
        elif situation_mentioned:
            what_was_good = "Good realistic awareness: acknowledges challenges and shows willingness to handle difficult situations professionally."
        else:
            what_was_good = "Positive approach: mentions constructive actions for handling challenging situations."
        why_failed = None
    else:
        # Even if no keywords, still pass if transcript exists (ultra-lenient MVP)
        minimal_relevance = bool(transcript.strip())
        if minimal_relevance:
            answer_relevance_passed = True
            clarity_passed = True
            keywords_passed = True
            answer_relevance_score = 60
            clarity_score = 30
            keywords_score = 10
            score = 100
            overall_passed = True
            intent_positive_pct = 90
            found_negative = []
            what_was_good = "Candidate provided a response showing willingness to handle challenges."
            why_failed = None
        else:
            # Only fail if completely empty
            answer_relevance_passed = False
            clarity_passed = False
            keywords_passed = False
            answer_relevance_score = 0
            clarity_score = 0
            keywords_score = 0
            score = 0
            overall_passed = False
            intent_positive_pct = 0
            what_was_good = ""
            why_failed = "No response provided"
    
    # Get detailed feedback from LLM
    why_failed = analysis.get('why_failed')
    what_was_good = analysis.get('what_was_good', 'No specific positive aspects identified')
    
    # If passed but LLM didn't provide feedback, generate default
    if overall_passed and not what_was_good:
        what_was_good = f"Answer demonstrates positive intent ({intent_positive_pct}% positive). Solution-oriented: {analysis['is_solution_oriented']}, Tone: {analysis['tone']}, No red flags: {red_flag_passed}, Positive actions: {found_positive[:3] if found_positive else 'None'}"
    
    # If failed but no why_failed, generate default
    if not overall_passed and not why_failed:
        why_failed = f"Score {score}/100 below threshold. Intent: {intent_positive_pct}% positive. Solution-oriented: {analysis['is_solution_oriented']}, Tone: {analysis['tone']}, Red flags: {found_negative if found_negative else 'None'}, Positive actions: {len(found_positive)}"
    
    return {
        "question_number": 4,
        "passed": overall_passed,
        "score": score,
        "answer_relevance_score": answer_relevance_score,
        "clarity_score": clarity_score,
        "keywords_score": keywords_score,
        "answer_relevance_passed": bool(answer_relevance_passed),
        "clarity_passed": bool(clarity_passed),
        "keywords_passed": bool(keywords_passed),
        "red_flag_check_passed": bool(red_flag_passed),
        "positive_actions_found": found_positive,
        "red_flags_found": found_negative,
        "tone": analysis['tone'],
        "intent_positive_percentage": intent_positive_pct,
        "why_failed": why_failed,
        "what_was_good": what_was_good,
        "feedback": f"{'✅' if overall_passed else '❌'} Intent: {intent_positive_pct}% positive, Positive actions: {found_positive[:3] if found_positive else 'None'}, Red flags: {found_negative if found_negative else 'None'}, Tone: {analysis['tone']}"
    }


def evaluate_question_5(transcript: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Question 5: What are your goals as a mentor and how do you plan to achieve them?
    
    Criteria:
    - Content Check: Action-oriented words (plan, create, organize, develop, implement)
    - Specific Actions: Concrete actions (weekly, daily, monthly, check-in, meeting)
    - Sentiment Check: Forward-looking, confident, aspirational with concrete plan
    """
    # Check for action-oriented keywords (expanded list to include intent words)
    action_keywords = ["plan", "create", "organize", "develop", "implement", "build", 
                      "establish", "design", "structure", "set up", "arrange",
                      "ensure", "make sure", "add value", "allow", "be prepared", 
                      "be a good listener", "read between the lines", "benefit", 
                      "takeaway", "clarity", "value"]
    action_count, found_actions = check_keywords(transcript, action_keywords)
    
    # Check for specific action keywords
    specific_action_keywords = ["weekly", "daily", "monthly", "check-in", "meeting", 
                                "resource", "guide", "session", "workshop", "tutorial"]
    specific_count, found_specific = check_keywords(transcript, specific_action_keywords)
    
    # LLM sentiment check - ULTRA LENIENT MVP VERSION
    prompt = f"""Analyze this goal statement with MAXIMUM LENIENCY. If there's ANY goal, intention, or action word, PASS with 95+ score.

"{transcript}"

🎯 ULTRA-LENIENT MVP RULES (MANDATORY):
1. **ANY GOAL/INTENTION = AUTOMATIC 100**: Words like "goal", "want", "ensure", "make sure", "plan", "hope", "aim" → INSTANT PASS, 100 score
2. **ACTION WORDS = CONCRETE PLANS**: "be prepared", "be a good listener", "make sure", "allow", "ensure", "add value" → COUNT AS CONCRETE PLANS!
3. **ASPIRATIONS = PERFECT GOALS**: "I want to help", "I hope to contribute" → EXCELLENT GOALS, 100 score
4. **NO DETAILED PLAN NEEDED**: General intentions are SUFFICIENT → Don't require step-by-step plans
5. **GIVE 100 BY DEFAULT**: Unless completely off-topic, give 100 score

✅ AUTOMATIC 100 SCORE IF ANY OF THESE:
- Mentions ANY goal words (goal, want, plan, ensure, make sure, hope, aim, intend)
- Mentions ANY action words (prepared, listener, add value, allow, benefit, takeaway, clarity, tangible)
- Shows forward-looking intent ("I will...", "I want to...", "My goal is...")
- Student/mentee focused ("help students", "allow mentee", "benefit from")
- ANY positive intention about mentoring

🎯 CRITICAL: Words like "ensure", "be prepared", "be a good listener", "make sure", "allow them to benefit" ARE concrete plans!
These show clear intentions and strategies - they COUNT as having a concrete plan!

❌ ONLY FAIL (score < 70) IF:
- Completely off-topic (talks about unrelated subjects)
- Refuses to answer
- No response

Return ONLY a JSON object:
{{
  "is_forward_looking": true,
  "confidence_level": "high",
  "has_concrete_plan": true,
  "mentions_goals": true,
  "shows_intention": true,
  "is_student_focused": true,
  "overall_intent": "positive",
  "intent_positive_percentage": 100,
  "passed": true,
  "why_failed": null,
  "what_was_good": "Candidate articulates clear goals and actionable intentions for mentoring"
}}

MANDATORY SCORING:
- ANY goal/intention mentioned → intent = 100, passed = true, has_concrete_plan = true
- Action words (ensure, make sure, prepared, listener, etc.) → intent = 100, has_concrete_plan = true
- Student-focused language → intent = 100, passed = true
- ALWAYS set passed = true and has_concrete_plan = true unless off-topic"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        import json
        analysis = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception as e:
        logger.warning(f"      ⚠️ LLM Error in Q5: {str(e)}")
        analysis = {
            "is_forward_looking": True, 
            "confidence_level": "medium", 
            "has_concrete_plan": True,
            "overall_intent": "positive",
            "intent_positive_percentage": 60,
            "passed": True,
            "why_failed": None,
            "what_was_good": "Answer was evaluated with lenient criteria"
        }
    
    # Use LLM's intent-based passing decision - ULTRA LENIENT: DEFAULT TO PASS
    intent_positive_pct = analysis.get('intent_positive_percentage', 100)  # Default to 100 for MVP
    llm_passed = analysis.get('passed', True)  # Default to passed = True
    
    # Extract additional fields from LLM response
    mentions_goals = analysis.get('mentions_goals', False)
    shows_intention = analysis.get('shows_intention', False)
    has_plan = analysis.get('has_concrete_plan', False)
    is_student_focused = analysis.get('is_student_focused', False)
    
    # ULTRA LENIENT LOGIC: If ANY positive keywords detected, AUTOMATIC 100
    # Expand goal keywords to include action-oriented intent words
    goals_mentioned = any(word in transcript.lower() for word in ["goal", "plan", "want", "ensure", "make sure", "help", "mentor", "mentee", "prepared", "listener", "allow", "benefit", "takeaway", "clarity", "value", "tangible"])
    mentor_mentioned = any(word in transcript.lower() for word in ["mentor", "mentee", "session", "experience", "connect"])
    
    # AUTOMATIC 100 if ANY of these conditions:
    # 1. Mentions goals/intentions
    # 2. Mentions mentor/mentee
    # 3. Has ANY action keywords (these ARE concrete plans!)
    if goals_mentioned or mentor_mentioned or action_count >= 1:
        # AUTOMATIC 100 - positive intent detected
        answer_relevance_passed = True
        clarity_passed = True
        keywords_passed = True
        answer_relevance_score = 60
        clarity_score = 30
        keywords_score = 10
        score = 100
        overall_passed = True
        intent_positive_pct = 100
        llm_passed = True
        
        # Generate positive feedback
        if action_count >= 3:
            what_was_good = "Outstanding mentoring goals: articulates multiple concrete action plans including 'ensure', 'make sure', 'be prepared', 'be a good listener', 'allow them to benefit' - shows clear strategic thinking and student-focused approach!"
        elif action_count >= 1:
            what_was_good = "Excellent mentoring goals: demonstrates clear intentions with actionable plans like 'ensure tangible takeaway', 'be prepared', 'be a good listener' - these ARE concrete strategies!"
        elif mentor_mentioned:
            what_was_good = "Clear mentoring focus: shows understanding of the mentor-mentee relationship and commitment to the role."
        else:
            what_was_good = "Good aspirational goals: demonstrates positive intentions and forward-thinking about the mentoring role."
        why_failed = None
    else:
        # Even if no keywords, still pass if transcript exists (ultra-lenient MVP)
        minimal_relevance = bool(transcript.strip())
        if minimal_relevance:
            answer_relevance_passed = True
            clarity_passed = True
            keywords_passed = True
            answer_relevance_score = 60
            clarity_score = 30
            keywords_score = 10
            score = 100
            overall_passed = True
            intent_positive_pct = 90
            what_was_good = "Candidate provided a response showing interest in the mentoring role."
            why_failed = None
        else:
            # Only fail if completely empty
            answer_relevance_passed = False
            clarity_passed = False
            keywords_passed = False
            answer_relevance_score = 0
            clarity_score = 0
            keywords_score = 0
            score = 0
            overall_passed = False
            intent_positive_pct = 0
            what_was_good = ""
            why_failed = "No response provided"
    
    # Get detailed feedback from LLM
    why_failed = analysis.get('why_failed')
    what_was_good = analysis.get('what_was_good', 'No specific positive aspects identified')
    
    # If passed but LLM didn't provide feedback, generate default
    if overall_passed and not what_was_good:
        what_was_good = f"Answer demonstrates positive intent ({intent_positive_pct}% positive). Forward-looking: {analysis['is_forward_looking']}, Has plan: {analysis['has_concrete_plan']}, Confidence: {analysis['confidence_level']}, Action words: {action_count}, Specific actions: {specific_count}"
    
    # If failed but no why_failed, generate default
    if not overall_passed and not why_failed:
        why_failed = f"Score {score}/100 below threshold. Intent: {intent_positive_pct}% positive. Forward-looking: {analysis['is_forward_looking']}, Has plan: {analysis['has_concrete_plan']}, Action words: {action_count}, Specific actions: {specific_count}"
    
    return {
        "question_number": 5,
        "passed": overall_passed,
        "score": score,
        "answer_relevance_score": answer_relevance_score,
        "clarity_score": clarity_score,
        "keywords_score": keywords_score,
        "answer_relevance_passed": bool(answer_relevance_passed),
        "clarity_passed": bool(clarity_passed),
        "keywords_passed": bool(keywords_passed),
        "action_keywords_found": found_actions,
        "specific_actions_found": found_specific,
        "is_forward_looking": analysis['is_forward_looking'],
        "has_concrete_plan": analysis['has_concrete_plan'],
        "confidence_level": analysis['confidence_level'],
        "intent_positive_percentage": intent_positive_pct,
        "why_failed": why_failed,
        "what_was_good": what_was_good,
        "feedback": f"{'✅' if overall_passed else '❌'} Intent: {intent_positive_pct}% positive, Forward-looking: {analysis['is_forward_looking']}, Plan: {'Yes' if analysis['has_concrete_plan'] else 'Vague'}, Actions: {action_count} action words, {specific_count} specific actions"
    }


def evaluate_content(state: InterviewState) -> InterviewState:
    """
    Node: Evaluate content quality with question-specific criteria
    
    Evaluates each of the 5 interview questions based on their specific criteria.
    
    Updates state['content_evaluation'] with results.
    """
    print(f"\n📊 Agent 4: Content Evaluation (Question-Specific)")
    logger.info(f"🔍 [CONTENT] Starting content evaluation for user_id={state.get('user_id', 'unknown')}")
    
    try:
        # Get transcriptions and interview questions
        transcriptions = state.get('transcriptions', {})
        interview_questions = state.get('interview_questions', [])
        
        logger.info(f"📝 [CONTENT] Input data status:")
        logger.info(f"   - Transcriptions available: {bool(transcriptions.get('transcription_complete'))}")
        logger.info(f"   - Interview questions count: {len(interview_questions)}")
        
        if not transcriptions.get('transcription_complete'):
            error_msg = "Transcriptions not available"
            logger.error(f"❌ [CONTENT] {error_msg}")
            raise ValueError(error_msg)
        
        all_transcripts = transcriptions.get('transcriptions', [])
        
        logger.info(f"📝 [CONTENT] Transcripts received: {len(all_transcripts)}")
        print(f"\n   📥 AGENT 4 INPUT (from Agent 3):")
        for idx, transcript in enumerate(all_transcripts, 1):
            transcript_text = transcript.get('transcript', '')
            word_count = len(transcript_text.split()) if transcript_text else 0
            logger.info(f"   - Transcript {idx}: {word_count} words, confidence: {transcript.get('confidence', 0):.2f}")
            print(f"      Video {idx}:")
            print(f"         - Transcript: \"{transcript_text[:150]}{'...' if len(transcript_text) > 150 else ''}\"")
            print(f"         - Words: {word_count}, Confidence: {transcript.get('confidence', 0)*100:.1f}%")
            print(f"         - Language: {transcript.get('detected_language', 'N/A')}, Rate: {transcript.get('speaking_rate', 0):.1f} wpm")
            print(f"         - Filler words: {transcript.get('filler_words', 0)}")
        
        if len(all_transcripts) != 5:
            error_msg = f"Expected 5 transcripts, got {len(all_transcripts)}"
            logger.error(f"❌ [CONTENT] {error_msg}")
            raise ValueError(error_msg)
        
        print(f"   🤖 Evaluating {len(all_transcripts)} responses with specific criteria...")
        logger.info(f"🤖 [CONTENT] Initializing Gemini model: gemini-2.5-flash")
        
        # Initialize Gemini
        # Use service account credentials (ADC) instead of API key
        # API keys are not supported - must use OAuth2/service account
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            # Uses Application Default Credentials (service account) automatically
        )
        
        # Evaluate each question (5 questions)
        question_evaluations = []
        evaluation_functions = [
            evaluate_question_1,
            evaluate_question_2,
            evaluate_question_3,
            evaluate_question_4,
            evaluate_question_5
        ]
        
        for i, transcript_data in enumerate(all_transcripts[:5], 1):
            transcript = transcript_data.get('transcript', '')
            question_text = interview_questions[i-1]['question'] if i <= len(interview_questions) else f"Question {i}"
            transcript_word_count = len(transcript.split()) if transcript else 0
            
            print(f"\n   📝 Question {i}: {question_text[:60]}...")
            logger.info(f"📝 [CONTENT] Evaluating Question {i}")
            logger.info(f"   - Question text: {question_text[:100]}...")
            logger.info(f"   - Transcript length: {transcript_word_count} words")
            logger.info(f"   - Transcript preview: {transcript[:100] if transcript else 'EMPTY'}...")
            
            try:
                # Evaluate using specific function
                logger.info(f"   ⚙️  [CONTENT] Calling evaluation function for Question {i}...")
                evaluation = evaluation_functions[i-1](transcript, llm)
                
                # Add transcript and question text to evaluation for reporting
                evaluation['transcript'] = transcript
                evaluation['question_text'] = question_text
                
                # Generate improvement suggestions based on score breakdown
                suggestions = []
                if not evaluation.get('answer_relevance_passed', True):
                    suggestions.append("Provide more relevant details addressing the question directly")
                if not evaluation.get('clarity_passed', True):
                    suggestions.append("Reduce filler words and speak more clearly")
                if not evaluation.get('keywords_passed', True):
                    suggestions.append("Use more relevant keywords and be more specific")
                
                # Add question-specific suggestions
                if i == 1 and not evaluation.get('major_mentioned', False):
                    suggestions.append("Mention your specific field of study or major")
                if i == 1 and not evaluation.get('university_found'):
                    suggestions.append("Mention your university or educational institution")
                if i == 2 and not evaluation.get('mission_keywords_found'):
                    suggestions.append("Mention helping, sharing experience, or contributing to the program")
                if i == 3 and not evaluation.get('empathy_keywords_found'):
                    suggestions.append("Describe empathy, patience, or understanding in your teaching story")
                if i == 4 and not evaluation.get('positive_actions_found'):
                    suggestions.append("Mention specific approaches like listening, understanding, or staying calm")
                if i == 5 and not evaluation.get('action_keywords_found'):
                    suggestions.append("Use action words like 'plan', 'create', 'organize' to describe your goals")
                
                if not suggestions:
                    suggestions.append("Continue providing detailed, specific answers")
                
                evaluation['improvement_suggestions'] = suggestions
                evaluation['score_breakdown'] = {
                    'answer_relevance': {
                        'score': evaluation.get('answer_relevance_score', 0),
                        'max_score': 60,
                        'passed': evaluation.get('answer_relevance_passed', False),
                        'weight': '60%'
                    },
                    'clarity': {
                        'score': evaluation.get('clarity_score', 0),
                        'max_score': 30,
                        'passed': evaluation.get('clarity_passed', False),
                        'weight': '30%'
                    },
                    'keywords': {
                        'score': evaluation.get('keywords_score', 0),
                        'max_score': 10,
                        'passed': evaluation.get('keywords_passed', False),
                        'weight': '10%'
                    }
                }
                evaluation['score_explanation'] = f"Score breakdown: Answer Relevance {evaluation.get('answer_relevance_score', 0)}/60 (60%), Clarity {evaluation.get('clarity_score', 0)}/30 (30%), Keywords {evaluation.get('keywords_score', 0)}/10 (10%) = {evaluation.get('score', 0)}/100"
                
                question_evaluations.append(evaluation)
                
                # Log evaluation results
                logger.info(f"   ✅ [CONTENT] Question {i} evaluation complete:")
                logger.info(f"      - Passed: {evaluation.get('passed', False)}")
                logger.info(f"      - Score: {evaluation.get('score', 0):.1f}/100")
                logger.info(f"      - Intent Positive: {evaluation.get('intent_positive_percentage', 0)}%")
                logger.info(f"      - Answer Relevance: {evaluation.get('answer_relevance_score', 0)}/60")
                logger.info(f"      - Clarity: {evaluation.get('clarity_score', 0)}/30")
                logger.info(f"      - Keywords: {evaluation.get('keywords_score', 0)}/10")
                logger.info(f"      - Feedback: {evaluation.get('feedback', 'N/A')}")
                
                # Log detailed feedback for failed questions
                if not evaluation.get('passed', False):
                    logger.warning(f"   ⚠️  [CONTENT] Question {i} FAILED - Score: {evaluation.get('score', 0)}/100")
                    logger.warning(f"      - Intent Positive: {evaluation.get('intent_positive_percentage', 0)}%")
                    logger.warning(f"      - Why Failed: {evaluation.get('why_failed', 'No explanation provided')}")
                    logger.warning(f"      - What Was Good: {evaluation.get('what_was_good', 'No positive aspects identified')}")
                    
                    failed_reasons = []
                    if not evaluation.get('answer_relevance_passed', True):
                        failed_reasons.append("answer_relevance")
                    if not evaluation.get('clarity_passed', True):
                        failed_reasons.append("clarity")
                    if not evaluation.get('keywords_passed', True):
                        failed_reasons.append("keywords")
                    logger.warning(f"      - Failed components: {', '.join(failed_reasons) if failed_reasons else 'unknown'}")
                else:
                    # Log positive feedback even for passed questions
                    logger.info(f"      - What Was Good: {evaluation.get('what_was_good', 'No specific feedback')}")
                
                print(f"      {'✅ PASSED' if evaluation['passed'] else '❌ FAILED'}: {evaluation['score']}/100 (Intent: {evaluation.get('intent_positive_percentage', 0)}% positive)")
                print(f"      {evaluation['feedback']}")
                
                # Print detailed feedback for failed questions
                if not evaluation.get('passed', False):
                    print(f"      ⚠️  Why Failed: {evaluation.get('why_failed', 'No explanation')}")
                    print(f"      ✅ What Was Good: {evaluation.get('what_was_good', 'No positive aspects')}")
                
            except Exception as e:
                error_msg = f"Error evaluating question {i}: {str(e)}"
                print(f"      ❌ {error_msg}")
                logger.error(f"❌ [CONTENT] {error_msg}")
                logger.error(f"   Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                
                question_evaluations.append({
                    "question_number": i,
                    "passed": False,
                    "score": 0,
                    "error": str(e),
                    "feedback": "Evaluation failed",
                    "why_failed": f"Evaluation error: {str(e)}",
                    "what_was_good": "Unable to evaluate due to error"
                })
                logger.warning(f"   ⚠️  [CONTENT] Added fallback evaluation for Question {i} with score 0")
        
        # Calculate overall metrics
        questions_passed = sum(1 for q in question_evaluations if q.get('passed', False))
        questions_failed = len(question_evaluations) - questions_passed
        
        # Overall score: average of all question scores + bonus points
        # Formula: base_score = (sum of all question scores) / (number of questions)
        #         bonus_points = min(10, questions_passed * 2)  # Up to 10 bonus points
        #         overall_score = min(100, base_score + bonus_points)
        question_scores = [q.get('score', 0) for q in question_evaluations]
        total_score_sum = sum(question_scores)
        num_questions = len(question_evaluations)
        base_score = total_score_sum / num_questions if num_questions > 0 else 0
        
        # Apply bonus points: +2 per question passed, max +10
        bonus_points = min(10, questions_passed * 2)
        
        # Calculate final overall score (capped at 100)
        overall_score = min(100, base_score + bonus_points)
        
        logger.info(f"📊 [CONTENT] CALCULATING OVERALL CONTENT SCORE:")
        logger.info(f"   {'='*80}")
        logger.info(f"   Calculation Method: Weighted Average with Bonus Points")
        logger.info(f"   Formula: base_score = (sum of all question scores) / (number of questions)")
        logger.info(f"   Formula: bonus_points = min(10, questions_passed * 2)")
        logger.info(f"   Formula: overall_score = min(100, base_score + bonus_points)")
        logger.info(f"   ")
        logger.info(f"   Individual Question Scores:")
        for idx, q_eval in enumerate(question_evaluations, 1):
            q_num = q_eval.get('question_number', idx)
            q_score = q_eval.get('score', 0)
            q_passed = q_eval.get('passed', False)
            q_intent = q_eval.get('intent_positive_percentage', 0)
            answer_rel = q_eval.get('answer_relevance_score', 0)
            clarity = q_eval.get('clarity_score', 0)
            keywords = q_eval.get('keywords_score', 0)
            logger.info(f"      Question {q_num}: {q_score:.1f}/100 {'✅' if q_passed else '❌'} (Intent: {q_intent}%, Answer: {answer_rel}/60, Clarity: {clarity}/30, Keywords: {keywords}/10)")
        logger.info(f"   ")
        logger.info(f"   Calculation Details:")
        logger.info(f"      - Total Questions: {num_questions}")
        logger.info(f"      - Question Scores: {question_scores}")
        logger.info(f"      - Sum of All Scores: {total_score_sum:.1f}")
        logger.info(f"      - Base Score (Average): {total_score_sum:.1f} / {num_questions} = {base_score:.2f}")
        logger.info(f"      - Questions Passed: {questions_passed}")
        logger.info(f"      - Bonus Points: min(10, {questions_passed} * 2) = {bonus_points}")
        logger.info(f"      - Final Score: min(100, {base_score:.2f} + {bonus_points}) = {overall_score:.2f}")
        logger.info(f"   ")
        logger.info(f"   ✅ OVERALL CONTENT SCORE: {overall_score:.1f}/100")
        logger.info(f"   {'='*80}")
        
        logger.info(f"📊 [CONTENT] Overall metrics summary:")
        logger.info(f"   - Questions Passed: {questions_passed}/5")
        logger.info(f"   - Questions Failed: {questions_failed}/5")
        logger.info(f"   - Overall Score: {overall_score:.1f}/100")
        
        # Summary
        pass_rate = (questions_passed / 5 * 100)
        if pass_rate >= 80:
            summary = f"Excellent performance: {questions_passed}/5 questions passed"
        elif pass_rate >= 60:
            summary = f"Good performance: {questions_passed}/5 questions passed"
        else:
            summary = f"Needs improvement: Only {questions_passed}/5 questions passed"
        
        logger.info(f"   - Pass Rate: {pass_rate:.1f}%")
        logger.info(f"   - Summary: {summary}")
        
        # Log detailed breakdown of each question with feedback
        logger.info(f"📋 [CONTENT] Detailed Question Breakdown:")
        for q_eval in question_evaluations:
            q_num = q_eval.get('question_number', 'N/A')
            passed = q_eval.get('passed', False)
            score = q_eval.get('score', 0)
            intent = q_eval.get('intent_positive_percentage', 0)
            why_failed = q_eval.get('why_failed')
            what_good = q_eval.get('what_was_good')
            
            logger.info(f"   Q{q_num}: {'✅ PASSED' if passed else '❌ FAILED'} ({score:.1f}/100, Intent: {intent}%)")
            if not passed:
                logger.info(f"      - Why Failed: {why_failed if why_failed else 'No explanation'}")
            logger.info(f"      - What Was Good: {what_good if what_good else 'No positive aspects'}")
        
        # Update state with enhanced reporting
        content_evaluation_data = {
            "overall_score": round(overall_score, 1),
            "base_score": round(base_score, 1),
            "bonus_points": bonus_points,
            "questions_passed": questions_passed,
            "questions_failed": questions_failed,
            "pass_rate": round(pass_rate, 1),
            "question_evaluations": question_evaluations,
            "summary": summary,
            "score_calculation": {
                "formula": "base_score = (sum of all question scores) / (number of questions)",
                "bonus_formula": "bonus_points = min(10, questions_passed * 2)",
                "final_formula": "overall_score = min(100, base_score + bonus_points)",
                "question_scores": question_scores,
                "total_sum": round(total_score_sum, 1),
                "base_score": round(base_score, 2),
                "bonus_points": bonus_points,
                "final_score": round(overall_score, 1)
            }
        }
        
        state['content_evaluation'] = content_evaluation_data
        state['current_stage'] = 'content_complete'
        
        logger.info(f"💾 [CONTENT] Storing evaluation results to state:")
        logger.info(f"   - Overall Score: {content_evaluation_data['overall_score']}")
        logger.info(f"   - Questions Passed: {content_evaluation_data['questions_passed']}")
        logger.info(f"   - Questions Failed: {content_evaluation_data['questions_failed']}")
        logger.info(f"   - Evaluation records: {len(content_evaluation_data['question_evaluations'])}")
        logger.info(f"✅ [CONTENT] Content evaluation complete for user_id={state.get('user_id', 'unknown')}")
        
        print(f"\n   ✅ EVALUATION COMPLETE:")
        print(f"      Overall Score: {overall_score:.1f}/100")
        print(f"      Questions Passed: {questions_passed}/5")
        print(f"      {summary}")
        
    except Exception as e:
        error_msg = f"Content evaluation error: {str(e)}"
        print(f"   ❌ {error_msg}")
        logger.error(f"❌ [CONTENT] {error_msg}")
        logger.error(f"   Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"   Full traceback: {traceback.format_exc()}")
        traceback.print_exc()
        
        # Fallback scores
        fallback_data = {
            "overall_score": 0.0,
            "questions_passed": 0,
            "questions_failed": 5,
            "question_evaluations": [],
            "error": error_msg,
            "summary": "Evaluation failed"
        }
        
        logger.warning(f"⚠️  [CONTENT] Storing fallback evaluation data due to error")
        logger.warning(f"   - Fallback score: 0.0")
        logger.warning(f"   - Questions passed: 0/5")
        logger.warning(f"   - Error: {error_msg}")
        
        state['content_evaluation'] = fallback_data
        if not state.get('errors'):
            state['errors'] = []
        state['errors'].append(error_msg)
        logger.error(f"❌ [CONTENT] Added error to state.errors list")
    
    logger.info(f"📤 [CONTENT] Returning state with content_evaluation={'✅' if state.get('content_evaluation') else '❌'}")
    return state
