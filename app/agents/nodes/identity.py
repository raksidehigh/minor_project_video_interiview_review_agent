"""
Identity Verification Node
Verifies candidate identity using:
3. Extract faces from profile_pic
4. Compare profile pic face with ALL video frames
"""
import os
import tempfile
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import face_recognition
import cv2
import numpy as np
import mediapipe as mp
from google.cloud import storage
from google.cloud import storage
# from google.cloud import vision  # Removed: No longer needed
from difflib import SequenceMatcher

from ..state import InterviewState
from ...utils.gcs_streaming import get_signed_url, download_small_file

logger = logging.getLogger(__name__)

# Initialize MediaPipe face detection (lightweight, fast)
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(
    model_selection=0,  # 0 = short-range (2 meters), 1 = full-range (5 meters)
    min_detection_confidence=0.5
)


def download_from_gcs(gcs_url: str) -> str:
    """
    DEPRECATED: Use get_signed_url() for videos or download_small_file() for images
    
    This function is kept for backward compatibility but should not be used.
    Videos should be streamed via signed URLs to save memory.
    """
    return download_small_file(gcs_url)


def detect_face_confidence(frame: np.ndarray) -> float:
    """
    Use MediaPipe to detect face and return detection confidence
    Higher confidence = better face visibility
    
    Args:
        frame: Video frame as numpy array (BGR format)
    
    Returns:
        Maximum face detection confidence (0.0 to 1.0), or 0.0 if no face detected
    """
    try:
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        results = face_detector.process(rgb_frame)
        
        if results.detections:
            # Return highest confidence score
            max_confidence = max(detection.score[0] for detection in results.detections)
            return max_confidence
        else:
            return 0.0
    except Exception as e:
        logger.warning(f"Face detection error: {e}")
        return 0.0


def extract_face_region(image_path: str) -> Optional[str]:
    """
    Extract and crop face region from image using MediaPipe
    This ensures face_recognition can detect the face even if the original image has issues
    
    Args:
        image_path: Path to image file
    
    Returns:
        Path to cropped face image, or None if no face detected
    """
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            logger.warning(f"Could not read image: {image_path}")
            return None
        
        # Convert BGR to RGB for MediaPipe
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        
        # Detect faces
        results = face_detector.process(rgb_img)
        
        if not results.detections or len(results.detections) == 0:
            logger.warning(f"No face detected by MediaPipe in: {image_path}")
            return None
        
        # Get the first (best) face detection
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box
        
        # Convert relative coordinates to pixel coordinates
        x = int(bbox.xmin * w)
        y = int(bbox.ymin * h)
        width = int(bbox.width * w)
        height = int(bbox.height * h)
        
        # Add padding (30% more on each side for better context)
        padding = int(max(width, height) * 0.3)
        x = max(0, x - padding)
        y = max(0, y - padding)
        width = min(w - x, width + (2 * padding))
        height = min(h - y, height + (2 * padding))
        
        # Crop face region
        face_crop = img[y:y+height, x:x+width]
        
        if face_crop.size == 0:
            logger.warning(f"Face crop is empty for: {image_path}")
            return None
        
        # Save cropped face
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        cv2.imwrite(temp_file.name, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        confidence_score = detection.score[0]
        logger.info(f"✅ Extracted face region from {os.path.basename(image_path)} (confidence: {confidence_score:.2f})")
        print(f"         ✅ Face detected with confidence: {confidence_score:.2f} ({confidence_score*100:.0f}%)")
        print(f"         📏 Face bounding box: {width}x{height} pixels (with padding)")
        return temp_file.name
        
    except Exception as e:
        logger.error(f"Error extracting face from {image_path}: {e}")
        return None


def extract_best_frame_with_face(video_url: str) -> str:
    """
    Extract the BEST frame from video that contains a clear face
    Uses MediaPipe face detection to find frames with visible faces
    Tries multiple positions (25%, 50%, 75% of video) and picks the best one
    
    Args:
        video_url: GCS URL (gs://...) or signed HTTPS URL
    
    Returns:
        Path to extracted frame image with best face visibility
    """
    # Convert GCS URL to signed URL for streaming
    if video_url.startswith('gs://'):
        video_url = get_signed_url(video_url)
        print(f"         🔗 Streaming from signed URL (no download)")
    
    cap = cv2.VideoCapture(video_url)
    best_frame = None
    best_confidence = 0.0
    best_position = 0
    
    if not cap.isOpened():
        cap.release()
        raise ValueError("Could not open video")
    
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Strategy: Try multiple positions to find best face
        candidate_positions = []
        
        if total_frames > 0:
            # Try 25%, 50%, 75% of video
            candidate_positions = [
                int(total_frames * 0.25),
                int(total_frames * 0.50),
                int(total_frames * 0.75)
            ]
            print(f"         🔍 Checking {len(candidate_positions)} candidate frames (total: {total_frames})")
        
        # Evaluate each candidate frame
        for pos in candidate_positions:
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame = cap.read()
                
                if ret and frame is not None and frame.size > 0:
                    confidence = detect_face_confidence(frame)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_frame = frame.copy()
                        best_position = pos
                    
                    print(f"            Position {pos}/{total_frames}: face confidence {confidence:.2f}")
            except Exception as e:
                logger.warning(f"Error checking frame {pos}: {e}")
                continue
        
        # If we found a good frame, save it
        if best_frame is not None and best_confidence > 0.3:  # Minimum 30% confidence
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"         ✅ Extracted best frame at position {best_position} (confidence: {best_confidence:.2f})")
            cap.release()
            return temp_file.name
        elif best_frame is not None:
            # Even if low confidence, use it (better than nothing)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"         ⚠️  Using frame with low confidence {best_confidence:.2f}")
            cap.release()
            return temp_file.name
        
        # Fallback: Try sequential reading if position-based failed
        print(f"         🔄 Position-based extraction failed, trying sequential...")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        for i in range(min(30, total_frames if total_frames > 0 else 30)):
            ret, frame = cap.read()
            if not ret:
                break
            
            confidence = detect_face_confidence(frame)
            if confidence > best_confidence:
                best_confidence = confidence
                best_frame = frame.copy()
                best_position = i
            
            if confidence > 0.5:  # Good enough, stop searching
                break
        
        if best_frame is not None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"         ✅ Extracted frame at position {best_position} (confidence: {best_confidence:.2f})")
            cap.release()
            return temp_file.name
        
    finally:
        cap.release()
    
    # Final FFmpeg fallback
    print(f"         🔄 OpenCV failed, trying FFmpeg fallback...")
    return _extract_frame_ffmpeg_fallback(video_url)


