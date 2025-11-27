"""
Identity Verification Node - OPTIMIZED with Parallel Processing
Uses local files from workspace instead of streaming
"""
import os
import logging
import subprocess
import tempfile
import threading
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional
import face_recognition
import cv2
import numpy as np
import mediapipe as mp
from google.cloud import vision
from difflib import SequenceMatcher
import re

from ..state import InterviewState

logger = logging.getLogger(__name__)

# Initialize MediaPipe face detection (lightweight, fast, thread-safe)
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(
    model_selection=0,  # 0 = short-range (2 meters), 1 = full-range (5 meters)
    min_detection_confidence=0.5
)


def extract_text_from_image(image_path: Path) -> str:
    """Extract text from government ID using Google Cloud Vision API OCR"""
    try:
        client = vision.ImageAnnotatorClient()
        
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if texts:
            return texts[0].description
        
        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")
        
        return ""
    
    except Exception as e:
        logger.error(f"OCR Error: {str(e)}")
        return ""


def extract_name_from_text(text: str) -> str:
    """Extract name from OCR text using heuristics"""
    if not text:
        return ""
    
    BLACKLIST_PHRASES = {
        'income tax', 'department', 'government', 'india', 'permanent account',
        'account number', 'pan card', 'aadhaar', 'aadhar', 'voter', 'election',
        'driving licence', 'passport', 'republic', 'issued by', 'date of birth',
        'dob', 'address', 'father', 'mother', 'registration'
    }
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    def is_blacklisted(line: str) -> bool:
        line_lower = line.lower()
        return any(phrase in line_lower for phrase in BLACKLIST_PHRASES)
    
    # Pattern 1: Look for "Name:" pattern
    for line in lines:
        if re.search(r'name\s*:?\s*', line, re.IGNORECASE):
            name_match = re.sub(r'^.*?name\s*:?\s*', '', line, flags=re.IGNORECASE)
            if name_match and len(name_match) > 2 and not is_blacklisted(name_match):
                return name_match.strip()
    
    # Pattern 2: Look for lines with 2-4 words
    for line in lines[:10]:
        if is_blacklisted(line):
            continue
        
        words = line.split()
        if 2 <= len(words) <= 4:
            if all(word.replace('.', '').isalpha() for word in words):
                return line.strip()
    
    # Fallback
    for line in lines[:10]:
        if is_blacklisted(line):
            continue
        if len(line) > 3 and any(c.isalpha() for c in line):
            return line.strip()
    
    return ""


def normalize_name(name: str) -> str:
    """
    Normalize name for better matching:
    - Remove extra spaces
    - Convert to lowercase
    - Remove special characters
    - Handle common variations
    """
    if not name:
        return ""
    
    # Convert to lowercase and remove extra spaces
    normalized = ' '.join(name.lower().split())
    
    # Remove special characters but keep spaces
    normalized = re.sub(r'[^a-z\s]', '', normalized)
    
    # Remove extra spaces again after special char removal
    normalized = ' '.join(normalized.split())
    
    return normalized


