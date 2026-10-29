"""Integrated Spoof-Aware Speaker Verification (SASV) Decision Engine.

Supports both:
1. Learned Score Fusion Engine (Single fused decision score trained on DEV)
2. Cascaded Tandem Decision Engine (Dual thresholding with explicit rejection reasons)

Reports raw decision scores and explicit verdicts without unverified probability claims.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class DecisionResult:
    decision: str  # "ACCESS_GRANTED" or "ACCESS_DENIED"
    verdict_type: str  # "AUTHENTICATED", "MARGINAL_FUSION_REJECTION", "SUSPECTED_SPOOF", "SPEAKER_MISMATCH", "DUAL_CRITERIA_FAILURE", "POOR_AUDIO_QUALITY"
    decision_score: float  # Fused decision score or primary score
    speaker_score: float  # Raw ECAPA-TDNN cosine similarity
    spoof_score: float  # Raw AASIST CM score
    speaker_matched: bool
    spoof_passed: bool
    threshold_used: float
    reasons: List[str]
    metadata: Dict
    risk_score: float = 0.0


class SASVDecisionEngine:
    """Production decision engine for SASV with separate live and offline operating points."""

    def __init__(
        self,
        fusion_metadata_path: str = "models/fusion_metadata.json",
        live_metadata_path: str = "models/live_pipeline_metadata.json",
        operating_policy: str = "strict_security",  # "strict_security" or "balanced"
        calibration_mode: str = "live",  # "live" or "offline_benchmark"
        speaker_threshold: Optional[float] = None,
        spoof_threshold: Optional[float] = None,
        fusion_threshold: Optional[float] = None,
        require_cm_gate: Optional[bool] = None,
        min_rms_energy: float = 0.003,
    ):
        self.operating_policy = operating_policy
        self.calibration_mode = calibration_mode
        self.min_rms_energy = min_rms_energy
        self.calibration_status = "UNCALIBRATED"
        self.policies = {}
        self.require_cm_gate = require_cm_gate if require_cm_gate is not None else (operating_policy == "strict_security")

        # 1. Offline SASV 2022 Benchmark Operating Points (Precomputed representation space)
        # Note: DEV-EER is 0.7233; DEV-Strict-Security is 1.3610. These apply strictly to the offline benchmark.
        self.offline_benchmark_eer_threshold = 0.7233
        self.offline_benchmark_strict_threshold = 1.3610

        meta_path = Path(fusion_metadata_path)
        live_path = Path(live_metadata_path)

        if calibration_mode == "live" and live_path.exists():
            with open(live_path, "r") as f:
                l_meta = json.load(f)
            self.calibration_status = l_meta.get("status", "EXPERIMENTAL_PILOT_ONLY")
            self.calibration_source = "experimental_pilot_live_audio"
            weights = l_meta.get("trained_fusion_weights", l_meta.get("live_weights", {}))
            self.w_asv = weights.get("w_asv", 12.7265)
            self.w_cm = weights.get("w_cm", 0.1767)
            self.bias = weights.get("bias", -3.4780)
            policies = l_meta.get("operating_policies", l_meta.get("operational_thresholds", {}))
            self.policies = policies
            if operating_policy not in policies:
                raise ValueError(f"Unknown operating policy: {operating_policy}")
            policy_cfg = policies[operating_policy]
            self.speaker_threshold = speaker_threshold if speaker_threshold is not None else policy_cfg.get("speaker_threshold", 0.35)
            self.spoof_threshold = spoof_threshold if spoof_threshold is not None else policy_cfg.get("spoof_threshold", -3.50)
            self.fusion_threshold = fusion_threshold if fusion_threshold is not None else policy_cfg.get("fusion_threshold", 0.4314)
            self.require_cm_gate = require_cm_gate if require_cm_gate is not None else policy_cfg.get(
                "require_cm_gate", (operating_policy == "strict_security")
            )
            self.has_fusion_model = True

        elif meta_path.exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
            self.calibration_source = "offline_benchmark_representations"
            self.w_asv = meta["weights"]["w_asv"]
            self.w_cm = meta["weights"]["w_cm"]
            self.bias = meta["weights"]["bias"]
            self.eer_threshold = meta["dev_metrics"]["eer_threshold"]
            self.strict_security_threshold = meta["dev_metrics"].get("strict_security_threshold", 1.3610)
            self.speaker_threshold = speaker_threshold if speaker_threshold is not None else 0.5891
            self.spoof_threshold = spoof_threshold if spoof_threshold is not None else -0.5878
            self.fusion_threshold = fusion_threshold if fusion_threshold is not None else (
                self.strict_security_threshold if operating_policy == "strict_security" else self.eer_threshold
            )
            self.require_cm_gate = require_cm_gate if require_cm_gate is not None else (operating_policy == "strict_security")
            self.has_fusion_model = True
        else:
            self.calibration_source = "default_fallback"
            self.w_asv = 3.0
            self.w_cm = 0.20
            self.bias = -1.0
            self.speaker_threshold = speaker_threshold if speaker_threshold is not None else 0.35
            self.spoof_threshold = spoof_threshold if spoof_threshold is not None else 0.50
            self.fusion_threshold = fusion_threshold if fusion_threshold is not None else 0.60
            self.has_fusion_model = False

        if not self.policies:
            self.policies = {
                name: {
                    "speaker_threshold": self.speaker_threshold,
                    "spoof_threshold": self.spoof_threshold,
                    "fusion_threshold": (
                        self.strict_security_threshold if name == "strict_security" else self.eer_threshold
                    ) if self.has_fusion_model else self.fusion_threshold,
                    "require_cm_gate": name == "strict_security",
                }
                for name in ("balanced", "strict_security")
            }
            if operating_policy not in self.policies:
                raise ValueError(f"Unknown operating policy: {operating_policy}")

    def apply_policy(self, policy_name: str):
        """Apply a known calibrated policy; reject unknown names without mutation."""
        policies = getattr(self, "policies", {})
        if policy_name not in policies:
            if not policies and policy_name == self.operating_policy:
                return
            raise ValueError(f"Unknown operating policy: {policy_name}")
        config = policies[policy_name]
        self.operating_policy = policy_name
        self.speaker_threshold = config.get("speaker_threshold", self.speaker_threshold)
        self.spoof_threshold = config.get("spoof_threshold", self.spoof_threshold)
        self.fusion_threshold = config.get("fusion_threshold", self.fusion_threshold)
        self.require_cm_gate = config.get("require_cm_gate", policy_name == "strict_security")

    def evaluate_fusion(
        self,
        speaker_score: float,
        spoof_score: float,
        audio_metadata: Optional[Dict] = None,
    ) -> DecisionResult:
        """Evaluates trial using the DEV-trained Learned Score Fusion model."""
        audio_metadata = audio_metadata or {}
        rms = audio_metadata.get("rms_energy", 0.05)
        if rms < self.min_rms_energy:
            return DecisionResult(
                decision="ACCESS_DENIED",
                verdict_type="POOR_AUDIO_QUALITY",
                decision_score=-999.0,
                speaker_score=round(speaker_score, 4),
                spoof_score=round(spoof_score, 4),
                speaker_matched=False,
                spoof_passed=False,
                threshold_used=self.fusion_threshold,
                reasons=[f"Audio signal is too faint or silent (RMS: {rms:.5f} < {self.min_rms_energy})"],
                metadata=audio_metadata,
            )

        fused_score = self.w_asv * speaker_score + self.w_cm * spoof_score + self.bias
        speaker_matched = speaker_score >= self.speaker_threshold
        spoof_passed = spoof_score >= self.spoof_threshold

        # Security Safeguard: If mandatory anti-spoof gate is active, a CM failure blocks access
        if self.require_cm_gate and not spoof_passed:
            decision = "ACCESS_DENIED"
            verdict = "SUSPECTED_SPOOF"
            reasons = [
                f"Anti-spoof verification did not pass: The countermeasure score is below the required threshold "
                f"(CM: {spoof_score:.3f} < {self.spoof_threshold:.3f}), blocking access despite "
                f"voice similarity ({speaker_score:.3f}) and fused score ({fused_score:.3f} vs {self.fusion_threshold:.3f}). "
                "Genuine speech can also receive a low countermeasure score; this result does not establish that the recording is synthetic or replayed."
            ]
            return DecisionResult(
                decision=decision,
                verdict_type=verdict,
                decision_score=round(fused_score, 4),
                speaker_score=round(speaker_score, 4),
                spoof_score=round(spoof_score, 4),
                speaker_matched=speaker_matched,
                spoof_passed=spoof_passed,
                threshold_used=self.fusion_threshold,
                reasons=reasons,
                metadata=audio_metadata,
            )

        granted = fused_score >= self.fusion_threshold

        reasons = []
        if granted:
            verdict = "AUTHENTICATED"
            decision = "ACCESS_GRANTED"
            reasons.append(
                f"Authentication successful: Fused SASV decision score ({fused_score:.3f}) meets operational threshold ({self.fusion_threshold:.3f}). "
                f"[ASV similarity: {speaker_score:.3f}, CM score: {spoof_score:.3f}]"
            )
        else:
            decision = "ACCESS_DENIED"
            if speaker_matched and spoof_passed:
                # Both passed standalone gates, but the linear combination fell short of fusion threshold
                verdict = "MARGINAL_FUSION_REJECTION"
                reasons.append(
                    f"Insufficient Fused Confidence: Fused score ({fused_score:.3f} < {self.fusion_threshold:.3f}) fell below the policy threshold, "
                    f"although individual speaker ({speaker_score:.3f} >= {self.speaker_threshold:.3f}) and anti-spoof ({spoof_score:.3f} >= {self.spoof_threshold:.3f}) scores met standalone minimums."
                )
            elif speaker_matched and not spoof_passed:
                verdict = "SUSPECTED_SPOOF"
                reasons.append(
                    f"Potential synthetic speech / spoof: Voice similarity passed ({speaker_score:.3f} >= {self.speaker_threshold:.3f}), "
                    f"but anti-spoof detector flagged acoustic artifacts (CM: {spoof_score:.3f} < {self.spoof_threshold:.3f})."
                )
            elif not speaker_matched and spoof_passed:
                verdict = "SPEAKER_MISMATCH"
                reasons.append(
                    f"Speaker identity mismatch: Anti-spoof check passed (CM: {spoof_score:.3f} >= {self.spoof_threshold:.3f}), "
                    f"but voiceprint similarity fell below threshold ({speaker_score:.3f} < {self.speaker_threshold:.3f})."
                )
            else:
                verdict = "DUAL_CRITERIA_FAILURE"
                reasons.append(
                    f"Dual Check Failure: Fused score ({fused_score:.3f} < {self.fusion_threshold:.3f}) failed. "
                    f"Neither speaker similarity ({speaker_score:.3f} < {self.speaker_threshold:.3f}) nor anti-spoofing ({spoof_score:.3f} < {self.spoof_threshold:.3f}) met criteria."
                )

        return DecisionResult(
            decision=decision,
            verdict_type=verdict,
            decision_score=round(fused_score, 4),
            speaker_score=round(speaker_score, 4),
            spoof_score=round(spoof_score, 4),
            speaker_matched=speaker_matched,
            spoof_passed=spoof_passed,
            threshold_used=self.fusion_threshold,
            reasons=reasons,
            metadata=audio_metadata,
        )

    def evaluate_tandem(
        self,
        speaker_score: float,
        spoof_score: float,
        audio_metadata: Optional[Dict] = None,
    ) -> DecisionResult:
        """Evaluates trial using independent two-stage tandem thresholds."""
        audio_metadata = audio_metadata or {}
        rms = audio_metadata.get("rms_energy", 0.05)
        if rms < self.min_rms_energy:
            return DecisionResult(
                decision="ACCESS_DENIED",
                verdict_type="POOR_AUDIO_QUALITY",
                decision_score=round(speaker_score, 4),
                speaker_score=round(speaker_score, 4),
                spoof_score=round(spoof_score, 4),
                speaker_matched=False,
                spoof_passed=False,
                threshold_used=self.speaker_threshold,
                reasons=[f"Audio signal is too faint or silent (RMS: {rms:.5f} < {self.min_rms_energy})"],
                metadata=audio_metadata,
            )

        speaker_matched = speaker_score >= self.speaker_threshold
        spoof_passed = spoof_score >= self.spoof_threshold

        reasons = []
        if speaker_matched and spoof_passed:
            decision = "ACCESS_GRANTED"
            verdict = "AUTHENTICATED"
            reasons.append(
                f"Access Granted: Speaker verified (Cosine {speaker_score:.3f} >= {self.speaker_threshold:.3f}) "
                f"and anti-spoof passed (CM {spoof_score:.3f} >= {self.spoof_threshold:.3f})."
            )
        elif not speaker_matched and spoof_passed:
            decision = "ACCESS_DENIED"
            verdict = "SPEAKER_MISMATCH"
            reasons.append(
                f"Speaker Mismatch: Anti-spoof check passed, but voice similarity ({speaker_score:.3f}) "
                f"fell below required threshold ({self.speaker_threshold:.3f})."
            )
        elif speaker_matched and not spoof_passed:
            decision = "ACCESS_DENIED"
            verdict = "SUSPECTED_SPOOF"
            reasons.append(
                f"Suspected Spoof: Claimed identity matched ({speaker_score:.3f} >= {self.speaker_threshold:.3f}), "
                f"but anti-spoof detector flagged synthetic artifacts ({spoof_score:.3f} < {self.spoof_threshold:.3f})."
            )
        else:
            decision = "ACCESS_DENIED"
            verdict = "DUAL_CRITERIA_FAILURE"
            reasons.append(
                f"Dual Failure: Failed speaker threshold ({speaker_score:.3f} < {self.speaker_threshold:.3f}) "
                f"and failed spoof threshold ({spoof_score:.3f} < {self.spoof_threshold:.3f})."
            )

        return DecisionResult(
            decision=decision,
            verdict_type=verdict,
            decision_score=round(speaker_score, 4),
            speaker_score=round(speaker_score, 4),
            spoof_score=round(spoof_score, 4),
            speaker_matched=speaker_matched,
            spoof_passed=spoof_passed,
            threshold_used=self.speaker_threshold,
            reasons=reasons,
            metadata=audio_metadata,
        )

    # Backward-compatible method
    evaluate = evaluate_tandem


# Backward-compatibility alias
BaselineDecisionEngine = SASVDecisionEngine
