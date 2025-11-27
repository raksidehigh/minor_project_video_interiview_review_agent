"""
Speech-to-Text Transcription Node
Google Speech-to-Text V2 API with Chirp 3 model for enhanced accuracy
"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from google.cloud import storage
from google.cloud.speech_v2.types import cloud_speech

from ..state import InterviewState
from ...utils.gcs_streaming import get_signed_url
from ...utils.speech_client import SpeechClientManager


def extract_audio_from_video(video_url: str) -> str:
    """
    Extract audio from video using FFmpeg (streams from GCS without downloading)
    Converts to FLAC for Speech-to-Text
    
    Args:
        video_url: GCS URL (gs://...) or signed HTTPS URL
    
    Returns:
        Path to extracted audio file (FLAC format)
    """
    # Convert GCS URL to signed URL for streaming
    if video_url.startswith('gs://'):
        video_url = get_signed_url(video_url)
        print(f"         🔗 Streaming from signed URL (no download)")
    
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.flac')
    temp_audio.close()
    
    # FFmpeg supports HTTPS URLs directly!
    cmd = [
        'ffmpeg', '-i', video_url,  # Stream from signed URL
        '-vn',              # No video
        '-acodec', 'flac',  # FLAC codec
        '-ar', '16000',     # 16kHz sample rate
        '-ac', '1',         # Mono
        '-y',
        temp_audio.name
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return temp_audio.name
    except Exception as e:
        if os.path.exists(temp_audio.name):
            os.unlink(temp_audio.name)
        raise RuntimeError(f"Audio extraction failed: {str(e)}")


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10).decode().strip()
        if output and output.replace('.', '').replace('-', '').isdigit():
            return float(output)
        return 0.0
    except:
        return 0.0


def upload_audio_to_gcs(audio_path: str, user_id: str) -> str:
    """Upload audio file to GCS for BatchRecognize (Chirp 3)"""
    import uuid
    from google.cloud import storage
    
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'virtual-interview-agent')
    temp_blob_path = f"temp_transcriptions/{user_id}/{uuid.uuid4()}.flac"
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(temp_blob_path)
    
    blob.upload_from_filename(audio_path)
    gcs_uri = f"gs://{bucket_name}/{temp_blob_path}"
    
    print(f"         📤 Uploaded audio to GCS for batch transcription: {gcs_uri}")
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
        
        print(f"         🧹 Deleted temp audio from GCS")
    except Exception as e:
        print(f"         ⚠️  Failed to delete temp audio: {str(e)}")


def transcribe_audio_google(audio_path: str, user_id: str = "unknown", region: str = None) -> Dict[str, Any]:
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
        print(f"         🎤 Audio duration: {duration:.1f} seconds")
        
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
            print(f"         📤 Using BatchRecognize (audio >= 60s: {duration:.1f}s)")
            
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
            print(f"         ⏳ Waiting for batch transcription (this may take a few minutes)...")
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
            print(f"         ⚡ Using synchronous Recognize (audio < 60s: {duration:.1f}s)")
            
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
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        detected_language = detected_languages[0] if detected_languages else "auto"
        
        words = transcript.split()
        word_count = len(words)
        
        # Count filler words
        filler_list = ['um', 'uh', 'like', 'you know', 'basically', 'actually']
        filler_count = sum(transcript.lower().count(f) for f in filler_list)
        
        # Calculate speaking rate (words per minute)
        speaking_rate = (word_count / duration * 60) if duration > 0 else 0.0
        
        print(f"         ✅ Detected language: {detected_language}")
        print(f"         📊 Quality Metrics:")
        print(f"            - Overall confidence: {confidence*100:.1f}%")
        print(f"            - Speaking rate: {speaking_rate:.1f} words/min")
        print(f"            - Filler words: {filler_count}")
        print(f"            - Word timestamps: {len(word_timestamps)}")
        print(f"         📝 FULL TRANSCRIPT:")
        print(f"            \"{transcript}\"")
        
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
        print(f"         ❌ Transcription error: {error_msg}")
        
        # If auto-detection fails, retry with explicit language (en-IN)
        if "language" in error_msg.lower() or "auto" in error_msg.lower():
            print(f"         🔄 Retrying with explicit language code (en-IN)...")
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


def transcribe_video(video_url: str, video_index: int, user_id: str = "unknown", region: str = None) -> Dict[str, Any]:
    """
    Transcribe audio from video using Google Speech-to-Text V2 with Chirp 3
    PRODUCTION IMPLEMENTATION - extracts real audio and transcribes
    
    Args:
        video_url: GCS URL (gs://...) or signed HTTPS URL
        video_index: Index of the video (1-4 for interview questions)
        user_id: User ID for GCS temp storage (optional)
        region: Google Cloud region (optional, defaults to env var or "us")
    
    Returns:
        dict with transcript, confidence, word_count, filler_words, speaking_rate,
        word_timestamps, detected_language, duration
    """
    audio_path = None
    
    try:
        # Extract audio from video (FFmpeg streams from URL)
        audio_path = extract_audio_from_video(video_url)
        
        # Transcribe using Google Speech-to-Text V2 with Chirp 3 (uses singleton client)
        result = transcribe_audio_google(audio_path, user_id=user_id, region=region)
        
        return result
        
    except Exception as e:
        return {
            "transcript": "",
            "confidence": 0.0,
            "word_count": 0,
            "speaking_rate": 0.0,
            "filler_words": 0,
            "error": str(e),
            "word_timestamps": [],
            "detected_language": None,
        }
    finally:
        # Cleanup audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except:
                pass


def transcribe_videos(state: InterviewState) -> InterviewState:
    """
    Node: Transcribe all videos using Chirp 3 model
    
    Extracts audio and transcribes speech from all videos with enhanced accuracy.
    Uses singleton client (loaded only once) for efficiency.
    
    Updates state['transcriptions'] with results.
    """
    print(f"\n🎤 Agent 3: Speech-to-Text Transcription (Chirp 3 - Enhanced Accuracy)")
    
    transcriptions = []
    user_id = state.get('user_id', 'unknown')
    region = os.getenv('GOOGLE_CLOUD_REGION', 'us')
    
    try:
        for i, video_url in enumerate(state['video_urls'], 1):
            print(f"   🎬 Transcribing video {i}/{len(state['video_urls'])}...")
            
            try:
                # Transcribe (streams video and extracts audio without downloading video)
                result = transcribe_video(video_url, i, user_id=user_id, region=region)
                result['video_url'] = video_url
                result['video_index'] = i
                
                transcriptions.append(result)
                
                lang_info = f" ({result.get('detected_language', 'unknown')})" if result.get('detected_language') else ""
                print(f"      ✅ {result['word_count']} words, {result['confidence']*100:.0f}% confidence{lang_info}")
                    
            except Exception as e:
                error_msg = f"Video {i} transcription failed: {str(e)}"
                print(f"      ❌ {error_msg}")
                transcriptions.append({
                    "video_url": video_url,
                    "video_index": i,
                    "error": str(e),
                    "transcript": "",
                    "confidence": 0.0,
                    "speaking_rate": 0.0,
                    "filler_words": 0,
                    "word_timestamps": [],
                    "detected_language": None,
                })
        
        # Calculate overall metrics
        confidences = [t.get('confidence', 0) for t in transcriptions if 'confidence' in t]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        total_words = sum(t.get('word_count', 0) for t in transcriptions)
        
        transcription_complete = all('transcript' in t for t in transcriptions)
        
        # Update state
        state['transcriptions'] = {
            "transcription_complete": transcription_complete,
            "transcriptions": transcriptions,
            "avg_confidence": avg_confidence,
            "total_words": total_words
        }
        
        state['current_stage'] = 'transcription_complete'
        
        print(f"   ✅ COMPLETE: {total_words} total words, {avg_confidence*100:.0f}% avg confidence")
        print(f"\n   📊 TRANSCRIPTION SUMMARY (Sent to Agent 4 & 5):")
        for i, t in enumerate(transcriptions, 1):
            print(f"      Video {i}:")
            print(f"         - Words: {t.get('word_count', 0)}, Confidence: {t.get('confidence', 0)*100:.1f}%")
            print(f"         - Language: {t.get('detected_language', 'N/A')}, Rate: {t.get('speaking_rate', 0):.1f} wpm")
            print(f"         - Filler words: {t.get('filler_words', 0)}")
            transcript_text = t.get('transcript', '')
            if transcript_text:
                print(f"         - Text: \"{transcript_text[:100]}{'...' if len(transcript_text) > 100 else ''}\"")
            else:
                print(f"         - Text: [EMPTY]")
        
    except Exception as e:
        error_msg = f"Transcription error: {str(e)}"
        print(f"   ❌ {error_msg}")
        
        state['transcriptions'] = {
            "transcription_complete": False,
            "error": error_msg
        }
        state['errors'].append(error_msg)
    
    return state

