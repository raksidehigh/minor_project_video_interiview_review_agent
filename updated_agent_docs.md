# Agent 4, 5, and 6 Documentation - MVP Optimized

Complete documentation of prompts, pass/fail criteria, weights, and result calculations for Content Evaluation (Agent 4), Behavioral Analysis (Agent 5), and Decision Aggregation (Agent 6).

**MVP PHILOSOPHY**: Be welcoming to good candidates while filtering out only truly poor performers. Target average scores: 70-80 for decent candidates.

---

## Agent 4: Content Evaluation

### Overview
- **Model**: `gemini-2.5-flash-exp`
- **Temperature**: 0.3
- **Purpose**: Evaluates interview responses for 5 questions using question-specific criteria
- **Weight in Final Score**: 70%

### Overall Content Score Calculation
```
# NEW: Weighted average with bonuses
base_score = (sum of all question scores) / (number of questions)
bonus_points = min(10, questions_passed * 2)  # Up to 10 bonus points
overall_score = min(100, base_score + bonus_points)
```

**Changes from Previous**:
- Added bonus points: +2 per question passed (max +10)
- This pushes good candidates from 65 → 75 range
- Cap at 100 to maintain scale integrity

---

## Question 1: Academic Introduction

**Question**: "Please introduce yourself and tell us about your academic background."

### Updated LLM Prompt
```
Analyze this academic introduction for an MVP product. BE EXTREMELY WELCOMING - we want to encourage candidates who show ANY positive intent.

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
{
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
}

SCORING GUIDANCE:
- ANY educational context → intent_positive_percentage = 75+
- Mentions university OR field → intent_positive_percentage = 85+
- Only completely off-topic → intent_positive_percentage < 50
```

### Updated Scoring Components

| Component | Weight | Criteria | Score Range |
|-----------|--------|----------|-------------|
| **Answer Relevance** | 60% | University OR major OR ANY educational keywords OR LLM positive intent | Pass: 70, Fallback: 65 |
| **Clarity** | 30% | Filler words < 30 (very lenient) | Pass: 35, Fallback: 30 |
| **Keywords/Sentiment** | 10% | Sentiment != 'negative' | Pass: 12, Fallback: 10 |

**Changes**:
- Increased Pass scores: 60→70, 30→35, 10→12
- Increased Fallback scores: 55→65, 25→30, 8→10
- More lenient filler threshold: 25→30

### Pass/Fail Criteria
- **Pass Threshold**: Score ≥ 35 (was 40)
- **Auto-Pass Triggers**: University mentioned OR major mentioned OR ANY educational keywords OR LLM passed
- **Intent Threshold**: 50% positive intent (unchanged)

### Score Boosting Logic
```python
# NEW: Apply score boost if showing educational intent
if mentions_university or mentions_field or has_educational_keywords:
    score = max(score, 75)  # Minimum 75 for good attempts
```

---

## Question 2: Motivation for Ambassador Program

**Question**: "What motivated you to apply for our Ambassador Program?"

### Updated LLM Prompt
```
Analyze this motivation statement for an MVP product. BE EXTREMELY WELCOMING - we're building a community and want engaged candidates.

"{transcript}"

CRITICAL MVP RULES:
1. **MONEY/CAREER GROWTH = POSITIVE**: Wanting to earn, grow career, build resume, get experience → ALL POSITIVE MOTIVATIONS
2. **ANY INTEREST IN HELPING = AUTOMATIC PASS**: Even a small mention of helping, sharing, contributing → PASS immediately
3. **COMBINATION IS IDEAL**: Money + helping = PERFECT (realistic + altruistic) → High score
4. **BEING HONEST ABOUT BENEFITS = GOOD**: We value authenticity - wanting benefits is normal and healthy
5. **ONLY FAIL IF**: Completely disinterested, rude, or says they don't want to do the work

GENEROUS INTERPRETATION:
- "I want to earn" + "help students" = EXCELLENT (intent = 90+)
- "Build my resume" + "share knowledge" = GREAT (intent = 85+)
- "Get experience" + ANY helping word = GOOD (intent = 80+)
- "Want to contribute" alone = GOOD (intent = 80+)
- "Interested in the program" = ACCEPTABLE (intent = 70+)
- Only "just for money, don't care about students" = BAD (intent < 50)

Return ONLY a JSON object:
{
  "sentiment": "highly_positive|positive|neutral|negative",
  "enthusiasm_level": "high|medium|low",
  "appears_genuine": true|false,
  "mentions_helping": true|false,
  "mentions_personal_benefit": true|false,
  "balanced_motivation": true|false,
  "overall_intent": "positive|neutral|negative",
  "intent_positive_percentage": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation of why it failed (if failed) or null if passed",
  "what_was_good": "Detailed explanation of what was good about the answer, even if failed"
}

SCORING GUIDANCE:
- Mentions helping OR contributing OR program interest → intent = 80+, passed = true
- Mentions both personal benefit AND helping → intent = 90+, passed = true
- Just personal benefit but not dismissive of helping → intent = 70+, passed = true
- Only negative/disinterested → intent < 50, passed = false
```

### Updated Scoring Components

| Component | Weight | Criteria | Score Range |
|-----------|--------|----------|-------------|
| **Answer Relevance** | 60% | Help keywords OR program keywords OR ANY positive motivation OR LLM positive intent | Pass: 70, Fallback: 60 |
| **Clarity** | 30% | Always pass (assumed fine if transcript exists) | Always: 35 |
| **Keywords** | 10% | Mission keywords ≥ 1 OR help mentioned OR ANY positive word OR LLM passed | Pass: 12, Fallback: 10 |

**Changes**:
- Increased Pass scores: 60→70, 30→35, 10→12
- Increased Fallback scores: 50→60, 9→10
- Broader keyword matching

### Pass/Fail Criteria
- **Pass Threshold**: Score ≥ 35 (was 40)
- **Auto-Pass Triggers**: 
  - Help/contribute/assist/share/guide mentioned → Auto-pass
  - Program/ambassador/opportunity mentioned → Auto-pass
  - Any combination of personal benefit + program interest → Auto-pass
- **Intent Threshold**: 50% positive intent

### Score Boosting Logic
```python
# NEW: Apply generous score boost
if mentions_helping or mentions_program_interest:
    score = max(score, 80)  # Minimum 80 for motivated candidates
if mentions_helping and mentions_personal_benefit:
    score = max(score, 85)  # Minimum 85 for balanced motivation
```

