<!-- ee32f7b5-039b-4772-9df6-8cd374fe28ed 7cd68733-f58e-4d0c-916e-54be18dbcc8e -->
# Evaluation Metrics Update Plan

## Overview

Update the evaluation system based on CTO requirements:

- **New weighting**: Content 70%, Behavioral 30% (Identity and Quality become gatekeepers only)
- **Improved name matching** with normalization and pattern matching
- **Video_0 handling** for identity + quality check separately
- **Pass threshold**: 70 (down from 75)
- **Remove identity verification requirement** for pass decision

## Key Changes

### 1. Agent 1 - Identity Verification (0% weight, gatekeeper only)

**File**: `app/agents/nodes/identity.py` or `identity_parallel.py`

Changes needed:

- Improve name matching algorithm with normalization (remove spaces, lowercase, handle special characters)
- Add pattern matching for common name variations
- On identity failure: flag for human-in-loop review but continue assessment
- Return identity result but make it clear it doesn't affect final score
- Only process video_0.webm for face matching

### 2. Agent 2 - Video Quality Assessment (0% weight, quality check only)

**File**: `app/agents/nodes/quality.py` or `quality_parallel.py`

Changes needed:

- Only assess video_0.webm (not videos 1-5)
- Remove quality from weighted scoring
- Make it a quality check gatekeeper only
- Return quality metrics for logging but no score contribution

### 3. Agent 3 - Transcription (0% weight)

**File**: `app/agents/nodes/transcribe.py` or `transcribe_parallel.py`

Changes needed:

- Remove transcription confidence from weighted scoring
- Move filler word counting and speaking rate analysis to Agent 5
- Just provide transcripts, confidence, and metrics to other agents

### 4. Agent 4 - Content Evaluation (70% weight)

**File**: `app/agents/nodes/content.py`

Changes needed for internal weightage per question:

- **60%**: Answer justifies the question (LLM evaluation of content relevance)
- **30%**: Clarity check (filler words, speaking patterns)
- **10%**: Content check (keywords, expressions, student focus)

Update each question evaluation function to use this new split.

### 5. Agent 5 - Behavioral Analysis (30% weight)

**File**: `app/agents/nodes/behavioral.py`

Changes needed:

- Incorporate transcription quality factors:
  - Confidence levels from transcription
  - Filler word analysis
  - Speaking rate assessment
- Keep existing behavioral metrics:
  - Emotional consistency
  - Stress indicators
  - Engagement level
  - Authenticity

Weighted scoring within the 30%:

- Transcription quality: 33% (of the 30%)
- Emotional consistency: 17%
- Confidence level: 17%
- Stress indicators: 17%
- Engagement: 16%

### 6. Agent 6 - Decision Aggregation (Final Decision)

**File**: `app/agents/nodes/aggregate.py`

Changes needed in `calculate_weighted_score()`:

```python
# OLD (lines 38-44):
final_score = (
    identity_score * 0.25 +
    quality_score * 0.10 +
    content_score * 0.40 +
    behavioral_score * 0.15 +
    transcription_score * 0.10
)

# NEW:
final_score = (
    content_score * 0.70 +
    behavioral_score * 0.30
)
```

Update decision thresholds (lines 84-95):

- Remove `identity_verified` requirement for PASS
- Change threshold from 75 to 70
- Keep identity failure as separate red flag for human review

### 7. State Management

**File**: `app/agents/state.py`

Update documentation to reflect:

- Identity and quality are gatekeeper checks only
- Final score is only content (70%) + behavioral (30%)
- video_0 is processed separately for identity/quality

### 8. Video Processing Logic

**Files**:

- `app/agents/graph.py` or `graph_optimized.py`
- `app/main.py`

Changes needed:

- Separate video_0.webm processing for identity + quality
- Process video_1 through video_5 for content evaluation
- Update file discovery logic to handle this split

## Implementation Checklist

### Phase 1: Core Scoring Changes

