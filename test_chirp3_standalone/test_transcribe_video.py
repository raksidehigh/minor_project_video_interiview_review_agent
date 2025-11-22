#!/usr/bin/env python3
"""
Test actual transcription with Chirp 3 + Denoiser on a real GCS video
"""
import os
import tempfile
import subprocess
from pathlib import Path

print("=" * 70)
print("CHIRP 3 TRANSCRIPTION TEST - Real GCS Video")
print("=" * 70)
print()

# Configuration
USER_ID = "user_2"
VIDEO_INDEX = 3
BUCKET_NAME = "edumentor-virtual-interview"
VIDEO_PATH = f"{USER_ID}/interview_videos/video_{VIDEO_INDEX}.webm"
GCS_URI = f"gs://{BUCKET_NAME}/{VIDEO_PATH}"

print(f"📹 Video: {GCS_URI}")
print()

# Check environment
print("1️⃣  Checking environment...")
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
if not PROJECT_ID:
    print("   ⚠️  GOOGLE_CLOUD_PROJECT not set, trying to get from credentials...")
    try:
        from google.auth import default
        _, PROJECT_ID = default()
        print(f"   ✅ Got project from credentials: {PROJECT_ID}")
    except Exception as e:
        print(f"   ❌ Failed to get project ID: {e}")
        print()
        print("   Please set GOOGLE_CLOUD_PROJECT environment variable:")
        print("   export GOOGLE_CLOUD_PROJECT='your-project-id'")
        exit(1)
else:
    print(f"   ✅ Project ID: {PROJECT_ID}")

# Check for ffmpeg
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    if result.returncode == 0:
        print(f"   ✅ FFmpeg is available")
    else:
        print(f"   ❌ FFmpeg check failed")
        exit(1)
except:
    print(f"   ❌ FFmpeg not found. Install with: brew install ffmpeg")
    exit(1)

print()

# Step 1: Get signed URL for video
print("2️⃣  Getting signed URL for video...")
try:
    from google.cloud import storage
    
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(VIDEO_PATH)
    
    # Check if blob exists
    if not blob.exists():
        print(f"   ❌ Video not found: {GCS_URI}")
        print(f"   💡 Make sure video_3 exists for user_2")
        exit(1)
    
    # Generate signed URL
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=3600,  # 1 hour
        method="GET"
    )
    print(f"   ✅ Got signed URL (valid for 1 hour)")
    
    # Get video size (reload metadata if needed)
    if blob.size is None:
        blob.reload()
    if blob.size:
        print(f"   📦 Video size: {blob.size / 1024 / 1024:.2f} MB")
    else:
        print(f"   📦 Video size: Unknown")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print()

# Step 2: Extract audio from video
print("3️⃣  Extracting audio from video...")
temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.flac')
temp_audio.close()

try:
    cmd = [
        'ffmpeg', '-i', signed_url,
        '-vn',              # No video
        '-acodec', 'flac',  # FLAC codec
        '-ar', '16000',     # 16kHz sample rate
        '-ac', '1',         # Mono
        '-y',
        temp_audio.name
    ]
    
    print(f"   🎬 Streaming and extracting audio...")
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    
    if result.returncode != 0:
        print(f"   ❌ FFmpeg failed: {result.stderr.decode()}")
        exit(1)
    
    # Get audio duration
    cmd_duration = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        temp_audio.name
    ]
    duration_output = subprocess.check_output(cmd_duration, timeout=10).decode().strip()
    duration = float(duration_output)
    
    audio_size = os.path.getsize(temp_audio.name) / 1024 / 1024
    print(f"   ✅ Audio extracted: {audio_size:.2f} MB, {duration:.1f} seconds")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    if os.path.exists(temp_audio.name):
        os.unlink(temp_audio.name)
    exit(1)

print()

