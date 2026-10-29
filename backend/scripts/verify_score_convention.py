"""AASIST Score Convention & Real ASVspoof Distribution Audit.

Loads genuine, synthetic (TTS/VC), and replay audio from official ASVspoof datasets,
runs pretrained AASIST inference on each, and computes mean, standard deviation, and
min/max score statistics for each class.
"""

import io
import os
import sys
sys.path.insert(0, ".")

import torch
import soundfile as sf
import pandas as pd
from huggingface_hub import hf_hub_download
from src.models.aasist import AASISTInferencer

def extract_audio_from_row(row):
    audio_dict = row["audio"]
    raw_bytes = audio_dict["bytes"]
    data, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    return torch.from_numpy(data).float(), sr

def main():
    print("Auditing AASIST score distribution on real ASVspoof data...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AASISTInferencer(device=device)
    model.load_weights()

    # 1. Load ASVspoof 2015 (TTS & Voice Conversion)
    p2015 = hf_hub_download("DynamicSuperb/SpoofDetection_ASVspoof2015", "data/test-00000-of-00001-4a252b1e92dc86af.parquet", repo_type="dataset")
    df15 = pd.read_parquet(p2015)

    # 2. Load ASVspoof 2017 (Physical Replay)
    p2017 = hf_hub_download("DynamicSuperb/SpoofDetection_ASVspoof2017", "data/test-00000-of-00001-e7ed034c56ededdd.parquet", repo_type="dataset")
    df17 = pd.read_parquet(p2017)

    # Collect samples
    genuine_samples = df15[df15["label"] == "authentic"].head(10)
    synthetic_samples = df15[df15["label"] == "spoofed"].head(15)
    replay_samples = df17[df17["label"] == "spoofed"].head(15)

    results = {"genuine": [], "synthetic": [], "replay": []}

    print("\nScoring Genuine Human Samples...")
    for idx, row in genuine_samples.iterrows():
        waveform, sr = extract_audio_from_row(row)
        score_info = model.score_audio(waveform)
        results["genuine"].append(score_info["cm_score"])
        print(f"  [Genuine] {row['file']}: CM Score = {score_info['cm_score']:+.4f} (Prob: {score_info['bona_fide_prob']:.4f})")

    print("\nScoring Real Synthetic / Voice Conversion Attacks (ASVspoof 2015)...")
    for idx, row in synthetic_samples.iterrows():
        waveform, sr = extract_audio_from_row(row)
        score_info = model.score_audio(waveform)
        results["synthetic"].append(score_info["cm_score"])
        print(f"  [Synthetic] {row['file']}: CM Score = {score_info['cm_score']:+.4f} (Prob: {score_info['bona_fide_prob']:.4f})")

    print("\nScoring Real Physical Replay Attacks (ASVspoof 2017)...")
    for idx, row in replay_samples.iterrows():
        waveform, sr = extract_audio_from_row(row)
        score_info = model.score_audio(waveform)
        results["replay"].append(score_info["cm_score"])
        print(f"  [Replay] {row['file']}: CM Score = {score_info['cm_score']:+.4f} (Prob: {score_info['bona_fide_prob']:.4f})")

    print("\n" + "=" * 65)
    print(" AASIST SCORE DISTRIBUTION SUMMARY (Real ASVspoof Data)")
    print("=" * 65)
    for cat, scores in results.items():
        s = pd.Series(scores)
        print(f" {cat.upper():<10} | Mean: {s.mean():>+7.3f} | Std: {s.std():>6.3f} | Min: {s.min():>+7.3f} | Max: {s.max():>+7.3f}")
    print("=" * 65)

if __name__ == "__main__":
    main()
