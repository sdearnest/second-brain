#!/bin/bash
# Local Whisper transcription script
# Usage: ./transcribe.sh /path/to/audio.ogg [output.txt]

set -e

WHISPER_URL="${WHISPER_URL:-http://localhost:8766}"
AUDIO_FILE="$1"
OUTPUT_FILE="${2:-${AUDIO_FILE}.txt}"

if [ -z "$AUDIO_FILE" ]; then
    echo "Usage: $0 <audio_file> [output_file]"
    echo "Example: $0 recording.ogg transcript.txt"
    exit 1
fi

if [ ! -f "$AUDIO_FILE" ]; then
    echo "Error: Audio file not found: $AUDIO_FILE"
    exit 1
fi

echo "Transcribing: $AUDIO_FILE"
echo "Using Whisper API at: $WHISPER_URL"

# Make the request (OpenAI-compatible format)
RESPONSE=$(curl -s -X POST "$WHISPER_URL/v1/audio/transcriptions" \
    -F "file=@${AUDIO_FILE}" \
    -F "model=whisper-1" \
    -F "response_format=json")

# Check if request succeeded
if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to Whisper API"
    exit 1
fi

# Extract text from JSON response
TEXT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('text', ''))")

if [ -z "$TEXT" ]; then
    echo "Error: No transcription returned"
    echo "Response: $RESPONSE"
    exit 1
fi

# Save to file
echo "$TEXT" > "$OUTPUT_FILE"

echo "✅ Transcription saved to: $OUTPUT_FILE"
echo ""
echo "Transcript:"
echo "$TEXT"
