"""Speaker Enrollment Manager.

Handles multi-utterance speaker enrollment:
- Validates audio signal quality (RMS energy, duration, sample rate).
- Validates anti-spoofing (enrollment clips must be bona fide human speech).
- Extracts and L2-normalizes 192-d ECAPA-TDNN speaker embeddings.
- Computes and persists average voiceprint templates and enrollment metadata.
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from src.core.audio_processor import AudioProcessor
from src.models.aasist import AASISTInferencer
from src.models.ecapa import ECAPAInferencer


@dataclass
class EnrollmentMetadata:
    username: str
    num_recordings: int
    created_at: str
    embedding_dim: int
    mean_speaker_norm: float
    enrollment_quality: Dict
    audio_files: List[str]


class EnrollmentManager:
    """Manages secure multi-session voiceprint template enrollment."""

    def __init__(
        self,
        storage_dir: str = "data/enrolled_users",
        audio_processor: Optional[AudioProcessor] = None,
        ecapa_model: Optional[ECAPAInferencer] = None,
        aasist_model: Optional[AASISTInferencer] = None,
        min_enrollment_clips: int = 1,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.audio_processor = audio_processor or AudioProcessor()
        self.ecapa = ecapa_model or ECAPAInferencer()
        self.aasist = aasist_model or AASISTInferencer()
        self.min_enrollment_clips = min_enrollment_clips

    def enroll_user(
        self,
        username: str,
        audio_paths: List[str],
        verify_authenticity: bool = True,
        spoof_threshold: float = -6.5,
    ) -> Dict:
        """Enrolls a speaker using multiple audio recordings.

        Parameters
        ----------
        username : str
            Unique speaker identifier.
        audio_paths : List[str]
            List of audio file paths provided for enrollment.
        verify_authenticity : bool
            If True, verifies that enrollment clips pass AASIST anti-spoof check.
        spoof_threshold : float
            Minimum AASIST CM score required for enrollment clips (default: -6.5).
        """
        if len(audio_paths) < self.min_enrollment_clips:
            raise ValueError(
                f"At least {self.min_enrollment_clips} audio recording(s) required for enrollment, got {len(audio_paths)}"
            )

        username = username.strip().lower().replace(" ", "_")
        embeddings = []
        clip_reports = []

        for p in audio_paths:
            waveform, meta = self.audio_processor.load_and_preprocess(p)

            # 1. Quality check
            if meta["rms_energy"] < 0.003:
                raise ValueError(f"Recording '{os.path.basename(p)}' is too faint or silent (RMS: {meta['rms_energy']:.5f})")

            # 2. Anti-spoof check on enrollment data
            if verify_authenticity:
                cm_result = self.aasist.score_audio(waveform)
                if cm_result["cm_score"] < spoof_threshold:
                    raise ValueError(
                        f"Enrollment rejected: Audio '{os.path.basename(p)}' failed anti-spoof verification "
                        f"(CM score: {cm_result['cm_score']:.3f} < threshold: {spoof_threshold:.3f}). Only bona fide human speech can be enrolled."
                    )
                clip_reports.append({"file": os.path.basename(p), "cm_score": cm_result["cm_score"], "rms": meta["rms_energy"]})
            else:
                clip_reports.append({"file": os.path.basename(p), "rms": meta["rms_energy"]})

            # 3. Extract ECAPA-TDNN embedding
            emb, _ = self.ecapa.extract_embedding(waveform)
            if isinstance(emb, torch.Tensor):
                emb = emb.detach().cpu().numpy().squeeze()
            # Normalize single embedding
            emb_norm = emb / (np.linalg.norm(emb) + 1e-12)
            embeddings.append(emb_norm)

        # 4. Average and re-normalize template
        mean_embedding = np.mean(embeddings, axis=0)
        voiceprint_template = mean_embedding / (np.linalg.norm(mean_embedding) + 1e-12)

        # 5. Persist template and metadata
        template_file = self.storage_dir / f"{username}_template.npy"
        meta_file = self.storage_dir / f"{username}_meta.json"

        np.save(template_file, voiceprint_template.astype(np.float32))

        metadata = {
            "username": username,
            "num_recordings": len(audio_paths),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "embedding_dim": int(voiceprint_template.shape[0]),
            "clip_reports": clip_reports,
            "template_file": str(template_file),
        }

        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def get_template(self, username: str) -> Optional[np.ndarray]:
        """Loads the enrolled voiceprint template for a user."""
        username = username.strip().lower().replace(" ", "_")
        template_file = self.storage_dir / f"{username}_template.npy"
        if not template_file.exists():
            return None
        return np.load(template_file)

    def is_enrolled(self, username: str) -> bool:
        """Checks if a user is currently enrolled."""
        username = username.strip().lower().replace(" ", "_")
        template_file = self.storage_dir / f"{username}_template.npy"
        return template_file.exists()

    def list_users(self) -> List[Dict]:
        """Lists all enrolled users and their enrollment summary."""
        users = []
        for meta_file in self.storage_dir.glob("*_meta.json"):
            try:
                with open(meta_file, "r") as f:
                    users.append(json.load(f))
            except Exception:
                continue
        return users

    def delete_user(self, username: str) -> bool:
        """Removes a user's enrolled template and metadata."""
        username = username.strip().lower().replace(" ", "_")
        template_file = self.storage_dir / f"{username}_template.npy"
        meta_file = self.storage_dir / f"{username}_meta.json"
        deleted = False
        if template_file.exists():
            template_file.unlink()
            deleted = True
        if meta_file.exists():
            meta_file.unlink()
            deleted = True
        return deleted


if __name__ == "__main__":
    manager = EnrollmentManager()
    pilot_audio = "data/pilot/audio/speaker_alpha_enroll.wav"
    if os.path.exists(pilot_audio):
        print(f"Enrolling pilot speaker 'speaker_alpha' with {pilot_audio}...")
        meta = manager.enroll_user("speaker_alpha", [pilot_audio], verify_authenticity=False)
        print("Enrollment successful:", meta)
        print("Enrolled users:", [u["username"] for u in manager.list_users()])