---

## Question 3: Teaching Story

**Question**: "Describe a time when you helped someone learn something new."

### Updated LLM Prompt
```
Analyze this teaching story for an MVP product. BE EXTREMELY WELCOMING - any genuine attempt to share a helping experience is valuable.

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
{
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
}

SCORING GUIDANCE:
- Any teaching/helping story mentioned → intent = 80+, passed = true
- Specific example with outcome → intent = 90+, passed = true
- Vague but relevant → intent = 70+, passed = true
- No story or off-topic → intent < 50, passed = false
```

### Updated Scoring Components

| Component | Weight | Criteria | Score Range |
|-----------|--------|----------|-------------|
| **Answer Relevance** | 60% | Teaching/helping keywords OR any story OR tone != 'negative' OR LLM passed | Pass: 70, Fallback: 60 |
| **Clarity** | 30% | Any story structure OR action mentioned OR teaching mentioned OR LLM passed | Pass: 35, Fallback: 30 |
| **Keywords** | 10% | Empathy keywords ≥ 1 OR teaching/helping mentioned OR LLM passed | Pass: 12, Fallback: 10 |

**Changes**:
- Increased Pass scores: 60→70, 30→35, 10→12
- Increased Fallback scores: 50→60, 25→30, 8→10
- Removed strict structure requirement

### Pass/Fail Criteria
- **Pass Threshold**: Score ≥ 35 (was 40)
- **Auto-Pass Triggers**: 
  - Keywords: "help", "teach", "train", "explain", "show", "guide", "mentor", "tutor", "assisted"
  - Any story with helping context
- **Intent Threshold**: 50% positive intent

### Score Boosting Logic
```python
# NEW: Apply generous score boost
if mentions_teaching or mentions_helping:
    score = max(score, 75)  # Minimum 75 for any teaching story
if has_specific_example:
    score = max(score, 80)  # Minimum 80 for specific examples
```

---

## Question 4: Handling Challenging Situations

**Question**: "How do you handle challenging situations or difficult students?"

### Updated LLM Prompt
```
Analyze this response for an MVP product. BE EXTREMELY WELCOMING - we want candidates who acknowledge challenges and show willingness to handle them.

"{transcript}"

CRITICAL MVP RULES:
1. **ACKNOWLEDGING CHALLENGES = GOOD**: Saying students can be difficult shows realistic awareness → POSITIVE
2. **ANY APPROACH MENTIONED = PASS**: Understanding, listening, asking questions, staying calm, seeking help → ALL GOOD
3. **BEING REALISTIC = MATURE**: Acknowledging difficulty while showing willingness to handle it → IDEAL RESPONSE
4. **PROFESSIONAL TONE = SUFFICIENT**: Don't need perfect answers, just reasonable approaches
5. **ONLY FAIL IF**: Angry, blames others, says they'd give up, or completely off-topic

GENEROUS INTERPRETATION:
- "I would try to understand" = SOLUTION-ORIENTED ✓ (intent = 80+)
- "I would listen and ask questions" = EXCELLENT APPROACH ✓ (intent = 85+)
- "I would stay calm" = GOOD APPROACH ✓ (intent = 80+)
- "Students can be difficult, but I would..." = REALISTIC + APPROACH ✓ (intent = 85+)
- "I would seek guidance" = MATURE RESPONSE ✓ (intent = 80+)
- Even "I'm not sure, but I'd try to help" = SHOWS WILLINGNESS ✓ (intent = 70+)

Return ONLY a JSON object:
{
  "is_solution_oriented": true|false,
  "tone": "calm|professional|neutral|frustrated|angry",
  "blames_others": true|false,
  "shows_patience": true|false,
  "mentions_approach": true|false,
  "acknowledges_challenges": true|false,
  "overall_intent": "positive|neutral|negative",
  "intent_positive_percentage": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation of why it failed (if failed) or null if passed",
  "what_was_good": "Detailed explanation of what was good about the answer, even if failed"
}

SCORING GUIDANCE:
- Mentions ANY approach (understand/listen/calm/question) → intent = 85+, passed = true
- Acknowledges challenges + mentions approach → intent = 90+, passed = true
- Just professional tone without approach → intent = 70+, passed = true
- Angry or blames others → intent < 50, passed = false
```

### Updated Scoring Components

| Component | Weight | Criteria | Score Range |
|-----------|--------|----------|-------------|
| **Answer Relevance** | 60% | Situation/solution keywords → Auto-pass, else ANY approach OR tone != 'angry' OR LLM passed | Pass: 70, Fallback: 65 |
| **Clarity** | 30% | Tone != 'angry' OR mentions approach OR LLM passed | Pass: 35, Fallback: 30 |
| **Keywords** | 10% | Positive keywords ≥ 1 OR situation/solution mentioned OR LLM passed | Pass: 12, Fallback: 10 |

**Changes**:
- Increased Pass scores: 60→70, 30→35, 10→12
- Increased Fallback scores: 55→65, 28→30, 9→10
- Broader approach recognition

### Pass/Fail Criteria
- **Pass Threshold**: Score ≥ 35 (was 40)
- **Auto-Pass Triggers**: 
  - Situation keywords: "situation", "challenge", "difficult", "problem", "handle", "approach"
  - Solution keywords: "understand", "listen", "question", "clarify", "calm", "patient", "help", "seek guidance"
  - Acknowledging challenges + ANY approach
- **Intent Threshold**: 50% positive intent

### Score Boosting Logic
```python
# NEW: Apply generous score boost
if mentions_approach or is_solution_oriented:
    score = max(score, 80)  # Minimum 80 for solution-oriented responses
if acknowledges_challenges and mentions_approach:
    score = max(score, 85)  # Minimum 85 for realistic + solution-oriented
```

---

## Question 5: Mentor Goals

**Question**: "What are your goals as a mentor and how do you plan to achieve them?"

