"""Start VoiceGuard with Windows certificate trust and optional model warmup."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
# Standard HTTPS downloads use the same verified system certificate store.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# Use the system's trusted CA store, retaining normal certificate validation.
import truststore
truststore.inject_into_ssl()

import uvicorn
from src.api import server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", action="store_true", help="Load all speech models before accepting requests")
    args = parser.parse_args()
    if args.warmup:
        print("Loading ECAPA, AASIST and Whisper before serving requests…", flush=True)
        pipeline = server.get_pipeline()
        pipeline.ecapa.load_model()
        pipeline.aasist.load_weights()
        pipeline.challenge.whisper_model
        server.MODELS_READY = True
        print("All speech models loaded. VoiceGuard is ready.", flush=True)
    uvicorn.run(server.app, host="127.0.0.1", port=8000, ws="none")
