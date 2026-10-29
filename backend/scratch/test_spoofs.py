import sys
sys.path.insert(0, ".")
from pathlib import Path
from src.models.aasist import AASISTInferencer
from src.core.audio_processor import AudioProcessor

m = AASISTInferencer()
m.load_weights()
ap = AudioProcessor()

for p in list(Path("data").rglob("*spoof*.wav"))[:5]:
    wf, _ = ap.load_and_preprocess(str(p))
    print(f"{p.name}: cm_score={m.score_audio(wf)['cm_score']:.3f}")
