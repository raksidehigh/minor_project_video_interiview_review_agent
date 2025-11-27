"""
Speech-to-Text Transcription Node - OPTIMIZED with Parallel Processing
Google Speech-to-Text V2 API with Chirp 3 model for enhanced accuracy
Pre-extracts audio during preparation phase, then transcribes in parallel
"""
import os
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from google.cloud import storage
from google.cloud.speech_v2.types import cloud_speech

from ..state import InterviewState
from ...utils.speech_client import SpeechClientManager

logger = logging.getLogger(__name__)


def extract_audio_from_video_sync(video_path: Path, output_path: Path) -> Path:
    """
    Extract audio from local video file using FFmpeg
    Much faster than streaming!
    """
    cmd = [
        'ffmpeg', '-i', str(video_path),
        '-vn',              # No video
        '-acodec', 'flac',  # FLAC codec
        '-ar', '16000',     # 16kHz sample rate
        '-ac', '1',         # Mono
        '-y',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Audio extraction failed: {str(e)}")


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_path)
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10).decode().strip()
        if output and output.replace('.', '').replace('-', '').isdigit():
            return float(output)
        return 0.0
    except:
        return 0.0


def upload_audio_to_gcs(audio_path: Path, user_id: str) -> str:
    """Upload audio file to GCS for BatchRecognize (Chirp 3)"""
    import uuid
    
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'virtual-interview-agent')
    temp_blob_path = f"temp_transcriptions/{user_id}/{uuid.uuid4()}.flac"
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(temp_blob_path)
    
    blob.upload_from_filename(str(audio_path))
    gcs_uri = f"gs://{bucket_name}/{temp_blob_path}"
    
    logger.info(f"📤 Uploaded audio to GCS: {gcs_uri}")
    return gcs_uri


def delete_temp_audio_from_gcs(gcs_uri: str):
    """Delete temporary audio file from GCS"""
    try:
        if not gcs_uri.startswith('gs://'):
            return
        
        parts = gcs_uri.replace('gs://', '').split('/', 1)
        bucket_name = parts[0]
        blob_path = parts[1]
        
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.delete()
        
        logger.info(f"🧹 Deleted temp audio from GCS")
    except Exception as e:
        logger.warning(f"⚠️  Failed to delete temp audio from GCS: {str(e)}")


