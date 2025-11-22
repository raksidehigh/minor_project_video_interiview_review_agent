"""
Video Quality Assessment Node - OPTIMIZED with Parallel Processing
Uses local files from workspace
Optimizations:
- MediaPipe for face detection (lighter than Haar Cascade)
- Reduced frame sampling (3 frames instead of 5)
- Downscaled frame processing (640px max width)
- Proper memory management with gc.collect()
"""
import logging
import cv2
import numpy as np
import gc
from pathlib import Path
from typing import Dict, Any
import mediapipe as mp

from ..state import InterviewState

logger = logging.getLogger(__name__)

# Initialize MediaPipe face detection at module level (loaded once, reused)
# MediaPipe is faster and lighter than Haar Cascade, already in requirements
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(
    model_selection=0,  # 0 = short-range (2 meters), faster than full-range
    min_detection_confidence=0.5
)

# Maximum width for frame processing (reduces memory usage significantly)
MAX_PROCESSING_WIDTH = 640


def detect_faces_mediapipe(frame: np.ndarray) -> tuple[int, bool]:
    """
    Detect faces using MediaPipe (lighter and faster than Haar Cascade)
    
    Args:
        frame: Video frame as numpy array (BGR format)
    
    Returns:
        tuple: (face_count, has_multiple_faces)
    """
    try:
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        results = face_detector.process(rgb_frame)
        
        face_count = len(results.detections) if results.detections else 0
        has_multiple = face_count > 1
        
        return face_count, has_multiple
    except Exception:
        return 0, False


def analyze_video_quality_local(video_path: Path, video_index: int) -> Dict[str, Any]:
    """
    Analyze quality of a single local video file with proper resource management
    Much faster than streaming!
    
    Optimizations:
    - Uses MediaPipe instead of Haar Cascade (lighter, faster)
    - Samples only 3 frames instead of 5 (25%, 50%, 75%)
    - Processes frames at 640px max width for memory efficiency
    - Explicit garbage collection after frame processing
    """
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return {"error": f"Could not open video: {video_path}", "success": False}
        
        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        # OPTIMIZATION: Sample only 3 frames instead of 5 (reduces processing by 40%)
        # Positions: 25%, 50%, 75% - still provides good coverage
        sample_positions = [0.25, 0.5, 0.75]
        brightness_scores = []
        sharpness_scores = []
        face_detected_count = 0
        multiple_faces_count = 0
        issues = []
        
        # Calculate scale factor for downscaling (if needed)
        scale_factor = 1.0
        if width > MAX_PROCESSING_WIDTH:
            scale_factor = MAX_PROCESSING_WIDTH / width
        
        for position in sample_positions:
            frame_num = int(frame_count * position)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            try:
                # OPTIMIZATION: Downscale frame for processing (reduces memory significantly)
                if scale_factor < 1.0:
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                # Convert to grayscale for brightness/sharpness calculations
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calculate brightness
                brightness = float(gray.mean())
                brightness_scores.append(brightness)
                
                # Calculate sharpness using Laplacian variance
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                sharpness_scores.append(float(sharpness))
                
                # OPTIMIZATION: Use MediaPipe for face detection (lighter than Haar Cascade)
                face_count, has_multiple = detect_faces_mediapipe(frame)
                if face_count > 0:
                    face_detected_count += 1
                if has_multiple:
                    multiple_faces_count += 1
                
                # Explicitly delete frame to free memory
                del frame, gray
                gc.collect()
                
            except Exception as e:
                logger.warning(f"Frame {frame_num} processing failed: {str(e)}")
                continue
        
        # Calculate metrics
        avg_brightness = sum(brightness_scores) / len(brightness_scores) if brightness_scores else 0
        avg_sharpness = sum(sharpness_scores) / len(sharpness_scores) if sharpness_scores else 0
        face_visibility_ratio = face_detected_count / len(sample_positions) if sample_positions else 0
        
        # Check issues - ONLY check for these two:
        # 1. Blurry/out of focus
        # 2. Poor face visibility
        if avg_sharpness < 100:
            issues.append("Blurry/out of focus")
        if face_visibility_ratio < 0.6:
            issues.append("Poor face visibility")
        
        # Calculate quality score
        resolution_score = min(100, (width * height) / (1920 * 1080) * 100)
        fps_score = min(100, fps / 30 * 100)
        brightness_score = 100 if 80 <= avg_brightness <= 180 else max(0, 100 - abs(avg_brightness - 130))
        sharpness_score = min(100, avg_sharpness / 500 * 100)
        face_score = face_visibility_ratio * 100
        
        quality_score = (
            resolution_score * 0.25 +
            fps_score * 0.15 +
            brightness_score * 0.20 +
            sharpness_score * 0.20 +
            face_score * 0.20
        )
        
        result = {
            "video_index": video_index,
            "resolution": f"{width}x{height}",
            "width": width,
            "height": height,
            "fps": float(fps),
            "duration": float(duration),
            "quality_score": float(quality_score),
            "brightness": float(avg_brightness),
            "sharpness": float(avg_sharpness),
            "face_visibility": float(face_visibility_ratio * 100),
            "multiple_people": bool(multiple_faces_count > 0),
            "issues": issues,
            "success": True
        }
        
        logger.info(f"Video {video_index}: Quality={quality_score:.1f}/100, Issues={len(issues)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Video {video_index} quality check failed: {str(e)}")
        return {
            "video_index": video_index,
            "error": str(e),
            "quality_score": 0,
            "success": False
        }
    finally:
        # CRITICAL: Always release VideoCapture
        if cap is not None:
            try:
                cap.release()
            except:
                pass
        # Force garbage collection to free memory
        gc.collect()


async def check_quality_parallel(resources: Dict, state: InterviewState) -> InterviewState:
    """
    Video Quality Assessment Node - OPTIMIZED
    As per CTO requirements: Only analyzes video_0 (identity check video)
    """
    logger.info("📹 Agent 2: Video Quality Assessment (video_0 only)")
    print(f"📹 [QUALITY] Starting quality assessment on video_0 only...")
    
    try:
        video_paths = resources['videos']
        
        # Get video_0 (first video in sorted list - the identity check video)
        video_0_path = video_paths[0] if video_paths else None
        
        if not video_0_path:
            raise ValueError("video_0 not found for quality assessment")
        
        print(f"📹 [QUALITY] Analyzing video_0: {video_0_path.name}...")
        video_0_analysis = analyze_video_quality_local(video_0_path, 0)
        print(f"📹 [QUALITY] Video_0 analysis complete")
        
        # Get score from video_0 only
        overall_score = video_0_analysis.get('quality_score', 0)
        quality_passed = bool(overall_score >= 60)
        
        state['video_quality'] = {
            "quality_passed": quality_passed,
            "overall_score": overall_score,
            "video_0_only": True,  # Flag indicating we only checked video_0
            "video_analyses": [video_0_analysis]
        }
        
        logger.info(f"✅ Quality (video_0 only): {'PASSED' if quality_passed else 'REVIEW'} (Score: {overall_score:.1f}/100)")
        print(f"✅ [QUALITY] Complete: {'PASSED' if quality_passed else 'REVIEW'} (Score: {overall_score:.1f}/100)")
        
    except Exception as e:
        logger.error(f"Quality assessment error: {str(e)}")
        print(f"❌ [QUALITY] ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        state['video_quality'] = {
            "quality_passed": False,
            "overall_score": 0.0,
            "error": str(e)
        }
        state['errors'].append(str(e))
    
    return state

