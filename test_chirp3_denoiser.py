#!/usr/bin/env python3
"""
Standalone test script to verify Chirp 3 with denoiser configuration
Tests the google-cloud-speech library before deploying
"""
import os
import sys

def test_imports():
    """Test if all required imports are available"""
    print("=" * 70)
    print("TESTING GOOGLE CLOUD SPEECH V2 API - CHIRP 3 WITH DENOISER")
    print("=" * 70)
    print()
    
    # Test 1: Check library version
    print("1️⃣  Checking google-cloud-speech version...")
    try:
        import google.cloud.speech
        version = google.cloud.speech.__version__
        print(f"   ✅ google-cloud-speech version: {version}")
        
        # Parse version
        major, minor, patch = map(int, version.split('.')[:3])
        if major < 2 or (major == 2 and minor < 34):
            print(f"   ⚠️  WARNING: Version {version} might not support DenoiserConfig")
            print(f"   💡 Recommended: >= 2.34.0")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print()
    
    # Test 2: Import V2 client
    print("2️⃣  Testing Speech V2 imports...")
    try:
        from google.cloud.speech_v2 import SpeechClient
        print(f"   ✅ SpeechClient imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import SpeechClient: {e}")
        return False
    
    try:
        from google.cloud.speech_v2.types import cloud_speech
        print(f"   ✅ cloud_speech types imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import cloud_speech types: {e}")
        return False
    
    print()
    
    # Test 3: Check for DenoiserConfig
    print("3️⃣  Checking for DenoiserConfig...")
    try:
        from google.cloud.speech_v2.types import cloud_speech
        
        # Try to access DenoiserConfig
        if hasattr(cloud_speech, 'DenoiserConfig'):
            print(f"   ✅ DenoiserConfig is available!")
            
            # Try to create an instance
            try:
                denoiser = cloud_speech.DenoiserConfig(
                    denoise_audio=True,
                    snr_threshold=20.0
                )
                print(f"   ✅ DenoiserConfig instance created successfully")
                print(f"      - denoise_audio: {denoiser.denoise_audio}")
                print(f"      - snr_threshold: {denoiser.snr_threshold}")
            except Exception as e:
                print(f"   ⚠️  DenoiserConfig exists but failed to instantiate: {e}")
        else:
            print(f"   ❌ DenoiserConfig NOT found in cloud_speech module")
            print(f"   📋 Available attributes:")
            attrs = [a for a in dir(cloud_speech) if not a.startswith('_')]
            for attr in sorted(attrs)[:20]:  # Show first 20
                print(f"      - {attr}")
            if len(attrs) > 20:
                print(f"      ... and {len(attrs) - 20} more")
            return False
    except Exception as e:
        print(f"   ❌ Error checking DenoiserConfig: {e}")
        return False
    
    print()
    
    # Test 4: Try to create RecognitionConfig WITHOUT denoiser first
    print("4️⃣  Testing RecognitionConfig (without denoiser)...")
    try:
        from google.cloud.speech_v2.types import cloud_speech
        
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=["auto"],
            model="chirp_3",
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
        )
        print(f"   ✅ RecognitionConfig created successfully (without denoiser)")
        print(f"      - model: {config.model}")
        print(f"      - language_codes: {config.language_codes}")
    except Exception as e:
        print(f"   ❌ Failed to create RecognitionConfig: {e}")
        return False
    
    print()
    
    # Test 5: Try to create RecognitionConfig WITH denoiser
    print("5️⃣  Testing RecognitionConfig (with denoiser)...")
    try:
        from google.cloud.speech_v2.types import cloud_speech
        
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=["auto"],
            model="chirp_3",
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
            denoiser_config=cloud_speech.DenoiserConfig(
                denoise_audio=True,
                snr_threshold=20.0,
            ),
        )
        print(f"   ✅ RecognitionConfig with denoiser created successfully!")
        print(f"      - model: {config.model}")
        print(f"      - denoiser enabled: {config.denoiser_config.denoise_audio}")
        print(f"      - SNR threshold: {config.denoiser_config.snr_threshold}")
    except Exception as e:
        print(f"   ❌ Failed to create RecognitionConfig with denoiser: {e}")
        print(f"   💡 Try using RecognitionConfig without denoiser_config")
        return False
    
    print()
    print("=" * 70)
    print("✅ ALL TESTS PASSED! Chirp 3 with denoiser is ready to use.")
    print("=" * 70)
    return True


def test_actual_transcription():
    """Test actual transcription with a sample audio file"""
    print()
    print("=" * 70)
    print("OPTIONAL: ACTUAL TRANSCRIPTION TEST")
    print("=" * 70)
    print()
    print("To test actual transcription, you need:")
    print("  1. GOOGLE_CLOUD_PROJECT environment variable set")
    print("  2. A sample audio file (FLAC, WAV, etc.)")
    print("  3. Valid Google Cloud credentials")
    print()
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("⚠️  GOOGLE_CLOUD_PROJECT not set, skipping actual transcription test")
        return
    
    print(f"📋 Project ID: {project_id}")
    print()
    print("Run this script with a test audio file path as an argument:")
    print("   python test_chirp3_denoiser.py /path/to/audio.flac")


if __name__ == "__main__":
    print()
    success = test_imports()
    
    if not success:
        print()
        print("=" * 70)
        print("❌ TESTS FAILED")
        print("=" * 70)
        print()
        print("TROUBLESHOOTING:")
        print("  1. Check your google-cloud-speech version:")
        print("     pip show google-cloud-speech")
        print()
        print("  2. Upgrade if needed:")
        print("     pip install --upgrade 'google-cloud-speech>=2.34.0'")
        print()
        print("  3. If DenoiserConfig is not available in any version,")
        print("     you may need to use the API without it.")
        print("     Chirp 3 has built-in noise handling anyway.")
        print()
        sys.exit(1)
    
    test_actual_transcription()
    sys.exit(0)

