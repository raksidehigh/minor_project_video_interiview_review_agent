"""
Video Quality Assessment Node - OPTIMIZED
Analyzes technical quality of videos using lightweight libraries
Optimizations:
- MediaPipe for face detection (lighter than Haar Cascade)
- Reduced frame sampling (3 frames instead of 5)
- Downscaled frame processing (640px max width)
- Proper memory management with gc.collect()
"""
import cv2
import gc
import numpy as np
from typing import Dict, Any
import mediapipe as mp

from ..state import InterviewState
from ...utils.gcs_streaming import get_signed_url

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


def analyze_video_quality(video_url: str) -> Dict[str, Any]:
    """
    Analyze technical quality of a single video (streams from GCS)
    
    Optimizations:
    - Uses MediaPipe instead of Haar Cascade (lighter, faster)
    - Samples only 3 frames instead of 5 (25%, 50%, 75%)
    - Processes frames at 640px max width for memory efficiency
    - Explicit garbage collection after frame processing
    
    Args:
        video_url: GCS URL (gs://...) or signed HTTPS URL
    
    Returns:
        dict with quality metrics
    """
    cap = None
    try:
        # Convert GCS URL to signed URL for streaming
        if video_url.startswith('gs://'):
            video_url = get_signed_url(video_url)
            print(f"         🔗 Streaming from signed URL (no download)")
        
        # Stream video from signed URL
        cap = cv2.VideoCapture(video_url)
        
        if not cap.isOpened():
            return {"error": f"Could not open video: {video_url}"}
        
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
                
                # Calculate brightness (simple mean)
                brightness = float(gray.mean())
                brightness_scores.append(brightness)
                
                # Calculate sharpness using Laplacian variance
                # Using CV_64F for better precision, but can use CV_8U for speed
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
                print(f"         ⚠️  Frame {frame_num} processing failed: {str(e)}")
                continue
        
        # Calculate average scores
        avg_brightness = sum(brightness_scores) / len(brightness_scores) if brightness_scores else 0
        avg_sharpness = sum(sharpness_scores) / len(sharpness_scores) if sharpness_scores else 0
        face_visibility_ratio = face_detected_count / len(sample_positions) if sample_positions else 0
        
        # Check for issues - ONLY check for these two:
        # 1. Blurry/out of focus
        # 2. Poor face visibility
        if avg_sharpness < 100:
            issues.append("Blurry/out of focus")
        if face_visibility_ratio < 0.6:
            issues.append("Poor face visibility")
        
        # Calculate quality score (0-100) with face visibility
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
        
        return {
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
            "issues": issues
        }
        
    except Exception as e:
        return {"error": f"Could not analyze video: {str(e)}"}
    finally:
        # CRITICAL: Always release VideoCapture to free resources
        if cap is not None:
            try:
                cap.release()
            except:
                pass
        # Force garbage collection
        gc.collect()


def check_quality(state: InterviewState) -> InterviewState:
    """
    Node: Assess video quality
    
    Analyzes technical quality of all videos:
    - Resolution, FPS, duration
    - Brightness, sharpness
    - Identifies issues
    
    Updates state['video_quality'] with results.
    """
    print(f"\n📹 Agent 2: Video Quality Assessment (OPTIMIZED)")
    
    video_analyses = []
    
    try:
        for i, video_url in enumerate(state['video_urls'], 1):
            print(f"   🎬 Analyzing video {i}/{len(state['video_urls'])}...")
            
            try:
                # Analyze quality (streams video without downloading)
                analysis = analyze_video_quality(video_url)
                analysis['video_url'] = video_url
                analysis['video_index'] = i
                
                video_analyses.append(analysis)
                
                score = analysis.get('quality_score', 0)
                issues = analysis.get('issues', [])
                print(f"      📊 Quality Score: {score:.1f}/100")
                if issues:
                    print(f"      ⚠️  Issues: {', '.join(issues)}")
                else:
                    print(f"      ✅ No issues detected")
                    
            except Exception as e:
                error_msg = f"Video {i} quality check failed: {str(e)}"
                print(f"      ❌ {error_msg}")
                video_analyses.append({
                    "video_url": video_url,
                    "video_index": i,
                    "error": str(e),
                    "quality_score": 0
                })
        
        # Calculate overall quality
        quality_scores = [v.get('quality_score', 0) for v in video_analyses]
        overall_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        quality_passed = bool(overall_score >= 60)  # Minimum 60/100 to pass
        
        # Update state
        state['video_quality'] = {
            "quality_passed": quality_passed,
            "overall_score": overall_score,
            "video_analyses": video_analyses
        }
        
        state['current_stage'] = 'quality_complete'
        
        print(f"   {'✅ PASSED' if quality_passed else '⚠️  REVIEW'}: Overall score {overall_score:.1f}/100")
        
    except Exception as e:
        error_msg = f"Quality assessment error: {str(e)}"
        print(f"   ❌ {error_msg}")
        
        state['video_quality'] = {
            "quality_passed": False,
            "overall_score": 0.0,
            "error": error_msg
        }
        state['errors'].append(error_msg)
    
    return state