def _extract_frame_ffmpeg_fallback(video_url: str) -> str:
    """FFmpeg fallback for frame extraction"""
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    temp_output.close()
    
    try:
        # Try middle of video
        extract_cmd = [
            'ffmpeg',
            '-ss', '2',  # 2 seconds in
            '-i', video_url,
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            temp_output.name
        ]
        
        subprocess.run(extract_cmd, check=True, capture_output=True, timeout=30)
        
        if os.path.exists(temp_output.name) and os.path.getsize(temp_output.name) > 0:
            print(f"         ✅ FFmpeg extracted frame successfully")
            return temp_output.name
    except Exception as e:
        if os.path.exists(temp_output.name):
            try:
                os.unlink(temp_output.name)
            except:
                pass
    
    raise ValueError(f"Could not extract any frame with face from video")


def extract_middle_frame(video_url: str) -> str:
    """
    Extract middle frame from video (streams from GCS via signed URL)
    Fail-safe approach: prioritizes getting ANY valid frame over perfect positioning
    
    Args:
        video_url: GCS URL (gs://...) or signed HTTPS URL
    
    Returns:
        Path to extracted frame image
    """
    # Convert GCS URL to signed URL for streaming
    if video_url.startswith('gs://'):
        video_url = get_signed_url(video_url)
        print(f"         🔗 Streaming from signed URL (no download)")
    
    # Try OpenCV first (most reliable for WebM)
    cap = cv2.VideoCapture(video_url)
    
    if cap.isOpened():
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Strategy 1: If we know frame count, extract middle frame
        if total_frames > 0:
            middle_frame = total_frames // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            
            if ret and frame is not None and frame.size > 0:
                cap.release()
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                cv2.imwrite(temp_file.name, frame)
                print(f"         ✅ Extracted middle frame ({middle_frame}/{total_frames})")
                return temp_file.name
        
        # Strategy 2: Frame count unknown or middle frame failed - try reading sequentially
        # Read a few frames in to skip potential black/loading frames
        print(f"         ⚠️  Frame count unavailable, reading sequentially...")
        for i in range(10):  # Skip first 10 frames
            ret, frame = cap.read()
            if not ret:
                break
        
        # Now read the actual frame we want
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None and frame.size > 0:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, frame)
            print(f"         ✅ Extracted frame from video stream")
            return temp_file.name
    
    cap.release()
    
    # Fallback: Use FFmpeg (works when OpenCV codec fails)
    print(f"         🔄 OpenCV failed, trying FFmpeg fallback...")
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    temp_output.close()
    
    try:
        # Try to get duration (but don't fail if it returns N/A)
        duration_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_url
        ]
        
        try:
            duration_output = subprocess.check_output(
                duration_cmd, 
                stderr=subprocess.STDOUT,
                timeout=10
            ).decode().strip()
            
            # Parse duration if valid
            if duration_output and duration_output != 'N/A' and duration_output.replace('.', '').replace('-', '').isdigit():
                duration = float(duration_output)
                middle_time = max(1.0, duration / 2)  # Ensure at least 1 second in
                print(f"         📊 Duration: {duration:.1f}s, extracting at {middle_time:.1f}s")
                seek_time = str(middle_time)
            else:
                # Duration unknown, extract from 2 seconds in
                print(f"         ⚠️  Duration unknown (got: '{duration_output}'), extracting at 2s")
                seek_time = "2"
        except:
            # ffprobe failed entirely, extract from 2 seconds in
            print(f"         ⚠️  ffprobe failed, extracting at 2s")
            seek_time = "2"
        
        # Extract frame using FFmpeg
        extract_cmd = [
            'ffmpeg',
            '-ss', seek_time,  # Seek to position
            '-i', video_url,
            '-vframes', '1',  # Extract 1 frame
            '-q:v', '2',      # High quality
            '-y',             # Overwrite
            temp_output.name
        ]
        
        result = subprocess.run(
            extract_cmd,
            check=True,
            capture_output=True,
            timeout=30
        )
        
        # Verify frame was extracted
        if os.path.exists(temp_output.name) and os.path.getsize(temp_output.name) > 0:
            print(f"         ✅ FFmpeg extracted frame successfully")
            return temp_output.name
        else:
            raise ValueError("FFmpeg produced empty output")
    
    except subprocess.TimeoutExpired:
        if os.path.exists(temp_output.name):
            try:
                os.unlink(temp_output.name)
            except:
                pass
        raise ValueError(f"Timeout while extracting frame (>30s)")
    
    except Exception as e:
        # Clean up temp file
        if os.path.exists(temp_output.name):
            try:
                os.unlink(temp_output.name)
            except:
                pass
        
        # Final attempt: extract first available frame (no seeking)
        print(f"         🔄 Last attempt: extracting first available frame...")
        temp_output2 = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_output2.close()
        
        try:
            extract_cmd = [
                'ffmpeg',
                '-i', video_url,
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                temp_output2.name
            ]
            
            subprocess.run(extract_cmd, check=True, capture_output=True, timeout=30)
            
            if os.path.exists(temp_output2.name) and os.path.getsize(temp_output2.name) > 0:
                print(f"         ✅ Extracted first frame as fallback")
                return temp_output2.name
        except:
            if os.path.exists(temp_output2.name):
                try:
                    os.unlink(temp_output2.name)
                except:
                    pass
        
        # All methods failed
        raise ValueError(f"Could not extract any frame from video. Last error: {str(e)}")