def calculate_name_similarity(name1: str, name2: str, extracted_text: str = "") -> float:
    """
    Calculate similarity between two names with improved normalization (0-100%)
    
    New logic:
    1. First try to match whole username from extracted text
    2. If not matched, truncate each word individually and match with extracted text
    3. If >50% matches, it's good to go
    
    Args:
        name1: Expected username
        name2: Extracted name from OCR
        extracted_text: Full OCR text for word-by-word matching
    """
    # Normalize both names
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    extracted_text_lower = extracted_text.lower() if extracted_text else ""
    
    logger.info(f"🔍 [IDENTITY] Name matching process:")
    logger.info(f"   - Expected name (normalized): '{norm1}'")
    logger.info(f"   - Extracted name (normalized): '{norm2}'")
    logger.info(f"   - OCR text available for matching: {bool(extracted_text_lower)}")
    if extracted_text_lower:
        logger.info(f"   - OCR text length: {len(extracted_text_lower)} characters")
    
    if not norm1 or not norm2:
        logger.warning(f"   ⚠️  Empty name detected - returning 0% similarity")
        return 0.0
    
    # Step 1: Try whole username match first
    if norm1 == norm2:
        logger.info(f"   ✅ Exact match found between normalized names")
        return 100.0
    
    # Check if whole username appears in extracted text
    if extracted_text_lower and norm1 in extracted_text_lower:
        logger.info(f"   ✅ Whole username '{norm1}' found in OCR text")
        return 100.0
    
    # Step 2: If whole match failed, truncate each word and match individually
    if extracted_text_lower:
        logger.info(f"   🔄 Trying word-by-word matching with truncated words...")
        name1_words = norm1.split()
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
    
    # Fallback: Calculate sequence similarity
    similarity = SequenceMatcher(None, norm1, norm2).ratio() * 100
    
    # Check word-level matching
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    # If one name is subset of another (e.g., "John Smith" vs "John Robert Smith")
    if words1.issubset(words2) or words2.issubset(words1):
        similarity = max(similarity, 85.0)
    
    # Check if all words from shorter name appear in longer name
    shorter_words = words1 if len(words1) <= len(words2) else words2
    longer_words = words2 if len(words1) <= len(words2) else words1
    
    matching_words = sum(1 for word in shorter_words if word in longer_words)
    word_match_ratio = (matching_words / len(shorter_words) * 100) if shorter_words else 0
    
    # Take the higher of sequence similarity and word match ratio
    similarity = max(similarity, word_match_ratio)
    
    return similarity


def detect_face_confidence(frame: np.ndarray) -> float:
    """Use MediaPipe to detect face and return detection confidence"""
    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detector.process(rgb_frame)
        
        if results.detections:
            max_confidence = max(detection.score[0] for detection in results.detections)
            return max_confidence
        else:
            return 0.0
    except Exception as e:
        logger.warning(f"Face detection error: {e}")
        return 0.0


