"""
Decision Aggregation Node
Makes final hiring/loan decision based on all agent results
"""
import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import InterviewState


def calculate_weighted_score(state: InterviewState) -> float:
    """
    Calculate weighted final score
    
    NEW Weights (as per CTO requirements):
    - Content: 70% (Answer relevance, clarity, keywords)
    - Behavioral: 30% (Confidence, sentiment, transcription quality)
    
    Note: Identity and Quality are now gatekeepers only (0% weight)
    """
    content = state.get('content_evaluation') or {}
    behavioral = state.get('behavioral_analysis') or {}
    
    # Get scores
    content_score = content.get('overall_score', 0)
    behavioral_score = behavioral.get('behavioral_score', 0)
    
    # Calculate weighted average: 70% content + 30% behavioral
    final_score = (
        content_score * 0.70 +
        behavioral_score * 0.30
    )
    
    return final_score


def aggregate_decision(state: InterviewState) -> InterviewState:
    """
    Node: Make final decision
    
    Aggregates all previous agent results to make final decision (MVP-FRIENDLY THRESHOLDS):
    - PASS: Score ≥ 60 + Identity verified (lowered from 70 for MVP)
    - REVIEW: Score 50-59 OR borderline cases (lowered from 60-69 for MVP)
    - FAIL: Score < 50 OR Identity failed (lowered from 60 for MVP)
    
    Updates state['final_decision'] with decision and reasoning.
    """
    print(f"\n🎯 Agent 6: Decision Aggregator")
    
    try:
        # Get component scores with fallbacks for None values
        identity = state.get('identity_verification') or {}
        quality = state.get('video_quality') or {}
        content = state.get('content_evaluation') or {}
        behavioral = state.get('behavioral_analysis') or {}
        transcriptions = state.get('transcriptions') or {}
        
        # Calculate weighted score (70% content + 30% behavioral)
        final_score = calculate_weighted_score(state)
        
        # Keep all 5 component scores for admin panel (even though only 2 are weighted)
        component_scores = {
            "identity": identity.get('confidence', 0),
            "quality": quality.get('overall_score', 0),
            "content": content.get('overall_score', 0),
            "behavioral": behavioral.get('behavioral_score', 0),
            "transcription": transcriptions.get('avg_confidence', 0) * 100
        }
        
        # Determine decision (MVP-OPTIMIZED THRESHOLDS)
        identity_verified = identity.get('verified', False)
        
        # MVP-OPTIMIZED THRESHOLDS: Updated for welcoming assessment
        if final_score >= 65:  # Updated: Increased from 60
            decision = "PASS"
            recommendation = "PROCEED TO NEXT ROUND - Shows potential and positive intent"
        elif final_score >= 55:  # Updated: Changed from 50-59 to 55-64
            decision = "REVIEW"
            recommendation = "MANUAL REVIEW REQUIRED - Borderline but salvageable"
        else:  # Less than 55 (updated from 50)
            decision = "FAIL"
            recommendation = "REJECT - Significant concerns or poor performance"
        
        # OVERRIDE: If identity verification failed, adjust decision
        if not identity_verified:
            if decision == "PASS":
                # Force passing scores to REVIEW when identity fails
                decision = "REVIEW"
                recommendation = "MANUAL REVIEW REQUIRED - Identity verification failed, requires human review"
                print(f"   ⚠️  Identity verification failed: Overriding PASS → REVIEW")
            elif decision == "REVIEW":
                # Keep as REVIEW (already going to manual review)
                recommendation = "MANUAL REVIEW REQUIRED - Identity verification failed, requires human review"
                print(f"   ⚠️  Identity verification failed: Already in REVIEW")
            # If decision is "FAIL", keep it as FAIL (they failed both identity and score)
            else:
                print(f"   ⚠️  Identity verification failed: Already FAILED (low score + identity failure)")
        
        print(f"   📊 Final Score: {final_score:.1f}/100")
        print(f"   🎯 Decision: {decision}")
        
        # Get LLM reasoning
        try:
            print(f"   🤖 Generating detailed reasoning...")
            
            # Use service account credentials (ADC) instead of API key
            # API keys are not supported - must use OAuth2/service account
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.3,
                # Uses Application Default Credentials (service account) automatically
            )
            
            system_prompt = """You are a hiring decision expert for an MVP product. BE WELCOMING, POSITIVE, AND ENCOURAGING in your assessment.

Based on the assessment data, provide:
1. **Clear reasoning** - Focus on what the candidate did WELL
2. **Key strengths** - Highlight EVERY positive aspect you can find
3. **Areas for growth** - Frame concerns as "opportunities for growth" not criticism
4. **Final recommendation** - Be encouraging and focus on potential

IMPORTANT MVP MINDSET:
- This is an MVP - we're building a community and need engaged people
- Focus on POTENTIAL, not perfection
- Normal career motivations (earning, growth) are HEALTHY and POSITIVE
- Slight nervousness shows they care about the opportunity
- If they answered questions and showed ANY positive intent → They should likely PASS
- Only strong negatives (anger, rudeness, completely off-topic) should result in FAIL

TONE GUIDELINES:
- For PASS: Enthusiastic and welcoming ("Great responses", "Shows strong potential")
- For REVIEW: Encouraging but neutral ("Shows promise", "With some development")
- For FAIL: Professional and constructive ("Not the right fit at this time")

Keep it professional, positive, and concise (3-5 sentences)."""
            
            assessment_data = {
                "decision": decision,
                "final_score": final_score,
                "component_scores": component_scores,
                "identity_verified": identity_verified,
                "content_summary": content.get('summary', ''),
                "behavioral_summary": behavioral.get('summary', '')
            }
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Assessment Data:\n\n{assessment_data}")
            ]
            
            response = llm.invoke(messages)
            reasoning = response.content.strip()
            
        except Exception as e:
            print(f"      ⚠️  Could not generate LLM reasoning: {e}")
            reasoning = f"Decision based on NEW weighted scoring (Content: 70%, Behavioral: 30%). Final score: {final_score:.1f}/100. Identity and Quality serve as gatekeepers only."
        
        # Collect strengths, concerns, and red flags
        strengths = []
        concerns = []
        red_flags = []
        
        # Identity checks (face verification only, no name matching)
        identity_data_detailed = state.get('identity_verification', {})
        face_verified = identity_data_detailed.get('face_verified', False)
        
        if not identity_verified:
            red_flags.append("IDENTITY_VERIFICATION_FAILED")
            if not face_verified:
                concerns.append("Face verification failed across video samples")
                red_flags.append("FACE_VERIFICATION_FAILED")
        elif component_scores['identity'] >= 80:
            if face_verified:
                strengths.append(f"Strong identity verification: Face verified across videos ({component_scores['identity']:.1f}% confidence)")
            else:
                strengths.append(f"Identity verification passed ({component_scores['identity']:.1f}% confidence)")
        elif component_scores['identity'] < 60:
            concerns.append("Low identity confidence")
            red_flags.append("LOW_SIMILARITY_SCORE")
        
        # Quality checks
        if component_scores['quality'] < 50:
            concerns.append("Poor video quality detected")
            red_flags.append("POOR_VIDEO_QUALITY")
        
        # Content checks (question-specific evaluation) - MVP-OPTIMIZED
        content_data_detailed = state.get('content_evaluation', {})
        questions_passed = content_data_detailed.get('questions_passed', 0)
        questions_failed = content_data_detailed.get('questions_failed', 5)
        
        if component_scores['content'] >= 80:
            strengths.append("Excellent responses showing strong understanding and relevant experience")
        elif component_scores['content'] >= 70:
            strengths.append("Good responses demonstrating motivation and relevant background")
        elif component_scores['content'] >= 65:
            strengths.append("Solid responses showing genuine interest and basic qualifications")
        elif component_scores['content'] >= 55:
            strengths.append("Shows potential with room for growth")
        elif component_scores['content'] < 50:
            concerns.append("Responses could be more detailed and focused")
        if component_scores['content'] < 40 and questions_passed <= 1:
            red_flags.append("INSUFFICIENT_RELEVANT_RESPONSES")
        
        # Behavioral checks - MVP-OPTIMIZED
        if component_scores['behavioral'] >= 90:
            strengths.append("Excellent communication skills and high engagement")
        elif component_scores['behavioral'] >= 85:
            strengths.append("Strong communication and professional demeanor")
        elif component_scores['behavioral'] >= 80:
            strengths.append("Good engagement and willingness to participate")
        elif component_scores['behavioral'] >= 75:
            strengths.append("Shows adequate communication and participation")
        elif component_scores['behavioral'] < 70:
            concerns.append("Communication could be clearer, but shows effort")
        if component_scores['behavioral'] < 50:
            red_flags.append("SIGNIFICANT_COMMUNICATION_CONCERNS")
        
        # Overall assessment logic - More forgiving combined assessment
        if component_scores['content'] >= 65 and component_scores['behavioral'] >= 80:
            strengths.append("Strong overall candidate - demonstrates both competence and engagement")
        elif component_scores['content'] >= 55 and component_scores['behavioral'] >= 75:
            strengths.append("Solid candidate with good potential for the ambassador role")
        elif component_scores['content'] >= 50 or component_scores['behavioral'] >= 70:
            strengths.append("Shows promise and willingness to contribute")
        
        # Transcription checks
        if component_scores['transcription'] >= 90:
            strengths.append(f"High-quality audio leading to accurate transcription ({component_scores['transcription']:.0f}% confidence)")
        elif component_scores['transcription'] < 70:
            concerns.append("Poor audio quality impacting transcription accuracy")
        
        # Quality-specific red flags
        quality_issues = quality.get('video_analyses', [])
        face_visibility_low = False
        for video_analysis in quality_issues:
            if video_analysis.get('face_visibility', 100) < 50:
                face_visibility_low = True
        
        if face_visibility_low:
            red_flags.append("POOR_FACE_VISIBILITY")
            concerns.append("Face was not clearly visible in the videos, which contributed to the identity verification failure.")
        
        if not concerns:
            concerns.append("No major concerns identified")
        
        # Calculate weighted breakdown (NEW: 70% content + 30% behavioral)
        content_score = component_scores['content']
        behavioral_score = component_scores['behavioral']
        content_weighted = round(content_score * 0.70, 1)
        behavioral_weighted = round(behavioral_score * 0.30, 1)
        
        weighted_breakdown = {
            "identity_weighted": 0.0,  # Gatekeeper only, no weight
            "quality_weighted": 0.0,   # Gatekeeper only, no weight
            "content_weighted": content_weighted,
            "behavioral_weighted": behavioral_weighted,
            "transcription_weighted": 0.0  # Now part of behavioral analysis
        }
        
        # Prepare comprehensive report with detailed breakdowns
        detailed_report = {
            "content_evaluation": {
                "overall_score": content_score,
                "weight": "70%",
                "weighted_score": content_weighted,
                "base_score": content_data_detailed.get('base_score', content_score),
                "bonus_points": content_data_detailed.get('bonus_points', 0),
                "calculation": content_data_detailed.get('score_calculation', {}),
                "questions_passed": questions_passed,
                "questions_failed": questions_failed,
                "question_details": []
            },
            "behavioral_evaluation": {
                "overall_score": behavioral_score,
                "weight": "30%",
                "weighted_score": behavioral_weighted,
                "detailed_breakdown": behavioral.get('detailed_breakdown', {}),
                "improvement_suggestions": behavioral.get('improvement_suggestions', []),
                "score_explanation": behavioral.get('score_explanation', ''),
                "transcription_metrics": behavioral.get('transcription_metrics', {}),
                "traits": behavioral.get('traits', []),
                "concerns": behavioral.get('concerns', [])
            },
            "final_score": {
                "value": round(final_score, 1),
                "calculation": f"({content_score} × 0.70) + ({behavioral_score} × 0.30) = {content_weighted} + {behavioral_weighted} = {round(final_score, 1)}",
                "content_contribution": content_weighted,
                "behavioral_contribution": behavioral_weighted
            }
        }
        
        # Add detailed question-by-question breakdown
        question_evaluations = content_data_detailed.get('question_evaluations', [])
        for q_eval in question_evaluations:
            detailed_report["content_evaluation"]["question_details"].append({
                "question_number": q_eval.get('question_number'),
                "question_text": q_eval.get('question_text', ''),
                "transcript": q_eval.get('transcript', ''),
                "score": q_eval.get('score', 0),
                "passed": q_eval.get('passed', False),
                "score_breakdown": q_eval.get('score_breakdown', {}),
                "score_explanation": q_eval.get('score_explanation', ''),
                "why_failed": q_eval.get('why_failed'),
                "what_was_good": q_eval.get('what_was_good'),
                "improvement_suggestions": q_eval.get('improvement_suggestions', []),
                "intent_positive_percentage": q_eval.get('intent_positive_percentage', 0)
            })
        
        # Update state
        state['final_decision'] = {
            "decision": decision,
            "final_score": round(float(final_score), 1),
            "confidence_level": "high" if abs(final_score - 75) > 10 else "medium",
            "component_scores": {k: round(v, 1) for k, v in component_scores.items()},
            "weighted_breakdown": weighted_breakdown,
            "reasoning": reasoning,
            "recommendation": recommendation,
            "strengths": strengths,
            "concerns": concerns,
            "red_flags": list(set(red_flags)),  # Remove duplicates
            "detailed_report": detailed_report  # Add comprehensive report
        }
        
        state['current_stage'] = 'complete'
        
        print(f"   ✅ Assessment Complete!")
        print(f"      Strengths: {', '.join(strengths)}")
        if concerns and concerns[0] != "No major concerns identified":
            print(f"      Concerns: {', '.join(concerns)}")
        
    except Exception as e:
        error_msg = f"Decision aggregation error: {str(e)}"
        print(f"   ❌ {error_msg}")
        
        # Fallback decision with proper component_scores structure
        state['final_decision'] = {
            "decision": "REVIEW",
            "final_score": 0.0,
            "component_scores": {
                "identity": 0,
                "quality": 0,
                "content": 0,
                "behavioral": 0,
                "transcription": 0
            },
            "reasoning": "Unable to complete full assessment. Manual review required.",
            "recommendation": "MANUAL REVIEW - Assessment incomplete",
            "strengths": [],
            "concerns": ["Assessment processing failed"],
            "error": error_msg
        }
        state['errors'].append(error_msg)
    
    return state