- [ ] Update `aggregate.py` weighted scoring formula (70/30 split)
- [ ] Update pass threshold from 75 to 70
- [ ] Remove identity_verified requirement for PASS decision
- [ ] Update component_scores structure to reflect new weights

### Phase 2: Identity Improvements

- [ ] Implement name normalization (remove spaces, lowercase)
- [ ] Add pattern matching for name variations
- [ ] Create human-in-loop webhook/endpoint trigger on identity failure
- [ ] Update identity agent to only process video_0

### Phase 3: Quality Assessment

- [ ] Update quality agent to only assess video_0
- [ ] Remove quality from weighted scoring
- [ ] Keep quality metrics for logging only

### Phase 4: Content Evaluation Restructure

- [ ] Update Question 1 evaluation with 60/30/10 split
- [ ] Update Question 2 evaluation with 60/30/10 split
- [ ] Update Question 3 evaluation with 60/30/10 split
- [ ] Update Question 4 evaluation with 60/30/10 split
- [ ] Update Question 5 evaluation with 60/30/10 split

### Phase 5: Behavioral Analysis Enhancement

- [ ] Move transcription quality factors to behavioral analysis
- [ ] Incorporate filler word analysis
- [ ] Add speaking rate evaluation
- [ ] Implement new internal weightage structure

### Phase 6: Video Processing

- [ ] Update video discovery to separate video_0 from video_1-5
- [ ] Ensure identity/quality only use video_0
- [ ] Ensure content evaluation uses video_1-5

### Phase 7: Testing & Validation

- [ ] Test with sample videos
- [ ] Verify new scoring produces expected results
- [ ] Validate name matching improvements
- [ ] Check human-in-loop webhook functionality

## Files to Modify

1. **`app/agents/nodes/aggregate.py`** - Core weighted scoring and decision logic
2. **`app/agents/nodes/identity.py` or `identity_parallel.py`** - Name matching improvements, video_0 only
3. **`app/agents/nodes/quality.py` or `quality_parallel.py`** - video_0 only assessment
4. **`app/agents/nodes/content.py`** - Internal 60/30/10 weightage per question
5. **`app/agents/nodes/behavioral.py`** - Add transcription quality factors
6. **`app/agents/nodes/transcribe.py`** - Continue providing metrics but no scoring
7. **`app/agents/state.py`** - Documentation updates
8. **`app/main.py`** - Video processing logic for video_0 separation
9. **`EVALUATION_CRITERIA_COMPLETE.md`** - Update documentation to match new system

## Red Flags System

Keep existing red flags but ensure they don't auto-fail:

- Negative language → Flag for review
- Multiple people detected → Flag for review
- Different speaker across videos → Flag for review
- Identity mismatch → Human-in-loop webhook + continue assessment

## Expected Outcomes

- Lower pass rate threshold (70 vs 75) should increase pass rates
- Better name matching reduces false identity failures
- Focus on content (70%) and behavior (30%) aligns with CTO requirements
- Human-in-loop for identity issues prevents auto-failures
- Cleaner separation of concerns (identity/quality as gatekeepers, content/behavior as evaluators)

### To-dos

- [ ] Update aggregate.py: Change weighted formula to 70% content + 30% behavioral, remove identity/quality/transcription weights
- [ ] Update aggregate.py: Change pass threshold from 75 to 70, remove identity_verified requirement
- [ ] Update identity agent: Add name normalization and pattern matching for better accuracy
- [ ] Update identity and quality agents to only process video_0.webm, not video_1-5
- [ ] Update content.py: Restructure each question evaluation to use 60% answer relevance, 30% clarity, 10% keywords
- [ ] Update behavioral.py: Add transcription quality factors (confidence, filler words, speaking rate) to behavioral analysis
- [ ] Update main.py and graph: Separate video_0 processing from video_1-5 processing
- [ ] Add webhook/endpoint trigger for identity failure cases (human-in-loop review)