"""SASV Pilot Smoke Test and Baseline Decision Pipeline.

Processes single or batch labelled audio clips, executes pretrained ECAPA-TDNN and AASIST,
applies the baseline decision rule, and reports latency and peak GPU memory metrics.

Usage:
  python main_smoke_test.py --run-all
  python main_smoke_test.py --test-audio data/pilot/audio/speaker_alpha_genuine.wav --enrolled-audio data/pilot/audio/speaker_alpha_enroll.wav
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Optional
import torch

from src.core.audio_processor import AudioProcessor
from src.models.ecapa import ECAPAInferencer
from src.models.aasist import AASISTInferencer
from src.core.decision_engine import BaselineDecisionEngine, DecisionResult


def run_single_verification(
    test_audio_path: str,
    enrolled_audio_path: str,
    audio_processor: AudioProcessor,
    ecapa_model: ECAPAInferencer,
    aasist_model: AASISTInferencer,
    decision_engine: BaselineDecisionEngine,
    claimed_speaker_id: str = "speaker_alpha",
    trial_metadata: Optional[Dict] = None,
) -> Dict:
    """Executes end-to-end verification for a test clip against an enrolled voice template."""
    start_total = time.perf_counter()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    # 1. Load and standardize audio
    test_waveform, test_meta = audio_processor.load_and_preprocess(test_audio_path)
    enroll_waveform, enroll_meta = audio_processor.load_and_preprocess(enrolled_audio_path)

    # 2. Extract ECAPA-TDNN Speaker Embeddings
    enrolled_emb, enroll_timing = ecapa_model.extract_embedding(enroll_waveform)
    test_emb, test_timing = ecapa_model.extract_embedding(test_waveform)
    speaker_score = ecapa_model.compute_similarity(test_emb, enrolled_emb)

    # 3. Compute AASIST Anti-Spoofing Score
    spoof_result = aasist_model.score_audio(test_waveform)
    spoof_score = spoof_result["cm_score"]

    # 4. Total Latency and Peak GPU VRAM
    total_time_ms = (time.perf_counter() - start_total) * 1000
    if device.type == "cuda":
        peak_vram_mb = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
    else:
        peak_vram_mb = 0.0

    # 5. Evaluate Decision Rule
    decision_result: DecisionResult = decision_engine.evaluate(
        speaker_score=speaker_score,
        spoof_score=spoof_score,
        audio_metadata=test_meta,
    )

    output = {
        "claimed_speaker": claimed_speaker_id,
        "test_file": os.path.basename(test_audio_path),
        "enrolled_file": os.path.basename(enrolled_audio_path),
        "decision": decision_result.decision,
        "verdict_type": decision_result.verdict_type,
        "speaker_score": decision_result.speaker_score,
        "speaker_threshold": decision_engine.speaker_threshold,
        "speaker_matched": decision_result.speaker_matched,
        "spoof_score": decision_result.spoof_score,
        "spoof_threshold": decision_engine.spoof_threshold,
        "spoof_passed": decision_result.spoof_passed,
        "risk_score": decision_result.risk_score,
        "reasons": decision_result.reasons,
        "telemetry": {
            "device": str(device),
            "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
            "ecapa_latency_ms": test_timing["latency_ms"],
            "aasist_latency_ms": spoof_result["latency_ms"],
            "total_latency_ms": round(total_time_ms, 2),
            "peak_vram_mb": round(peak_vram_mb, 2),
        },
        "trial_metadata": trial_metadata or {},
    }
    return output


def print_single_result(res: Dict):
    """Pretty prints the verification output."""
    t = res["telemetry"]
    print("=" * 78)
    print(f" SASV VERIFICATION RESULT: [{res['test_file']}]")
    print("=" * 78)
    print(f" Claimed Speaker    : {res['claimed_speaker']}")
    print(f" Decision           : {res['decision']}  ({res['verdict_type']})")
    print(f" Risk Score         : {res['risk_score']}/100")
    print(f" Speaker Match Score: {res['speaker_score']:+.4f} (Threshold: {res['speaker_threshold']:.2f}) -> {'PASS' if res['speaker_matched'] else 'FAIL'}")
    print(f" Spoof Logit Score  : {res['spoof_score']:+.4f} (Threshold: {res['spoof_threshold']:.2f}) -> {'PASS' if res['spoof_passed'] else 'FAIL'}")
    print(f" Decision Reasons   :")
    for r in res["reasons"]:
        print(f"   • {r}")
    print("-" * 78)
    print(f" Hardware & Latency Telemetry:")
    print(f"   • Compute Device : {t['device_name']} ({t['device']})")
    print(f"   • ECAPA Time     : {t['ecapa_latency_ms']} ms")
    print(f"   • AASIST Time    : {t['aasist_latency_ms']} ms")
    print(f"   • Total Time     : {t['total_latency_ms']} ms")
    print(f"   • Peak GPU VRAM  : {t['peak_vram_mb']} MB")
    print("=" * 78)


def run_all_pilot_trials(speaker_threshold: float = 0.35, spoof_threshold: float = -2.0):
    """Executes the full calibrated pilot trial list from data/pilot/pilot_trials.json."""
    manifest_path = "data/pilot/pilot_trials.json"
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest not found at {manifest_path}. Run scripts/prepare_pilot_data.py first.")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        trials = json.load(f)

    print("\nInitializing Pretrained Models on GPU/CPU...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Active Device: {device} ({torch.cuda.get_device_name(device) if device.type == 'cuda' else 'CPU'})")

    audio_proc = AudioProcessor()
    ecapa = ECAPAInferencer(device=device)
    aasist = AASISTInferencer(device=device)
    engine = BaselineDecisionEngine(speaker_threshold=speaker_threshold, spoof_threshold=spoof_threshold)

    print("Loading ECAPA-TDNN & AASIST weights into VRAM...")
    ecapa.load_model()
    aasist.load_weights()
    print("Models loaded successfully!\n")

    results = []
    audio_dir = "data/pilot/audio"

    for trial in trials:
        test_path = os.path.join(audio_dir, trial["test_file"])
        enroll_path = os.path.join(audio_dir, trial["enrolled_file"])

        res = run_single_verification(
            test_audio_path=test_path,
            enrolled_audio_path=enroll_path,
            audio_processor=audio_proc,
            ecapa_model=ecapa,
            aasist_model=aasist,
            decision_engine=engine,
            claimed_speaker_id=trial["claimed_speaker"],
            trial_metadata=trial,
        )
        results.append(res)
        print_single_result(res)

    # Save complete benchmark report
    report_path = "data/pilot/smoke_test_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[DONE] Saved comprehensive smoke test telemetry report to: {report_path}")

    # Summary table
    print("\n" + "=" * 90)
    print(f"{'Trial ID':<10} | {'Test File':<32} | {'Spk Score':<9} | {'Spoof Scr':<9} | {'Decision':<14} | {'Verdict':<16}")
    print("-" * 90)
    for r in results:
        meta = r["trial_metadata"]
        print(f"{meta.get('trial_id', 'N/A'):<10} | {r['test_file']:<32} | {r['speaker_score']:>+9.4f} | {r['spoof_score']:>+9.4f} | {r['decision']:<14} | {r['verdict_type']:<16}")
    print("=" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(description="SASV Pilot Smoke Test")
    parser.add_argument("--run-all", action="store_true", help="Run all calibrated pilot trials")
    parser.add_argument("--test-audio", type=str, help="Path to test audio WAV")
    parser.add_argument("--enrolled-audio", type=str, help="Path to enrolled audio WAV")
    parser.add_argument("--speaker-id", type=str, default="speaker_alpha", help="Claimed speaker ID")
    parser.add_argument("--speaker-threshold", type=float, default=0.35, help="ECAPA cosine threshold")
    parser.add_argument("--spoof-threshold", type=float, default=-2.0, help="AASIST bona_fide logit threshold")

    args = parser.parse_args()

    if args.run_all or (not args.test_audio and not args.enrolled_audio):
        run_all_pilot_trials(speaker_threshold=args.speaker_threshold, spoof_threshold=args.spoof_threshold)
    else:
        if not args.test_audio or not args.enrolled_audio:
            print("Error: Both --test-audio and --enrolled-audio must be provided for single evaluation.")
            sys.exit(1)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        audio_proc = AudioProcessor()
        ecapa = ECAPAInferencer(device=device)
        aasist = AASISTInferencer(device=device)
        engine = BaselineDecisionEngine(
            speaker_threshold=args.speaker_threshold, spoof_threshold=args.spoof_threshold
        )

        ecapa.load_model()
        aasist.load_weights()

        res = run_single_verification(
            test_audio_path=args.test_audio,
            enrolled_audio_path=args.enrolled_audio,
            audio_processor=audio_proc,
            ecapa_model=ecapa,
            aasist_model=aasist,
            decision_engine=engine,
            claimed_speaker_id=args.speaker_id,
        )
        print_single_result(res)


if __name__ == "__main__":
    main()
