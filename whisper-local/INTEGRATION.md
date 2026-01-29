# Integrating Local Whisper with Second Brain

This guide shows how to connect the local Whisper service to your second-brain project.

## Overview

```
SimpleX Voice Message
    ↓
SimpleX Bridge (detects audio)
    ↓
Local Whisper API (transcribe)
    ↓
n8n Workflow (classify)
    ↓
Obsidian Database (store)
```

## Step 1: Copy Files to Your Second Brain Repo

```bash
# Copy the whisper-local folder to your second-brain repo
cp -r /home/cypherdoc/clawd/whisper-local /path/to/second-brain/

cd /path/to/second-brain
```

## Step 2: Start the Whisper Service

```bash
# Build and start
docker compose -f docker-compose.whisper.yml build
docker compose -f docker-compose.whisper.yml up -d

# Verify it's running
docker ps | grep whisper
docker logs whisper-local

# Test health
curl http://localhost:8766/health
```

Expected output:
```json
{
  "status": "healthy",
  "model": "base",
  "device": "cuda",
  "compute_type": "float16"
}
```

## Step 3: Test with an Audio File

```bash
# If you have the audio file from earlier:
./whisper-local/transcribe.sh /home/cypherdoc/.clawdbot/media/inbound/cdb2542b-dc6e-46f0-b72a-e48b9db9ee09.ogg

# Or test with any audio file
./whisper-local/transcribe.sh /path/to/test.ogg
```

## Step 4: Update SimpleX Bridge

Edit `scripts/bridge.py` to handle audio messages:

```python
import requests
from pathlib import Path

# Add near the top with other config
WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:8000")

def transcribe_audio(audio_path):
    """Transcribe audio using local Whisper API"""
    try:
        with open(audio_path, 'rb') as f:
            files = {'file': (Path(audio_path).name, f, 'audio/ogg')}
            data = {
                'model': 'whisper-1',
                'response_format': 'json'
            }
            response = requests.post(
                f"{WHISPER_URL}/v1/audio/transcriptions",
                files=files,
                data=data,
                timeout=60
            )
            response.raise_for_status()
            return response.json()['text']
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return None

def extract_message(ci):
    """
    Enhance existing extract_message to handle audio messages
    """
    # ... existing code ...
    
    content = chatItem.get("content") or {}
    msg_content = content.get("msgContent") or {}
    
    # Check for audio/voice message
    if msg_content.get("type") == "voice":
        audio_url = msg_content.get("url")  # or however SimpleX provides audio
        if audio_url:
            # Download and transcribe
            audio_path = download_audio(audio_url)  # implement this
            transcribed_text = transcribe_audio(audio_path)
            if transcribed_text:
                text = f"[Voice] {transcribed_text}"
            else:
                text = "[Voice message - transcription failed]"
    else:
        text = msg_content.get("text")
    
    # ... rest of existing code ...
```

## Step 5: Update Docker Compose Main File

Edit your main `docker-compose.yml` to include Whisper in the network:

```yaml
services:
  simplex-bridge:
    environment:
      # Add this
      - WHISPER_URL=http://whisper:8000
```

Or create a unified compose file:

```bash
# Start everything together
docker compose \
  -f docker-compose.yml \
  -f docker-compose.ollama.yml \
  -f docker-compose.whisper.yml \
  up -d
```

## Step 6: Update n8n Workflow (Optional)

If you want n8n to handle transcription directly:

1. Add HTTP Request node
2. Configure:
   - Method: POST
   - URL: `http://whisper:8000/v1/audio/transcriptions`
   - Body: Form-Data
     - `file`: `{{$binary.audio}}`
     - `model`: `whisper-1`
3. Connect to existing classification workflow

## Step 7: Test End-to-End

1. Send a voice message in SimpleX
2. Check bridge logs: `docker logs -f simplex-bridge`
3. Check Whisper logs: `docker logs -f whisper-local`
4. Verify transcription appears in n8n workflow
5. Check if it gets classified and filed correctly

## Troubleshooting

### Bridge can't reach Whisper

```bash
# Verify both containers are on same network
docker network inspect second-brain

# Test from inside bridge container
docker exec simplex-bridge curl http://whisper:8000/health
```

### Whisper service crashes

```bash
# Check GPU is accessible
docker exec whisper-local nvidia-smi

# Check logs for OOM
docker logs whisper-local | grep -i "memory\|oom"

# If OOM, reduce model size in docker-compose.whisper.yml:
WHISPER_MODEL: tiny
```

### Transcription is slow

```bash
# Check GPU utilization during transcription
watch -n 1 nvidia-smi

# Should show:
# - GPU usage spiking during transcription
# - Memory allocated to whisper-local process
```

If GPU isn't being used:
```bash
# Rebuild with GPU support
docker compose -f docker-compose.whisper.yml down
docker compose -f docker-compose.whisper.yml build --no-cache
docker compose -f docker-compose.whisper.yml up -d
```

## Performance Tips

### 1. Model Selection
- Start with `base` (fast + good quality)
- Upgrade to `small` if you need better accuracy on accents/noisy audio
- `medium` for near-perfect transcription (slower)

### 2. Batch Processing
If you have multiple voice messages, process them in parallel:

```python
from concurrent.futures import ThreadPoolExecutor

def transcribe_batch(audio_files):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(transcribe_audio, audio_files)
    return list(results)
```

### 3. Pre-download Models
Bake models into the Docker image to avoid download delays:

```dockerfile
# In Dockerfile, uncomment this line:
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
```

## Advanced: Multiple Languages

If you send voice messages in different languages:

```python
# Auto-detect language
def transcribe_audio(audio_path, language=None):
    # ... existing code ...
    data = {
        'model': 'whisper-1',
        'response_format': 'verbose_json'
    }
    if language:
        data['language'] = language
    
    response = requests.post(...)
    result = response.json()
    
    return {
        'text': result['text'],
        'language': result['language']
    }
```

## Next Steps

1. **Voice commands:** Train keywords to trigger actions
   - "Remind me..." → Create admin task
   - "Call X tomorrow" → Create calendar event + follow-up

2. **Meeting recorder:** Record video calls, auto-transcribe
   - Use OBS to record audio
   - Send to Whisper
   - Summarize with Clawdbot

3. **Voice journal:** Daily voice notes, auto-transcribed and filed
   - Morning reflection → Daily notes
   - Evening review → Projects database

---

You now have **private, fast, free voice-to-text** integrated with your second brain! 🎙️✨
