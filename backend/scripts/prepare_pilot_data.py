"""Script to prepare a small, calibrated pilot dataset for SASV smoke testing.

Fetches genuine human reference samples and synthesizes/augments target spoof and replay samples.
Creates:
  - data/pilot/audio/
  - data/pilot/pilot_trials.json
  - data/pilot/pilot_trials.csv
"""

import os
import json
import csv
import numpy as np
import soundfile as sf
import scipy.signal
from huggingface_hub import hf_hub_download

PILOT_DIR = "data/pilot"
AUDIO_DIR = os.path.join(PILOT_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


def create_synthetic_voice_variant(data: np.ndarray, sr: int) -> np.ndarray:
    """Simulates vocoder/synthetic speech phase and harmonic quantization artifacts.

    Applies spectral comb filtering, phase dispersion, and robotic modulation
    characteristic of neural vocoders and synthesis artifacts.
    """
    # 1. Harmonic comb & robotic phase disturbance
    t = np.arange(len(data)) / sr
    modulator = 1.0 + 0.15 * np.sin(2 * np.pi * 120 * t)  # Pitch modulation
    synthetic = data * modulator

    # 2. Resample down and up to simulate vocoder band-limiting (e.g. 8kHz/12kHz vocoder bottleneck)
    low_sr = 12000
    down = scipy.signal.resample(synthetic, int(len(synthetic) * low_sr / sr))
    up = scipy.signal.resample(down, len(synthetic))

    # 3. Add high-frequency spectral phase smearing
    b, a = scipy.signal.butter(4, [1000 / (sr / 2), 6000 / (sr / 2)], btype="band")
    band_pass = scipy.signal.lfilter(b, a, up)

    spoof = 0.7 * up + 0.3 * band_pass
    return spoof.astype(np.float32)


def create_replay_variant(data: np.ndarray, sr: int) -> np.ndarray:
    """Simulates physical acoustic replay.

    Applies room reverberation impulse response, loudspeaker frequency rolloff,
    and background room hiss.
    """
    # 1. Acoustic room reflection impulse response (reverb)
    ir_len = int(0.2 * sr)  # 200 ms room response
    ir = np.zeros(ir_len)
    ir[0] = 1.0
    ir[int(0.03 * sr)] = 0.45  # Early wall reflection
    ir[int(0.07 * sr)] = 0.25  # Secondary reflection
    ir[int(0.12 * sr)] = 0.12  # Floor bounce
    decay = np.exp(-np.linspace(0, 5, ir_len))
    ir = ir * decay

    # Convolve with room impulse
    replayed = scipy.signal.fftconvolve(data, ir, mode="same")

    # 2. Loudspeaker & microphone bandpass limitation (cheap speaker frequency response)
    b, a = scipy.signal.butter(2, [300 / (sr / 2), 3800 / (sr / 2)], btype="band")
    replayed = scipy.signal.lfilter(b, a, replayed)

    # 3. Add ambient room microphone noise
    noise = np.random.normal(0, 0.005, len(replayed))
    replayed = replayed + noise

    # Normalize
    replayed = replayed / (np.max(np.abs(replayed)) + 1e-6) * 0.90
    return replayed.astype(np.float32)


def main():
    print("Preparing pilot data...")

    # 1. Download reference speech samples from HuggingFace SpeechBrain repo
    print("Downloading reference human speech samples...")
    ex1_path = hf_hub_download(
        repo_id="speechbrain/spkrec-ecapa-voxceleb", filename="example1.wav"
    )
    ex2_path = hf_hub_download(
        repo_id="speechbrain/spkrec-ecapa-voxceleb", filename="example2.flac"
    )

    data1, sr1 = sf.read(ex1_path, dtype="float32")
    data2, sr2 = sf.read(ex2_path, dtype="float32")

    # Resample both to 16kHz mono if needed
    if sr1 != 16000:
        data1 = scipy.signal.resample(data1, int(len(data1) * 16000 / sr1)).astype(np.float32)
    if sr2 != 16000:
        data2 = scipy.signal.resample(data2, int(len(data2) * 16000 / sr2)).astype(np.float32)

    # Split data1 into two distinct non-overlapping utterances for Speaker Alpha (enrollment & test)
    mid = len(data1) // 2
    spk_alpha_enroll = data1[:mid]
    spk_alpha_genuine = data1[mid:]
    spk_beta_impostor = data2[: len(spk_alpha_genuine)]

    # Generate synthetic voice attack (Target Spoof: sounds like Alpha, but synthetic vocoded)
    spk_alpha_synthetic = create_synthetic_voice_variant(spk_alpha_genuine, 16000)

    # Generate physical replay attack (Target Replay: Alpha replayed through acoustic channel)
    spk_alpha_replay = create_replay_variant(spk_alpha_genuine, 16000)

    # Save all audio files
    files = {
        "speaker_alpha_enroll.wav": spk_alpha_enroll,
        "speaker_alpha_genuine.wav": spk_alpha_genuine,
        "speaker_beta_impostor.wav": spk_beta_impostor,
        "speaker_alpha_synthetic_spoof.wav": spk_alpha_synthetic,
        "speaker_alpha_replay_spoof.wav": spk_alpha_replay,
    }

    for fname, audio in files.items():
        out_path = os.path.join(AUDIO_DIR, fname)
        sf.write(out_path, audio, 16000)
        print(f"Saved: {out_path} ({len(audio)/16000:.2f}s)")

    # 2. Build Pilot Trial List
    trials = [
        {
            "trial_id": "PILOT-01",
            "enrolled_speaker_id": "speaker_alpha",
            "enrolled_file": "speaker_alpha_enroll.wav",
            "test_file": "speaker_alpha_genuine.wav",
            "claimed_speaker": "speaker_alpha",
            "target_type": "target",
            "spoof_label": "bona_fide",
            "attack_type": "none",
            "source_provenance": "VoxCeleb reference (split segment B)",
            "expected_decision": "ACCESS_GRANTED",
            "expected_verdict": "TARGET_GENUINE",
        },
        {
            "trial_id": "PILOT-02",
            "enrolled_speaker_id": "speaker_alpha",
            "enrolled_file": "speaker_alpha_enroll.wav",
            "test_file": "speaker_beta_impostor.wav",
            "claimed_speaker": "speaker_alpha",
            "target_type": "impostor",
            "spoof_label": "bona_fide",
            "attack_type": "none",
            "source_provenance": "VoxCeleb reference (different speaker)",
            "expected_decision": "ACCESS_DENIED",
            "expected_verdict": "IMPOSTOR_HUMAN",
        },
        {
            "trial_id": "PILOT-03",
            "enrolled_speaker_id": "speaker_alpha",
            "enrolled_file": "speaker_alpha_enroll.wav",
            "test_file": "speaker_alpha_synthetic_spoof.wav",
            "claimed_speaker": "speaker_alpha",
            "target_type": "target",
            "spoof_label": "spoof",
            "attack_type": "synthetic_tts_vc",
            "source_provenance": "Calibrated vocoder/spectral perturbation of Speaker Alpha",
            "expected_decision": "ACCESS_DENIED",
            "expected_verdict": "SPOOF_ATTACK",
        },
        {
            "trial_id": "PILOT-04",
            "enrolled_speaker_id": "speaker_alpha",
            "enrolled_file": "speaker_alpha_enroll.wav",
            "test_file": "speaker_alpha_replay_spoof.wav",
            "claimed_speaker": "speaker_alpha",
            "target_type": "target",
            "spoof_label": "spoof",
            "attack_type": "physical_replay",
            "source_provenance": "Simulated acoustic room impulse & bandpass loudspeaker replay",
            "expected_decision": "ACCESS_DENIED",
            "expected_verdict": "SPOOF_ATTACK",
        },
    ]

    json_path = os.path.join(PILOT_DIR, "pilot_trials.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(trials, f, indent=2)

    csv_path = os.path.join(PILOT_DIR, "pilot_trials.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(trials[0].keys()))
        writer.writeheader()
        writer.writerows(trials)

    print(f"\nPilot trial list generated successfully:")
    print(f" - JSON: {json_path}")
    print(f" - CSV:  {csv_path}")


if __name__ == "__main__":
    main()
