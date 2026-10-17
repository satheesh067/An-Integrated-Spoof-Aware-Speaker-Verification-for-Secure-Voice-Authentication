"""Official SASV 2022 Protocol Scorer.

Extracts ASV cosine similarity and AASIST CM scores across the official
ASVspoof 2019 / SASV 2022 Challenge development and evaluation protocol trials.
"""

import os
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch

from src.models.aasist import AASISTInferencer


class SASVProtocolScorer:
    """Computes and caches scores for SASV 2022 development and evaluation protocols."""

    def __init__(
        self,
        embeddings_dir: str = "data/sasv_baseline/embeddings",
        protocols_dir: str = "data/protocols",
        output_dir: str = "data/benchmark",
    ):
        self.embeddings_dir = Path(embeddings_dir)
        self.protocols_dir = Path(protocols_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load AASIST out_layer weights for CM scoring
        self.inf = AASISTInferencer()
        self.inf.load_weights()
        out_w = self.inf.model.out_layer.weight.detach().cpu().numpy()
        out_b = self.inf.model.out_layer.bias.detach().cpu().numpy()
        
        # In AASIST out_layer: index 0 is spoof, index 1 is bona_fide
        # Decision score convention: logit(bonafide) - logit(spoof)
        self.w_diff = out_w[1] - out_w[0]
        self.b_diff = float(out_b[1] - out_b[0])

    def score_partition(self, partition: str = "dev") -> pd.DataFrame:
        """Scores all trials in a partition ('dev' or 'eval').

        Returns a DataFrame with columns:
        ['speaker_id', 'utt_id', 'attack', 'key', 'asv_score', 'cm_score']
        """
        assert partition in ("dev", "eval"), "Partition must be 'dev' or 'eval'"

        protocol_file = self.protocols_dir / f"ASVspoof2019.LA.asv.{partition}.gi.trl.txt"
        spk_model_file = self.embeddings_dir / f"spk_model_{partition}.pk"
        asv_embd_file = self.embeddings_dir / f"asv_embd_{partition}.pk"
        cm_embd_file = self.embeddings_dir / f"cm_embd_{partition}.pk"

        if not protocol_file.exists():
            raise FileNotFoundError(f"Protocol file not found: {protocol_file}")

        print(f"Loading {partition.upper()} embeddings...")
        with open(spk_model_file, "rb") as f:
            spk_models = pickle.load(f)
        with open(asv_embd_file, "rb") as f:
            asv_embds = pickle.load(f)
        with open(cm_embd_file, "rb") as f:
            cm_embds = pickle.load(f)

        print(f"Reading {partition.upper()} trial list: {protocol_file}")
        with open(protocol_file, "r") as f:
            lines = [line.strip().split() for line in f if line.strip()]

        print(f"Scoring {len(lines)} {partition.upper()} trials...")
        records = []

        # Vectorized batch processing
        for parts in lines:
            spk_id = parts[0]
            utt_id = parts[1]
            attack = parts[2]
            key = parts[3]

            spk_vec = spk_models[spk_id]
            utt_asv = asv_embds[utt_id]
            utt_cm = cm_embds[utt_id]

            # Cosine similarity for ASV
            norm_prod = np.linalg.norm(spk_vec) * np.linalg.norm(utt_asv)
            asv_score = float(np.dot(spk_vec, utt_asv) / (norm_prod + 1e-12))

            # Linear logit difference for CM
            cm_score = float(np.dot(self.w_diff, utt_cm) + self.b_diff)

            records.append({
                "speaker_id": spk_id,
                "utt_id": utt_id,
                "attack": attack,
                "key": key,
                "asv_score": asv_score,
                "cm_score": cm_score,
            })

        df = pd.DataFrame(records)
        out_csv = self.output_dir / f"{partition}_scores.csv"
        df.to_csv(out_csv, index=False)
        print(f"Saved {len(df)} scored trials to: {out_csv}")
        return df


if __name__ == "__main__":
    scorer = SASVProtocolScorer()
    print("\n--- Scoring Official DEV Partition ---")
    dev_df = scorer.score_partition("dev")
    print(f"DEV trials scored: {len(dev_df)} (Target: {sum(dev_df['key'] == 'target')}, "
          f"Nontarget: {sum(dev_df['key'] == 'nontarget')}, Spoof: {sum(dev_df['key'] == 'spoof')})")

    print("\n--- Scoring Official EVAL Partition ---")
    eval_df = scorer.score_partition("eval")
    print(f"EVAL trials scored: {len(eval_df)} (Target: {sum(eval_df['key'] == 'target')}, "
          f"Nontarget: {sum(eval_df['key'] == 'nontarget')}, Spoof: {sum(eval_df['key'] == 'spoof')})")
