"""
Identity Verification Node
Verifies candidate identity using:
1. OCR extraction from government ID (Google Cloud Vision API)
2. Name matching between gov_id and username
3. face_recognition library (dlib-based) for facial matching
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
from google.cloud import vision
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


def extract_text_from_image(image_path: str) -> str:
    """
    Extract text from government ID using Google Cloud Vision API OCR
    
    Args:
        image_path: Local path to the image file
    
    Returns:
        Extracted text from the image
    """
    try:
        client = vision.ImageAnnotatorClient()
        
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Perform text detection
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if texts:
            # First annotation contains all text
            full_text = texts[0].description
            return full_text
        
        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")
        
        return ""
    
    except Exception as e:
        print(f"      ⚠️ OCR Error: {str(e)}")
        return ""


def extract_name_from_text(text: str) -> str:
    """
    Extract name from OCR text (heuristic-based)
    
    Common patterns in government IDs:
    - "Name: John Doe"
    - "NAME\nJOHN DOE"
    - First few lines usually contain the name
    
    Returns the most likely name candidate
    """
    if not text:
        return ""
    
    # Blacklist common government ID headers/text
    BLACKLIST_PHRASES = {
        'income tax', 'department', 'government', 'india', 'permanent account',
        'account number', 'pan card', 'aadhaar', 'aadhar', 'voter', 'election',
        'driving licence', 'passport', 'republic', 'भारत', 'सत्यमेव जयते',
        'satyamev jayate', 'आयकर', 'विभाग', 'issued by', 'date of birth',
        'dob', 'address', 'father', 'mother', 'registration'
    }
    
    # Split into lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    def is_blacklisted(line: str) -> bool:
        """Check if line contains blacklisted phrases"""
        line_lower = line.lower()
        return any(phrase in line_lower for phrase in BLACKLIST_PHRASES)
    
    # Pattern 1: Look for "Name:" or "NAME:" pattern
    for line in lines:
        if re.search(r'name\s*:?\s*', line, re.IGNORECASE):
            # Extract text after "name:"
            name_match = re.sub(r'^.*?name\s*:?\s*', '', line, flags=re.IGNORECASE)
            if name_match and len(name_match) > 2 and not is_blacklisted(name_match):
                return name_match.strip()
    
    # Pattern 2: Look for lines with 2-4 words (likely names) - skip blacklisted
    for line in lines[:10]:  # Check first 10 lines
        if is_blacklisted(line):
            continue
        
        words = line.split()
        if 2 <= len(words) <= 4:
            # Check if words look like names (alphabetic)
            if all(word.replace('.', '').isalpha() for word in words):
                return line.strip()
    
    # Fallback: Return first substantial line (not blacklisted)
    for line in lines[:10]:
        if is_blacklisted(line):
            continue
        if len(line) > 3 and any(c.isalpha() for c in line):
            return line.strip()
    
    return ""


def calculate_name_similarity(name1: str, name2: str, extracted_text: str = "") -> float:
    """
    Calculate similarity between two names (0-100%)
    
    New logic:
    1. First try to match whole username from extracted text
    2. If not matched, truncate each word individually and match with extracted text
    3. If >50% matches, it's good to go
    
    Args:
        name1: Expected username
        name2: Extracted name from OCR
        extracted_text: Full OCR text for word-by-word matching
    """
    # Normalize: lowercase, remove extra spaces
    name1 = ' '.join(name1.lower().split())
    name2 = ' '.join(name2.lower().split())
    extracted_text_lower = extracted_text.lower() if extracted_text else ""
    
    logger.info(f"🔍 [IDENTITY] Name matching process:")
    logger.info(f"   - Expected name (normalized): '{name1}'")
    logger.info(f"   - Extracted name (normalized): '{name2}'")
    logger.info(f"   - OCR text available for matching: {bool(extracted_text_lower)}")
    if extracted_text_lower:
        logger.info(f"   - OCR text length: {len(extracted_text_lower)} characters")
    
    # Step 1: Try whole username match first
    if name1 == name2:
        logger.info(f"   ✅ Exact match found between normalized names")
        return 100.0
    
    # Check if whole username appears in extracted text
    if extracted_text_lower and name1 in extracted_text_lower:
        logger.info(f"   ✅ Whole username '{name1}' found in OCR text")
        return 100.0
    
    # Step 2: If whole match failed, truncate each word and match individually
    if extracted_text_lower:
        logger.info(f"   🔄 Trying word-by-word matching with truncated words...")
        name1_words = name1.split()
        matched_words = 0
        matched_word_details = []
        
        logger.info(f"   - Splitting expected name into words: {name1_words}")
        
        for word in name1_words:
            word_matched = False
            matched_truncation = None
            # Try different truncations of the word
            word_len = len(word)
            # Try full word, then progressively shorter versions (min 3 chars)
            for trunc_len in range(word_len, max(2, word_len - 5), -1):
                truncated = word[:trunc_len]
                if truncated in extracted_text_lower:
                    matched_words += 1
                    word_matched = True
                    matched_truncation = truncated
                    break  # Found a match for this word, move to next
            
            if word_matched:
                matched_word_details.append(f"'{word}' -> matched as '{matched_truncation}'")
                logger.info(f"      ✅ Word '{word}' matched (truncated to '{matched_truncation}') in OCR text")
            else:
                matched_word_details.append(f"'{word}' -> NO MATCH")
                logger.warning(f"      ❌ Word '{word}' NOT found in OCR text")
        
        # Calculate match percentage
        if len(name1_words) > 0:
            match_percentage = (matched_words / len(name1_words)) * 100
            logger.info(f"   📊 Word matching results:")
            logger.info(f"      - Total words in expected name: {len(name1_words)}")
            logger.info(f"      - Words matched: {matched_words}")
            logger.info(f"      - Match percentage: {match_percentage:.1f}%")
            logger.info(f"      - Match details: {', '.join(matched_word_details)}")
            
            if match_percentage > 50:
                logger.info(f"   ✅ Match percentage > 50% - PASSING")
                return match_percentage
            else:
                logger.warning(f"   ⚠️  Match percentage ≤ 50% - FALLING BACK to sequence similarity")
    
    # Fallback: Calculate sequence similarity (original logic)
    similarity = SequenceMatcher(None, name1, name2).ratio() * 100
    
    # Also check if all words from shorter name are in longer name
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if words1.issubset(words2) or words2.issubset(words1):
        # Boost similarity if one is subset of other
        similarity = max(similarity, 85.0)
    
    return similarity


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
    Node: Verify candidate identity with comprehensive checks:
    1. Extract name from government ID using OCR
    2. Compare extracted name with provided username
    3. Extract faces from profile_pic and gov_id
    4. Compare both reference faces with all 5 video frames
    
    Updates state['identity_verification'] with results.
    """
    print(f"\n🔍 Agent 1: Identity Verification - User {state['user_id']}")
    
    errors = []
    video_results = []
    
    try:
        # ========== STEP 1: Extract name from government ID ==========
        print("   📄 Step 1: Extracting text from government ID...")
        gov_id_path = download_from_gcs(state['gov_id_url'])
        
        extracted_text = extract_text_from_image(gov_id_path)
        extracted_name = extract_name_from_text(extracted_text)
        
        # Log FULL OCR text extracted from government ID
        logger.info(f"📄 [IDENTITY] FULL OCR Text extracted from government ID for user_id={state['user_id']}:")
        logger.info(f"   {'='*80}")
        if extracted_text:
            logger.info(f"   Full OCR Text (length: {len(extracted_text)} characters):")
            logger.info(f"   {extracted_text}")
        else:
            logger.warning(f"   ⚠️  NO TEXT DETECTED from government ID!")
        logger.info(f"   {'='*80}")
        
        print(f"      OCR Text Preview: {extracted_text[:100] if extracted_text else '(no text detected)'}...")
        print(f"      Extracted Name: '{extracted_name}'")
        
        # ========== STEP 2: Compare names ==========
        print(f"   📝 Step 2: Comparing names...")
        expected_name = state['username']
        
        logger.info(f"📝 [IDENTITY] Starting name matching:")
        logger.info(f"   - Expected Name (from username): '{expected_name}'")
        logger.info(f"   - Extracted Name (from OCR): '{extracted_name}'")
        logger.info(f"   - Full OCR Text will be used for word-by-word matching")
        logger.info(f"   - OCR Text Length: {len(extracted_text)} characters")
        
        name_similarity = calculate_name_similarity(expected_name, extracted_name, extracted_text)
        name_match = bool(name_similarity >= 50.0)  # 50% similarity threshold (changed from 70%)
        
        print(f"      Expected: '{expected_name}'")
        print(f"      Extracted: '{extracted_name}'")
        print(f"      Similarity: {name_similarity:.1f}%")
        print(f"      {'✅ MATCH' if name_match else '❌ NO MATCH'}")
        
        # Log final summary of what text was used for matching
        logger.info(f"📋 [IDENTITY] NAME MATCHING SUMMARY:")
        logger.info(f"   - Full OCR Text Available: {bool(extracted_text)}")
        logger.info(f"   - OCR Text Length: {len(extracted_text)} characters")
        logger.info(f"   - Expected Name: '{expected_name}'")
        logger.info(f"   - Extracted Name (heuristic): '{extracted_name}'")
        logger.info(f"   - Similarity Score: {name_similarity:.1f}%")
        logger.info(f"   - Match Result: {'✅ MATCH (≥50%)' if name_match else '❌ NO MATCH (<50%)'}")
        logger.info(f"   - OCR Text Used For Matching: {'✅ YES - Full text used for word-by-word matching' if extracted_text else '❌ NO - Only extracted name used'}")
        
        if not name_match:
            errors.append(f"Name mismatch: Expected '{expected_name}', extracted '{extracted_name}' (similarity: {name_similarity:.1f}%)")
        
        # ========== STEP 3: Download profile picture ==========
        print("   📥 Step 3: Downloading profile picture...")
        profile_pic_path = download_from_gcs(state['profile_pic_url'])
        
        # ========== STEP 4: Compare faces with video_0 only ==========
        # Only check video_0 (first video) with profile_pic, not gov_id
        print(f"   👤 Step 4: Comparing profile pic face with video_0 only...")
        
        if state['video_urls']:
            video_0_url = state['video_urls'][0]  # First video is video_0
            print(f"      🎬 Video 0 (identity check video)...")
            
            try:
                # Extract best frame with face detection (streams video without downloading)
                frame_path = extract_best_frame_with_face(video_0_url)
                
                # Compare with profile_pic only (no gov_id matching)
                profile_result = verify_face_match(profile_pic_path, frame_path)
                
                video_results.append({
                    "video_url": video_0_url,
                    "video_index": 0,
                    "verified": profile_result.get('verified', False),
                    "similarity": profile_result.get('similarity', 0),
                    "profile_pic_similarity": profile_result.get('similarity', 0),
                    "best_match_source": "profile_pic"
                })
                
                print(f"         Profile Pic: {profile_result.get('similarity', 0):.1f}%")
                print(f"         {'✅ MATCH' if profile_result.get('verified', False) else '❌ NO MATCH'}")
                
                # Cleanup extracted frame
                os.unlink(frame_path)
                
            except Exception as e:
                error_msg = f"Video 0 failed: {str(e)}"
                errors.append(error_msg)
                print(f"         ❌ {error_msg}")
                video_results.append({
                    "video_url": video_0_url,
                    "video_index": 0,
                    "verified": False,
                    "similarity": 0,
                    "error": str(e)
                })
        
        # AGGRESSIVE CLEANUP: Delete ALL temp files
        try:
            if profile_pic_path and os.path.exists(profile_pic_path) and profile_pic_path != state['profile_pic_url']:
                os.unlink(profile_pic_path)
                print(f"      🧹 Deleted profile_pic temp file")
        except Exception as e:
            print(f"      ⚠️  Failed to delete profile_pic: {e}")
        
        try:
            if gov_id_path and os.path.exists(gov_id_path) and gov_id_path != state['gov_id_url']:
                os.unlink(gov_id_path)
                print(f"      🧹 Deleted gov_id temp file")
        except Exception as e:
            print(f"      ⚠️  Failed to delete gov_id: {e}")
        
        # ========== STEP 5: Calculate overall verification ==========
        # Only video_0 is checked now
        verified_count = sum(1 for r in video_results if r.get('verified', False))
        total_count = len(video_results)
        face_verification_rate = (verified_count / total_count * 100) if total_count > 0 else 0
        
        # Calculate average face similarity (only video_0)
        confidences = [r.get('similarity', 0) for r in video_results if 'similarity' in r]
        avg_face_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Overall verification requires BOTH name match AND face verification
        # Face verification: video_0 must pass with >= 60% similarity
        face_verified = bool(verified_count >= 1 and avg_face_confidence >= 60)
        overall_verified = bool(name_match and face_verified)
        
        # Calculate combined confidence score
        # 50% weight to name, 50% weight to face verification
        combined_confidence = (name_similarity * 0.5) + (avg_face_confidence * 0.5)
        
        # Update state
        state['identity_verification'] = {
            "verified": overall_verified,
            "confidence": combined_confidence,
            "name_match": name_match,
            "name_similarity": name_similarity,
            "extracted_name": extracted_name,
            "expected_name": expected_name,
            "face_verified": face_verified,
            "face_verification_rate": face_verification_rate,
            "videos_passed": verified_count,
            "videos_total": total_count,
            "avg_face_confidence": avg_face_confidence,
            "video_results": video_results,
            "red_flags": errors,
            "ocr_text": extracted_text[:500]  # Store first 500 chars for debugging
        }
        
        # Set control flow - ALWAYS continue to gather all evidence
        state['current_stage'] = 'identity_complete'
        
        # Log failure but don't block workflow
        if not overall_verified:
            if not state.get('errors'):
                state['errors'] = []
            
            failure_reasons = []
            if not name_match:
                failure_reasons.append(f"Name mismatch ({name_similarity:.1f}% similarity)")
            if not face_verified:
                failure_reasons.append(f"Face verification failed ({face_verification_rate:.0f}% pass rate)")
            
            state['errors'].append(
                f"Identity verification failed: {', '.join(failure_reasons)}"
            )
        
        print(f"\n   📊 VERIFICATION SUMMARY:")
        print(f"      Name Match: {'✅' if name_match else '❌'} ({name_similarity:.1f}%)")
        print(f"      Face Match: {'✅' if face_verified else '❌'} ({verified_count}/5 videos passed)")
        print(f"      Overall: {'✅ VERIFIED' if overall_verified else '❌ FAILED'} (Confidence: {combined_confidence:.1f}%)")
        
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

