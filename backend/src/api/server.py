"""FastAPI Backend Server for Integrated Spoof-Aware Speaker Verification (SASV).

Provides production REST endpoints for:
- System health and GPU/VRAM telemetry
- Multi-utterance speaker enrollment and template management
- Single-use, time-bound spoken challenge generation
- End-to-end voice authentication and spoof detection
- Official SASV 2022 benchmark metrics retrieval
"""

import os
import json
import shutil
import sys
import tempfile
import time
import threading
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root is in sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.authentication_pipeline import AuthenticationPipeline, AuthenticationResponse
from src.core.challenge_manager import ChallengeManager
from src.core.enrollment_manager import EnrollmentManager
from src.api.input_validation import canonical_username, audio_suffix
from src.core.demo_voice import synthesize_demo
from src.api import recording_history as history_store


app = FastAPI(
    title="Integrated Spoof-Aware Speaker Verification (SASV) API",
    description="High-security voice authentication with ECAPA-TDNN speaker verification, AASIST spoof detection, dynamic Whisper phrase challenges, and learned score fusion.",
    version="1.0.0",
)


@app.get("/", tags=["General"])
def root():
    """Root endpoint welcoming clients and directing to API documentation."""
    return {
        "service": "Integrated Spoof-Aware Speaker Verification (SASV) API",
        "status": "online",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "health": "GET /health",
            "challenge": "GET /api/v1/challenge?username={username}",
            "authenticate": "POST /api/v1/authenticate",
            "enroll": "POST /api/v1/enroll",
            "users": "GET /api/v1/users",
            "benchmark": "GET /api/v1/benchmark",
        },
    }

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the browser workspace on the same origin as the API. Keep the
# existing JSON root endpoint available for API clients.
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = PROJECT_ROOT.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")

    @app.get("/app", include_in_schema=False)
    def browser_workspace():
        return RedirectResponse(url="/ui/")

# Lazy singleton pipeline
_pipeline: Optional[AuthenticationPipeline] = None
MODELS_READY = False
_pipeline_lock = threading.RLock()