# Step 3: Transcribe with Chirp 3 + Denoiser
print("4️⃣  Transcribing with Chirp 3 + Denoiser...")
try:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    from google.api_core.client_options import ClientOptions
    
    # Initialize client
    REGION = os.getenv('GOOGLE_CLOUD_REGION', 'us')
    client = SpeechClient(
        client_options=ClientOptions(
            api_endpoint=f"{REGION}-speech.googleapis.com",
        )
    )
    recognizer = f"projects/{PROJECT_ID}/locations/{REGION}/recognizers/_"
    
    print(f"   🔧 Region: {REGION}")
    print(f"   🔧 Using {'BatchRecognize' if duration >= 60 else 'Recognize'} (duration: {duration:.1f}s)")
    
    # Configure recognition with Chirp 3 + Denoiser
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
    
    print(f"   🎤 Transcribing...")
    
    # Use synchronous recognize for short audio (< 60s)
    if duration < 60:
        with open(temp_audio.name, 'rb') as audio_file:
            audio_content = audio_file.read()
        
        request = cloud_speech.RecognizeRequest(
            recognizer=recognizer,
            config=config,
            content=audio_content,
        )
        
        response = client.recognize(request=request)
        results = response.results
    else:
        # For longer audio, upload to GCS and use BatchRecognize
        print(f"   📤 Uploading to GCS for batch processing...")
        temp_gcs_path = f"temp_transcriptions/{USER_ID}/test_video_{VIDEO_INDEX}.flac"
        blob = bucket.blob(temp_gcs_path)
        blob.upload_from_filename(temp_audio.name)
        temp_gcs_uri = f"gs://{BUCKET_NAME}/{temp_gcs_path}"
        
        file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=temp_gcs_uri)
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=recognizer,
            config=config,
            files=[file_metadata],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig(),
            ),
        )
        
        print(f"   ⏳ Waiting for batch transcription...")
        operation = client.batch_recognize(request=request)
        response = operation.result(timeout=300)
        
        batch_result = response.results[temp_gcs_uri]
        results = batch_result.transcript.results if batch_result.transcript else []
        
        # Cleanup temp GCS file
        blob.delete()
    
    # Process results
    if not results:
        print(f"   ⚠️  No speech detected in audio")
    else:
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
            
            # Get detected language
            if hasattr(result, 'language_code') and result.language_code:
                detected_languages.append(result.language_code)
            
            # Extract word-level info
            if alternative.words:
                for word_info in alternative.words:
                    word_timestamps.append({
                        "word": word_info.word,
                        "start": float(word_info.start_offset.total_seconds()) if word_info.start_offset else None,
                        "end": float(word_info.end_offset.total_seconds()) if word_info.end_offset else None,
                        "confidence": word_info.confidence if hasattr(word_info, 'confidence') else None,
                    })
        
        # Combine results
        transcript = " ".join(transcripts)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        detected_language = detected_languages[0] if detected_languages else "auto"
        word_count = len(transcript.split())
        speaking_rate = (word_count / duration * 60) if duration > 0 else 0.0
        
        # Count filler words
        filler_list = ['um', 'uh', 'like', 'you know', 'basically', 'actually']
        filler_count = sum(transcript.lower().count(f) for f in filler_list)
        
        print(f"   ✅ Transcription complete!")
        print()
        print("=" * 70)
        print("📊 RESULTS")
        print("=" * 70)
        print(f"🌍 Detected Language: {detected_language}")
        print(f"📝 Word Count: {word_count}")
        print(f"🎯 Overall Confidence: {confidence*100:.1f}%")
        print(f"🗣️  Speaking Rate: {speaking_rate:.1f} words/min")
        print(f"🤔 Filler Words: {filler_count}")
        print(f"⏱️  Word Timestamps: {len(word_timestamps)}")
        print()
        print("📝 TRANSCRIPT:")
        print("-" * 70)
        print(transcript)
        print("-" * 70)
        print()
        
        if word_timestamps[:5]:
            print("🔤 First 5 words with timestamps:")
            for i, word_info in enumerate(word_timestamps[:5], 1):
                conf_str = f" (conf: {word_info['confidence']:.2f})" if word_info.get('confidence') else ""
                print(f"   {i}. \"{word_info['word']}\" [{word_info['start']:.1f}s - {word_info['end']:.1f}s]{conf_str}")
            print()
        
except Exception as e:
    print(f"   ❌ Transcription error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

finally:
    # Cleanup
    if os.path.exists(temp_audio.name):
        os.unlink(temp_audio.name)

print("=" * 70)
print("✅ TEST COMPLETE")
print("=" * 70)