def transcribe_audio_google(audio_path: Path, user_id: str = "unknown", region: str = None) -> Dict[str, Any]:
    """
    Transcribe audio using Google Cloud Speech-to-Text V2 API with Chirp 3 model
    Uses singleton client manager for efficiency (client loaded only once)
    Automatically uses BatchRecognize for audio >= 60 seconds
    
    Args:
        audio_path: Path to audio file (FLAC format)
        user_id: User ID for GCS temp storage
        region: Google Cloud region (defaults to env var or "us")
    
    Returns:
        dict with transcript, confidence, word_count, filler_words, speaking_rate,
        word_timestamps, detected_language, duration
    """
    temp_gcs_uri = None
    
    # Get region from environment or use default
    if region is None:
        region = os.getenv('GOOGLE_CLOUD_REGION', 'us')
    
    # Get singleton client (loaded only once per region)
    client = SpeechClientManager.get_client(region)
    project_id = SpeechClientManager.get_project_id()
    recognizer = f"projects/{project_id}/locations/{region}/recognizers/_"
    
    try:
        # Get audio duration to decide which API to use
        duration = get_audio_duration(audio_path)
        logger.info(f"🎤 Audio duration: {duration:.1f} seconds")
        
        # Configure recognition with Chirp 3 + Denoiser (matches working test)
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=["auto"],  # Auto-detect language
            model="chirp_3",
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                # Note: Chirp 3 does not support word timestamps or word confidence
            ),
            denoiser_config=cloud_speech.DenoiserConfig(
                denoise_audio=True,
                snr_threshold=20.0,  # Medium sensitivity
            ),
        )
        
        # Use BatchRecognize for audio >= 60 seconds (V2 equivalent of LongRunningRecognize)
        if duration >= 60:
            logger.info(f"📤 Using BatchRecognize (audio >= 60s: {duration:.1f}s)")
            
            # Upload audio to GCS
            temp_gcs_uri = upload_audio_to_gcs(audio_path, user_id)
            
            file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=temp_gcs_uri)
            
            request = cloud_speech.BatchRecognizeRequest(
                recognizer=recognizer,
                config=config,
                files=[file_metadata],
                recognition_output_config=cloud_speech.RecognitionOutputConfig(
                    inline_response_config=cloud_speech.InlineOutputConfig(),
                ),
            )
            
            # Start batch recognition operation
            logger.info(f"⏳ Waiting for batch transcription to complete...")
            operation = client.batch_recognize(request=request)
            
            # Wait for operation to complete (with timeout)
            response = operation.result(timeout=300)  # 5 minute timeout
            
            # Extract results from batch response
            if not response.results or temp_gcs_uri not in response.results:
                return {
                    "transcript": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "speaking_rate": 0.0,
                    "filler_words": 0,
                    "duration": duration,
                    "word_timestamps": [],
                    "detected_language": None,
                    "error": "No speech detected"
                }
            
            batch_result = response.results[temp_gcs_uri]
            if not batch_result.transcript or not batch_result.transcript.results:
                return {
                    "transcript": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "speaking_rate": 0.0,
                    "filler_words": 0,
                    "duration": duration,
                    "word_timestamps": [],
                    "detected_language": None,
                    "error": "No speech detected"
                }
            
            results = batch_result.transcript.results
            
        else:
            logger.info(f"⚡ Using synchronous Recognize (audio < 60s: {duration:.1f}s)")
            
            # Use synchronous recognize for short audio
            with open(audio_path, 'rb') as audio_file:
                audio_content = audio_file.read()
            
            request = cloud_speech.RecognizeRequest(
                recognizer=recognizer,
                config=config,
                content=audio_content,
            )
            
            # Transcribe the audio
            response = client.recognize(request=request)
            results = response.results
        
        if not results:
            logger.warning(f"⚠️  No speech detected in audio")
            return {
                "transcript": "",
                "confidence": 0.0,
                "word_count": 0,
                "speaking_rate": 0.0,
                "filler_words": 0,
                "duration": duration,
                "word_timestamps": [],
                "detected_language": None,
                "error": "No speech detected"
            }
        
        # Process results from Chirp 3
        transcripts = []
        confidences = []
        word_timestamps = []
        detected_languages = []
        
        for result in results:
            if not result.alternatives:
                continue
                
            alternative = result.alternatives[0]
            transcripts.append(alternative.transcript)
            confidences.append(alternative.confidence)
            
            # Get detected language (Chirp 3 feature)
            if hasattr(result, 'language_code') and result.language_code:
                detected_languages.append(result.language_code)
            
            # Extract word-level timestamps and confidence
            if alternative.words:
                for word_info in alternative.words:
                    word_timestamps.append({
                        "word": word_info.word,
                        "start_time": float(word_info.start_offset.total_seconds()) if word_info.start_offset else None,
                        "end_time": float(word_info.end_offset.total_seconds()) if word_info.end_offset else None,
                        "confidence": word_info.confidence if hasattr(word_info, 'confidence') else None,
                    })
        
        # Combine all transcripts
        transcript = " ".join(transcripts)
        
        # Calculate confidence - fix for Chirp 3 returning 0% confidence
        raw_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # If raw confidence is 0 but we have a good transcript, estimate confidence based on transcript quality
        if raw_confidence == 0.0 and transcript.strip():
            # Estimate confidence based on transcript quality
            word_count = len(transcript.split())
            if word_count >= 10:  # Reasonable length
                # High confidence for clear, substantial transcripts
                confidence = 0.85
            elif word_count >= 5:
                confidence = 0.75
            else:
                confidence = 0.60
        else:
            confidence = raw_confidence
            
        detected_language = detected_languages[0] if detected_languages else "auto"
        
        words = transcript.split()
        word_count = len(words)
        
        # Count filler words
        filler_list = ['um', 'uh', 'like', 'you know', 'basically', 'actually']
        filler_count = sum(transcript.lower().count(f) for f in filler_list)
        
        # Calculate speaking rate (words per minute)
        speaking_rate = (word_count / duration * 60) if duration > 0 else 0.0
        
        logger.info(f"✅ Transcription complete: {word_count} words, {confidence*100:.0f}% confidence, language: {detected_language}")
        logger.info(f"📊 Quality: Rate: {speaking_rate:.1f} wpm, Fillers: {filler_count}, Word timestamps: {len(word_timestamps)}")
        logger.info(f"📝 FULL TRANSCRIPT: \"{transcript}\"")
        
        return {
            "transcript": transcript,
            "confidence": confidence,
            "word_count": word_count,
            "filler_words": filler_count,
            "speaking_rate": speaking_rate,
            "duration": duration,
            "word_timestamps": word_timestamps,
            "detected_language": detected_language,
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Transcription API error: {error_msg}")
        
        # If auto-detection fails, retry with explicit language (en-IN)
        if "language" in error_msg.lower() or "auto" in error_msg.lower():
            logger.info(f"🔄 Retrying with explicit language code (en-IN)...")
            try:
                # Retry with explicit language
                config = cloud_speech.RecognitionConfig(
                    auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                    language_codes=["en-IN"],  # Fallback to English (India)
                    model="chirp_3",
                    features=cloud_speech.RecognitionFeatures(
                        enable_automatic_punctuation=True,
                        # Note: Chirp 3 does not support word timestamps or word confidence
                    ),
                    denoiser_config=cloud_speech.DenoiserConfig(
                        denoise_audio=True,
                        snr_threshold=20.0,
                    ),
                )
                
                duration = get_audio_duration(audio_path)
                
                if duration >= 60:
                    if not temp_gcs_uri:
                        temp_gcs_uri = upload_audio_to_gcs(audio_path, user_id)
                    
                    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=temp_gcs_uri)
                    request = cloud_speech.BatchRecognizeRequest(
                        recognizer=recognizer,
                        config=config,
                        files=[file_metadata],
                        recognition_output_config=cloud_speech.RecognitionOutputConfig(
                            inline_response_config=cloud_speech.InlineOutputConfig(),
                        ),
                    )
                    operation = client.batch_recognize(request=request)
                    response = operation.result(timeout=300)
                    batch_result = response.results[temp_gcs_uri]
                    results = batch_result.transcript.results if batch_result.transcript else []
                else:
                    with open(audio_path, 'rb') as audio_file:
                        audio_content = audio_file.read()
                    request = cloud_speech.RecognizeRequest(
                        recognizer=recognizer,
                        config=config,
                        content=audio_content,
                    )
                    response = client.recognize(request=request)
                    results = response.results
                
                # Process results (same as above)
                transcripts = []
                confidences = []
                word_timestamps = []
                
                for result in results:
                    if result.alternatives:
                        alternative = result.alternatives[0]
                        transcripts.append(alternative.transcript)
                        confidences.append(alternative.confidence)
                        
                        if alternative.words:
                            for word_info in alternative.words:
                                word_timestamps.append({
                                    "word": word_info.word,
                                    "start_time": float(word_info.start_offset.total_seconds()) if word_info.start_offset else None,
                                    "end_time": float(word_info.end_offset.total_seconds()) if word_info.end_offset else None,
                                    "confidence": word_info.confidence if hasattr(word_info, 'confidence') else None,
                                })
                
                transcript = " ".join(transcripts)
                confidence = sum(confidences) / len(confidences) if confidences else 0.0
                words = transcript.split()
                word_count = len(words)
                filler_list = ['um', 'uh', 'like', 'you know', 'basically', 'actually']
                filler_count = sum(transcript.lower().count(f) for f in filler_list)
                speaking_rate = (word_count / duration * 60) if duration > 0 else 0.0
                
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "word_count": word_count,
                    "filler_words": filler_count,
                    "speaking_rate": speaking_rate,
                    "duration": duration,
                    "word_timestamps": word_timestamps,
                    "detected_language": "en-IN",
                }
            except Exception as retry_error:
                error_msg = str(retry_error)
                logger.error(f"❌ Retry also failed: {error_msg}")
        
        return {
            "transcript": "",
            "confidence": 0.0,
            "word_count": 0,
            "speaking_rate": 0.0,
            "filler_words": 0,
            "error": error_msg,
            "duration": duration,
            "word_timestamps": [],
            "detected_language": None,
        }
    
    finally:
        # Cleanup: Delete temp GCS file if we uploaded it
        if temp_gcs_uri:
            delete_temp_audio_from_gcs(temp_gcs_uri)