def validated_username(value: str) -> str:
    try:
        return canonical_username(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def get_pipeline() -> AuthenticationPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = AuthenticationPipeline()
        return _pipeline


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    """Returns system status, active compute device, and VRAM telemetry."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    telemetry = {
        "status": "healthy",
        "models_ready": MODELS_READY,
        "enforced_policy": SERVER_POLICY,
        "asr_model": getattr(getattr(_pipeline, "challenge", None), "whisper_model_name", os.getenv("SASV_WHISPER_MODEL", "small.en")),
        "device": device,
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        telemetry["gpu_name"] = torch.cuda.get_device_name(0)
        telemetry["vram_allocated_mb"] = round(torch.cuda.memory_allocated(0) / (1024 * 1024), 2)
        telemetry["vram_reserved_mb"] = round(torch.cuda.memory_reserved(0) / (1024 * 1024), 2)
        telemetry["total_vram_mb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024), 2)

    return telemetry


@app.get("/api/v1/challenge", tags=["Authentication"])
def request_challenge(username: str):
    """Issues a fresh single-use randomized spoken challenge phrase with a 45-second TTL."""
    username = validated_username(username)

    pipeline = get_pipeline()
    with _pipeline_lock:
        challenge = pipeline.challenge.issue_challenge(username)
    return challenge


VOICES_DIR = PROJECT_ROOT / "data" / "voices"
ENROLLED_VOICES_DIR = VOICES_DIR / "enrolled"
TESTING_VOICES_DIR = VOICES_DIR / "testing"
ENROLLED_VOICES_DIR.mkdir(parents=True, exist_ok=True)
TESTING_VOICES_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/v1/enroll", tags=["Enrollment"])
def enroll_user(
    username: str = Form(..., description="Unique speaker identifier"),
    files: List[UploadFile] = File(..., description="Bona fide voice recordings for enrollment"),
):
    """Enrolls a speaker using 1 or more bona fide voice recordings.
    
    Security Policy:
    - Enrollment anti-spoof verification is strictly mandatory.
    - Any uploaded recording failing the countermeasure gate is rejected.
    """
    username = validated_username(username)
    if not files:
        raise HTTPException(status_code=400, detail="At least one audio file must be uploaded.")

    pipeline = get_pipeline()
    temp_dir = tempfile.mkdtemp(prefix="sasv_enroll_")
    saved_paths = []
    user_enroll_dir = ENROLLED_VOICES_DIR / username
    user_enroll_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    try:
        for idx, upload in enumerate(files):
            suffix = audio_suffix(upload.filename)
            file_path = os.path.join(temp_dir, f"clip_{idx}{suffix}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(upload.file, buffer)
            saved_paths.append(file_path)

            # Persist copy to permanent data/voices/enrolled/{username}/
            perm_path = user_enroll_dir / f"{username}_enroll_{timestamp}_{idx}{suffix}"
            shutil.copy2(file_path, perm_path)

        with _pipeline_lock:
            meta = pipeline.enrollment.enroll_user(
                username=username,
                audio_paths=saved_paths,
                verify_authenticity=True,
                spoof_threshold=-10.0,
            )
            # Only publish a reference after all enrollment checks succeed.
            reference = user_enroll_dir / "reference.wav"
            import soundfile as sf
            samples, rate = sf.read(saved_paths[0], dtype="float32")
            sf.write(reference, samples, rate, subtype="PCM_16")
        return {
            "status": "success",
            "message": f"User '{username}' enrolled successfully.",
            "data": meta,
            "saved_recordings_dir": str(user_enroll_dir),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment error: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/v1/users", tags=["Enrollment"])
def list_enrolled_users():
    """Lists all enrolled speakers and their voiceprint metadata."""
    pipeline = get_pipeline()
    with _pipeline_lock:
        return {"enrolled_users": pipeline.enrollment.list_users()}


@app.delete("/api/v1/users/{username}", tags=["Enrollment"])
def delete_user(username: str):
    """Deletes an enrolled speaker's template and metadata."""
    pipeline = get_pipeline()
    username = validated_username(username)
    with _pipeline_lock:
        deleted = pipeline.enrollment.delete_user(username)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")
    return {"status": "success", "message": f"User '{username}' deleted successfully."}


@app.get("/api/v1/users/{username}/reference", tags=["Enrollment"])
def enrolled_reference(username: str):
    username = validated_username(username)
    with _pipeline_lock:
        if not get_pipeline().enrollment.is_enrolled(username):
            raise HTTPException(404, "Speaker is not enrolled.")
    reference = ENROLLED_VOICES_DIR / username / "reference.wav"
    if not reference.is_file():
        raise HTTPException(404, "No confirmed enrollment reference is available. Re-enroll to save one.")
    return FileResponse(reference, media_type="audio/wav", headers={"Cache-Control": "no-store"})


SERVER_POLICY = os.getenv("SASV_SERVER_POLICY", "strict_security")


@app.get("/api/v1/recordings")
def recording_history():
    return {"recordings": history_store.list_items()}


@app.post("/api/v1/recordings")
def save_recording(username: str = Form("unassigned"), name: str = Form("Recording"), source_type: str = Form("microphone_or_upload"), audio_file: UploadFile = File(...)):
    import io
    import soundfile as sf
    username = validated_username(username)
    content = audio_file.file.read(40 * 1024 * 1024 + 1)
    if not content or len(content) > 40 * 1024 * 1024:
        raise HTTPException(400, "Recording must be nonempty and smaller than 40 MB.")
    try:
        samples, rate = sf.read(io.BytesIO(content))
        if not len(samples) or len(samples) / rate > 60:
            raise ValueError()
    except Exception as exc:
        raise HTTPException(400, "Supply a valid recording of at most 60 seconds.") from exc
    return history_store.save_audio(content, username, name, source_type)


@app.get("/api/v1/recordings/{key}/{kind}")
def recorded_audio(key: str, kind: str):
    if kind not in {"audio", "reference"}:
        raise HTTPException(404, "Recording not found.")
    try:
        path = history_store.path_for(key, ".wav" if kind == "audio" else "_reference.wav")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, "Audio unavailable.")
    return FileResponse(path, media_type="audio/wav")


class DemoVoiceRequest(BaseModel):
    username: str
    session_id: str
    voice: str = "default"