# Removed: extract_text_from_image, extract_name_from_text, calculate_name_similarity


def verify_face_match(ref_image: str, target_image: str) -> Dict[str, Any]:
    """
    Verify if faces match using face_recognition library (dlib-based)
    Uses MediaPipe to extract face regions first for better detection
    
    Args:
        ref_image: Reference image (profile_pic or gov_id face)
        target_image: Target image (video frame)
    
    Returns:
        Verification result with similarity score
    """
    ref_crop = None
    target_crop = None
    
    try:
        # Extract face regions using MediaPipe (ensures face_recognition can detect them)
        print(f"      🔍 [FACE EXTRACTION] Step 1: Extracting face region from reference image ({os.path.basename(ref_image)})...")
        ref_crop = extract_face_region(ref_image)
        if ref_crop is None:
            # Fallback: try original image directly
            print(f"      ⚠️  [FACE EXTRACTION] MediaPipe didn't find face in reference, using original image...")
            ref_crop = ref_image
            ref_face_extracted = False
        else:
            print(f"      ✅ [FACE EXTRACTION] SUCCESS: Face region extracted from reference image!")
            print(f"         📍 Extracted face saved to: {os.path.basename(ref_crop)}")
            ref_face_extracted = True
        
        print(f"      🔍 [FACE EXTRACTION] Step 2: Extracting face region from target image ({os.path.basename(target_image)})...")
        target_crop = extract_face_region(target_image)
        if target_crop is None:
            # Fallback: try original image directly
            print(f"      ⚠️  [FACE EXTRACTION] MediaPipe didn't find face in target, using original image...")
            target_crop = target_image
            target_face_extracted = False
        else:
            print(f"      ✅ [FACE EXTRACTION] SUCCESS: Face region extracted from target image!")
            print(f"         📍 Extracted face saved to: {os.path.basename(target_crop)}")
            target_face_extracted = True
        
        print(f"      📊 [FACE EXTRACTION] Summary:")
        print(f"         - Reference face extracted: {'✅ YES' if ref_face_extracted else '❌ NO (using original)'}")
        print(f"         - Target face extracted: {'✅ YES' if target_face_extracted else '❌ NO (using original)'}")
        
        # Load images (either cropped or original)
        ref_img = face_recognition.load_image_file(ref_crop)
        target_img = face_recognition.load_image_file(target_crop)
        
        # Get face encodings (128-dimensional vectors)
        print(f"      🔍 [FACE RECOGNITION] Step 3: Detecting faces using face_recognition library...")
        ref_encodings = face_recognition.face_encodings(ref_img)
        target_encodings = face_recognition.face_encodings(target_img)
        
        print(f"      📊 [FACE RECOGNITION] Detection Results:")
        print(f"         - Reference face detected: {'✅ YES' if len(ref_encodings) > 0 else '❌ NO'}")
        print(f"         - Target face detected: {'✅ YES' if len(target_encodings) > 0 else '❌ NO'}")
        
        # Check if faces were found
        if len(ref_encodings) == 0:
            print(f"      ❌ [FACE RECOGNITION] ERROR: No face found in reference image (even after MediaPipe extraction)")
            print(f"         This means face_recognition library couldn't detect face in the extracted/cropped image")
            return {
                "verified": False,
                "similarity": 0.0,
                "error": "No face found in reference image"
            }
        
        if len(target_encodings) == 0:
            print(f"      ❌ [FACE RECOGNITION] ERROR: No face found in target image (even after MediaPipe extraction)")
            print(f"         This means face_recognition library couldn't detect face in the extracted/cropped image")
            return {
                "verified": False,
                "similarity": 0.0,
                "error": "No face found in target image"
            }
        
        # Use first face found in each image
        ref_encoding = ref_encodings[0]
        target_encoding = target_encodings[0]
        
        print(f"      🔍 [FACE RECOGNITION] Step 4: Calculating face similarity...")
        # Calculate face distance (Euclidean distance, 0.0 = identical, 1.0+ = different)
        distance = face_recognition.face_distance([ref_encoding], target_encoding)[0]
        print(f"      📊 [FACE RECOGNITION] Distance: {distance:.4f} (lower = more similar, 0.0 = identical)")
        
        # Threshold adjustment for face verification (balanced)
        # Lower distance = more similar
        threshold = 0.62  # Balanced threshold between strict and lenient
        lenient_threshold = threshold * 1.04  # 0.6386 - 3% tolerance for minor variations
        
        # Check if faces match
        lenient_verified = bool(distance < lenient_threshold)
        
        # Convert distance to similarity percentage (0-100%)
        # Distance 0.0 = 100% similarity, Distance 1.0 = 0% similarity
        # Using exponential decay for better visualization
        if distance <= threshold:
            # Good match: map 0.0-threshold to 100%-60%
            similarity = 100.0 - (distance / threshold) * 40.0
        else:
            # Poor match: map threshold-1.0 to 60%-0%
            similarity = max(0.0, 60.0 - ((distance - threshold) / (1.0 - threshold)) * 60.0)
        
        display_similarity = float(min(100.0, max(0.0, similarity)))
        
        print(f"      📊 [FACE RECOGNITION] Final Results:")
        print(f"         - Face Distance: {distance:.4f}")
        print(f"         - Threshold: {threshold:.2f} (lenient: {lenient_threshold:.4f})")
        print(f"         - Similarity Score: {display_similarity:.1f}%")
        print(f"         - Match Status: {'✅ VERIFIED' if lenient_verified else '❌ NOT VERIFIED'}")
        print(f"      ✅ [FACE RECOGNITION] Comparison complete!")
        
        return {
            "verified": lenient_verified,
            "similarity": display_similarity,
            "distance": float(distance),
            "threshold": threshold
        }
    except Exception as e:
        print(f"      ❌ face_recognition Error: {str(e)}")
        return {
            "verified": False,
            "similarity": 0.0,
            "error": str(e)
        }
    finally:
        # Cleanup extracted face crops
        if ref_crop and ref_crop != ref_image and os.path.exists(ref_crop):
            try:
                os.unlink(ref_crop)
            except:
                pass
        if target_crop and target_crop != target_image and os.path.exists(target_crop):
            try:
                os.unlink(target_crop)
            except:
                pass


