#!/usr/bin/env python3
"""
Simple test to check if DenoiserConfig is available in google-cloud-speech
"""

print("=" * 70)
print("TESTING CHIRP 3 DENOISER CONFIG")
print("=" * 70)
print()

# Test 1: Check version
print("1️⃣  Checking google-cloud-speech version...")
try:
    import google.cloud.speech
    version = google.cloud.speech.__version__
    print(f"   ✅ Version: {version}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print()

# Test 2: Import V2 API
print("2️⃣  Importing Speech V2 API...")
try:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    print(f"   ✅ Imports successful")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print()

# Test 3: Check for DenoiserConfig
print("3️⃣  Checking for DenoiserConfig...")
try:
    from google.cloud.speech_v2.types import cloud_speech
    
    if hasattr(cloud_speech, 'DenoiserConfig'):
        print(f"   ✅ DenoiserConfig EXISTS!")
        
        # Try to create one
        denoiser = cloud_speech.DenoiserConfig(
            denoise_audio=True,
            snr_threshold=20.0
        )
        print(f"   ✅ Created DenoiserConfig instance")
        print(f"      - denoise_audio: {denoiser.denoise_audio}")
        print(f"      - snr_threshold: {denoiser.snr_threshold}")
    else:
        print(f"   ❌ DenoiserConfig NOT FOUND")
        print(f"   📋 Available in cloud_speech:")
        attrs = [a for a in dir(cloud_speech) if 'denois' in a.lower() or 'Denois' in a]
        if attrs:
            for attr in attrs:
                print(f"      - {attr}")
        else:
            print(f"      - No denoiser-related attributes found")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()

# Test 4: Create full RecognitionConfig with denoiser
print("4️⃣  Creating RecognitionConfig with denoiser...")
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
    print(f"   ✅ RecognitionConfig with denoiser created!")
    print(f"      - Model: {config.model}")
    print(f"      - Denoiser: {config.denoiser_config.denoise_audio}")
    print(f"      - SNR threshold: {config.denoiser_config.snr_threshold}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 70)
print("✅ SUCCESS! DenoiserConfig is available and working!")
print("=" * 70)

