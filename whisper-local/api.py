#!/usr/bin/env python3
"""
Local Whisper API - OpenAI-compatible endpoint using faster-whisper
Optimized for NVIDIA GPU inference
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Local Whisper API",
    description="OpenAI-compatible Whisper transcription API using faster-whisper",
    version="1.0.0"
)

# Model configuration from environment
MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large-v3
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")     # cuda or cpu
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")  # float16, int8_float16, int8

# Initialize model on startup
model = None

@app.on_event("startup")
async def load_model():
    global model
    logger.info(f"Loading Whisper model: {MODEL_SIZE} on {DEVICE} with compute_type={COMPUTE_TYPE}")
    try:
        model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            download_root=os.getenv("WHISPER_MODEL_DIR", "/app/models")
        )
        logger.info("✅ Model loaded successfully!")
        
        # Log GPU info if available
        if DEVICE == "cuda":
            import torch
            if torch.cuda.is_available():
                logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.get("/health")
async def health():
    return {
        "status": "healthy" if model else "model_not_loaded",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE
    }


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    model_name: str = Form(alias="model", default="whisper-1"),
    language: Optional[str] = Form(default=None),
    prompt: Optional[str] = Form(default=None),
    response_format: str = Form(default="json"),
    temperature: float = Form(default=0.0)
):
    """
    OpenAI-compatible transcription endpoint.
    
    Accepts the same parameters as OpenAI's /v1/audio/transcriptions
    """
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Save uploaded file to temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        logger.info(f"Transcribing: {file.filename} ({len(content)} bytes)")
        
        # Transcribe
        segments, info = model.transcribe(
            tmp_path,
            language=language,
            initial_prompt=prompt,
            temperature=temperature,
            vad_filter=True,  # Voice activity detection - removes silence
            beam_size=5
        )
        
        # Collect segments
        transcription_text = ""
        all_segments = []
        
        for segment in segments:
            transcription_text += segment.text
            all_segments.append({
                "id": segment.id,
                "seek": segment.seek,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "tokens": segment.tokens,
                "temperature": segment.temperature,
                "avg_logprob": segment.avg_logprob,
                "compression_ratio": segment.compression_ratio,
                "no_speech_prob": segment.no_speech_prob
            })
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        logger.info(f"✅ Transcribed {len(all_segments)} segments, detected language: {info.language}")
        
        # Return format matching OpenAI API
        if response_format == "json":
            return JSONResponse({
                "text": transcription_text.strip()
            })
        elif response_format == "verbose_json":
            return JSONResponse({
                "task": "transcribe",
                "language": info.language,
                "duration": info.duration,
                "text": transcription_text.strip(),
                "segments": all_segments
            })
        elif response_format == "text":
            return transcription_text.strip()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported response_format: {response_format}")
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        # Clean up temp file if it exists
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/transcribe")
async def transcribe_simple(
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None)
):
    """
    Simplified endpoint - just returns text.
    """
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        segments, info = model.transcribe(tmp_path, language=language, vad_filter=True)
        
        text = "".join([segment.text for segment in segments]).strip()
        
        os.unlink(tmp_path)
        
        return {"text": text, "language": info.language}
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