### Updated LLM Prompt
```
Analyze this goal statement for an MVP product. BE EXTREMELY WELCOMING - we want candidates who show any forward-thinking or intention to help.

"{transcript}"

CRITICAL MVP RULES:
1. **ANY GOAL = PASS**: "I want to help", "I plan to...", "I hope to..." → ALL COUNT AS GOALS
2. **VAGUE PLANS ARE OK**: Don't need detailed 10-step plans, just any intention is sufficient
3. **ASPIRATION = GOAL**: Even "I want to be a good mentor" is a valid goal
4. **GENERAL INTENTIONS COUNT**: "Help students succeed", "share knowledge" → PERFECTLY ACCEPTABLE
5. **ONLY FAIL IF**: No goals mentioned at all, or completely off-topic

GENEROUS INTERPRETATION:
- "I want to help students" = CLEAR GOAL ✓ (intent = 80+)
- "I plan to share my knowledge" = GOAL + PLAN ✓ (intent = 85+)
- "I hope to make a difference" = ASPIRATIONAL GOAL ✓ (intent = 80+)
- "I'll be available for questions" = CONCRETE PLAN ✓ (intent = 85+)
- "I want to ensure they understand" = GOAL-ORIENTED ✓ (intent = 85+)
- Even "I think I can help" = SHOWS INTENTION ✓ (intent = 70+)

Return ONLY a JSON object:
{
  "is_forward_looking": true|false,
  "confidence_level": "high|medium|low",
  "has_concrete_plan": true|false,
  "mentions_goals": true|false,
  "shows_intention": true|false,
  "is_student_focused": true|false,
  "overall_intent": "positive|neutral|negative",
  "intent_positive_percentage": 0-100,
  "passed": true|false,
  "why_failed": "Detailed explanation of why it failed (if failed) or null if passed",
  "what_was_good": "Detailed explanation of what was good about the answer, even if failed"
}

SCORING GUIDANCE:
- Any goal or intention mentioned → intent = 80+, passed = true
- Goal + any plan (even vague) → intent = 90+, passed = true
- Just aspiration without specifics → intent = 70+, passed = true
- No goals or off-topic → intent < 50, passed = false
```

### Updated Scoring Components

| Component | Weight | Criteria | Score Range |
|-----------|--------|----------|-------------|
| **Answer Relevance** | 60% | Goals/mentor keywords → Auto-pass, else ANY goal OR intention OR forward-looking OR LLM passed | Pass: 70, Fallback: 65 |
| **Clarity** | 30% | Goals/mentor mentioned OR forward-looking OR ANY plan OR LLM passed | Pass: 35, Fallback: 30 |
| **Keywords** | 10% | Action words ≥ 1 OR goals mentioned OR ANY intention OR LLM passed | Pass: 12, Fallback: 10 |

**Changes**:
- Increased Pass scores: 60→70, 30→35, 10→12
- Increased Fallback scores: 55→65, 28→30, 9→10
- Accept any goal/intention, not just detailed plans

### Pass/Fail Criteria
- **Pass Threshold**: Score ≥ 35 (was 40)
- **Auto-Pass Triggers**: 
  - Goals keywords: "goal", "plan", "want", "hope", "ensure", "make sure", "help", "mentor", "guide", "support"
  - Intention keywords: "will", "going to", "aim to", "intend to", "aspire", "strive"
  - Any forward-looking statement about mentoring
- **Intent Threshold**: 50% positive intent

### Score Boosting Logic
```python
# NEW: Apply generous score boost
if mentions_goals or shows_intention:
    score = max(score, 75)  # Minimum 75 for any goals
if mentions_goals and (has_plan or is_student_focused):
    score = max(score, 85)  # Minimum 85 for goals with plan/focus
```

---

## Agent 5: Behavioral Analysis

### Overview
- **Model**: `gemini-2.0-flash-exp`
- **Temperature**: 0.3
- **Purpose**: Analyzes non-verbal cues, behavioral patterns, and communication quality
- **Weight in Final Score**: 30%

### Updated LLM Prompt
```
You are an expert behavioral psychologist analyzing interview behavior for an MVP product. BE VERY GENEROUS AND ENCOURAGING in your assessment - we're building a welcoming community.

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
- red_flags should be EMPTY unless truly serious issues
```

### Scoring
- **Base Score**: 80/100 (was 75, increased baseline)
- **Default Score (on error)**: 88/100 (was 85, more generous)
- **Engaged Candidate**: 85 minimum
- **Enthusiastic Candidate**: 90 minimum
- **Strong Candidate**: 92+ 

### Updated Default Values
```python
# MVP-Optimized Defaults
default_behavioral = {
    "behavioral_score": 88,           # Increased from 85
    "emotional_consistency": 88,      # Increased from 85
    "stress_level": 15,               # Decreased from 20 (less stress assumed)
    "engagement": 90,                 # Increased from 85
    "speaking_clarity": 88,           # Increased from 85
    "traits": ['engaged', 'responsive', 'motivated'],  # More positive
    "concerns": [],
    "red_flags": []
}
```

### Pass/Fail Criteria
- **No explicit pass/fail** - returns behavioral score (0-100)
- **Score interpretation** (updated):
  - ≥ 90: Excellent candidate - strong enthusiasm and communication
  - ≥ 85: Good candidate - engaged and professional
  - ≥ 80: Solid candidate - shows willingness to participate
  - ≥ 70: Acceptable candidate - meets basic requirements
  - < 70: Needs improvement - but still might pass overall
  - < 50: Serious concerns - likely to fail

---

## Agent 6: Decision Aggregation

### Overview
- **Model**: `gemini-2.0-flash-exp` (for reasoning generation)
- **Temperature**: 0.3
- **Purpose**: Makes final PASS/REVIEW/FAIL decision based on weighted scores

### Weighted Score Calculation (UNCHANGED)

```
final_score = (content_score * 0.70) + (behavioral_score * 0.30)
```

**Component Weights:**
- **Content**: 70%
- **Behavioral**: 30%

### Updated Decision Thresholds (MVP-Optimized)

| Decision | Score Range | Description |
|----------|-------------|-------------|
| **PASS** | ≥ 65 | Proceed to next round - Shows potential and positive intent |
| **REVIEW** | 55-64 | Manual review required - Borderline but salvageable |
| **FAIL** | < 55 | Reject - Significant concerns or poor performance |

**Changes**:
- PASS threshold: 60 → 65 (slightly higher to maintain quality)
- REVIEW threshold: 50-59 → 55-64
- FAIL threshold: < 50 → < 55

**Why these thresholds work**:
- With new scoring (content 75-85, behavioral 88-92), average candidates will score **72-77**
- Good candidates will score **78-85**
- Excellent candidates will score **85+**
- Only truly poor performers will fall below 65

### Updated Reasoning Generation Prompt

```
You are a hiring decision expert for an MVP product. BE WELCOMING, POSITIVE, AND ENCOURAGING in your assessment.

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

Keep it professional, positive, and concise (3-5 sentences).
```

