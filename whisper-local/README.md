# Local Whisper Transcription Service

Fast, private speech-to-text using faster-whisper with GPU acceleration.

## Hardware Requirements

- NVIDIA GPU with 2GB+ VRAM (your RTX 4060 Ti has 16GB — perfect!)
- NVIDIA Container Toolkit installed
- Docker + Docker Compose

## Model Selection Guide

| Model    | Params | VRAM | Speed          | Accuracy |
|----------|--------|------|----------------|----------|
| tiny     | 39M    | ~1GB | Fastest        | Basic    |
| **base** | 74M    | ~1GB | Fast           | Good     |
| small    | 244M   | ~2GB | Moderate       | Better   |
| medium   | 769M   | ~5GB | Slower         | High     |
| large-v3 | 1550M  | ~10GB| Slowest        | Best     |

**Recommendation for your setup:** Start with `base` (fast + good quality). Upgrade to `small` or `medium` if you need better accuracy.

## Quick Start

### 1. Build and start the service

```bash
cd /path/to/second-brain

# Build the container
docker compose -f docker-compose.whisper.yml build

# Start the service
docker compose -f docker-compose.whisper.yml up -d

# Check logs
docker logs -f whisper-local
```

You should see:
```
INFO:     Loading Whisper model: base on cuda with compute_type=float16
INFO:     ✅ Model loaded successfully!
INFO:     GPU: NVIDIA GeForce RTX 4060 Ti
INFO:     VRAM: 16.0 GB
```

### 2. Test it

```bash
# Make transcribe script executable
chmod +x whisper-local/transcribe.sh

# Test with an audio file
./whisper-local/transcribe.sh /path/to/audio.ogg

# Or use curl directly
curl -X POST http://localhost:8766/v1/audio/transcriptions \
  -F "file=@audio.ogg" \
  -F "model=whisper-1" \
  -F "response_format=json"
```

### 3. Check health

```bash
curl http://localhost:8766/health
```

Expected response:
```json
{
  "status": "healthy",
  "model": "base",
  "device": "cuda",
  "compute_type": "float16"
}
```

## Integration with Second Brain

### Update SimpleX Bridge

Edit `scripts/bridge.py` to use local Whisper instead of OpenAI:

```python
# At the top, change:
WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:8000")

# In the transcribe function:
def transcribe_audio(audio_path):
    with open(audio_path, 'rb') as f:
        files = {'file': f}
        data = {'model': 'whisper-1', 'response_format': 'json'}
        response = requests.post(f"{WHISPER_URL}/v1/audio/transcriptions", files=files, data=data)
        return response.json()['text']
```

### Update n8n Workflow

Add a node to handle voice messages:
1. Detect if message has audio attachment
2. Download audio file
3. POST to `http://whisper:8000/v1/audio/transcriptions`
4. Extract `text` from response
5. Send to existing capture workflow

## Configuration

Edit `docker-compose.whisper.yml` environment variables:

```yaml
environment:
  # Change model size
  WHISPER_MODEL: small  # tiny|base|small|medium|large-v3
  
  # Use CPU instead of GPU (slower)
  WHISPER_DEVICE: cpu
  
  # Reduce GPU memory usage (slight quality loss)
  WHISPER_COMPUTE_TYPE: int8_float16
```

## Performance Benchmarks (RTX 4060 Ti)

Expected transcription speeds (real-time factor):

| Model  | Speed        | Example (60s audio) |
|--------|--------------|---------------------|
| tiny   | ~10x faster  | 6 seconds           |
| base   | ~8x faster   | 7.5 seconds         |
| small  | ~5x faster   | 12 seconds          |
| medium | ~3x faster   | 20 seconds          |
| large  | ~2x faster   | 30 seconds          |

*Your mileage may vary based on audio quality and GPU load.*

## Troubleshooting

### GPU not detected

```bash
# Check NVIDIA drivers
nvidia-smi

# Check Docker can see GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install NVIDIA Container Toolkit:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Out of memory

Reduce model size or switch to int8 quantization:
```yaml
WHISPER_MODEL: tiny
WHISPER_COMPUTE_TYPE: int8_float16
```

### Slow transcription

1. Verify GPU is being used: `docker logs whisper-local | grep GPU`
2. Check GPU load during transcription: `nvidia-smi -l 1`
3. Try a smaller model (base → tiny)

### Container won't start

```bash
# Check logs
docker logs whisper-local

# Rebuild from scratch
docker compose -f docker-compose.whisper.yml down
docker compose -f docker-compose.whisper.yml build --no-cache
docker compose -f docker-compose.whisper.yml up -d
```

## API Reference

### OpenAI-Compatible Endpoint

`POST /v1/audio/transcriptions`

Accepts the same parameters as OpenAI's Whisper API.

**Form data:**
- `file` (required): Audio file (mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg)
- `model` (optional): Model name (ignored, using local model)
- `language` (optional): ISO-639-1 language code (e.g., "en", "es")
- `prompt` (optional): Text to guide the model's style
- `response_format` (optional): json | verbose_json | text
- `temperature` (optional): 0-1, sampling temperature

**Response (json format):**
```json
{
  "text": "Transcribed text here."
}
```

### Simplified Endpoint

`POST /transcribe`

Minimal endpoint, just returns text.

**Form data:**
- `file` (required): Audio file
- `language` (optional): Language code

**Response:**
```json
{
  "text": "Transcribed text here.",
  "language": "en"
}
```

## Cost Comparison

| Service        | Cost (per hour) | Privacy | Speed    |
|----------------|-----------------|---------|----------|
| OpenAI Whisper | $0.006          | ❌      | Fast     |
| Local Whisper  | $0.00           | ✅      | Faster!  |

Your RTX 4060 Ti pays for itself in ~150,000 hours of transcription. 😉

## Next Steps

1. **Voice capture in SimpleX:** Send voice messages, get transcriptions automatically
2. **Semantic search:** Use transcriptions to make voice notes searchable
3. **Meeting recorder:** Record calls, auto-transcribe and summarize
4. **Language learning:** Practice speaking, get instant transcriptions

Enjoy your private, fast, and free speech-to-text! 🎙️
