"""Threshold Calibration on DEV and Single Untouched Evaluation on EVAL.

Step 1: Runs DEV partition to find calibrated operating thresholds via EER sweep.
Step 2: Freezes thresholds and tests ONCE on the untouched EVAL partition.
"""

import os
import sys
import json
import torch
import numpy as np
import pandas as pd
from typing import Dict, Tuple

sys.path.insert(0, ".")

from src.core.audio_processor import AudioProcessor
from src.models.ecapa import ECAPAInferencer
from src.models.aasist import AASISTInferencer
from src.core.decision_engine import BaselineDecisionEngine, DecisionResult


def compute_eer(scores: np.ndarray, labels: np.ndarray) -> Tuple[float, float]:
    """Computes Equal Error Rate (EER) and the optimal threshold.
    labels: 1 for positive (bona_fide / target), 0 for negative (spoof / impostor).
    """
    sorted_indices = np.argsort(scores)
    sorted_scores = scores[sorted_indices]
    sorted_labels = labels[sorted_indices]

    n_pos = np.sum(sorted_labels == 1)
    n_neg = np.sum(sorted_labels == 0)

    if n_pos == 0 or n_neg == 0:
        return 0.0, float(np.median(scores))

    # Sweep thresholds
    thresholds = sorted_scores
    fnr = []  # False Negative Rate (FRR)
    fpr = []  # False Positive Rate (FAR)

    for th in thresholds:
        fn = np.sum((scores < th) & (labels == 1))
        fp = np.sum((scores >= th) & (labels == 0))
        fnr.append(fn / n_pos)
        fpr.append(fp / n_neg)

    fnr = np.array(fnr)
    fpr = np.array(fpr)

    diff = np.abs(fnr - fpr)
    min_idx = np.argmin(diff)
    optimal_th = float(thresholds[min_idx])
    eer = float((fnr[min_idx] + fpr[min_idx]) / 2.0)

    return eer, optimal_th


def process_partition(
    manifest_csv: str,
    audio_dir: str,
    ecapa: ECAPAInferencer,
    aasist: AASISTInferencer,
    audio_proc: AudioProcessor,
) -> pd.DataFrame:
    df = pd.read_csv(manifest_csv)
    results = []

    for _, row in df.iterrows():
        test_path = os.path.join(audio_dir, row["test_file"])
        enroll_path = os.path.join(audio_dir, row["enrolled_file"])

        test_wave, test_meta = audio_proc.load_and_preprocess(test_path)
        enroll_wave, _ = audio_proc.load_and_preprocess(enroll_path)

        # ECAPA speaker verification
        test_emb, _ = ecapa.extract_embedding(test_wave)
        enroll_emb, _ = ecapa.extract_embedding(enroll_wave)
        spk_score = ecapa.compute_similarity(test_emb, enroll_emb)

        # AASIST spoof detection
        spoof_res = aasist.score_audio(test_wave)
        spoof_score = spoof_res["cm_score"]

        res = dict(row)
        res["speaker_score"] = spk_score
        res["spoof_score"] = spoof_score
        results.append(res)

    return pd.DataFrame(results)


def main():
    print("=" * 80)
    print(" SASV SCIENTIFIC CALIBRATION & INDEPENDENT BENCHMARK PIPELINE")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} ({torch.cuda.get_device_name(device) if device.type == 'cuda' else 'CPU'})")

    audio_proc = AudioProcessor()
    ecapa = ECAPAInferencer(device=device)
    aasist = AASISTInferencer(device=device)

    print("\n[1/3] Loading models...")
    ecapa.load_model()
    aasist.load_weights()

    # Phase 1: Run DEV partition for threshold calibration
    print("\n[2/3] Processing DEV partition (data/benchmark/dev_manifest.csv)...")
    dev_df = process_partition(
        "data/benchmark/dev_manifest.csv",
        "data/benchmark/dev/audio",
        ecapa,
        aasist,
        audio_proc,
    )

    # 1. Calibrate Speaker Threshold on DEV (target vs impostor on bona_fide audio)
    bona_fide_dev = dev_df[dev_df["spoof_label"] == "bona_fide"]
    spk_labels = (bona_fide_dev["target_type"] == "target").astype(int).values
    spk_scores = bona_fide_dev["speaker_score"].values
    asv_eer, calib_spk_th = compute_eer(spk_scores, spk_labels)

    # 2. Calibrate Anti-Spoof Threshold on DEV (bona_fide vs spoof)
    cm_labels = (dev_df["spoof_label"] == "bona_fide").astype(int).values
    cm_scores = dev_df["spoof_score"].values
    cm_eer, calib_cm_th = compute_eer(cm_scores, cm_labels)

    print("\n" + "-" * 80)
    print(" DEV CALIBRATION RESULTS:")
    print(f"   • Speaker ASV-EER  : {asv_eer*100:.2f}% | Calibrated Speaker Threshold : {calib_spk_th:+.4f}")
    print(f"   • Anti-Spoof CM-EER: {cm_eer*100:.2f}% | Calibrated Spoof Threshold   : {calib_cm_th:+.4f}")
    print("-" * 80)

    # Phase 2: Test ONCE on untouched EVAL partition using frozen calibrated thresholds
    print("\n[3/3] Testing on UNTOUCHED EVAL partition (data/benchmark/eval_manifest.csv)...")
    eval_df = process_partition(
        "data/benchmark/eval_manifest.csv",
        "data/benchmark/eval/audio",
        ecapa,
        aasist,
        audio_proc,
    )

    engine = BaselineDecisionEngine(
        speaker_threshold=calib_spk_th,
        spoof_threshold=calib_cm_th,
    )

    eval_results = []
    for _, row in eval_df.iterrows():
        dec: DecisionResult = engine.evaluate(
            speaker_score=row["speaker_score"],
            spoof_score=row["spoof_score"],
        )
        r = dict(row)
        r["decision"] = dec.decision
        r["verdict_type"] = dec.verdict_type
        r["risk_score"] = dec.risk_score
        r["reasons"] = dec.reasons[0] if dec.reasons else ""
        eval_results.append(r)

    eval_out_df = pd.DataFrame(eval_results)
    eval_out_df.to_csv("data/benchmark/eval_results.csv", index=False)

    print("\n" + "=" * 100)
    print(" UNTOUCHED EVALUATION SET RESULTS (Frozen Calibrated Thresholds)")
    print("=" * 100)
    print(f"{'Trial':<9} | {'Source / Attack Type':<32} | {'Spk Scr':<8} | {'CM Scr':<8} | {'Risk':<5} | {'Decision':<14} | {'Verdict'}")
    print("-" * 100)
    for _, r in eval_out_df.iterrows():
        source_label = r['attack_family'] if r['attack_family'] != 'none' else r['target_type'].upper()
        print(f"{r['trial_id']:<9} | {source_label:<32} | {r['speaker_score']:>+7.3f} | {r['spoof_score']:>+7.3f} | {r['risk_score']:>4.1f}% | {r['decision']:<14} | {r['verdict_type']}")
    print("=" * 100)


if __name__ == "__main__":
    main()
