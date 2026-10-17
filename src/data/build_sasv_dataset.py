"""SASV Dataset Builder and Protocol Manager.

Manages the official SASV 2022 Challenge evaluation protocols, ensuring trials
are strictly defined by ground truth metadata (target genuine, bona fide non-target, spoof),
never by intermediate model prediction scores.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd


class SASVDatasetManager:
    """Manages ground-truth trial manifests for official SASV 2022 protocols."""

    def __init__(self, protocols_dir: str = "data/protocols"):
        self.protocols_dir = Path(protocols_dir)

    def load_manifest(self, partition: str = "dev") -> pd.DataFrame:
        """Loads the official SASV trial protocol into a structured DataFrame.

        Ground truth keys are strictly one of:
        - 'target': Bona fide speech matching the enrolled speaker model.
        - 'nontarget': Bona fide human speech from a different human speaker.
        - 'spoof': Logical access attack (TTS, voice conversion) claiming the identity.

        Parameters
        ----------
        partition : str
            'dev' (29,548 trials) or 'eval' (102,579 trials).
        """
        assert partition in ("dev", "eval"), "Partition must be 'dev' or 'eval'"
        file_path = self.protocols_dir / f"ASVspoof2019.LA.asv.{partition}.gi.trl.txt"

        if not file_path.exists():
            raise FileNotFoundError(f"Protocol file not found: {file_path}")

        records = []
        with open(file_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 4:
                    records.append({
                        "speaker_id": parts[0],
                        "utterance_id": parts[1],
                        "attack_type": parts[2],
                        "trial_key": parts[3],  # 'target', 'nontarget', 'spoof'
                    })

        df = pd.DataFrame(records)
        return df

    def get_summary(self, partition: str = "dev") -> Dict[str, int]:
        """Returns ground-truth class distribution counts."""
        df = self.load_manifest(partition)
        counts = df["trial_key"].value_counts().to_dict()
        return {
            "total_trials": len(df),
            "target": counts.get("target", 0),
            "nontarget": counts.get("nontarget", 0),
            "spoof": counts.get("spoof", 0),
        }


if __name__ == "__main__":
    manager = SASVDatasetManager()
    print("--- Official SASV 2022 Protocols Summary ---")
    for part in ["dev", "eval"]:
        summary = manager.get_summary(part)
        print(f"[{part.upper()}] Total: {summary['total_trials']:,} trials | "
              f"Target: {summary['target']:,} | "
              f"Nontarget: {summary['nontarget']:,} | "
              f"Spoof: {summary['spoof']:,}")
