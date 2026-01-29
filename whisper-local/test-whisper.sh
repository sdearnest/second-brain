#!/bin/bash
# Test script for local Whisper service

set -e

WHISPER_URL="${WHISPER_URL:-http://localhost:8766}"

echo "======================================"
echo "Local Whisper Service Test"
echo "======================================"
echo ""

# Test 1: Health check
echo "1. Checking service health..."
HEALTH=$(curl -s "$WHISPER_URL/health")
echo "   Response: $HEALTH"
echo ""

# Check if healthy
if echo "$HEALTH" | grep -q "healthy"; then
    echo "   ✅ Service is healthy!"
else
    echo "   ❌ Service is not healthy"
    exit 1
fi

echo ""

# Test 2: Transcribe a test file (if provided)
if [ -n "$1" ] && [ -f "$1" ]; then
    echo "2. Transcribing test file: $1"
    
    START=$(date +%s)
    
    RESPONSE=$(curl -s -X POST "$WHISPER_URL/v1/audio/transcriptions" \
        -F "file=@$1" \
        -F "model=whisper-1" \
        -F "response_format=verbose_json")
    
    END=$(date +%s)
    DURATION=$((END - START))
    
    echo "   ✅ Transcription completed in ${DURATION}s"
    echo ""
    
    # Parse response
    TEXT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('text', ''))" 2>/dev/null || echo "")
    LANG=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('language', ''))" 2>/dev/null || echo "")
    
    if [ -n "$TEXT" ]; then
        echo "   Language: $LANG"
        echo "   Text: $TEXT"
    else
        echo "   ❌ No text returned"
        echo "   Response: $RESPONSE"
    fi
else
    echo "2. Skipping transcription test (no audio file provided)"
    echo "   To test transcription, run:"
    echo "   ./test-whisper.sh /path/to/audio.ogg"
fi

echo ""
echo "======================================"
echo "Test completed!"
echo "======================================"