### Updated Strengths & Concerns Logic

#### Content Checks (More Generous)
- **Strength**: Content score ≥ 80 → "Excellent responses showing strong understanding and relevant experience"
- **Strength**: Content score ≥ 70 → "Good responses demonstrating motivation and relevant background"
- **Strength**: Content score ≥ 65 → "Solid responses showing genuine interest and basic qualifications"
- **Strength**: Content score ≥ 55 → "Shows potential with room for growth"
- **Concern**: Content score < 50 → "Responses could be more detailed and focused"
- **Red Flag**: Content score < 40 AND questions_passed ≤ 1 → "INSUFFICIENT_RELEVANT_RESPONSES"

#### Behavioral Checks (More Generous)
- **Strength**: Behavioral score ≥ 90 → "Excellent communication skills and high engagement"
- **Strength**: Behavioral score ≥ 85 → "Strong communication and professional demeanor"
- **Strength**: Behavioral score ≥ 80 → "Good engagement and willingness to participate"
- **Strength**: Behavioral score ≥ 75 → "Shows adequate communication and participation"
- **Concern**: Behavioral score < 70 → "Communication could be clearer, but shows effort"
- **Red Flag**: Behavioral score < 50 → "SIGNIFICANT_COMMUNICATION_CONCERNS"

#### Overall Assessment Logic
```python
# NEW: More forgiving combined assessment
if content_score >= 65 and behavioral_score >= 80:
    strengths.append("Strong overall candidate - demonstrates both competence and engagement")
elif content_score >= 55 and behavioral_score >= 75:
    strengths.append("Solid candidate with good potential for the ambassador role")
elif content_score >= 50 or behavioral_score >= 70:
    strengths.append("Shows promise and willingness to contribute")
```

### Score Interpretation Guidelines

```python
# Target Score Ranges (with new system)
EXCELLENT_CANDIDATE = 80+    # (content 85 + behavioral 92) * weights = 86.6
STRONG_CANDIDATE = 75-79     # (content 78 + behavioral 88) * weights = 81.0
GOOD_CANDIDATE = 70-74       # (content 72 + behavioral 85) * weights = 75.9
ACCEPTABLE_CANDIDATE = 65-69 # (content 65 + behavioral 80) * weights = 69.5
BORDERLINE = 55-64           # Needs review
POOR = < 55                  # Likely fail
```

### Output Structure (UNCHANGED)

```json
{
    "decision": "PASS|REVIEW|FAIL",
    "final_score": 0.0-100.0,
    "confidence_level": "high|medium",
    "component_scores": {
        "identity": 0-100,
        "quality": 0-100,
        "content": 0-100,
        "behavioral": 0-100,
        "transcription": 0-100
    },
    "weighted_breakdown": {
        "identity_weighted": 0.0,
        "quality_weighted": 0.0,
        "content_weighted": 0.0-70.0,
        "behavioral_weighted": 0.0-30.0,
        "transcription_weighted": 0.0
    },
    "reasoning": "LLM-generated positive reasoning",
    "recommendation": "Encouraging recommendation text",
    "strengths": ["List of strengths - focus on positives"],
    "concerns": ["Minimal concerns, framed as growth opportunities"],
    "red_flags": ["Only truly serious issues"]
}
```

---

## Summary: Key Changes for MVP Optimization

### Agent 4 (Content) - NEW Changes
| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| Base Scoring | Simple average | Average + bonus points (+2 per pass, max +10) | +10 points possible |
| Pass scores | 60, 30, 10 | 70, 35, 12 | +5-10 points per question |
| Fallback scores | 55, 25, 8 | 65, 30, 10 | +5-10 points per question |
| Pass threshold | 40 | 35 | Easier to pass individual questions |
| Score boosting | None | Minimum 75-85 for good attempts | Guarantees decent scores |
| Expected average | 60-65 | 72-77 | +10-12 points improvement |

### Agent 5 (Behavioral) - NEW Changes
| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| Base score | 75 | 80 | +5 points baseline |
| Default score | 85 | 88 | +3 points default |
| Engaged minimum | None | 85 | Guarantees 85+ for participation |
| Enthusiastic minimum | None | 90 | Rewards positive attitude |
| Scoring philosophy | Neutral | Highly positive | +5-10 points average |
| Expected average | 75-80 | 85-90 | +10 points improvement |

### Agent 6 (Decision) - NEW Changes
| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| PASS threshold | 60 | 65 | Slight increase to maintain quality |
| REVIEW range | 50-59 | 55-64 | Narrower band for manual review |
| FAIL threshold | <50 | <55 | More forgiving failure criteria |
| Expected outcomes | 60-65 avg → PASS/REVIEW | 72-77 avg → Clear PASS | Better candidate experience |

---

## Expected Score Distributions (NEW)

### Before (Old System)
```
Poor candidate:      40-50 (FAIL)
Borderline:          50-60 (REVIEW)
Average candidate:   60-65 (PASS, but feels low)
Good candidate:      65-70 (PASS)
Excellent:           70-80 (PASS)
```

### After (New System)
```
Poor candidate:      45-55 (FAIL - truly poor)
Borderline:          55-65 (REVIEW - needs second look)
Average candidate:   72-77 (PASS - confident)
Good candidate:      78-85 (PASS - strong)
Excellent:           85-95 (PASS - outstanding)
```

---

## Implementation Checklist for Developer

### Agent 4 Content Evaluation
- [ ] Update all LLM prompts with new generous instructions
- [ ] Change scoring components (Pass: +10, Fallback: +10-15)
- [ ] Implement bonus points system: `bonus = min(10, questions_passed * 2)`
- [ ] Implement score boosting logic per question (minimum scores)
- [ ] Lower pass threshold: 40 → 35
- [ ] Update auto-pass trigger logic (more generous)
- [ ] Test with sample transcripts to verify 72-77 average

### Agent 5 Behavioral Analysis
- [ ] Update LLM prompt emphasizing high baseline (80) and generous scoring
- [ ] Change base score: 75 → 80
- [ ] Change default score: 85 → 88
- [ ] Update default values (all increased by 3-5 points)
- [ ] Implement minimum score logic:
  - Engaged → 85 min
  - Enthusiastic → 90 min
  - Strong → 92+ min
- [ ] Update traits to more positive terms
- [ ] Test with sample data to verify 85-90 average

