import os
import sys
sys.path.insert(0, ".")
import soundfile as sf
import numpy as np
from pathlib import Path
from src.models.aasist import AASISTInferencer
from src.core.audio_processor import AudioProcessor

model = AASISTInferencer()
model.load_weights()
ap = AudioProcessor()

files = sorted(Path("data/voices/enrolled/sam").glob("*20261012_123625*.wav"))
for f in files:
    waveform, meta = ap.load_and_preprocess(str(f))
    cm = model.score_audio(waveform)
    print(f"{f.name}: dur={meta['duration_sec']:.2f}s, sr={meta['sample_rate']}, rms={meta['rms_energy']:.5f}, peak={meta['peak_amplitude']:.5f}, cm_score={cm['cm_score']:.3f}")

