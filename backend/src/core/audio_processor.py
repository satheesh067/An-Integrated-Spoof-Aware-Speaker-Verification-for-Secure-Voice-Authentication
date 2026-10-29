"""Audio Preprocessing Module for SASV.

Ensures standard 16 kHz mono format, checks signal amplitude/clipping,
and provides consistent windowing across models.
"""

import os
import io
from typing import Tuple, Optional
import numpy as np
import soundfile as sf
import torch


class AudioProcessor:
    def __init__(self, target_sample_rate: int = 16000, target_length_sec: float = 4.0):
        self.target_sample_rate = target_sample_rate
        self.target_samples = int(target_sample_rate * target_length_sec)

    def load_and_preprocess(
        self, file_path: str | bytes, max_duration_sec: Optional[float] = 10.0
    ) -> Tuple[torch.Tensor, dict]:
        """Loads an audio file and standardizes it for model inference.

        Returns:
            waveform: Tensor of shape (samples,) at 16kHz mono.
            metadata: Audio diagnostics (original_sr, duration, rms, is_clipped).
        """
        if isinstance(file_path, str) and not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        source = io.BytesIO(file_path) if isinstance(file_path, bytes) else file_path
        data, sr = sf.read(source, dtype="float32")
        if data.size == 0 or not np.isfinite(data).all():
            raise ValueError("Audio contains no usable finite samples.")

        # Convert multi-channel to mono
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Basic signal statistics
        peak = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
        rms = float(np.sqrt(np.mean(data**2))) if len(data) > 0 else 0.0
        is_clipped = peak >= 0.999

        # Resample to 16kHz if necessary
        if sr != self.target_sample_rate:
            import scipy.signal

            num_target_samples = int(len(data) * self.target_sample_rate / sr)
            data = scipy.signal.resample(data, num_target_samples).astype(np.float32)

        # Peak normalization if signal is not silent
        if peak > 1e-4:
            data = data / max(peak, 1e-4) * 0.95

        waveform = torch.from_numpy(data).float()

        metadata = {
            "original_sr": sr,
            "target_sr": self.target_sample_rate,
            "duration_sec": round(len(waveform) / self.target_sample_rate, 2),
            "rms_energy": round(rms, 4),
            "peak_amplitude": round(peak, 4),
            "is_clipped": is_clipped,
            "sample_rate": self.target_sample_rate,
            "duration_seconds": round(len(waveform) / self.target_sample_rate, 2),
            "preprocessing": "mono_16khz_peak_0.95_v1",
            "normalization_gain": float(0.95 / peak) if peak > 1e-4 else 1.0,
        }

        return waveform, metadata

    def prepare_aasist_window(self, waveform: torch.Tensor, cut_length: int = 64600) -> torch.Tensor:
        """Pads or tiles audio to exact 64,600 samples (~4.03 sec at 16kHz) for AASIST.

        If audio is longer, cuts first 64,600 samples or can be windowed.
        Returns tensor of shape (1, cut_length).
        """
        samples = waveform.size(0)
        if samples < cut_length:
            # Tile waveform repeatedly until cut_length
            repeat_factor = int(np.ceil(cut_length / samples))
            padded = waveform.repeat(repeat_factor)[:cut_length]
            return padded.unsqueeze(0)
        elif samples > cut_length:
            return waveform[:cut_length].unsqueeze(0)
        else:
            return waveform.unsqueeze(0)
