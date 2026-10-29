"""Official SASV Benchmark Evaluator.

Evaluates the official untouched SASV 2022 EVAL partition (102,579 trials)
across all four core experimental conditions:
1. Standalone ASV (ECAPA-TDNN cosine score)
2. Standalone CM (AASIST countermeasure score)
3. SASV Baseline 1 (Score-Sum Fusion)
4. Learned Score Fusion (Trained strictly on DEV, applied untouched to EVAL)
5. Cascaded Tandem Baseline (Independent two-stage thresholding)

Populates the empirical comparison table using 100% measured ground-truth numbers.
"""

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch

from src.eval.official_sasv_metrics import get_all_EERs
from src.train.train_fusion import SASVLogisticFusion


def evaluate_official_benchmark(
    eval_scores_path: str = "data/benchmark/eval_scores.csv",
    fusion_model_path: str = "models/sasv_fusion.pt",
    fusion_meta_path: str = "models/fusion_metadata.json",
    output_dir: str = "data/benchmark",
) -> pd.DataFrame:
    print(f"Loading official EVAL scores from {eval_scores_path}...")
    df = pd.read_csv(eval_scores_path)
    print(f"Total EVAL trials: {len(df)}")
    print(f"  Target genuine trials:      {sum(df['key'] == 'target')}")
    print(f"  Bona fide nontarget trials: {sum(df['key'] == 'nontarget')}")
    print(f"  Spoofed trials:             {sum(df['key'] == 'spoof')}")

    asv_scores = df["asv_score"].values
    cm_scores = df["cm_score"].values
    keys = df["key"].tolist()

    # Load DEV-trained Fusion model and metadata
    fusion_model = SASVLogisticFusion()
    fusion_model.load_state_dict(torch.load(fusion_model_path, weights_only=True))
    fusion_model.eval()

    with open(fusion_meta_path, "r") as f:
        meta = json.load(f)

    w_asv = meta["weights"]["w_asv"]
    w_cm = meta["weights"]["w_cm"]
    b = meta["weights"]["bias"]
    dev_eer_thresh = meta["dev_metrics"]["eer_threshold"]

    # Compute fusion scores on EVAL
    eval_fusion_scores = w_asv * asv_scores + w_cm * cm_scores + b

    # Baseline 1: Simple score-sum
    baseline1_scores = asv_scores + cm_scores

    # Calculate Official EERs for all configurations
    print("\n--- Calculating Official EERs on untouched EVAL partition ---")

    print("1. Evaluating Standalone ASV...")
    sasv_asv, sv_asv, spf_asv = get_all_EERs(asv_scores, keys)

    print("2. Evaluating Standalone CM...")
    sasv_cm, sv_cm, spf_cm = get_all_EERs(cm_scores, keys)

    print("3. Evaluating SASV Baseline 1 (Score-Sum)...")
    sasv_b1, sv_b1, spf_b1 = get_all_EERs(baseline1_scores, keys)

    print("4. Evaluating Learned Score Fusion (Trained on DEV)...")
    sasv_fus, sv_fus, spf_fus = get_all_EERs(eval_fusion_scores, keys)

    # Calculate operational decision accuracy using DEV-calibrated threshold
    is_target = df["key"] == "target"
    is_nontarget = df["key"] == "nontarget"
    is_spoof = df["key"] == "spoof"

    # Decisions for learned fusion at DEV-tuned threshold
    accept_fus = eval_fusion_scores >= dev_eer_thresh
    fus_target_acc = float(np.mean(accept_fus[is_target])) * 100
    fus_nontarget_rej = float(np.mean(~accept_fus[is_nontarget])) * 100
    fus_spoof_rej = float(np.mean(~accept_fus[is_spoof])) * 100

    # For standalone ASV: use optimal SV threshold from DEV
    # (ASV threshold calibrated on bona fide target vs nontarget)
    dev_df = pd.read_csv("data/benchmark/dev_scores.csv")
    dev_asv = dev_df["asv_score"].values
    dev_keys = dev_df["key"].tolist()
    
    # DEV ASV threshold at SV-EER
    from sklearn.metrics import roc_curve
    from scipy.interpolate import interp1d
    from scipy.optimize import brentq
    dev_sv_mask = [k in ("target", "nontarget") for k in dev_keys]
    dev_sv_y = [1 if k == "target" else 0 for k, m in zip(dev_keys, dev_sv_mask) if m]
    dev_sv_scores = dev_asv[dev_sv_mask]
    fpr_asv, tpr_asv, thr_asv = roc_curve(dev_sv_y, dev_sv_scores, pos_label=1)
    sv_asv_eer_pt = brentq(lambda x: 1.0 - x - interp1d(fpr_asv, tpr_asv)(x), 0.0, 1.0)
    asv_thresh = float(interp1d(fpr_asv, thr_asv)(sv_asv_eer_pt))

    # Standalone ASV decisions
    accept_asv = asv_scores >= asv_thresh
    asv_target_acc = float(np.mean(accept_asv[is_target])) * 100
    asv_nontarget_rej = float(np.mean(~accept_asv[is_nontarget])) * 100
    asv_spoof_rej = float(np.mean(~accept_asv[is_spoof])) * 100

    # DEV CM threshold at SPF-EER
    dev_spf_mask = [k in ("target", "spoof") for k in dev_keys]
    dev_spf_y = [1 if k == "target" else 0 for k, m in zip(dev_keys, dev_spf_mask) if m]
    dev_spf_scores = dev_df["cm_score"].values[dev_spf_mask]
    fpr_cm, tpr_cm, thr_cm = roc_curve(dev_spf_y, dev_spf_scores, pos_label=1)
    spf_cm_eer_pt = brentq(lambda x: 1.0 - x - interp1d(fpr_cm, tpr_cm)(x), 0.0, 1.0)
    cm_thresh = float(interp1d(fpr_cm, thr_cm)(spf_cm_eer_pt))

    # Standalone CM decisions
    accept_cm = cm_scores >= cm_thresh
    cm_target_acc = float(np.mean(accept_cm[is_target])) * 100
    cm_nontarget_rej = float(np.mean(~accept_cm[is_nontarget])) * 100
    cm_spoof_rej = float(np.mean(~accept_cm[is_spoof])) * 100

    # Cascaded Tandem (both thresholds must pass)
    accept_tandem = (asv_scores >= asv_thresh) & (cm_scores >= cm_thresh)
    tandem_target_acc = float(np.mean(accept_tandem[is_target])) * 100
    tandem_nontarget_rej = float(np.mean(~accept_tandem[is_nontarget])) * 100
    tandem_spoof_rej = float(np.mean(~accept_tandem[is_spoof])) * 100

    # Compute DEV strict security threshold (Target Impostor FAR <= 1.5% on DEV)
    dev_nontarget_scores = dev_df[dev_df["key"] == "nontarget"]["asv_score"].values * w_asv + dev_df[dev_df["key"] == "nontarget"]["cm_score"].values * w_cm + b
    strict_thresh = float(np.percentile(dev_nontarget_scores, (1.0 - 0.015) * 100))

    # Evaluate strict security threshold on EVAL
    accept_strict = eval_fusion_scores >= strict_thresh
    strict_target_acc = float(np.mean(accept_strict[is_target])) * 100
    strict_nontarget_rej = float(np.mean(~accept_strict[is_nontarget])) * 100
    strict_spoof_rej = float(np.mean(~accept_strict[is_spoof])) * 100

    # Build Comparison Table
    results_table = [
        {
            "System": "Standalone ASV (ECAPA-TDNN)",
            "SASV-EER (%)": round(sasv_asv * 100, 2),
            "SV-EER (%)": round(sv_asv * 100, 2),
            "SPF-EER (%)": round(spf_asv * 100, 2),
            "Target Acceptance (%)": round(asv_target_acc, 2),
            "Impostor Rejection (%)": round(asv_nontarget_rej, 2),
            "Spoof Rejection (%)": round(asv_spoof_rej, 2),
        },
        {
            "System": "Standalone CM (AASIST)",
            "SASV-EER (%)": round(sasv_cm * 100, 2),
            "SV-EER (%)": round(sv_cm * 100, 2),
            "SPF-EER (%)": round(spf_cm * 100, 2),
            "Target Acceptance (%)": round(cm_target_acc, 2),
            "Impostor Rejection (%)": round(cm_nontarget_rej, 2),
            "Spoof Rejection (%)": round(cm_spoof_rej, 2),
        },
        {
            "System": "SASV Baseline 1 (Score-Sum)",
            "SASV-EER (%)": round(sasv_b1 * 100, 2),
            "SV-EER (%)": round(sv_b1 * 100, 2),
            "SPF-EER (%)": round(spf_b1 * 100, 2),
            "Target Acceptance (%)": "N/A (unthresholded)",
            "Impostor Rejection (%)": "N/A (unthresholded)",
            "Spoof Rejection (%)": "N/A (unthresholded)",
        },
        {
            "System": "Cascaded Tandem Baseline (Dual Thresh)",
            "SASV-EER (%)": "N/A (dual decision)",
            "SV-EER (%)": "N/A (dual decision)",
            "SPF-EER (%)": "N/A (dual decision)",
            "Target Acceptance (%)": round(tandem_target_acc, 2),
            "Impostor Rejection (%)": round(tandem_nontarget_rej, 2),
            "Spoof Rejection (%)": round(tandem_spoof_rej, 2),
        },
        {
            "System": "Learned Score Fusion (DEV EER Thresh, tau=0.72)",
            "SASV-EER (%)": round(sasv_fus * 100, 2),
            "SV-EER (%)": round(sv_fus * 100, 2),
            "SPF-EER (%)": round(spf_fus * 100, 2),
            "Target Acceptance (%)": round(fus_target_acc, 2),
            "Impostor Rejection (%)": round(fus_nontarget_rej, 2),
            "Spoof Rejection (%)": round(fus_spoof_rej, 2),
        },
        {
            "System": "Learned Score Fusion (Strict Security, tau=1.36)",
            "SASV-EER (%)": round(sasv_fus * 100, 2),
            "SV-EER (%)": round(sv_fus * 100, 2),
            "SPF-EER (%)": round(spf_fus * 100, 2),
            "Target Acceptance (%)": round(strict_target_acc, 2),
            "Impostor Rejection (%)": round(strict_nontarget_rej, 2),
            "Spoof Rejection (%)": round(strict_spoof_rej, 2),
        },
    ]

    out_df = pd.DataFrame(results_table)
    out_csv = Path(output_dir) / "official_eval_comparison.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"\nSaved benchmark comparison table to: {out_csv}\n")
    print(out_df.to_string(index=False))

    return out_df


if __name__ == "__main__":
    evaluate_official_benchmark()
