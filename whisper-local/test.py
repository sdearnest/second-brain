#!/usr/bin/env python3
"""
Quick test script for local Whisper API
"""
import requests
import sys
from pathlib import Path

WHISPER_URL = "http://localhost:8766"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{WHISPER_URL}/health")
    data = response.json()
    
    print(f"   Status: {data.get('status')}")
    print(f"   Model: {data.get('model')}")
    print(f"   Device: {data.get('device')}")
    print(f"   Compute Type: {data.get('compute_type')}")
    
    if data.get('status') == 'healthy':
        print("   ✅ Service is healthy!\n")
        return True
    else:
        print("   ❌ Service is not healthy\n")
        return False

def test_transcription(audio_file):
    """Test transcription endpoint"""
    print(f"🎙️  Transcribing: {audio_file}")
    
    if not Path(audio_file).exists():
        print(f"   ❌ File not found: {audio_file}")
        return False
    
    with open(audio_file, 'rb') as f:
        files = {'file': (Path(audio_file).name, f, 'audio/ogg')}
        data = {
            'model': 'whisper-1',
            'response_format': 'verbose_json'
        }
        
        print("   Sending request...")
        response = requests.post(
            f"{WHISPER_URL}/v1/audio/transcriptions",
            files=files,
            data=data,
            timeout=120
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Transcription successful!")
        print(f"   Language: {result.get('language', 'unknown')}")
        print(f"   Duration: {result.get('duration', 0):.1f}s")
        print(f"   Segments: {len(result.get('segments', []))}")
        print(f"\n   📝 Transcript:")
        print(f"   {result.get('text', '').strip()}\n")
        return True
    else:
        print(f"   ❌ Transcription failed: {response.status_code}")
        print(f"   {response.text}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Local Whisper API Test")
    print("=" * 50)
    print()
    
    # Test health
    if not test_health():
        print("⚠️  Service is not healthy. Make sure it's running:")
        print("   docker compose -f docker-compose.whisper.yml up -d")
        sys.exit(1)
    
    # Test transcription if file provided
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if test_transcription(audio_file):
            print("✅ All tests passed!")
        else:
            print("❌ Transcription test failed")
            sys.exit(1)
    else:
        print("ℹ️  To test transcription, provide an audio file:")
        print(f"   python3 {sys.argv[0]} /path/to/audio.ogg")
        print()
        print("✅ Health check passed!")