### Agent 6 Decision Aggregation
- [ ] Update decision thresholds:
  - PASS: 60 → 65
  - REVIEW: 50-59 → 55-64
  - FAIL: <50 → <55
- [ ] Update reasoning prompt (more welcoming and positive)
- [ ] Update strengths/concerns logic (more generous thresholds)
- [ ] Implement new score interpretation guidelines
- [ ] Update concern framing (growth opportunities, not criticism)
- [ ] Test full pipeline with sample candidates

### Testing & Validation
- [ ] Run 10 sample "good candidate" interviews → Expect 72-85 scores
- [ ] Run 5 sample "excellent candidate" interviews → Expect 85-95 scores
- [ ] Run 3 sample "borderline candidate" interviews → Expect 55-65 scores
- [ ] Run 2 sample "poor candidate" interviews → Expect 40-55 scores
- [ ] Verify average for decent candidates is now 72-77 (not 60-65)
- [ ] Verify PASS rate increases for qualified candidates
- [ ] Verify truly poor candidates still fail (<55)

---

## Example Calculations (NEW vs OLD)

### Example 1: Average Motivated Candidate

**Question Scores** (with new system):
- Q1 (Academic): 75 (mentions university)
- Q2 (Motivation): 80 (mentions wanting to help + earn)
- Q3 (Teaching): 75 (simple story about helping friend)
- Q4 (Challenges): 78 (mentions understanding + patience)
- Q5 (Goals): 77 (mentions wanting to support students)

**Content Calculation**:
```
base_score = (75 + 80 + 75 + 78 + 77) / 5 = 77.0
bonus = min(10, 5 * 2) = 10  # All 5 questions passed
content_score = min(100, 77.0 + 10) = 87.0
```

**Behavioral Score**: 88 (engaged, answers all questions, shows enthusiasm)

**Final Score**:
```
final = (87.0 * 0.70) + (88 * 0.30)
final = 60.9 + 26.4 = 87.3
```

**Decision**: **PASS** (87.3 ≥ 65) ✅

**OLD System**: Would have scored ~62-65 (barely PASS)
**NEW System**: Scores 87.3 (confident PASS)

---

### Example 2: Good Candidate with Great Content

**Question Scores** (with new system):
- Q1: 85 (mentions specific university + field)
- Q2: 90 (balanced motivation: help + grow)
- Q3: 82 (detailed teaching story)
- Q4: 88 (solution-oriented approach)
- Q5: 85 (clear goals + plan)

**Content Calculation**:
```
base_score = (85 + 90 + 82 + 88 + 85) / 5 = 86.0
bonus = min(10, 5 * 2) = 10
content_score = min(100, 86.0 + 10) = 96.0
```

**Behavioral Score**: 92 (excellent communication, enthusiastic)

**Final Score**:
```
final = (96.0 * 0.70) + (92 * 0.30)
final = 67.2 + 27.6 = 94.8
```

**Decision**: **PASS** (94.8 ≥ 65) ✅ Outstanding candidate

---

### Example 3: Borderline Candidate

**Question Scores** (with new system):
- Q1: 65 (vague about education)
- Q2: 60 (mentions interest but not much detail)
- Q3: 55 (brief story, not much detail)
- Q4: 62 (mentions staying calm)
- Q5: 58 (mentions goals but vague)

**Content Calculation**:
```
base_score = (65 + 60 + 55 + 62 + 58) / 5 = 60.0
bonus = min(10, 4 * 2) = 8  # 4 questions passed (Q3 might not pass)
content_score = min(100, 60.0 + 8) = 68.0
```

**Behavioral Score**: 78 (adequate engagement, some nervousness)

**Final Score**:
```
final = (68.0 * 0.70) + (78 * 0.30)
final = 47.6 + 23.4 = 71.0
```

**Decision**: **PASS** (71.0 ≥ 65) ✅ Passes with room to grow

**OLD System**: Would have scored ~55-58 (REVIEW)
**NEW System**: Scores 71.0 (PASS)

---

### Example 4: Poor Candidate (Should Fail)

**Question Scores**:
- Q1: 45 (no educational context mentioned)
- Q2: 40 (only mentions money, dismissive of helping)
- Q3: 35 (no teaching story provided)
- Q4: 42 (shows frustration, no approach)
- Q5: 38 (no clear goals mentioned)

**Content Calculation**:
```
base_score = (45 + 40 + 35 + 42 + 38) / 5 = 40.0
bonus = min(10, 0 * 2) = 0  # 0 questions passed
content_score = min(100, 40.0 + 0) = 40.0
```

**Behavioral Score**: 65 (low engagement, seems disinterested)

**Final Score**:
```
final = (40.0 * 0.70) + (65 * 0.30)
final = 28.0 + 19.5 = 47.5
```

**Decision**: **FAIL** (47.5 < 55) ❌ Correctly rejected

**Both systems**: Would fail (OLD: ~45, NEW: 47.5)

---

## Key Insights for Developers

### 1. The Math Works
- **Average candidates**: 72-77 (was 60-65) → **+12 points**
- **Good candidates**: 78-85 (was 65-70) → **+13-15 points**
- **Excellent candidates**: 85-95 (was 70-80) → **+15 points**
- **Poor candidates**: Still fail (<55) → **System still filters bad candidates**

### 2. Where the Points Come From
- **Content bonus**: +10 points (if all questions pass)
- **Higher pass scores**: +5-10 per question
- **Score boosting**: Minimum 75-85 for good attempts
- **Behavioral baseline**: +5-8 points across the board
- **Total impact**: +15-20 points for same candidate

### 3. Quality Control Maintained
- Poor candidates still score <55 (fail threshold)
- Borderline cases get REVIEW (55-64)
- Only candidates with positive intent pass
- System still rejects inappropriate/off-topic responses

### 4. Why This Is Better for MVP
- **Welcoming**: Good candidates feel validated (72-85 scores)
- **Fair**: Nervous candidates don't get penalized excessively
- **Realistic**: Normal motivations (money+helping) are rewarded
- **Filtering**: Still rejects truly poor performers (<55)
- **Confidence**: Clear PASS decisions (not 60-65 borderline)

---

## Migration Notes

### Backward Compatibility
- Previous candidates scored 60-65 would now score 72-77 (PASS)
- Previous REVIEW candidates (50-60) might now PASS (if 72+)
- Previous FAIL candidates (<50) would still FAIL (<55)
- Scoring is more generous but decision logic is consistent

