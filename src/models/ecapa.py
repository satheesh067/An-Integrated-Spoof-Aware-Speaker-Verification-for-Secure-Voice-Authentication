"""ECAPA-TDNN Speaker Verification Module using SpeechBrain.

Provides speaker embedding extraction (192-dim) and cosine similarity scoring
with latency and VRAM telemetry.
"""

import os
import time
from typing import Dict, Optional, List, Tuple
import numpy as np
import torch
import torch.nn.functional as F


class ECAPAInferencer:
    """Wrapper for SpeechBrain ECAPA-TDNN speaker encoder."""

    def __init__(self, device: Optional[torch.device] = None, run_opts: Optional[dict] = None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.classifier = None
        self.model_source = "speechbrain/spkrec-ecapa-voxceleb"
        self.embedding_dim = 192

    def load_model(self, save_dir: str = "models/checkpoints/ecapa_local"):
        """Loads pretrained SpeechBrain ECAPA-TDNN weights."""
        os.makedirs(save_dir, exist_ok=True)
        device_str = "cuda" if self.device.type == "cuda" else "cpu"

        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy

        self.classifier = EncoderClassifier.from_hparams(
            source=self.model_source, savedir=save_dir, run_opts={"device": device_str},
            local_strategy=LocalStrategy.COPY,
        )

    def extract_embedding(self, waveform: torch.Tensor) -> Tuple[torch.Tensor, dict]:
        """Extracts normalized 192-d speaker embedding.

        waveform: Tensor of shape (samples,) or (1, samples) at 16kHz.
        """
        if self.classifier is None:
            self.load_model()

        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        waveform = waveform.to(self.device)

        if self.device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(self.device)
            torch.cuda.synchronize(self.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            embedding = self.classifier.encode_batch(waveform).squeeze()
            # Length normalization (unit sphere projection)
            norm = torch.norm(embedding, p=2, dim=-1, keepdim=True) + 1e-10
            embedding = embedding / norm

        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
            peak_vram_mb = torch.cuda.max_memory_allocated(self.device) / (1024 * 1024)
        else:
            peak_vram_mb = 0.0

        latency_ms = (time.perf_counter() - t0) * 1000

        return embedding, {
            "latency_ms": round(latency_ms, 2),
            "peak_vram_mb": round(peak_vram_mb, 2),
            "device": str(self.device),
        }

    def compute_similarity(
        self, test_embedding: torch.Tensor, enrolled_embedding: torch.Tensor
    ) -> float:
        """Computes cosine similarity between two normalized embeddings [-1.0, 1.0]."""
        cos_sim = F.cosine_similarity(test_embedding.view(1, -1), enrolled_embedding.view(1, -1), dim=1)
        return float(cos_sim.item())
