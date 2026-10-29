import sys
sys.path.insert(0, ".")
import soundfile as sf
import numpy as np
from pathlib import Path
from src.core.audio_processor import AudioProcessor
from src.core.challenge_manager import ChallengeManager

ap = AudioProcessor()
cm = ChallengeManager()

files = sorted(Path("data/voices/enrolled/sam").glob("*20261012_123625*.wav"))
for f in files:
    data, sr = sf.read(str(f))
    trans = cm.whisper_model.transcribe(data.astype(np.float32), language="en", fp16=False)["text"]
    active = np.where(np.abs(data) > 0.01)[0]
    start_sec = active[0] / sr if len(active) else 0
    end_sec = active[-1] / sr if len(active) else 0
    print(f"\n{f.name}:")
    print(f"  Transcript: '{trans.strip()}'")
    print(f"  Speech activity: {start_sec:.2f}s to {end_sec:.2f}s (Total: {len(data)/sr:.2f}s)")
