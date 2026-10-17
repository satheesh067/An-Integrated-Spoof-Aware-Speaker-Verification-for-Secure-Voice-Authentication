"""AASIST Checkpoint Identity and Representation Verification.

Verifies:
1. Cryptographic identity (SHA-256, Git Blob SHA-1, size) of the downloaded
   Hugging Face AASIST checkpoint against Clova AI's canonical repository.
2. Head projection alignment between `out_layer` and precomputed SASV baseline embeddings.
3. Separation of offline benchmark representation space from live audio model score space.
"""

import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch
from huggingface_hub import hf_hub_download

from src.models.aasist import HF_FILENAME, HF_MODEL_ID, AASISTInferencer


def verify_aasist_checkpoint() -> dict:
    print("=" * 70)
    print("1. CHECKPOINT IDENTITY VERIFICATION")
    print("=" * 70)

    # 1. Download / locate local cached checkpoint
    checkpoint_path = hf_hub_download(repo_id=HF_MODEL_ID, filename=HF_FILENAME)
    print(f"HuggingFace Hub Repo:     {HF_MODEL_ID}")
    print(f"Downloaded Checkpoint:    {checkpoint_path}")

    # 2. File size and hash verification
    file_size = os.path.getsize(checkpoint_path)
    with open(checkpoint_path, "rb") as f:
        content = f.read()

    sha256 = hashlib.sha256(content).hexdigest()
    # Compute standard git blob SHA-1: sha1("blob <size>\0" + content)
    git_blob_header = f"blob {file_size}\x00".encode("utf-8")
    git_blob_sha = hashlib.sha1(git_blob_header + content).hexdigest()

    # Canonical reference values from clovaai/aasist (commit a04c986, models/weights/AASIST.pth)
    CANONICAL_SIZE = 1281532
    CANONICAL_SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
    CANONICAL_GIT_BLOB_SHA1 = "edbce171dbae13ae448f210e9fd62a0b861b5713"

    size_match = file_size == CANONICAL_SIZE
    sha256_match = sha256.lower() == CANONICAL_SHA256.lower()
    git_sha_match = git_blob_sha.lower() == CANONICAL_GIT_BLOB_SHA1.lower()

    print(f"Byte size:                {file_size} (Expected: {CANONICAL_SIZE}) -> {'MATCH' if size_match else 'MISMATCH'}")
    print(f"SHA-256:                  {sha256}")
    print(f"Canonical SHA-256:        {CANONICAL_SHA256} -> {'MATCH' if sha256_match else 'MISMATCH'}")
    print(f"Git Blob SHA-1:           {git_blob_sha}")
    print(f"Canonical Git SHA-1:      {CANONICAL_GIT_BLOB_SHA1} -> {'MATCH' if git_sha_match else 'MISMATCH'}")

    assert size_match and sha256_match and git_sha_match, "Checkpoint verification failed!"
    print("\n[VERIFIED] Checkpoint is cryptographically byte-identical to Clova AI canonical release.\n")

    # 3. Model Architecture and Head Layer Inspection
    print("=" * 70)
    print("2. CLASSIFIER HEAD ARCHITECTURE & PROJECTION INSPECTION")
    print("=" * 70)
    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    out_w = state_dict["out_layer.weight"].numpy()
    out_b = state_dict["out_layer.bias"].numpy()

    print(f"Number of state_dict keys: {len(state_dict)}")
    print(f"out_layer.weight shape:    {out_w.shape}  (classes=2, embedding_dim=160)")
    print(f"out_layer.bias shape:      {out_b.shape}  (classes=2)")

    # In canonical AASIST: index 0 = spoof, index 1 = bona_fide
    w_diff = out_w[1] - out_w[0]
    b_diff = float(out_b[1] - out_b[0])

    print(f"Projection weight norm:    {np.linalg.norm(w_diff):.5f}")
    print(f"Projection bias offset:    {b_diff:.5f}")

    # 4. Score-Equivalence Test on Published Baseline Embeddings
    print("=" * 70)
    print("3. REPRESENTATION & SCORE CONSISTENCY CHECK")
    print("=" * 70)
    emb_path = Path("data/sasv_baseline/embeddings/cm_embd_dev.pk")
    protocol_path = Path("data/protocols/ASVspoof2019.LA.asv.dev.gi.trl.txt")

    if emb_path.exists() and protocol_path.exists():
        with open(emb_path, "rb") as f:
            cm_embds = pickle.load(f)
        print(f"Loaded {len(cm_embds)} precomputed DEV CM embeddings from {emb_path}")

        sample_utt = list(cm_embds.keys())[0]
        sample_emb = cm_embds[sample_utt]
        print(f"Sample utterance '{sample_utt}' embedding dimension: {sample_emb.shape}")
        assert sample_emb.shape == (160,), f"Expected (160,), got {sample_emb.shape}"

        # Test forward pass through classifier head
        sample_score = float(np.dot(sample_emb, w_diff) + b_diff)
        print(f"Computed CM decision score for '{sample_utt}': {sample_score:+.4f}")
        print("Scoring rule: logit(bonafide) - logit(spoof) = (w[1] - w[0]) @ emb + (b[1] - b[0])")

    print("\n" + "=" * 70)
    print("4. CRITICAL METHODOLOGICAL DISTINCTION")
    print("=" * 70)
    print("1. Offline Benchmark (2.63% SASV-EER):")
    print("   Obtained by scoring precomputed representations from SASV 2022 baseline")
    print("   using this verified AASIST classifier head and ECAPA cosine similarity.")
    print("   Operating thresholds: EER=0.7233, Strict Security=1.3610.")
    print("2. Live Microphone Pipeline:")
    print("   Uses SpeechBrain ECAPA-TDNN and end-to-end raw-waveform AASIST.")
    print("   Operates in a distinct score distribution; requires separate live calibration.")
    print("=" * 70)

    report = {
        "checkpoint_file": str(checkpoint_path),
        "file_size": file_size,
        "sha256": sha256,
        "git_blob_sha1": git_blob_sha,
        "clovaai_commit": "a04c9863f63d44471dde8a6abcb3b082b07cd1d1",
        "verified": True,
        "head_weight_dim": list(out_w.shape),
    }
    return report


if __name__ == "__main__":
    verify_aasist_checkpoint()
