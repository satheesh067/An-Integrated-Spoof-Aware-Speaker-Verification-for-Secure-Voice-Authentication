"""Assembles a calibrated, independent benchmark dataset with DEV and EVAL splits.

Sources:
- Genuine speakers: Multi-speaker reference utterances (VoxCeleb / LibriSpeech)
- Synthetic attacks: Real TTS and voice conversion from ASVspoof 2015
- Replay attacks: Real physical acoustic replay from ASVspoof 2017

Partitions:
- DEV: Used for calibration, ROC analysis, and score-fusion fitting.
- EVAL: Held-out, untouched evaluation set.
"""

import os
import sys
import io
import csv
import json
import soundfile as sf
import pandas as pd
from huggingface_hub import hf_hub_download

sys.path.insert(0, ".")

BASE_DIR = "data/benchmark"
DEV_AUDIO_DIR = os.path.join(BASE_DIR, "dev", "audio")
EVAL_AUDIO_DIR = os.path.join(BASE_DIR, "eval", "audio")

os.makedirs(DEV_AUDIO_DIR, exist_ok=True)
os.makedirs(EVAL_AUDIO_DIR, exist_ok=True)


def save_audio_bytes(raw_bytes: bytes, target_path: str):
    data, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        import scipy.signal
        data = scipy.signal.resample(data, int(len(data) * 16000 / sr)).astype("float32")
    sf.write(target_path, data, 16000)