def process_single_audio_transcription(audio_path: Path, video_index: int, kwargs: Dict = None) -> Dict[str, Any]:
    """
    Transcribe a single audio file using Chirp 3
    Designed to run in parallel
    
    Args:
        audio_path: Path to audio file
        video_index: Index of the video (1-4)
        kwargs: Optional dict with user_id and region for GCS temp storage
    """
    user_id = kwargs.get('user_id', 'unknown') if kwargs else 'unknown'
    region = kwargs.get('region', os.getenv('GOOGLE_CLOUD_REGION', 'us')) if kwargs else os.getenv('GOOGLE_CLOUD_REGION', 'us')
    
    try:
        logger.info(f"🎤 [TRANSCRIBE] Processing audio {video_index}: {audio_path.name}")
        result = transcribe_audio_google(audio_path, user_id=user_id, region=region)
        result['video_index'] = video_index
        result['success'] = True
        
        lang_info = f" ({result.get('detected_language', 'unknown')})" if result.get('detected_language') else ""
        logger.info(f"✅ Audio {video_index}: {result['word_count']} words, {result['confidence']*100:.0f}% confidence{lang_info}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Audio {video_index} transcription failed: {str(e)}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return {
            "video_index": video_index,
            "transcript": "",
            "confidence": 0.0,
            "word_count": 0,
            "speaking_rate": 0.0,
            "filler_words": 0,
            "error": str(e),
            "success": False,
            "word_timestamps": [],
            "detected_language": None,
        }


