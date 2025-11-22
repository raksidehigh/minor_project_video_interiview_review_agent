# Logging Memory Implications

## Overview

This document explains the RAM/memory implications of different logging strategies in the video interview assessment system.

---

## Memory Impact Comparison

### 1. In-Memory Logging (Current Implementation)

**How it works:**
- All log messages are stored in Python's logging handlers
- Logs are buffered in memory before being written
- Console output goes directly to stdout/stderr

**Memory Usage:**
- **Low to Moderate:** ~5-50 MB per assessment session
- Logs are kept in memory buffers (typically 1-10 MB)
- Python's logging system uses circular buffers or size limits
- Memory is released after the request completes

**Pros:**
- ✅ Fast - no disk I/O during execution
- ✅ Real-time visibility in console/logs
- ✅ No file system overhead
- ✅ Works well with containerized deployments (logs go to stdout)

**Cons:**
- ❌ Memory usage accumulates if many concurrent requests
- ❌ Logs lost if application crashes before flush
- ❌ Can fill up memory in high-traffic scenarios

**Best for:**
- Production environments with log aggregation (Cloud Logging, ELK stack)
- Containerized deployments (Docker, Cloud Run)
- Real-time debugging

---

### 2. File-Based Logging

**How it works:**
- Logs are written directly to text files on disk
- Files can be rotated (size/time-based)
- Each assessment can write to a separate file or shared log file

**Memory Usage:**
- **Very Low:** ~1-5 MB per assessment session
- Logs written immediately to disk
- Memory only holds current log line being written

**Pros:**
- ✅ Minimal memory footprint
- ✅ Persistent logs survive application crashes
- ✅ Easy to archive and analyze later
- ✅ Can be indexed/searched

**Cons:**
- ❌ Slower due to disk I/O operations
- ❌ Disk space management required
- ❌ File system overhead (inodes, permissions)
- ❌ May slow down high-concurrency scenarios

**Best for:**
- Development environments
- Long-term audit trails
- Systems with limited RAM
- Compliance requirements

---

### 3. Hybrid Approach (Recommended)

**How it works:**
- Critical logs → File (persistent)
- Debug/Info logs → Memory → Rotated to file
- Error logs → Both file and memory

**Memory Usage:**
- **Low:** ~2-10 MB per assessment session
- Buffers only recent logs in memory
- Frequent flushes to disk for critical data

**Pros:**
- ✅ Balance between speed and persistence
- ✅ Critical data always saved
- ✅ Good performance with persistence
- ✅ Flexible configuration

**Cons:**
- ❌ More complex to implement
- ❌ Requires file rotation logic

---

## Memory Calculation Examples

### Current Implementation (In-Memory Logging)

**Per Assessment Session:**
```
- Identity verification logs:     ~2 MB
- Quality assessment logs:        ~1 MB
- Transcription logs:             ~3 MB
- Content evaluation logs:        ~5 MB
- Behavioral analysis logs:      ~2 MB
- Aggregate/decision logs:       ~1 MB
-----------------------------------------
Total per session:               ~14 MB
```

**Concurrent Sessions:**
```
- 1 session:      ~14 MB
- 10 sessions:    ~140 MB
- 100 sessions:   ~1.4 GB (can be problematic!)
```

**Memory Release:**
- Python garbage collector frees memory after request completes
- Takes ~10-30 seconds per session
- Concurrent requests accumulate memory

---

### File-Based Logging

**Per Assessment Session:**
```
- Memory for current log line:   ~1 KB
- Buffer (if used):              ~10-50 KB
- File I/O overhead:             Minimal
-----------------------------------------
Total per session:               ~1-5 MB
```

**Disk Space:**
```
- Per assessment log file:       ~500 KB - 2 MB
- 100 assessments:               ~50-200 MB
- 1000 assessments:              ~500 MB - 2 GB
```

**Memory Usage (Concurrent):**
```
- 1 session:      ~5 MB
- 10 sessions:    ~50 MB
- 100 sessions:   ~500 MB (much better!)
```

---

## Recommendations

### Production Environment (Cloud Run/GKE)

**Use:** In-memory logging → stdout → Cloud Logging

```python
# Current setup - optimized for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Logs go to stdout, Cloud Run captures them automatically
```

**Why:**
- Cloud Run/GKE automatically aggregates stdout logs
- No disk space management needed
- Real-time log streaming
- Memory is acceptable (14 MB per request)

**Memory Impact:** ✅ Acceptable (14 MB × concurrent requests)

---

### Development/Local Environment

