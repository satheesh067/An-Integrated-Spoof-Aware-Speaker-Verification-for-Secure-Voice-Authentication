"""End-to-End Integrated Spoof-Aware Speaker Verification (SASV) Authentication Pipeline.

Orchestrates all 5 verification layers:
1. Audio Signal Quality Diagnostics (RMS energy, duration, clipping)
2. Dynamic Spoken Challenge & Liveness Verification (Whisper ASR)
3. Anti-Spoof Detection (AASIST raw-waveform CM score)
4. Speaker Verification (ECAPA-TDNN vs enrolled voiceprint template)
5. Integrated SASV Score Fusion & Decision Engine (DEV-calibrated)
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Union

import numpy as np
import torch

from src.core.audio_processor import AudioProcessor
from src.core.challenge_manager import ChallengeManager
from src.core.decision_engine import DecisionResult, SASVDecisionEngine
from src.core.enrollment_manager import EnrollmentManager
from src.models.aasist import AASISTInferencer
from src.models.ecapa import ECAPAInferencer


@dataclass
class AuthenticationResponse:
    decision: str  # "ACCESS_GRANTED" or "ACCESS_DENIED"
    verdict_type: str  # "AUTHENTICATED", "SPEAKER_MISMATCH", "SUSPECTED_SPOOF", "CHALLENGE_FAILED", "MARGINAL_FUSION_REJECTION", "DUAL_CRITERIA_FAILURE", "POOR_AUDIO_QUALITY"
    claimed_user: str
    fused_score: float
    fusion_threshold: float
    speaker_score: float
    speaker_threshold: float
    speaker_matched: bool
    spoof_score: float
    spoof_threshold: float
    spoof_passed: bool
    challenge_status: Dict
    reasons: List[str]
    telemetry: Dict
    calibration_status: str = "EXPERIMENTAL_PILOT_ONLY"
    calibration_source: str = "experimental_pilot_live_audio"
    evidence: Dict = field(default_factory=dict)


class AuthenticationPipeline:
    """Master orchestrator for multi-layer voice authentication."""

    def __init__(
        self,
        audio_processor: Optional[AudioProcessor] = None,
        ecapa_model: Optional[ECAPAInferencer] = None,
        aasist_model: Optional[AASISTInferencer] = None,
        enrollment_manager: Optional[EnrollmentManager] = None,
        challenge_manager: Optional[ChallengeManager] = None,
        decision_engine: Optional[SASVDecisionEngine] = None,
    ):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.audio_processor = audio_processor or AudioProcessor()
        self.ecapa = ecapa_model or ECAPAInferencer()
        self.aasist = aasist_model or AASISTInferencer()
        self.enrollment = enrollment_manager or EnrollmentManager(
            audio_processor=self.audio_processor, ecapa_model=self.ecapa, aasist_model=self.aasist
        )
        self.challenge = challenge_manager or ChallengeManager()
        self.decision_engine = decision_engine or SASVDecisionEngine()

    def authenticate(
        self,
        username: str,
        audio_source: Union[str, bytes],
        session_id: Optional[str] = None,
        require_challenge: bool = True,
        decision_mode: str = "fusion",
        policy: Optional[str] = None,
        speaker_threshold: Optional[float] = None,
        spoof_threshold: Optional[float] = None,
        fusion_threshold: Optional[float] = None,
    ) -> AuthenticationResponse:
        """Executes full SASV authentication for a claimed user."""
        t_start = time.perf_counter()
        username = username.strip().lower().replace(" ", "_")

        # Snapshot original baseline decision engine state before any per-request overrides
        orig_policy = getattr(self.decision_engine, "operating_policy", None)
        orig_spk = self.decision_engine.speaker_threshold
        orig_cm = self.decision_engine.spoof_threshold
        orig_fus = self.decision_engine.fusion_threshold
        orig_gate = getattr(self.decision_engine, "require_cm_gate", False)

        try:
            if policy is not None and hasattr(self.decision_engine, "apply_policy"):
                self.decision_engine.apply_policy(policy)

            if speaker_threshold is not None:
                self.decision_engine.speaker_threshold = speaker_threshold
            if spoof_threshold is not None:
                self.decision_engine.spoof_threshold = spoof_threshold
            if fusion_threshold is not None:
                self.decision_engine.fusion_threshold = fusion_threshold

            if self.device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(self.device)

            # ------------------------------------------------------------------
            # Stage 1: Audio Signal Quality Diagnostics & Standardization
            # ------------------------------------------------------------------
            # Browser uploads, enrollment, and calibration must use exactly the
            # same input scale. A separate bytes path previously skipped gain
            # normalization, shifting CM scores far below calibrated thresholds.
            waveform, meta = self.audio_processor.load_and_preprocess(audio_source)
            data = waveform.numpy()

            # Check usable audio energy
            if meta["rms_energy"] < 0.003:
                return self._build_denial(
                    username=username,
                    verdict="POOR_AUDIO_QUALITY",
                    reason=f"Audio signal is too faint or silent (RMS: {meta['rms_energy']:.5f} < 0.003).",
                    t_start=t_start,
                    audio_meta=meta,
                )

            # ------------------------------------------------------------------
            # Stage 2: Dynamic Spoken Challenge & Liveness Check
            # ------------------------------------------------------------------
            challenge_report = {"required": require_challenge, "passed": True}
            if require_challenge:
                if not session_id:
                    return self._build_denial(
                        username=username,
                        verdict="CHALLENGE_FAILED",
                        reason="Missing session challenge ID. A fresh challenge must be requested before authentication.",
                        t_start=t_start,
                        audio_meta=meta,
                    )

                ch_res = self.challenge.verify_challenge(
                    session_id=session_id,
                    username=username,
                    audio_input=data,
                )
                challenge_report = ch_res

                if not ch_res["passed"]:
                    return self._build_denial(
                        username=username,
                        verdict="CHALLENGE_FAILED",
                        reason=ch_res["reason"],
                        t_start=t_start,
                        audio_meta=meta,
                        challenge_report=challenge_report,
                    )

            # ------------------------------------------------------------------
            # Stage 3: Anti-Spoof Detection (AASIST)
            # ------------------------------------------------------------------
            cm_result = self.aasist.score_audio(waveform)
            spoof_score = cm_result["cm_score"]
            spoof_passed = spoof_score >= self.decision_engine.spoof_threshold

            # ------------------------------------------------------------------
            # Stage 4: Speaker Verification (ECAPA-TDNN)
            # ------------------------------------------------------------------
            template = self.enrollment.get_template(username)
            if template is None:
                return self._build_denial(
                    username=username,
                    verdict="IMPOSTOR_HUMAN",
                    reason=f"User '{username}' is not enrolled in the system. Please enroll before authenticating.",
                    t_start=t_start,
                    audio_meta=meta,
                    spoof_score=spoof_score,
                    challenge_report=challenge_report,
                )

            test_emb, asv_timing = self.ecapa.extract_embedding(waveform)
            if isinstance(test_emb, torch.Tensor):
                test_emb = test_emb.detach().cpu().numpy().squeeze()
            test_emb_norm = test_emb / (np.linalg.norm(test_emb) + 1e-12)
            speaker_score = float(np.dot(template, test_emb_norm))
            speaker_matched = speaker_score >= self.decision_engine.speaker_threshold

            # ------------------------------------------------------------------
            # Stage 5: Integrated SASV Decision Engine
            # ------------------------------------------------------------------
            if decision_mode == "tandem":
                decision_res: DecisionResult = self.decision_engine.evaluate_tandem(
                    speaker_score=speaker_score,
                    spoof_score=spoof_score,
                    audio_metadata=meta,
                )
            else:
                decision_res: DecisionResult = self.decision_engine.evaluate_fusion(
                    speaker_score=speaker_score,
                    spoof_score=spoof_score,
                    audio_metadata=meta,
                )

            total_latency_ms = (time.perf_counter() - t_start) * 1000
            peak_vram_mb = 0.0
            if self.device.type == "cuda":
                peak_vram_mb = torch.cuda.max_memory_allocated(self.device) / (1024 * 1024)

            cal_status = getattr(self.decision_engine, "calibration_status", "EXPERIMENTAL_PILOT_ONLY")
            cal_source = getattr(self.decision_engine, "calibration_source", "experimental_pilot_live_audio")

            telemetry = {
                "device": str(self.device),
                "device_name": torch.cuda.get_device_name(self.device) if self.device.type == "cuda" else "CPU",
                "calibration_status": cal_status,
                "calibration_source": cal_source,
                "ecapa_latency_ms": asv_timing["latency_ms"],
                "aasist_latency_ms": cm_result["latency_ms"],
                "asr_latency_ms": challenge_report.get("asr_latency_ms", 0.0),
                "total_latency_ms": round(total_latency_ms, 2),
                "peak_vram_mb": round(peak_vram_mb, 2),
                "audio_metadata": meta,
            }

            return AuthenticationResponse(
                decision=decision_res.decision,
                verdict_type=decision_res.verdict_type,
                claimed_user=username,
                fused_score=decision_res.decision_score,
                fusion_threshold=self.decision_engine.fusion_threshold,
                speaker_score=round(speaker_score, 4),
                speaker_threshold=self.decision_engine.speaker_threshold,
                speaker_matched=speaker_matched,
                spoof_score=round(spoof_score, 4),
                spoof_threshold=self.decision_engine.spoof_threshold,
                spoof_passed=spoof_passed,
                challenge_status=challenge_report,
                reasons=decision_res.reasons,
                telemetry=telemetry,
                calibration_status=cal_status,
                calibration_source=cal_source,
                evidence={
                    "speaker": {
                        "reference_embedding": template.tolist(),
                        "probe_embedding": test_emb_norm.tolist(),
                        "description": "L2-normalized ECAPA features; feature indices are not audio timestamps.",
                    },
                    "countermeasure": {
                        "bona_fide_logit": cm_result.get("bona_fide_logit"),
                        "spoof_logit": cm_result.get("spoof_logit"),
                        "input_start_seconds": 0,
                        "input_end_seconds": min(len(data) / 16000, 64600 / 16000),
                        "short_clip_repeated": len(data) < 64600,
                        "description": "Whole model-input score; no localized spoof prediction is produced.",
                    },
                    "fusion": {
                        "speaker_weight": self.decision_engine.w_asv,
                        "countermeasure_weight": self.decision_engine.w_cm,
                        "bias": self.decision_engine.bias,
                        "speaker_contribution": self.decision_engine.w_asv * speaker_score,
                        "countermeasure_contribution": self.decision_engine.w_cm * spoof_score,
                        "require_cm_gate": self.decision_engine.require_cm_gate,
                    },
                },
            )

        finally:
            # Unconditionally restore original engine baseline state on ANY return or exception
            if orig_policy is not None and hasattr(self.decision_engine, "apply_policy"):
                self.decision_engine.apply_policy(orig_policy)
            self.decision_engine.speaker_threshold = orig_spk
            self.decision_engine.spoof_threshold = orig_cm
            self.decision_engine.fusion_threshold = orig_fus
            self.decision_engine.require_cm_gate = orig_gate

    def _build_denial(
        self,
        username: str,
        verdict: str,
        reason: str,
        t_start: float,
        audio_meta: Dict,
        spoof_score: float = -999.0,
        speaker_score: float = -999.0,
        challenge_report: Optional[Dict] = None,
    ) -> AuthenticationResponse:
        total_latency_ms = (time.perf_counter() - t_start) * 1000
        peak_vram_mb = 0.0
        if self.device.type == "cuda":
            peak_vram_mb = torch.cuda.max_memory_allocated(self.device) / (1024 * 1024)

        cal_status = getattr(self.decision_engine, "calibration_status", "EXPERIMENTAL_PILOT_ONLY")
        cal_source = getattr(self.decision_engine, "calibration_source", "experimental_pilot_live_audio")

        return AuthenticationResponse(
            decision="ACCESS_DENIED",
            verdict_type=verdict,
            claimed_user=username,
            fused_score=-999.0,
            fusion_threshold=self.decision_engine.fusion_threshold,
            speaker_score=round(speaker_score, 4),
            speaker_threshold=self.decision_engine.speaker_threshold,
            speaker_matched=False,
            spoof_score=round(spoof_score, 4),
            spoof_threshold=self.decision_engine.spoof_threshold,
            spoof_passed=False,
            challenge_status=challenge_report or {"required": True, "passed": False, "reason": reason},
            reasons=[reason],
            telemetry={
                "device": str(self.device),
                "device_name": torch.cuda.get_device_name(self.device) if self.device.type == "cuda" else "CPU",
                "calibration_status": cal_status,
                "calibration_source": cal_source,
                "total_latency_ms": round(total_latency_ms, 2),
                "peak_vram_mb": round(peak_vram_mb, 2),
                "audio_metadata": audio_meta,
            },
            calibration_status=cal_status,
            calibration_source=cal_source,
        )


if __name__ == "__main__":
    pipeline = AuthenticationPipeline()
    print("AuthenticationPipeline initialized successfully on:", pipeline.device)
