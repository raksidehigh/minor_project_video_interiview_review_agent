# Changelog

All notable changes to the Video Interview Assessment System.

---

## [2.2.0] - 2025-11-27

### 🎯 Major Update: Full Stack Developer Technical Interview

Complete overhaul from Ambassador Program to Full Stack Developer technical assessment.

### Changed

#### Prompts & Evaluation Logic
- **`app/agents/nodes/content.py`** - Complete rewrite
  - Question 1: Academic background → System Design (YouTube-like platform)
  - Question 2: Motivation → Architecture Comparison (Monolithic vs Microservices)
  - Question 3: Empathy story → Authentication & Authorization
  - Question 4: Handling challenges → Performance Optimization
  - Question 5: Future goals → Real-time Notification System
  - Pass threshold: 70 → 60 (more appropriate for technical depth)

- **`app/agents/nodes/batched_evaluation.py`** - Updated prompt template
  - Changed from soft skills to technical competency evaluation
  - Updated JSON response structure for technical fields
  - Removed MVP "generous scoring" rules
  - Added technical depth assessment criteria

- **`app/agents/nodes/behavioral.py`** - Updated behavioral analysis
  - Changed focus from "welcoming community" to "technical communication"
  - Base score: 80 → 70 (more balanced for technical interviews)
  - Added `problem_solving_approach` field
  - Removed soft skill emphasis (empathy, enthusiasm)

#### Documentation
- **`README.md`** - Updated to v2.2.0
  - Updated interview questions section
  - Rewrote Agent 4 (Content Evaluation) description
  - Updated Agent 5 (Behavioral Analysis) description
  - Replaced "MVP Philosophy" with "Technical Depth Assessment"
  - Removed old Ambassador Program prompt examples
  - Added new technical evaluation criteria

- **`PROMPT_CHANGES_SUMMARY.md`** - Created
  - Detailed change documentation
  - Before/after comparison
  - Testing checklist

- **`DEPLOY_PROMPT_CHANGES.md`** - Created
  - Quick deployment guide
  - Verification steps
  - Rollback instructions

### Technical Details

#### Evaluation Criteria Changes

**Question 1 (System Design):**
```
Old: University name, major/field of study
New: Architecture components (upload, storage, CDN, database), scalability
```

**Question 2 (Architecture):**
```
Old: Mission alignment, helping keywords
New: Monolithic vs Microservices comparison, trade-offs
```

**Question 3 (Auth/AuthZ):**
```
Old: Empathy, helping experience, STAR method
New: AuthN vs AuthZ distinction, JWT/sessions, security
```

**Question 4 (Performance):**
```
Old: Handling difficult students, conflict resolution
New: Systematic optimization (measure → optimize), multi-layer approach
```

**Question 5 (Real-time):**
```
Old: Future goals, concrete plans
New: Technology choice (WebSockets/SSE), architecture, reliability
```

#### Scoring Changes

| Metric | Old (Ambassador) | New (Technical) |
|--------|------------------|-----------------|
| Pass Threshold | 70/100 | 60/100 |
| Behavioral Base | 80/100 | 70/100 |
| Focus | Soft skills | Technical depth |
| Philosophy | MVP generous | Balanced assessment |

### Migration Notes

⚠️ **Breaking Change:** Not backward compatible with Ambassador Program interviews.

**Impact:**
- Old interview recordings will be evaluated against new technical criteria
- Historical scores may differ if re-evaluated

**Recommendations:**
- Archive old Ambassador Program data before deploying
- Consider maintaining separate evaluation pipelines if both interview types are needed

### Deployment

```bash
./deploy_new.sh
```

**Deployment Time:** ~5-10 minutes  
**Downtime:** Zero (rolling update)

---

## [2.1.0] - 2025-11-XX

### Added
- Optimized 4-phase pipeline (30-45 seconds processing)
- Parallel agent execution
- Mandatory workspace cleanup
- Video streaming via signed URLs

### Changed
- Processing time: 4-5 minutes → 30-45 seconds (90% faster)
- Memory usage: Reduced by streaming instead of downloading

---

## [2.0.0] - 2025-11-XX

### Added
- Initial release
- 6-agent LangGraph workflow
- Identity verification with face recognition
- Video quality analysis
- Speech-to-Text with Google Chirp 3
- Content and behavioral evaluation
- Google Cloud Run deployment

---

## Version Numbering

- **Major (X.0.0):** Breaking changes, architecture overhaul
- **Minor (0.X.0):** New features, prompt updates, evaluation logic changes
- **Patch (0.0.X):** Bug fixes, documentation updates