**Use:** File-based logging with rotation

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'assessment.log',
    maxBytes=10*1024*1024,  # 10 MB per file
    backupCount=5  # Keep 5 rotated files
)
logger.addHandler(handler)
```

**Why:**
- Persistent logs for debugging
- Lower memory usage
- Easy to analyze

**Memory Impact:** ✅ Very Low (1-5 MB per request)

---

### High-Traffic Scenarios

**If memory becomes an issue:**

1. **Reduce log verbosity:**
   - Change `logging.INFO` → `logging.WARNING`
   - Remove debug-level logs
   - Only log errors and critical events

2. **Use log rotation:**
   ```python
   from logging.handlers import RotatingFileHandler
   
   handler = RotatingFileHandler(
       'logs/assessment.log',
       maxBytes=10*1024*1024,  # 10 MB
       backupCount=3
   )
   ```

3. **Implement async logging:**
   ```python
   from logging.handlers import QueueHandler, QueueListener
   import queue
   
   log_queue = queue.Queue(-1)
   queue_handler = QueueHandler(log_queue)
   file_handler = RotatingFileHandler('assessment.log')
   listener = QueueListener(log_queue, file_handler)
   ```

4. **Limit log message size:**
   ```python
   # Truncate long OCR text in logs
   logger.info(f"OCR Text: {extracted_text[:500]}...")  # Limit to 500 chars
   ```

---

## Specific Memory Concerns

### 1. OCR Text Logging

**Current:**
```python
logger.info(f"Full OCR Text: {extracted_text}")  # Could be 1000+ chars
```

**Memory per log:** ~1-5 KB
**Impact:** Low (text is small)

**Recommendation:** ✅ Keep as-is (text logs are small)

---

### 2. Detailed Evaluation Logs

**Current:**
```python
logger.info(f"Question {i} evaluation complete:")
logger.info(f"   - Score: {score:.1f}/100")
logger.info(f"   - Answer Relevance: {answer_rel}/60")
# ... many more lines
```

**Memory per assessment:** ~5 MB (for all detailed logs)

**Impact:** Moderate (but acceptable)

**Recommendation:** ✅ Keep as-is (useful for debugging)

---

### 3. State Storage (Not Logging, but Related)

**Current:**
```python
state['identity_verification'] = {...}  # Stored in memory
state['content_evaluation'] = {...}     # Stored in memory
```

**Memory per state:** ~2-5 MB

**This is NOT logging, but part of application state.**

**Recommendation:** ✅ This is necessary for processing

---

## Summary

### Current Implementation (In-Memory Logging)

| Metric | Value | Status |
|--------|-------|--------|
| Memory per session | ~14 MB | ✅ Acceptable |
| Memory for 10 concurrent | ~140 MB | ✅ Good |
| Memory for 100 concurrent | ~1.4 GB | ⚠️ Monitor |
| Disk I/O | None | ✅ Fast |
| Persistence | Lost on crash | ⚠️ Consider |

### File-Based Logging Alternative

| Metric | Value | Status |
|--------|-------|--------|
| Memory per session | ~1-5 MB | ✅ Excellent |
| Memory for 10 concurrent | ~50 MB | ✅ Excellent |
| Memory for 100 concurrent | ~500 MB | ✅ Excellent |
| Disk I/O | Yes | ⚠️ Slower |
| Persistence | Saved | ✅ Reliable |

---

## Final Recommendation

**For Production (Cloud Run/GKE):**
✅ **Keep current in-memory logging**
- Memory usage is acceptable (14 MB per request)
- Cloud Run handles log aggregation automatically
- Real-time visibility is valuable
- No disk management needed

**For Development:**
✅ **Consider file-based logging**
- Lower memory usage helpful on local machines
- Persistent logs useful for debugging
- Easy to implement with RotatingFileHandler

**If Memory Issues Occur:**
1. Reduce log verbosity (INFO → WARNING)
2. Implement log rotation
3. Truncate long log messages
4. Consider async logging for high concurrency

---

## Code Example: File-Based Logging Setup

```python
import logging
from logging.handlers import RotatingFileHandler
import os

# Create logs directory
os.makedirs('logs', exist_ok=True)

# Configure file-based logging
file_handler = RotatingFileHandler(
    'logs/assessment.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,          # Keep 5 backup files
    encoding='utf-8'
)

file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
)

# Also keep console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only warnings and above to console

# Add both handlers
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
```

This setup:
- Writes detailed logs to file (low memory)
- Shows only warnings/errors to console
- Automatically rotates files when they reach 10 MB
- Keeps 5 backup files (50 MB total disk space)