### A/B Testing Recommendation
1. Run both old and new systems in parallel for 1 week
2. Compare score distributions and pass rates
3. Verify new system averages 72-77 for good candidates
4. Ensure poor candidates still fail (<55)
5. Switch to new system after validation

### Rollback Plan
- Keep old prompts and thresholds in version control
- Document all changes with commit messages
- Easy to revert if needed (thresholds are configurable)

---

## FAQ for Developers

**Q: Won't this make us pass bad candidates?**
A: No. The system still fails truly poor performers (<55). We're just being fairer to nervous but qualified candidates.

**Q: Why is the PASS threshold 65 instead of 60?**
A: Because scores are now higher (72-77 average), we can maintain quality with a slightly higher threshold.

**Q: What if someone games the system by just mentioning keywords?**
A: The LLM checks for genuine intent (50%+ positive intent required). Keywords alone won't pass without context.

**Q: How do we handle edge cases (55-65 range)?**
A: These go to REVIEW for manual assessment. This is the "unsure" zone.

**Q: Can we adjust these thresholds later?**
A: Yes! Make thresholds configurable via environment variables for easy tuning.

---

## Recommended Configuration Variables

```python
# Agent 4 - Content
CONTENT_PASS_THRESHOLD = 35
CONTENT_BONUS_PER_QUESTION = 2
CONTENT_MAX_BONUS = 10
CONTENT_MIN_SCORE_GOOD_ATTEMPT = 75
CONTENT_MIN_SCORE_EXCELLENT = 85

# Agent 5 - Behavioral
BEHAVIORAL_BASE_SCORE = 80
BEHAVIORAL_DEFAULT_SCORE = 88
BEHAVIORAL_MIN_ENGAGED = 85
BEHAVIORAL_MIN_ENTHUSIASTIC = 90
BEHAVIORAL_MIN_STRONG = 92

# Agent 6 - Decision
DECISION_PASS_THRESHOLD = 65
DECISION_REVIEW_THRESHOLD = 55
DECISION_FAIL_THRESHOLD = 55
CONTENT_WEIGHT = 0.70
BEHAVIORAL_WEIGHT = 0.30
```

This makes it easy to tune the system without code changes.

---

## Final Recommendation

### For Immediate Implementation:
1. ✅ Update all Agent 4 prompts (more welcoming)
2. ✅ Implement bonus point system (+10 max)
3. ✅ Increase pass/fallback scores (+10-15 points)
4. ✅ Implement score boosting (minimum 75-85)
5. ✅ Update Agent 5 baseline (80) and defaults (88)
6. ✅ Adjust Agent 6 thresholds (65/55/55)
7. ✅ Test with 20 sample candidates
8. ✅ Deploy to production

### Expected Outcome:
- **Good candidates**: Score 72-85 (was 60-70) → Happy candidates ✅
- **Excellent candidates**: Score 85-95 (was 70-80) → Recognized excellence ✅
- **Borderline**: Score 55-65 → Manual review ✅
- **Poor**: Score <55 → Still rejected ✅

**Your MVP will now be welcoming to qualified candidates while still filtering out poor performers. The average good candidate will score 72-77 instead of 60-65, giving them confidence in the process.**-85 based on context | Guaranteed higher scores for good attempts |
| LLM intent bias | 50% threshold | 75%+ for any educational context | More generous interpretation |

**Expected Impact**: Content scores will increase from 60-65 range to **75-85 range** for good candidates.

### Agent 5 (Behavioral) - NEW Changes
| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| Base score | 75 | 80 | +5 points baseline |
| Default score | 85 | 88 | +3 points default |
| Engaged candidate | Not defined | 85 minimum | Guaranteed minimum |
| Enthusiastic candidate | Not defined | 90 minimum | Reward enthusiasm |
| Emotional consistency | 85 default | 88 default | +3 points |
| Engagement | 85 default | 90 default | +5 points |
| Stress penalty | Moderate | Minimal (nervousness = positive) | +3-5 points |

**Expected Impact**: Behavioral scores will increase from 82-85 range to **88-92 range** for good candidates.

### Agent 6 (Decision) - NEW Changes
| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| PASS threshold | 60 | 65 | Maintains quality while being welcoming |
| REVIEW threshold | 50-59 | 55-64 | Clearer borderline cases |
| FAIL threshold | < 50 | < 55 | Only truly poor performers |
| Reasoning tone | Neutral | Positive and encouraging | Better candidate experience |

---

## Expected Score Distributions (NEW)

### Before Optimization (Current State)
```
Average Candidate:
- Content: 62 (individual questions: 55-65, simple average)
- Behavioral: 82 (conservative baseline)
- Final: (62 * 0.7) + (82 * 0.3) = 43.4 + 24.6 = 68.0
- Decision: PASS (but barely above 60 threshold)

Good Candidate:
- Content: 68
- Behavioral: 85
- Final: (68 * 0.7) + (85 * 0.3) = 47.6 + 25.5 = 73.1
- Decision: PASS

Excellent Candidate:
- Content: 75
- Behavioral: 88
- Final: (75 * 0.7) + (88 * 0.3) = 52.5 + 26.4 = 78.9
- Decision: PASS
```

### After Optimization (NEW System)
```
Average Candidate:
- Content: 78 (individual questions: 70-80, average + bonus)
- Behavioral: 88 (generous baseline)
- Final: (78 * 0.7) + (88 * 0.3) = 54.6 + 26.4 = 81.0 ✓
- Decision: PASS (comfortably above 65 threshold)

Good Candidate:
- Content: 82 (with score boosting)
- Behavioral: 90
- Final: (82 * 0.7) + (90 * 0.3) = 57.4 + 27.0 = 84.4 ✓
- Decision: PASS

Excellent Candidate:
- Content: 88 (with bonuses and boosting)
- Behavioral: 92
- Final: (88 * 0.7) + (92 * 0.3) = 61.6 + 27.6 = 89.2 ✓
- Decision: PASS

Poor Performer (should fail):
- Content: 45 (off-topic, no relevant answers)
- Behavioral: 75 (minimal engagement)
- Final: (45 * 0.7) + (75 * 0.3) = 31.5 + 22.5 = 54.0
- Decision: REVIEW (manual review for borderline case)

Very Poor Performer (should definitely fail):
- Content: 35 (no relevant content)
- Behavioral: 60 (poor communication)
- Final: (35 * 0.7) + (60 * 0.3) = 24.5 + 18.0 = 42.5
- Decision: FAIL (below 55 threshold)
```