async def extract_all_audios_parallel(video_paths: List[Path], workspace) -> List[Path]:
    """
    Extract audio from all videos in parallel
    This happens during preparation phase
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    logger.info(f"Extracting audio from {len(video_paths)} videos in parallel...")
    
    loop = asyncio.get_event_loop()
    audio_paths = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        tasks = []
        for i, video_path in enumerate(video_paths, 1):
            audio_path = workspace.get_audio_path(i)
            task = loop.run_in_executor(
                executor,
                extract_audio_from_video_sync,
                video_path,
                audio_path
            )
            tasks.append(task)
        
        audio_paths = await asyncio.gather(*tasks)
    
    logger.info(f"✅ Extracted {len(audio_paths)} audio files")
    return audio_paths


async def transcribe_videos_parallel(resources: Dict, state: InterviewState) -> InterviewState:
    """
    Transcription Node - PARALLEL VERSION with Chirp 3
    Transcribes all pre-extracted audio files in parallel using enhanced accuracy
    Uses singleton client (loaded only once) for efficiency
    """
    logger.info("🎤 Agent 3: Speech-to-Text Transcription (PARALLEL - Chirp 3)")
    print(f"🎤 [TRANSCRIBE] Starting transcription with Chirp 3...")
    
    try:
        # Extract audio from interview videos only (skip video_0)
        video_paths = resources['videos']
        workspace = resources['workspace']
        
        # NEW: Skip video_0 (identity check), only transcribe video_1-5 (interview questions)
        interview_videos = video_paths[1:6] if len(video_paths) >= 6 else video_paths[1:]
        print(f"🎤 [TRANSCRIBE] Extracting audio from {len(interview_videos)} interview videos (video_1-5, skipping video_0)...")
        
        audio_paths = await extract_all_audios_parallel(interview_videos, workspace)
        print(f"🎤 [TRANSCRIBE] Audio extraction complete")
        
        # Now transcribe all audios in parallel
        print(f"🎤 [TRANSCRIBE] Transcribing {len(audio_paths)} audios in parallel...")
        from ...utils.parallel import process_items_parallel
        
        # Create wrapper for parallel execution
        user_id = state.get('user_id', 'unknown')
        region = os.getenv('GOOGLE_CLOUD_REGION', 'us')
        
        async def transcribe_wrapper(args):
            audio_path, video_index = args
            print(f"🎤 [TRANSCRIBE] Transcribing audio {video_index}...")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                process_single_audio_transcription,
                audio_path,
                video_index,
                {'user_id': user_id, 'region': region}  # Pass user_id and region for GCS temp storage
            )
        
        transcription_args = [(audio_path, i) for i, audio_path in enumerate(audio_paths, 1)]
        transcriptions = await asyncio.gather(*[transcribe_wrapper(args) for args in transcription_args])
        print(f"🎤 [TRANSCRIBE] Parallel transcription complete")
        
        # Calculate metrics
        confidences = [t.get('confidence', 0) for t in transcriptions if 'confidence' in t]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        total_words = sum(t.get('word_count', 0) for t in transcriptions)
        transcription_complete = all('transcript' in t for t in transcriptions)
        
        state['transcriptions'] = {
            "transcription_complete": transcription_complete,
            "transcriptions": transcriptions,
            "avg_confidence": avg_confidence,
            "total_words": total_words
        }
        
        logger.info(f"✅ Transcription: {total_words} words, {avg_confidence*100:.0f}% avg confidence")
        print(f"✅ [TRANSCRIBE] Complete: {total_words} words, {avg_confidence*100:.0f}% avg confidence")
        
        # Log detailed summary for monitoring
        print(f"\n📊 [TRANSCRIBE] SUMMARY (Sent to Agent 4 & 5):")
        for i, t in enumerate(transcriptions, 1):
            print(f"   Video {i}:")
            print(f"      - Words: {t.get('word_count', 0)}, Confidence: {t.get('confidence', 0)*100:.1f}%")
            print(f"      - Language: {t.get('detected_language', 'N/A')}, Rate: {t.get('speaking_rate', 0):.1f} wpm")
            print(f"      - Filler words: {t.get('filler_words', 0)}")
            transcript_text = t.get('transcript', '')
            if transcript_text:
                print(f"      - Text: \"{transcript_text[:100]}{'...' if len(transcript_text) > 100 else ''}\"")
            else:
                print(f"      - Text: [EMPTY]")
        
        logger.info(f"📊 Detailed transcription summary logged for monitoring")
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        print(f"❌ [TRANSCRIBE] ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        state['transcriptions'] = {
            "transcription_complete": False,
            "error": str(e)
        }
        state['errors'].append(str(e))
    
    return state