def verify_identity(state: InterviewState) -> InterviewState:
    """
    Node: Verify candidate identity using pure Face Verification:
    1. Download Profile Picture
    2. Compare Profile Picture face with faces in ALL uploaded videos
    3. Calculate pass rate (must match in >80% of videos)
    
    Updates state['identity_verification'] with results.
    """
    print(f"\n🔍 Agent 1: Identity Verification - User {state['user_id']}")
    
    errors = []
    video_results = []
    
    try:
        # ========== STEP 1: Download profile picture ==========
        print("   📥 Step 1: Downloading profile picture...")
        profile_pic_path = download_from_gcs(state['profile_pic_url'])
        
        # ========== STEP 2: Compare faces with ALL videos ==========
        print(f"   👤 Step 2: Comparing profile pic face with ALL {len(state['video_urls'])} videos...")
        
        for i, video_url in enumerate(state['video_urls']):
            print(f"      🎬 Checking Video {i}...")
            
            try:
                # Extract best frame with face detection (streams video without downloading)
                frame_path = extract_best_frame_with_face(video_url)
                
                # Compare with profile_pic
                profile_result = verify_face_match(profile_pic_path, frame_path)
                
                video_results.append({
                    "video_url": video_url,
                    "video_index": i,
                    "verified": profile_result.get('verified', False),
                    "similarity": profile_result.get('similarity', 0),
                    "profile_pic_similarity": profile_result.get('similarity', 0),
                    "best_match_source": "profile_pic"
                })
                
                print(f"         Similarity: {profile_result.get('similarity', 0):.1f}%")
                print(f"         {'✅ MATCH' if profile_result.get('verified', False) else '❌ NO MATCH'}")
                
                # Cleanup extracted frame
                if os.path.exists(frame_path):
                    os.unlink(frame_path)
                
            except Exception as e:
                error_msg = f"Video {i} failed: {str(e)}"
                errors.append(error_msg)
                print(f"         ❌ {error_msg}")
                video_results.append({
                    "video_url": video_url,
                    "video_index": i,
                    "verified": False,
                    "similarity": 0,
                    "error": str(e)
                })
        
        # AGGRESSIVE CLEANUP: Delete profile pic temp file
        try:
            if profile_pic_path and os.path.exists(profile_pic_path) and profile_pic_path != state['profile_pic_url']:
                os.unlink(profile_pic_path)
                print(f"      🧹 Deleted profile_pic temp file")
        except Exception as e:
            print(f"      ⚠️  Failed to delete profile_pic: {e}")
        
        # ========== STEP 3: Calculate overall verification ==========
        verified_count = sum(1 for r in video_results if r.get('verified', False))
        total_count = len(video_results)
        face_verification_rate = (verified_count / total_count * 100) if total_count > 0 else 0
        
        # Calculate average face similarity
        confidences = [r.get('similarity', 0) for r in video_results if 'similarity' in r]
        avg_face_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Overall verification: Must pass in >80% of videos OR have high average confidence (>75%)
        # This allows for 1 bad video (lighting/angle) if others are strong
        face_verified = bool(face_verification_rate >= 80 or avg_face_confidence >= 75)
        
        # Update state
        state['identity_verification'] = {
            "verified": face_verified,
            "confidence": avg_face_confidence,
            "name_match": True, # Deprecated but kept for schema compatibility
            "face_verified": face_verified,
            "face_verification_rate": face_verification_rate,
            "videos_passed": verified_count,
            "videos_total": total_count,
            "avg_face_confidence": avg_face_confidence,
            "video_results": video_results,
            "red_flags": errors
        }
        
        # Set control flow - ALWAYS continue to gather all evidence
        state['current_stage'] = 'identity_complete'
        
        # Log failure but don't block workflow
        if not face_verified:
            if not state.get('errors'):
                state['errors'] = []
            
            state['errors'].append(
                f"Identity verification failed: Face matched in only {verified_count}/{total_count} videos ({face_verification_rate:.0f}%)"
            )
        
        print(f"\n   📊 VERIFICATION SUMMARY:")
        print(f"      Videos Passed: {verified_count}/{total_count} ({face_verification_rate:.0f}%)")
        print(f"      Avg Confidence: {avg_face_confidence:.1f}%")
        print(f"      Overall: {'✅ VERIFIED' if face_verified else '❌ FAILED'}")
        
    except Exception as e:
        error_msg = f"Identity verification system error: {str(e)}"
        print(f"   ❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        state['identity_verification'] = {
            "verified": False,
            "confidence": 0.0,
            "name_match": False,
            "face_verified": False,
            "error": error_msg
        }
        if not state.get('errors'):
            state['errors'] = []
        state['errors'].append(error_msg)
    
    return state

