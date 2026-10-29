"""Train SASV Score Fusion Model on Official DEV Partition.

Trains a PyTorch Logistic Regression classifier to combine ECAPA-TDNN ASV cosine similarity
and AASIST CM decision score strictly on the official SASV 2022 DEV partition.
Finds the optimal decision threshold on DEV using official SASV-EER metrics.
"""

import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.eval.official_sasv_metrics import get_all_EERs


class SASVLogisticFusion(nn.Module):
    """Linear decision model combining ASV and CM scores: f(s) = w_asv * s_asv + w_cm * s_cm + b."""

    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)

    def get_score(self, asv_score: float, cm_score: float) -> float:
        with torch.no_grad():
            x = torch.tensor([[asv_score, cm_score]], dtype=torch.float32)
            return float(self.linear(x).item())


def train_fusion_model(
    dev_scores_path: str = "data/benchmark/dev_scores.csv",
    models_dir: str = "models",
    lr: float = 0.01,
    epochs: int = 1200,
) -> Tuple[SASVLogisticFusion, Dict]:
    models_path = Path(models_dir)
    models_path.mkdir(parents=True, exist_ok=True)

    print(f"Loading DEV scores from {dev_scores_path}...")
    df = pd.read_csv(dev_scores_path)

    asv_scores = df["asv_score"].values
    cm_scores = df["cm_score"].values
    keys = df["key"].tolist()

    # Ground truth: target genuine = 1, non-target human & spoof = 0
    y_labels = np.array([1.0 if k == "target" else 0.0 for k in keys], dtype=np.float32)
    X_features = np.column_stack([asv_scores, cm_scores]).astype(np.float32)

    X_tensor = torch.tensor(X_features, dtype=torch.float32)
    y_tensor = torch.tensor(y_labels, dtype=torch.float32).unsqueeze(1)

    # Class imbalance weighting
    n_pos = float(sum(y_labels == 1.0))
    n_neg = float(sum(y_labels == 0.0))
    pos_weight = torch.tensor([n_neg / n_pos])

    model = SASVLogisticFusion()
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    print(f"Training Logistic Fusion model on {len(df)} DEV trials ({int(n_pos)} target, {int(n_neg)} imp/spoof)...")
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        logits = model(X_tensor)
        loss = criterion(logits, y_tensor)
        loss.backward()
        optimizer.step()

        if epoch % 300 == 0 or epoch == epochs:
            print(f"  Epoch {epoch:4d}/{epochs} - BCE Loss: {loss.item():.4f}")

    # Evaluate on DEV
    with torch.no_grad():
        dev_fusion_scores = model(X_tensor).squeeze(1).cpu().numpy()

    sasv_eer, sv_eer, spf_eer = get_all_EERs(dev_fusion_scores, keys)
    w = model.linear.weight.detach().squeeze().cpu().numpy()
    b = float(model.linear.bias.detach().item())

    # Find optimal operating threshold on DEV
    # For logistic logit, 0.0 is the balanced prior threshold, but we also compute the empirical EER threshold
    # Sort scores to compute EER threshold
    from sklearn.metrics import roc_curve
    from scipy.interpolate import interp1d
    from scipy.optimize import brentq
    fpr, tpr, thresholds = roc_curve(y_labels, dev_fusion_scores, pos_label=1)
    eer_func = lambda x: 1.0 - x - interp1d(fpr, tpr)(x)
    optimal_fpr = brentq(eer_func, 0.0, 1.0)
    # Threshold corresponding to EER
    eer_threshold = float(interp1d(fpr, thresholds)(optimal_fpr))

    results = {
        "dataset": "SASV 2022 Development Set",
        "num_trials": len(df),
        "target_trials": int(n_pos),
        "nontarget_trials": int(sum(df["key"] == "nontarget")),
        "spoof_trials": int(sum(df["key"] == "spoof")),
        "weights": {
            "w_asv": float(w[0]),
            "w_cm": float(w[1]),
            "bias": b,
        },
        "dev_metrics": {
            "sasv_eer_pct": round(sasv_eer * 100, 3),
            "sv_eer_pct": round(sv_eer * 100, 3),
            "spf_eer_pct": round(spf_eer * 100, 3),
            "eer_threshold": round(eer_threshold, 4),
        },
    }

    # Save checkpoint & metadata
    ckpt_path = models_path / "sasv_fusion.pt"
    meta_path = models_path / "fusion_metadata.json"

    torch.save(model.state_dict(), ckpt_path)
    with open(meta_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nModel saved to: {ckpt_path}")
    print(f"Metadata saved to: {meta_path}")
    print(f"DEV SASV-EER: {results['dev_metrics']['sasv_eer_pct']}% | "
          f"SV-EER: {results['dev_metrics']['sv_eer_pct']}% | "
          f"SPF-EER: {results['dev_metrics']['spf_eer_pct']}%")
    print(f"Optimal DEV EER Decision Threshold: {results['dev_metrics']['eer_threshold']}")
    print(f"Weights: w_asv={results['weights']['w_asv']:.4f}, w_cm={results['weights']['w_cm']:.4f}, bias={results['weights']['bias']:.4f}")

    return model, results


if __name__ == "__main__":
    train_fusion_model()