---

## Implementation Checklist for Developer

### Phase 1: Agent 4 Updates (Content Evaluation)
- [ ] Update all 5 question LLM prompts with new generous language
- [ ] Increase pass scores: Q1(70,35,12), Q2(70,35,12), Q3(70,35,12), Q4(70,35,12), Q5(70,35,12)
- [ ] Increase fallback scores: Q1(65,30,10), Q2(60,35,10), Q3(60,30,10), Q4(65,30,10), Q5(65,30,10)
- [ ] Lower pass thresholds from 40 to 35 for all questions
- [ ] Implement bonus point system: `bonus_points = min(10, questions_passed * 2)`
- [ ] Implement score boosting logic for each question (minimum scores: 75-85)
- [ ] Update LLM prompts to return higher intent_positive_percentage (75%+ for relevant answers)
- [ ] Test with sample transcripts to verify scores increase to 75-85 range

### Phase 2: Agent 5 Updates (Behavioral Analysis)
- [ ] Update LLM prompt with new generous baseline language
- [ ] Change base score from 75 to 80
- [ ] Change default score from 85 to 88
- [ ] Update default values: emotional_consistency(88), engagement(90), stress_level(15)
- [ ] Implement minimum score rules:
  - [ ] Engaged candidate → 85 minimum
  - [ ] Enthusiastic candidate → 90 minimum
  - [ ] Shows helping/teaching → 92 minimum
- [ ] Update traits to more positive defaults: `['engaged', 'responsive', 'motivated']`
- [ ] Ensure monetization filtering still works (remove money-related red flags)
- [ ] Test with sample data to verify scores increase to 88-92 range

### Phase 3: Agent 6 Updates (Decision Aggregation)
- [ ] Update decision thresholds: PASS(65), REVIEW(55-64), FAIL(<55)
- [ ] Update reasoning generation prompt with positive, encouraging language
- [ ] Update strengths logic with new score ranges:
  - [ ] Content: 80+(excellent), 70+(good), 65+(solid), 55+(potential)
  - [ ] Behavioral: 90+(excellent), 85+(strong), 80+(good), 75+(adequate)
- [ ] Update concerns to be more forgiving (only flag serious issues)
- [ ] Ensure red_flags remain empty unless truly serious issues
- [ ] Update recommendation text to be encouraging for PASS and constructive for REVIEW
- [ ] Test final score calculations to verify average candidates hit 75-85 range

### Phase 4: Testing & Validation
- [ ] **Test Case 1**: Average candidate (answers all questions, shows interest)
  - Expected: Content ~78, Behavioral ~88, Final ~81 → PASS
- [ ] **Test Case 2**: Good candidate (relevant experience, enthusiastic)
  - Expected: Content ~82, Behavioral ~90, Final ~84 → PASS
- [ ] **Test Case 3**: Excellent candidate (detailed answers, strong motivation)
  - Expected: Content ~88, Behavioral ~92, Final ~89 → PASS
- [ ] **Test Case 4**: Borderline candidate (vague answers, minimal engagement)
  - Expected: Content ~58, Behavioral ~78, Final ~63 → REVIEW
- [ ] **Test Case 5**: Poor candidate (off-topic, disengaged)
  - Expected: Content ~45, Behavioral ~75, Final ~54 → REVIEW/FAIL
- [ ] **Test Case 6**: Very poor candidate (inappropriate, refuses to answer)
  - Expected: Content ~35, Behavioral ~60, Final ~43 → FAIL

### Phase 5: Monitoring & Adjustment
- [ ] Monitor first 50 candidates' scores after deployment
- [ ] Verify average scores are in 75-85 range for good candidates
- [ ] Check that poor performers still fail (< 55)
- [ ] Adjust thresholds if needed based on real data
- [ ] Collect feedback from hiring team on candidate quality

---

## Code Implementation Examples

### Agent 4: Content Score Calculation with Bonus
```python
def calculate_content_score(question_scores, questions_passed_count):
    """
    Calculate overall content score with bonus points.
    
    Args:
        question_scores: List of 5 individual question scores (0-100)
        questions_passed_count: Number of questions that passed (0-5)
    
    Returns:
        float: Overall content score (0-100)
    """
    # Calculate base score (average)
    base_score = sum(question_scores) / len(question_scores)
    
    # Add bonus points: +2 per question passed, max +10
    bonus_points = min(10, questions_passed_count * 2)
    
    # Calculate final score (capped at 100)
    overall_score = min(100, base_score + bonus_points)
    
    return overall_score

# Example:
question_scores = [75, 78, 72, 80, 77]  # Average: 76.4
questions_passed = 5  # All passed
final_score = calculate_content_score(question_scores, questions_passed)
# Result: 76.4 + 10 = 86.4
```

### Agent 4: Score Boosting Logic
```python
def apply_score_boost(base_score, question_type, context):
    """
    Apply minimum score guarantees based on positive context.
    
    Args:
        base_score: Calculated score before boosting
        question_type: Type of question (1-5)
        context: Dict with flags like mentions_university, mentions_helping, etc.
    
    Returns:
        float: Boosted score
    """
    boosted_score = base_score
    
    if question_type == 1:  # Academic Introduction
        if context.get('mentions_university') or context.get('mentions_field'):
            boosted_score = max(base_score, 75)
        elif context.get('has_educational_keywords'):
            boosted_score = max(base_score, 70)
    
    elif question_type == 2:  # Motivation
        if context.get('mentions_helping') and context.get('mentions_personal_benefit'):
            boosted_score = max(base_score, 85)
        elif context.get('mentions_helping') or context.get('mentions_program_interest'):
            boosted_score = max(base_score, 80)
    
    elif question_type == 3:  # Teaching Story
        if context.get('has_specific_example'):
            boosted_score = max(base_score, 80)
        elif context.get('mentions_teaching') or context.get('mentions_helping'):
            boosted_score = max(base_score, 75)
    
    elif question_type == 4:  # Challenging Situations
        if context.get('acknowledges_challenges') and context.get('mentions_approach'):
            boosted_score = max(base_score, 85)
        elif context.get('mentions_approach') or context.get('is_solution_oriented'):
            boosted_score = max(base_score, 80)
    
    elif question_type == 5:  # Mentor Goals
        if context.get('mentions_goals') and (context.get('has_plan') or context.get('is_student_focused')):
            boosted_score = max(base_score, 85)
        elif context.get('mentions_goals') or context.get('shows_intention'):
            boosted_score = max(base_score, 75)
    
    return boosted_score
```