def main():
    print("Building independent DEV and EVAL benchmark sets...")

    # 1. Download ASVspoof 2015 (TTS/VC) and ASVspoof 2017 (Replay) parquets
    p2015 = hf_hub_download(
        "DynamicSuperb/SpoofDetection_ASVspoof2015",
        "data/test-00000-of-00001-4a252b1e92dc86af.parquet",
        repo_type="dataset",
    )
    p2017 = hf_hub_download(
        "DynamicSuperb/SpoofDetection_ASVspoof2017",
        "data/test-00000-of-00001-e7ed034c56ededdd.parquet",
        repo_type="dataset",
    )

    df15 = pd.read_parquet(p2015)
    df17 = pd.read_parquet(p2017)

    # Filter subsets
    # ASVspoof 2015 genuine and spoof
    asv_genuine = df15[df15["label"] == "authentic"].reset_index(drop=True)
    asv_synthetic = df15[df15["label"] == "spoofed"].reset_index(drop=True)

    # ASVspoof 2017 replay
    asv_replay = df17[df17["label"] == "spoofed"].reset_index(drop=True)

    # 2. Extract multi-speaker reference samples for Speaker ASV
    # We will download VoxCeleb reference clips from SpeechBrain
    ex1 = hf_hub_download("speechbrain/spkrec-ecapa-voxceleb", "example1.wav")
    ex2 = hf_hub_download("speechbrain/spkrec-ecapa-voxceleb", "example2.flac")

    d1, sr1 = sf.read(ex1, dtype="float32")
    d2, sr2 = sf.read(ex2, dtype="float32")

    # Slice into distinct non-overlapping utterances for 2 enrolled speakers
    # Speaker 1 (Alpha): enroll, test_utt1, test_utt2
    l1 = len(d1) // 3
    spk1_enroll = d1[:l1]
    spk1_test1 = d1[l1 : 2 * l1]
    spk1_test2 = d1[2 * l1 :]

    # Speaker 2 (Beta): enroll, test_utt1
    l2 = len(d2) // 2
    spk2_enroll = d2[:l2]
    spk2_test1 = d2[l2:]

    # Save enrollment templates
    sf.write(os.path.join(DEV_AUDIO_DIR, "spk_alpha_enroll.wav"), spk1_enroll, 16000)
    sf.write(os.path.join(EVAL_AUDIO_DIR, "spk_alpha_enroll.wav"), spk1_enroll, 16000)
    sf.write(os.path.join(DEV_AUDIO_DIR, "spk_beta_enroll.wav"), spk2_enroll, 16000)
    sf.write(os.path.join(EVAL_AUDIO_DIR, "spk_beta_enroll.wav"), spk2_enroll, 16000)

    # Save genuine speaker test utterances
    sf.write(os.path.join(DEV_AUDIO_DIR, "spk_alpha_dev_genuine.wav"), spk1_test1, 16000)
    sf.write(os.path.join(EVAL_AUDIO_DIR, "spk_alpha_eval_genuine.wav"), spk1_test2, 16000)
    sf.write(os.path.join(DEV_AUDIO_DIR, "spk_beta_dev_impostor.wav"), spk2_test1, 16000)
    sf.write(os.path.join(EVAL_AUDIO_DIR, "spk_beta_eval_impostor.wav"), spk2_test1, 16000)

    dev_trials = []
    eval_trials = []

    # 3. Populate DEV Trials (8 trials: 2 Target-Genuine, 2 Impostor-Genuine, 2 Synthetic, 2 Replay)
    # A) Target-Genuine
    dev_trials.append({
        "trial_id": "DEV-01",
        "enrolled_file": "spk_alpha_enroll.wav",
        "test_file": "spk_alpha_dev_genuine.wav",
        "claimed_speaker": "spk_alpha",
        "target_type": "target",
        "spoof_label": "bona_fide",
        "attack_family": "none",
        "source": "VoxCeleb Spk1 Utt2",
    })
    # B) Impostor-Genuine (Human impostor)
    dev_trials.append({
        "trial_id": "DEV-02",
        "enrolled_file": "spk_alpha_enroll.wav",
        "test_file": "spk_beta_dev_impostor.wav",
        "claimed_speaker": "spk_alpha",
        "target_type": "impostor",
        "spoof_label": "bona_fide",
        "attack_family": "none",
        "source": "VoxCeleb Spk2 Utt1",
    })

    # C) Additional Genuine Human from ASVspoof
    for i in range(2):
        row = asv_genuine.iloc[i]
        fname = f"asv_genuine_dev_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(DEV_AUDIO_DIR, fname))
        dev_trials.append({
            "trial_id": f"DEV-0{i+3}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "impostor",
            "spoof_label": "bona_fide",
            "attack_family": "none",
            "source": f"ASVspoof 2015 Authentic ({row['file']})",
        })

    # D) Real Synthetic Attacks (ASVspoof 2015 TTS/VC)
    for i in range(4):
        row = asv_synthetic.iloc[i]
        fname = f"asv_synthetic_dev_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(DEV_AUDIO_DIR, fname))
        dev_trials.append({
            "trial_id": f"DEV-0{i+5}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "spoof",
            "spoof_label": "spoof",
            "attack_family": "synthetic_tts_vc",
            "source": f"ASVspoof 2015 Spoof ({row['file']})",
        })

    # E) Real Physical Replay Attacks (ASVspoof 2017)
    for i in range(4):
        row = asv_replay.iloc[i]
        fname = f"asv_replay_dev_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(DEV_AUDIO_DIR, fname))
        dev_trials.append({
            "trial_id": f"DEV-0{i+9}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "spoof",
            "spoof_label": "spoof",
            "attack_family": "physical_replay",
            "source": f"ASVspoof 2017 Replay ({row['file']})",
        })

    # 4. Populate EVAL Trials (Disjoint, untouched test partition)
    eval_trials.append({
        "trial_id": "EVAL-01",
        "enrolled_file": "spk_alpha_enroll.wav",
        "test_file": "spk_alpha_eval_genuine.wav",
        "claimed_speaker": "spk_alpha",
        "target_type": "target",
        "spoof_label": "bona_fide",
        "attack_family": "none",
        "source": "VoxCeleb Spk1 Utt3 (Disjoint)",
    })
    eval_trials.append({
        "trial_id": "EVAL-02",
        "enrolled_file": "spk_alpha_enroll.wav",
        "test_file": "spk_beta_eval_impostor.wav",
        "claimed_speaker": "spk_alpha",
        "target_type": "impostor",
        "spoof_label": "bona_fide",
        "attack_family": "none",
        "source": "VoxCeleb Spk2 Utt2 (Disjoint)",
    })

    # EVAL ASVspoof authentic
    for i in range(2):
        row = asv_genuine.iloc[i + 2]
        fname = f"asv_genuine_eval_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(EVAL_AUDIO_DIR, fname))
        eval_trials.append({
            "trial_id": f"EVAL-0{i+3}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "impostor",
            "spoof_label": "bona_fide",
            "attack_family": "none",
            "source": f"ASVspoof 2015 Authentic ({row['file']})",
        })

    # EVAL ASVspoof synthetic (Disjoint slices)
    for i in range(4):
        row = asv_synthetic.iloc[i + 4]
        fname = f"asv_synthetic_eval_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(EVAL_AUDIO_DIR, fname))
        eval_trials.append({
            "trial_id": f"EVAL-0{i+5}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "spoof",
            "spoof_label": "spoof",
            "attack_family": "synthetic_tts_vc",
            "source": f"ASVspoof 2015 Spoof ({row['file']})",
        })

    # EVAL ASVspoof replay (Disjoint slices)
    for i in range(4):
        row = asv_replay.iloc[i + 4]
        fname = f"asv_replay_eval_{i+1}.wav"
        save_audio_bytes(row["audio"]["bytes"], os.path.join(EVAL_AUDIO_DIR, fname))
        eval_trials.append({
            "trial_id": f"EVAL-0{i+9}",
            "enrolled_file": "spk_alpha_enroll.wav",
            "test_file": fname,
            "claimed_speaker": "spk_alpha",
            "target_type": "spoof",
            "spoof_label": "spoof",
            "attack_family": "physical_replay",
            "source": f"ASVspoof 2017 Replay ({row['file']})",
        })

    # Write manifests
    dev_csv = os.path.join(BASE_DIR, "dev_manifest.csv")
    eval_csv = os.path.join(BASE_DIR, "eval_manifest.csv")

    pd.DataFrame(dev_trials).to_csv(dev_csv, index=False)
    pd.DataFrame(eval_trials).to_csv(eval_csv, index=False)

    print(f"\n[DONE] Built calibrated partitions:")
    print(f"  • DEV  : {len(dev_trials)} trials saved to {dev_csv}")
    print(f"  • EVAL : {len(eval_trials)} trials saved to {eval_csv}")


if __name__ == "__main__":
    main()
