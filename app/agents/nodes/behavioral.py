"""
Behavioral Analysis Node
Analyzes non-verbal cues and behavioral patterns using LLM
"""
import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import InterviewState


def analyze_behavior(state: InterviewState) -> InterviewState:
    """
    Node: Analyze behavioral patterns
    
    Uses Gemini to analyze:
    - Emotional consistency
    - Confidence indicators
    - Stress/nervousness levels
    - Engagement level
    - Authenticity signals
    
    Updates state['behavioral_analysis'] with results.
    """
    print(f"\n🎭 Agent 5: Behavioral Analysis")
    
    try:
        # Get previous results
        identity_data = state.get('identity_verification', {})
        transcriptions = state.get('transcriptions', {})
        
        # Prepare context for LLM (now includes transcription quality factors)
        all_transcripts = transcriptions.get('transcriptions', [])
        
        # Calculate transcription quality metrics
        avg_confidence = transcriptions.get('avg_confidence', 0) * 100  # Convert to 0-100
        total_filler_words = sum(t.get('filler_words', 0) for t in all_transcripts)
        avg_speaking_rate = sum(
            t.get('speaking_rate', 0) for t in all_transcripts
        ) / len(all_transcripts) if all_transcripts else 0
        
        context = {
            "identity_confidence": identity_data.get('confidence', 0),
            "transcripts": [t.get('transcript', '') for t in all_transcripts],
            "transcription_quality": {
                "avg_confidence": avg_confidence,
                "total_filler_words": total_filler_words,
                "avg_speaking_rate": avg_speaking_rate,
                "audio_quality_note": "High confidence indicates clear audio and speaking"
            },
            "speaking_metrics": {
                "avg_speaking_rate": avg_speaking_rate,
                "filler_words": total_filler_words
            }
        }
        
        # Log what Agent 5 receives from Agent 3
        print(f"\n   📥 AGENT 5 INPUT (from Agent 3):")
        print(f"      Transcription Quality Metrics:")
        print(f"         - Avg Confidence: {avg_confidence:.1f}%")
        print(f"         - Total Filler Words: {total_filler_words}")
        print(f"         - Avg Speaking Rate: {avg_speaking_rate:.1f} words/min")
        print(f"      Transcripts:")
        for idx, transcript_data in enumerate(all_transcripts, 1):
            transcript_text = transcript_data.get('transcript', '')
            print(f"         Video {idx}: \"{transcript_text[:100]}{'...' if len(transcript_text) > 100 else ''}\"")
            print(f"            - Confidence: {transcript_data.get('confidence', 0)*100:.1f}%, Rate: {transcript_data.get('speaking_rate', 0):.1f} wpm")
        
        print(f"   🤖 Analyzing behavioral patterns with Gemini...")
        
        # Initialize Gemini
        # Use service account credentials (ADC) instead of API key
        # API keys are not supported - must use OAuth2/service account
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            # Uses Application Default Credentials (service account) automatically
        )
        
        # Analysis prompt - MVP OPTIMIZED VERSION
        system_prompt = """You are an expert behavioral psychologist analyzing interview behavior for an MVP product. BE VERY GENEROUS AND ENCOURAGING in your assessment - we're building a welcoming community.

CRITICAL: This is an MVP - we want to attract good candidates. Default to HIGH scores unless there are serious concerns.

Based on the transcripts, speaking metrics, and transcription quality, analyze the candidate's behavioral patterns.

MVP GUIDELINES:
- Normal career motivations (money, growth, opportunities) are NOT red flags - they're HEALTHY and NORMAL
- Slight nervousness is expected in interviews - DO NOT penalize (it shows they care!)
- Any sign of helpfulness, experience, or positive intent should be HEAVILY REWARDED
- Focus on POTENTIAL and POSITIVE aspects, not perfection
- Give benefit of doubt - assume positive intent always

SCORING GUIDELINES FOR MVP (CRITICAL):
- **Base score: 80/100** (high baseline - candidates earned the interview)
- **Default to 85** for anyone who seems engaged and answers questions
- **90+ for anyone who shows enthusiasm or relevant experience**
- Only reduce below 80 for serious red flags (anger, inappropriate behavior, refusing to answer)
- Nervousness should ADD to score (shows they care) not reduce it
- Normal human speech patterns (filler words, pauses) are NOT negatives

SPECIFIC SCORING RULES:
- If they answer all questions and seem engaged → 85 minimum
- If they show any enthusiasm or positive traits → 90 minimum
- If they mention helping/teaching/relevant experience → 92 minimum
- Only go below 80 for: anger, rudeness, refusing to participate, inappropriate content
- Slight nervousness → 88-92 range (shows they care about the opportunity)

Return ONLY a JSON object:
{
  "behavioral_score": 85,
  "confidence_level": "High|Medium|Low",
  "emotional_consistency": 88,
  "stress_level": 15,
  "engagement": 90,
  "speaking_clarity": 88,
  "transcription_quality_impact": 5,
  "traits": ["engaged", "enthusiastic", "helpful"],
  "concerns": [],
  "summary": "Brief positive summary highlighting strengths and potential",
  "red_flags": []
}

MANDATORY: 
- behavioral_score must be 85+ for normal engaged candidates
- Only reduce below 80 for serious issues
- Focus summary on positives and potential
- Keep concerns list SHORT or empty for normal candidates
- red_flags should be EMPTY unless truly serious issues"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Candidate Data:\n\n{context}")
        ]
        
        response = llm.invoke(messages)
        
        # Parse JSON
        import json
        import re
        
        response_text = response.content
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            raise ValueError("Could not parse LLM response")
        
        # Ensure required fields - MVP-optimized defaults (higher scores)
        analysis.setdefault('behavioral_score', 88)  # Updated: Increased from 85
        analysis.setdefault('confidence_level', 'Medium')
        analysis.setdefault('emotional_consistency', 88)  # Updated: Increased from 85
        analysis.setdefault('stress_level', 15)  # Updated: Decreased from 20 (less stress assumed)
        analysis.setdefault('engagement', 90)  # Updated: Increased from 85
        analysis.setdefault('speaking_clarity', 88)  # Updated: Increased from 85
        analysis.setdefault('transcription_quality_impact', 0)
        analysis.setdefault('traits', ['engaged', 'responsive', 'motivated'])  # More positive default traits
        analysis.setdefault('concerns', [])
        analysis.setdefault('red_flags', [])
        analysis.setdefault('summary', 'Behavioral analysis complete - positive assessment')
        
        # Apply minimum score guarantees based on context
        # Check if candidate shows engagement (answered all questions)
        all_transcripts_text = ' '.join([t.get('transcript', '') for t in all_transcripts])
        has_transcripts = len(all_transcripts) > 0 and any(len(t.get('transcript', '')) > 10 for t in all_transcripts)
        mentions_helping = any(word in all_transcripts_text.lower() for word in ["help", "teach", "mentor", "guide", "assist", "support"])
        mentions_teaching = any(word in all_transcripts_text.lower() for word in ["teaching", "tutoring", "explaining", "showing"])
        
        # Apply minimum score guarantees
        if mentions_helping or mentions_teaching:
            analysis['behavioral_score'] = max(analysis['behavioral_score'], 92)  # Minimum 92 for helping/teaching
        elif has_transcripts and analysis['engagement'] >= 80:
            # Check if they show enthusiasm (positive words, engagement)
            analysis['behavioral_score'] = max(analysis['behavioral_score'], 90)  # Minimum 90 for enthusiastic
        elif has_transcripts:
            analysis['behavioral_score'] = max(analysis['behavioral_score'], 85)  # Minimum 85 for engaged
        
        # Ensure score doesn't go below base unless serious issues
        if not analysis.get('red_flags') or len(analysis['red_flags']) == 0:
            analysis['behavioral_score'] = max(analysis['behavioral_score'], 80)  # Base score: 80
        
        # MVP: Remove monetization-related red flags - it's normal!
        red_flags = analysis.get('red_flags', [])
        monetization_keywords = ['monetization', 'monetized', 'money', 'salary', 'financial', 'paid', 'earn']
        analysis['red_flags'] = [
            flag for flag in red_flags 
            if not any(keyword.lower() in str(flag).lower() for keyword in monetization_keywords)
        ]
        
        # Also filter concerns about monetization
        concerns = analysis.get('concerns', [])
        analysis['concerns'] = [
            concern for concern in concerns 
            if not any(keyword.lower() in str(concern).lower() for keyword in monetization_keywords)
        ]
        
        # Add detailed behavioral breakdown for reporting
        analysis['detailed_breakdown'] = {
            'behavioral_score': {
                'value': analysis['behavioral_score'],
                'max_value': 100,
                'explanation': 'Overall behavioral assessment based on communication, engagement, and authenticity'
            },
            'emotional_consistency': {
                'value': analysis['emotional_consistency'],
                'max_value': 100,
                'explanation': 'Consistency of emotional state across all responses'
            },
            'engagement': {
                'value': analysis['engagement'],
                'max_value': 100,
                'explanation': 'Level of engagement and participation in the interview'
            },
            'speaking_clarity': {
                'value': analysis['speaking_clarity'],
                'max_value': 100,
                'explanation': 'Clarity and quality of speech based on transcription confidence'
            },
            'stress_level': {
                'value': analysis['stress_level'],
                'max_value': 100,
                'explanation': 'Indicators of nervousness or stress (lower is better)'
            }
        }
        
        # Generate improvement suggestions
        behavioral_suggestions = []
        if analysis['behavioral_score'] < 90:
            behavioral_suggestions.append("Show more enthusiasm and engagement in responses")
        if analysis['engagement'] < 85:
            behavioral_suggestions.append("Participate more actively and provide detailed answers")
        if analysis['speaking_clarity'] < 85:
            behavioral_suggestions.append("Speak more clearly and reduce background noise")
        if analysis['stress_level'] > 25:
            behavioral_suggestions.append("Try to relax and speak more naturally")
        if analysis['emotional_consistency'] < 85:
            behavioral_suggestions.append("Maintain consistent tone and energy throughout responses")
        
        if not behavioral_suggestions:
            behavioral_suggestions.append("Continue demonstrating strong communication and engagement")
        
        analysis['improvement_suggestions'] = behavioral_suggestions
        analysis['score_explanation'] = f"Behavioral score: {analysis['behavioral_score']}/100 based on engagement ({analysis['engagement']}), emotional consistency ({analysis['emotional_consistency']}), speaking clarity ({analysis['speaking_clarity']}), and stress indicators ({analysis['stress_level']})"
        
        # Add transcription quality metrics
        analysis['transcription_metrics'] = {
            "avg_confidence": avg_confidence,
            "filler_words": total_filler_words,
            "speaking_rate": avg_speaking_rate
        }
        
        # Update state
        state['behavioral_analysis'] = analysis
        state['current_stage'] = 'behavioral_complete'
        
        print(f"   ✅ Behavioral Score: {analysis['behavioral_score']}/100 (includes transcription quality)")
        print(f"      Confidence: {analysis['confidence_level']}")
        print(f"      Speaking Clarity: {analysis.get('speaking_clarity', 'N/A')}/100")
        print(f"      Transcription Confidence: {avg_confidence:.1f}%")
        print(f"      Traits: {', '.join(analysis['traits'][:3])}")
        
    except Exception as e:
        error_msg = f"Behavioral analysis error: {str(e)}"
        print(f"   ❌ {error_msg}")
        
        # Fallback - MVP-optimized (higher scores)
        state['behavioral_analysis'] = {
            "behavioral_score": 88,  # Updated: Increased from 80
            "confidence_level": "Medium",
            "emotional_consistency": 88,  # Updated: Increased from 80
            "engagement": 90,  # Updated: Increased from 80
            "speaking_clarity": 88,  # Updated: Increased from 80
            "traits": ['engaged', 'communicative'],
            "concerns": [],
            "red_flags": [],
            "summary": "Behavioral analysis completed with fallback assessment - positive",
            "error": error_msg
        }
        state['errors'].append(error_msg)
    
    return state