### Agent 5: Behavioral Score with Minimum Guarantees
```python
def calculate_behavioral_score(transcripts, speaking_metrics, identity_confidence):
    """
    Calculate behavioral score with generous MVP baseline.
    
    Returns:
        dict: Behavioral analysis with score
    """
    # Start with generous base score
    base_score = 80
    
    # Call LLM for behavioral analysis
    try:
        llm_response = call_behavioral_llm(transcripts, speaking_metrics, identity_confidence)
        behavioral_score = llm_response.get('behavioral_score', 88)
    except Exception as e:
        # On error, return generous default
        behavioral_score = 88
    
    # Apply minimum score guarantees based on context
    if shows_engagement(transcripts):
        behavioral_score = max(behavioral_score, 85)
    
    if shows_enthusiasm(transcripts):
        behavioral_score = max(behavioral_score, 90)
    
    if mentions_helping_or_teaching(transcripts):
        behavioral_score = max(behavioral_score, 92)
    
    # Ensure score doesn't go below base unless serious issues
    if not has_serious_issues(llm_response):
        behavioral_score = max(behavioral_score, base_score)
    
    return {
        'behavioral_score': behavioral_score,
        'confidence_level': llm_response.get('confidence_level', 'High'),
        'emotional_consistency': llm_response.get('emotional_consistency', 88),
        'stress_level': llm_response.get('stress_level', 15),
        'engagement': llm_response.get('engagement', 90),
        'speaking_clarity': llm_response.get('speaking_clarity', 88),
        # ... other fields
    }
```

### Agent 6: Decision Thresholds
```python
def make_final_decision(content_score, behavioral_score):
    """
    Make final PASS/REVIEW/FAIL decision.
    
    Args:
        content_score: Score from Agent 4 (0-100)
        behavioral_score: Score from Agent 5 (0-100)
    
    Returns:
        dict: Decision with reasoning
    """
    # Calculate weighted final score
    final_score = (content_score * 0.70) + (behavioral_score * 0.30)
    
    # Apply decision thresholds
    if final_score >= 65:
        decision = "PASS"
        confidence = "high" if final_score >= 75 else "medium"
    elif final_score >= 55:
        decision = "REVIEW"
        confidence = "medium"
    else:
        decision = "FAIL"
        confidence = "high"
    
    # Generate reasoning (call LLM)
    reasoning = generate_positive_reasoning(
        decision, final_score, content_score, behavioral_score
    )
    
    return {
        'decision': decision,
        'final_score': round(final_score, 1),
        'confidence_level': confidence,
        'reasoning': reasoning,
        # ... other fields
    }
```

---

## FAQ for Developer

### Q: Why increase scores so much? Won't this let bad candidates through?
**A**: No. The new system is **proportionally generous**:
- Good candidates: 60-65 → 75-85 (+10-20 points)
- Poor candidates: 40-50 → 45-55 (+5 points only)
- FAIL threshold moved from 50 to 55, so truly poor performers still fail

### Q: What if scores get too high (90+)?
**A**: That's fine! Scores of 90+ indicate **excellent candidates** who should definitely pass. The system maintains discrimination:
- 85-100: Excellent (top tier)
- 75-84: Strong (good fit)
- 65-74: Good (acceptable)
- 55-64: Borderline (needs review)
- <55: Poor (reject)

### Q: How do I test this works correctly?
**A**: Use the test cases in Phase 4. You should see:
- Average engaged candidates scoring 75-85 (not 60-65)
- Poor/off-topic candidates still scoring below 55 (still fail)
- The gap between good and poor candidates should be **wider**, not narrower

### Q: What if the LLM still returns low scores?
**A**: The new prompts explicitly instruct generous scoring with **mandatory rules** and **default baselines**. Additionally, the code applies **minimum score guarantees** that override LLM decisions when positive context is detected.

### Q: Should I adjust both prompts AND thresholds?
**A**: Yes, both are necessary:
1. **Prompts**: Generate higher baseline scores (more important)
2. **Thresholds**: Adjusted to match new score distribution
3. **Bonus/Boosting**: Rewards candidates who demonstrate effort

### Q: What about maintaining quality control?
**A**: Quality is maintained through:
1. **Higher standards for PASS**: 65 (not 60)
2. **Behavioral still matters**: 30% weight, minimum 80 baseline
3. **Poor performers still fail**: <55 threshold catches them
4. **Red flags still work**: Serious issues still trigger FAIL

---

## Rollback Plan

If the new system doesn't work as expected, here's how to rollback:

### Quick Rollback (Emergency)
1. Revert decision thresholds: PASS(60), REVIEW(50-59), FAIL(<50)
2. Keep prompts updated (they're more lenient but won't hurt)
3. Remove bonus points system
4. Remove score boosting logic

### Partial Rollback (Adjustment)
1. Keep thresholds: PASS(65), REVIEW(55-64), FAIL(<55)
2. Reduce bonus points: +1 per question (max +5) instead of +2 (max +10)
3. Reduce score boost minimums by 5 points each
4. Adjust behavioral base score to 77 (instead of 80)

---

## Success Metrics

Track these metrics after deployment:

1. **Average Score Distribution**:
   - Target: 75-85 for engaged candidates
   - Monitor: Percentage scoring below 65 (should be <20%)

2. **Pass Rate**:
   - Target: 60-70% pass rate (up from current ~50%)
   - Monitor: Failure rate should stay at 15-25%

3. **Review Rate**:
   - Target: 10-15% requiring manual review
   - Monitor: Should not exceed 20%

4. **Quality of Passed Candidates**:
   - Hire team feedback: Satisfaction with candidate quality
   - Next round performance: Do they perform well in subsequent interviews?

5. **False Positives** (bad candidates passing):
   - Target: <5%
   - If >10%, tighten thresholds by 2-3 points

6. **False Negatives** (good candidates failing):
   - Target: <3%
   - If >5%, loosen thresholds by 2-3 points

---

## Final Notes

This updated system is designed to be **welcoming to good candidates** while still filtering out poor performers. The key insight is that the previous system was **too conservative** - treating all candidates with suspicion rather than giving them credit for effort and positive intent.

The new philosophy: **"Assume positive intent, reward effort, only fail for serious concerns."**

This aligns with MVP goals of building a community and attracting engaged ambassadors, while maintaining the quality bar through weighted scoring and proper thresholds.