@app.post("/api/v1/demo-voice", tags=["Authentication"])
def demo_voice(request: DemoVoiceRequest):
    username = validated_username(request.username)
    pipeline = get_pipeline()
    with _pipeline_lock:
        challenge = pipeline.challenge.active_challenges.get(request.session_id)
        if not challenge or challenge["username"] != username:
            raise HTTPException(400, "Request a challenge for this speaker first.")
        if challenge["consumed"] or time.time() > challenge["expires_at"]:
            raise HTTPException(400, "Generate a fresh challenge before creating demo audio.")
        phrase = challenge["phrase"]
    if request.voice not in {"default", "female", "male"}:
        raise HTTPException(400, "Unknown demo voice.")
    try:
        content = synthesize_demo(phrase, request.voice)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503, "Local speech synthesis is unavailable. Use an installed Windows speech voice.") from exc
    return Response(content=content, media_type="audio/wav", headers={"Cache-Control": "no-store", "X-Audio-Source": "synthetic-demo"})


@app.post("/api/v1/authenticate", tags=["Authentication"])
def authenticate_user(
    username: str = Form(..., description="Claimed user identifier"),
    session_id: str = Form(..., description="Mandatory single-use challenge session token"),
    audio_file: UploadFile = File(..., description="WAV audio recording responding to challenge"),
    source_type: str = Form("microphone_or_upload"),
    recording_id: str = Form(""),
):
    """Performs end-to-end voice authentication against the enrolled user.
    
    Security Policy:
    - A fresh, unexpired challenge session_id is mandatory.
    - Operating thresholds are strictly server-enforced based on DEV calibration.
    - Policy selection is strictly server-controlled (default: 'strict_security').
    """
    username = validated_username(username)
    pipeline = get_pipeline()
    content = audio_file.file.read(40 * 1024 * 1024 + 1)
    if not content or len(content) > 40 * 1024 * 1024:
        raise HTTPException(400, "Supply a nonempty audio file smaller than 40 MB.")

    import io
    import numpy as np
    import soundfile as sf
    try:
        samples, rate = sf.read(io.BytesIO(content), dtype="float32")
        if samples.size == 0 or not np.isfinite(samples).all():
            raise ValueError("Audio contains no usable samples.")
        if len(samples) / rate > 60:
            raise ValueError("Audio must be at most 60 seconds long.")
    except Exception as exc:
        raise HTTPException(400, "Audio could not be decoded. Record a new response or upload a valid WAV file.") from exc
    with _pipeline_lock:
        try:
            result = pipeline.authenticate(
                username=username,
                audio_source=content,
                session_id=session_id,
                require_challenge=True,
                policy=SERVER_POLICY,
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise HTTPException(500, f"Authentication pipeline error: {str(exc)}") from exc

    # Persist probe audio sample permanently into data/voices/testing/{username}/
    user_test_dir = TESTING_VOICES_DIR / username
    user_test_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    perm_test_path = user_test_dir / f"{username}_test_{timestamp}_{result.decision}.wav"
    try:
        with open(perm_test_path, "wb") as f:
            f.write(content)
    except Exception:
        pass

    resp = asdict(result)
    resp["saved_probe_path"] = str(perm_test_path)
    resp["enforced_policy"] = SERVER_POLICY
    # A client-declared diagnostic label; never an authorization signal.
    resp["source_type"] = "synthetic_demo" if source_type == "synthetic_demo" else "microphone_or_upload"
    try:
        with history_store.LOCK:
            item = history_store.get_item(recording_id) if recording_id else history_store.save_audio(content, username, "Verification recording", resp["source_type"])
            if item["username"] == username and history_store.path_for(item["id"], ".wav").read_bytes() == content:
                item["result"] = resp
                history_store.write_item(item)
                resp["recording_id"] = item["id"]
    except (ValueError, OSError):
        pass
    # Preserve the reason alongside the already archived recording so a
    # transient browser result can be diagnosed without reusing its nonce.
    try:
        perm_test_path.with_suffix(".json").write_text(json.dumps(resp, indent=2), encoding="utf-8")
    except OSError:
        pass
    return resp


@app.get("/api/v1/benchmark", tags=["Research & Evaluation"])
def get_benchmark_results():
    """Returns official SASV 2022 Challenge benchmark evaluation metrics."""
    comp_file = Path("data/benchmark/official_eval_comparison.csv")
    if not comp_file.exists():
        raise HTTPException(status_code=404, detail="Benchmark results not found.")

    df = pd.read_csv(comp_file)
    return {
        "evaluation_partition": "SASV 2022 Official Evaluation Set (102,579 Trials)",
        "results": df.to_dict(orient="records"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, ws="none")