def extract_face_region(image_path: Path) -> Optional[Path]:
    """
    Extract and crop face region from image using MediaPipe
    This ensures face_recognition can detect the face even if the original image has issues
    """
    try:
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"Could not read image: {image_path}")
            return None
        
        # Convert BGR to RGB for MediaPipe
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        
        # Detect faces
        results = face_detector.process(rgb_img)
        
        if not results.detections or len(results.detections) == 0:
            logger.warning(f"No face detected by MediaPipe in: {image_path.name}")
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
            logger.warning(f"Face crop is empty for: {image_path.name}")
            return None
        
        # Save cropped face
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        cv2.imwrite(temp_file.name, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        confidence_score = detection.score[0]
        logger.info(f"✅ Extracted face region from {image_path.name} (confidence: {confidence_score:.2f})")
        print(f"         ✅ Face detected with confidence: {confidence_score:.2f} ({confidence_score*100:.0f}%)")
        print(f"         📏 Face bounding box: {width}x{height} pixels (with padding)")
        return Path(temp_file.name)
        
    except Exception as e:
        logger.error(f"Error extracting face from {image_path}: {e}")
        return None


def extract_frame_from_video(video_path: Path) -> Path:
    """
    Extract BEST frame with face detection from local video file
    Tries multiple positions and picks frame with best face visibility
    """
    cap = cv2.VideoCapture(str(video_path))
    best_frame = None
    best_confidence = 0.0
    best_position = 0
    
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Could not open video: {video_path}")
    
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Try 25%, 50%, 75% positions
        candidate_positions = []
        if total_frames > 0:
            candidate_positions = [
                int(total_frames * 0.25),
                int(total_frames * 0.50),
                int(total_frames * 0.75)
            ]
        
        # Evaluate each candidate
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
                    
                    if confidence > 0.5:  # Good enough, stop
                        break
            except Exception as e:
                logger.warning(f"Error checking frame {pos}: {e}")
                continue
        
        # If found good frame, save it
        if best_frame is not None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            logger.info(f"Extracted best frame at position {best_position} (confidence: {best_confidence:.2f})")
            cap.release()
            return Path(temp_file.name)
        
        # Fallback: sequential reading
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
            
            if confidence > 0.5:
                break
        
        if best_frame is not None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cap.release()
            return Path(temp_file.name)
    
    finally:
        cap.release()
    
    raise ValueError(f"Could not extract frame with face from {video_path}")


def verify_face_match(ref_image: Path, target_image: Path) -> Dict[str, Any]:
    """Verify if faces match using face_recognition library (dlib-based)
    Uses MediaPipe to extract face regions first for better detection"""
    ref_crop = None
    target_crop = None
    
    try:
        print(f"      face_recognition: Comparing {ref_image.name} with {target_image.name}...")
        
        # Extract face regions using MediaPipe (ensures face_recognition can detect them)
        print(f"      🔍 [FACE EXTRACTION] Step 1: Extracting face region from reference image ({ref_image.name})...")
        logger.info(f"Extracting face region from reference: {ref_image.name}")
        ref_crop = extract_face_region(ref_image)
        if ref_crop is None:
            logger.warning(f"MediaPipe didn't find face in reference, trying original image...")
            print(f"      ⚠️  [FACE EXTRACTION] MediaPipe didn't find face in reference, using original image...")
            ref_crop = ref_image
            ref_face_extracted = False
        else:
            logger.info(f"✅ Face region extracted from reference")
            print(f"      ✅ [FACE EXTRACTION] SUCCESS: Face region extracted from reference image!")
            print(f"         📍 Extracted face saved to: {ref_crop.name}")
            ref_face_extracted = True
        
        print(f"      🔍 [FACE EXTRACTION] Step 2: Extracting face region from target image ({target_image.name})...")
        logger.info(f"Extracting face region from target: {target_image.name}")
        target_crop = extract_face_region(target_image)
        if target_crop is None:
            logger.warning(f"MediaPipe didn't find face in target, trying original image...")
            print(f"      ⚠️  [FACE EXTRACTION] MediaPipe didn't find face in target, using original image...")
            target_crop = target_image
            target_face_extracted = False
        else:
            logger.info(f"✅ Face region extracted from target")
            print(f"      ✅ [FACE EXTRACTION] SUCCESS: Face region extracted from target image!")
            print(f"         📍 Extracted face saved to: {target_crop.name}")
            target_face_extracted = True
        
        print(f"      📊 [FACE EXTRACTION] Summary:")
        print(f"         - Reference face extracted: {'✅ YES' if ref_face_extracted else '❌ NO (using original)'}")
        print(f"         - Target face extracted: {'✅ YES' if target_face_extracted else '❌ NO (using original)'}")
        
        # Load images (either cropped or original)
        ref_img = face_recognition.load_image_file(str(ref_crop))
        target_img = face_recognition.load_image_file(str(target_crop))
        
        # Get face encodings (128-dimensional vectors)
        print(f"      🔍 [FACE RECOGNITION] Step 3: Detecting faces using face_recognition library...")
        ref_encodings = face_recognition.face_encodings(ref_img)
        target_encodings = face_recognition.face_encodings(target_img)
        
        print(f"      📊 [FACE RECOGNITION] Detection Results:")
        print(f"         - Reference face detected: {'✅ YES' if len(ref_encodings) > 0 else '❌ NO'}")
        print(f"         - Target face detected: {'✅ YES' if len(target_encodings) > 0 else '❌ NO'}")
        
        # Check if faces were found
        if len(ref_encodings) == 0:
            logger.warning(f"No face found in reference image (even after MediaPipe extraction): {ref_image.name}")
            print(f"      ❌ [FACE RECOGNITION] ERROR: No face found in reference image (even after MediaPipe extraction)")
            print(f"         This means face_recognition library couldn't detect face in the extracted/cropped image")
            return {
                "verified": False,
                "similarity": 0.0,
                "error": "No face found in reference image"
            }
        
        if len(target_encodings) == 0:
            logger.warning(f"No face found in target image (even after MediaPipe extraction): {target_image.name}")
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
        threshold = 0.62  # Balanced threshold between strict and lenient
        lenient_threshold = threshold * 1.04  # 0.6386 - 3% tolerance for minor variations
        
        # Check if faces match
        lenient_verified = bool(distance < lenient_threshold)
        
        # Convert distance to similarity percentage (0-100%)
        if distance <= threshold:
            # Good match: map 0.0-0.6 to 100%-60%
            similarity = 100.0 - (distance / threshold) * 40.0
        else:
            # Poor match: map 0.6-1.0 to 60%-0%
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
        logger.error(f"face_recognition Error: {str(e)}")
        # Force garbage collection to free memory
        gc.collect()
        return {
            "verified": False,
            "similarity": 0.0,
            "error": str(e)
        }
    finally:
        # Cleanup extracted face crops
        if ref_crop and ref_crop != ref_image and ref_crop.exists():
            try:
                os.unlink(ref_crop)
            except:
                pass
        if target_crop and target_crop != target_image and target_crop.exists():
            try:
                os.unlink(target_crop)
            except:
                pass


def process_single_video_identity(
    video_path: Path,
    video_index: int,
    profile_pic_path: Path,
    gov_id_path: Path = None  # No longer used, kept for compatibility
) -> Dict[str, Any]:
    """
    Process identity verification for a single video (video_0 only)
    Only compares with profile_pic, not gov_id
    """
    frame_path = None
    
    try:
        # Extract frame from local video (fast!)
        frame_path = extract_frame_from_video(video_path)
        
        # Compare with profile_pic only (no gov_id matching)
        profile_result = verify_face_match(profile_pic_path, frame_path)
        
        result = {
            "video_index": video_index,
            "verified": profile_result.get('verified', False),
            "similarity": profile_result.get('similarity', 0),
            "profile_pic_similarity": profile_result.get('similarity', 0),
            "best_match_source": "profile_pic",
            "success": True
        }
        
        logger.info(f"Video {video_index}: Profile Pic={profile_result.get('similarity', 0):.1f}% {'✅' if profile_result.get('verified', False) else '❌'}")
        
        return result
        
    except Exception as e:
        logger.error(f"Video {video_index} identity check failed: {str(e)}")
        return {
            "video_index": video_index,
            "verified": False,
            "similarity": 0,
            "error": str(e),
            "success": False
        }
    finally:
        # Cleanup extracted frame
        if frame_path and frame_path.exists():
            try:
                os.unlink(frame_path)
            except:
                pass


async def verify_identity_parallel(resources: Dict, state: InterviewState) -> InterviewState:
    """
    Identity Verification Node - PARALLEL VERSION
    Processes all videos in parallel using local files
    """
    logger.info("🔍 Agent 1: Identity Verification (PARALLEL)")
    print(f"🔍 [IDENTITY] Starting identity verification...")
    
    try:
        # Step 1: Name verification removed (no gov ID)
        print(f"🔍 [IDENTITY] Skipping name extraction (no gov ID)")
        name_match_score = 100.0  # Default pass
        extracted_name = state['username']  # Use provided username
        
        print(f"🔍 [IDENTITY] Using provided name: {extracted_name}")
        
        expected_name = state['username']
        name_similarity = 100.0  # Perfect match since we use provided name
        name_match = True
        
        logger.info(f"✅ [IDENTITY] Name matching complete:")
        logger.info(f"   - Similarity: {name_similarity:.1f}%")
        logger.info(f"   - Match Result: {'✅ MATCH' if name_match else '❌ NO MATCH'}")
        
        # Log final summary of what text was used for matching
        logger.info(f"📋 [IDENTITY] NAME MATCHING SUMMARY:")
        logger.info(f"   - Full OCR Text Available: {bool(extracted_text)}")
        logger.info(f"   - OCR Text Length: {len(extracted_text)} characters")
        logger.info(f"   - Expected Name: '{expected_name}'")
        logger.info(f"   - Extracted Name (heuristic): '{extracted_name}'")
        logger.info(f"   - Similarity Score: {name_similarity:.1f}%")
        logger.info(f"   - Match Result: {'✅ MATCH (≥50%)' if name_match else '❌ NO MATCH (<50%)'}")
        logger.info(f"   - OCR Text Used For Matching: {'✅ YES - Full text used for word-by-word matching' if extracted_text else '❌ NO - Only extracted name used'}")
        
        # Step 2: Process ONLY video_0 (identity check video)
        # As per CTO requirements: Identity check only on video_0.webm
        print(f"🔍 [IDENTITY] Step 2: Processing video_0 only (identity check video)...")
        
        profile_pic_path = resources['profile_pic']
        video_paths = resources['videos']
        
        # Get video_0 (first video in sorted list - the identity check video)
        video_0_path = video_paths[0] if video_paths else None
        
        if not video_0_path:
            raise ValueError("video_0 not found for identity verification")
        
        print(f"🔍 [IDENTITY] Processing video_0: {video_0_path.name}...")
        video_0_result = process_single_video_identity(
            video_0_path,
            0,  # video_0 index
            profile_pic_path
            # gov_id_path removed - no longer used for face matching
        )
        
        video_results = [video_0_result]
        print(f"🔍 [IDENTITY] Video_0 processing complete")
        
        # Calculate overall verification (based on video_0 only)
        verified = video_0_result.get('verified', False)
        face_confidence = video_0_result.get('similarity', 0)
        
        face_verified = bool(verified and face_confidence >= 60)
        overall_verified = bool(name_match and face_verified)
        combined_confidence = (name_similarity * 0.5) + (face_confidence * 0.5)
        
        # Update state
        state['identity_verification'] = {
            "verified": overall_verified,
            "confidence": combined_confidence,
            "name_match": name_match,
            "name_similarity": name_similarity,
            "extracted_name": extracted_name,
            "expected_name": expected_name,
            "face_verified": face_verified,
            "video_0_only": True,
            "face_confidence": face_confidence,
            "video_results": video_results
        }
        
        # NEW: Trigger webhook for identity failure (human-in-loop)
        if not overall_verified:
            logger.warning(f"⚠️ Identity verification failed for {state.get('username')}, triggering webhook...")
            print(f"🔔 [IDENTITY] Sending webhook for human review...")
            try:
                from ...utils.webhook_client import get_webhook_client
                webhook_client = get_webhook_client()
                webhook_sent = await webhook_client.send_identity_failure(
                    user_id=state.get('user_id', 'unknown'),
                    username=state.get('username', 'unknown'),
                    identity_data=state['identity_verification']
                )
                if webhook_sent:
                    print(f"✅ [IDENTITY] Webhook sent successfully")
                else:
                    print(f"⚠️ [IDENTITY] Webhook failed (continuing assessment)")
            except Exception as webhook_error:
                logger.error(f"Webhook error: {str(webhook_error)}")
                print(f"⚠️ [IDENTITY] Webhook error (continuing assessment): {str(webhook_error)}")
        
        logger.info(f"✅ Identity (video_0 only): Overall={'VERIFIED' if overall_verified else 'FAILED'} (Confidence: {combined_confidence:.1f}%)")
        print(f"✅ [IDENTITY] Complete: {'VERIFIED' if overall_verified else 'FAILED'} (Confidence: {combined_confidence:.1f}%)")
        
    except Exception as e:
        logger.error(f"Identity verification error: {str(e)}")
        print(f"❌ [IDENTITY] ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        state['identity_verification'] = {
            "verified": False,
            "confidence": 0.0,
            "error": str(e)
        }
        state['errors'].append(str(e))
    
    return state

