# SASV Benchmark Provenance & Security Analysis

## 1. AASIST Checkpoint Verification & Representation Alignment

A rigorous cryptographic verification was performed on the AASIST checkpoint loaded via Hugging Face (`SpeechAntiSpoofingBenchmarks/AASIST`):

| Property | HuggingFace Local Checkpoint | Clova AI Canonical Repository (`clovaai/aasist`) | Verification Status |
| :--- | :--- | :--- | :---: |
| **File Name** | `AASIST.pth` | `models/weights/AASIST.pth` (commit `a04c986`) | **MATCH** |
| **Byte Size** | 1,281,532 bytes | 1,281,532 bytes | **MATCH** |
| **SHA-256** | `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0` | `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0` | **MATCH** |
| **Git Blob SHA-1** | `edbce171dbae13ae448f210e9fd62a0b861b5713` | `edbce171dbae13ae448f210e9fd62a0b861b5713` | **MATCH** |

### Head Projection & Representation Scoring
- In [`src/eval/sasv_scorer.py`](file:///c:/Projects/Integrated%20Spoof-Aware%20Speaker%20Verification%20for%20Secure%20Voice%20Authentication/src/eval/sasv_scorer.py), the 160-dimensional penultimate representations pre-extracted from the official SASV 2022 baseline are scored using the classifier head extracted from this checkpoint:
  $$\text{score}_{\text{cm}} = (w_{\text{bonafide}} - w_{\text{spoof}}) \cdot x_{\text{cm}} + (b_{\text{bonafide}} - b_{\text{spoof}})$$
- **Methodological Scope:** The **2.63% SASV-EER** is treated specifically as the result of this scoring procedure on the official precomputed baseline representations. Until an end-to-end forward pass on raw audio waveforms across all 102,579 challenge audio files is computed, this figure is strictly an **offline representation benchmark result**.

---

## 2. Offline Benchmark Score Space vs. Live Pipeline Score Space

Offline representation benchmark scores and live microphone pipeline scores exist in **fundamentally different score spaces**:

| System Dimension | Offline Benchmark (`data/benchmark/eval_scores.csv`) | Live Experimental Pipeline (`models/live_pipeline_metadata.json`) |
| :--- | :--- | :--- |
| **Status** | Validated Official Protocol (102,579 Trials) | **EXPERIMENTAL_PILOT_ONLY** (42 Multi-Speaker Dataset Trials) |
| **ASV Architecture** | `TaoRuijie/ECAPATDNN` (pretrained on VoxCeleb2) | `SpeechBrain/spkrec-ecapa-voxceleb` (16 kHz mono raw waveform) |
| **Target ASV Cosine Range** | $\sim 0.65$ to $0.95$ | $\sim 0.25$ to $0.55$ (short utterances, domain acoustic shifts) |
| **Human Impostor ASV Range**| $\sim -0.15$ to $0.35$ | $\sim -0.10$ to $0.25$ |
| **CM Input** | Precomputed 160-d penultimate embeddings | 64,600 raw waveform audio samples via local PyTorch AASIST |
| **DEV Fusion Weights** | $w_{\text{asv}}=5.7398,\; w_{\text{cm}}=0.2297,\; b=-4.4233$ | $w_{\text{asv}}=12.7265,\; w_{\text{cm}}=0.1767,\; b=-3.4780$ (Trained PyTorch Logistic Regression on DEV) |
| **Operational Thresholds**| $\tau_{\text{EER}} = 0.7233,\quad \tau_{\text{Strict}} = 1.3610$ | Convenience: $\tau=-0.3500$, Balanced: $\tau=0.2000$, Strict: $\tau=0.4314$ |

### Operational Rule
- The DEV-derived **1.3610** and **0.7233** values are **offline representation benchmark operating points**.
- Applying $1.3610$ directly to live microphone inference would lead to complete false rejection of genuine users because the live SpeechBrain cosine similarity distribution is centered lower than TaoRuijie's representation space.
- The live backend operates via [`models/live_pipeline_metadata.json`](file:///c:/Projects/Integrated%20Spoof-Aware%20Speaker%20Verification%20for%20Secure%20Voice%20Authentication/models/live_pipeline_metadata.json), explicitly labeled with `status: "EXPERIMENTAL_PILOT_ONLY"`. Every API authentication response and telemetry payload attaches this status.

---

## 3. Multi-Speaker Pilot Trial Sets, Partition Provenance & Gate Separation

### Partition Structure & Enrollment Provenance
- **Account Enrollment Templates:** The account templates (`spk_alpha_enroll.wav`, `spk_beta_enroll.wav`) are intentionally shared across DEV and EVAL to evaluate authentication against existing enrolled accounts. The partitions are therefore **not completely disjoint in enrollment templates**, though all test audio recordings are strictly distinct.
- **Third Speaker Partition Disjointness:** DEV enrolls and evaluates `spk_gamma` (studio-clean slice), whereas EVAL enrolls and evaluates `spk_delta` (disjoint studio slice).
- **Trial Composition (21 Trials per Partition):**
  - 3 Target Genuine trials (`spk_alpha`, `spk_beta`, `spk_gamma`/`spk_delta`)
  - 8 Human Impostor trials (cross-speaker authentic pairs)
  - 4 Target Spoofs (synthetic vocoder clones and replay attacks directly impersonating the enrolled speaker)
  - 6 Non-Target Spoofs (attacks using acoustic variants of unrelated speakers)

### Target Spoofs vs. Non-Target Spoofs: Why Gate Separation Matters
In previous iterations, all spoof clips were paired against an unrelated enrollment account. Standalone speaker verification trivially rejected them because the speaker didn't match ($s_{\text{asv}} \approx -0.05$ to $0.15$), masking whether AASIST or fusion contributed anything beyond speaker mismatch.

To establish whether the countermeasure contributes beyond speaker verification, we generated and evaluated **Target Spoofs** where the attack audio is synthesized or replayed from the claimed enrolled identity:

| Decision Gate | Threshold | Target Genuine Acceptance (TAR) | Human Impostor Rejection | Target Spoof Rejection | Non-Target Spoof Rejection | Overall Spoof Rejection |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standalone ASV Gate** | $\tau_{\text{asv}} = 0.3000$ | 66.7% (2/3) | **100.0%** (8/8) | **50.0%** (2/4) *(FAILS: Accepts 2 target spoofs!)* | **100.0%** (6/6) | 80.0% (8/10) |
| **Standalone CM Gate** | $\tau_{\text{cm}} = -4.5000$ | 66.7% (2/3) | **25.0%** (2/8) *(FAILS: Passes 6 human impostors!)* | **75.0%** (3/4) | **16.7%** (1/6) | 40.0% (4/10) |
| **Fused (high_convenience [Pure])** | $\tau_{\text{fus}} = -0.3500$ | **100.0%** (3/3) | **100.0%** (8/8) | **25.0%** (1/4) | **100.0%** (6/6) | 70.0% (7/10) |
| **Fused (balanced [Pure])** | $\tau_{\text{fus}} = 0.2000$ | 66.7% (2/3) | **100.0%** (8/8) | **25.0%** (1/4) | **100.0%** (6/6) | 70.0% (7/10) |
| **Fused (strict_security [Pure])** | $\tau_{\text{fus}} = 0.4314$ | 66.7% (2/3) | **100.0%** (8/8) | **50.0%** (2/4) *(FAILS: Accepts Beta clone & replay!)* | **100.0%** (6/6) | 80.0% (8/10) |
| **Fused (strict_security [Gated])** | $\tau_{\text{fus}} = 0.4314$ | **33.3%** (1/3) *(COST: Rejects EVAL-B-GEN)* | **100.0%** (8/8) | **100.0%** (4/4) *(BLOCKS ALL TARGET ATTACKS)* | **100.0%** (6/6) | **100.0%** (10/10) |

### Key Experimental Insights:
1. **The Pure Fusion Flaw on Enrolled Target Attacks:** In unconstrained linear score fusion, high voice similarity ($s_{\text{asv}} \ge +0.718$) on `speaker_beta` synthetic clone ($s_{\text{fus}}=+4.59$) and replay ($s_{\text{fus}}=+4.81$) completely overpowers the negative CM warning ($s_{\text{cm}} \approx -6.06, -5.85$), exceeding the strict threshold $\tau=0.4314$. Thus, unconstrained linear fusion provides NO hard anti-spoof guarantee and rejects only 50% (2/4) of EVAL target attacks.
2. **Mandatory Anti-Spoof Safeguard Gate:** When the pipeline enforces that a countermeasure failure ($s_{\text{cm}} < \tau_{\text{cm}}$) mandatorily blocks access (`require_cm_gate = True`), Target Spoof Rejection on EVAL reaches **100.0% (4/4)**, correctly denying both Beta clone and replay attacks with verdict `SUSPECTED_SPOOF`.
3. **The Genuine-User Cost & CM Distribution Overlap:** Enforcing the mandatory CM gate drops EVAL genuine acceptance from 66.7% (2/3) to **33.3% (1/3)**. This occurs because the authentic probe for speaker Beta (`EVAL-B-GEN`) scored $s_{\text{cm}} = -6.2595$, which is lower (more spoof-like according to AASIST) than the synthetic clone ($-6.0606$) and replay ($-5.8459$). On this sample, acoustic properties caused an inversion between authentic and attack audio, meaning no static CM threshold can separate authentic Beta from its attacks without penalizing genuine access.
4. **Policy Derivation and Partition Integrity:**
   - Operating thresholds are derived strictly from DEV partition distributions, avoiding EVAL data snooping.
   - **High Convenience** ($\tau = -0.3500$) is an empirically permissive tier calibrated on DEV to minimize false rejections. On DEV, it accepts 1/8 human impostors and 3/4 target spoofs. Its observed 3/3 genuine acceptance on EVAL is a measured pilot observation across three clips, not an operational zero-false-rejection guarantee.
   - EVAL should not be described as untouched validation if thresholds are selected with foreknowledge of EVAL outcomes.
5. **Operational Scope:** A 42-trial pilot across 3 enrolled accounts proves execution pathways and demonstrates the mathematical necessity of a mandatory anti-spoof gate. However, establishing an operational security policy or production FAR/FRR requires a substantially larger corpus of genuine speakers and targeted attacks to overcome small-sample acoustic inversion.

---

## 4. Operational Decisions vs. Ground-Truth Labels

At inference time, an automated biometric system outputs **operational access decisions and diagnostic hypotheses**, NOT known physical ground truth:

- **`AUTHENTICATED` (Access Granted):** The fused decision score meets or exceeds the operational threshold, and the dynamic spoken challenge passed verification. This is an access grant decision, not an ontological assertion of dataset ground truth.
- **`SPEAKER_MISMATCH` (Access Denied):** The countermeasure check passed, but voice similarity fell below the required speaker threshold.
- **`SUSPECTED_SPOOF` (Access Denied):** Voice similarity matched the claimed identity, but AASIST flagged synthetic spectral artifacts or anomalous acoustic cues.
- **`MARGINAL_FUSION_REJECTION` (Access Denied):** Both individual scores met standalone baseline minimums, but their linear combination fell short of the joint fusion threshold.
- **`DUAL_CRITERIA_FAILURE` (Access Denied):** Neither the speaker verification nor the countermeasure criteria were satisfied.
- **`CHALLENGE_FAILED` (Access Denied):** Audio failed prompt transcription, missed the mandatory security number, or replayed an expired token.
- **`POOR_AUDIO_QUALITY` (Access Denied):** Audio signal is too faint or silent (RMS energy below minimum threshold).

---

## 5. Dynamic Spoken Challenge: Scope and Adversarial Boundaries

The dynamic challenge subsystem in [`src/core/challenge_manager.py`](file:///c:/Projects/Integrated%20Spoof-Aware%20Speaker%20Verification%20for%20Secure%20Voice%20Authentication/src/core/challenge_manager.py) enforces three structural defenses:
1. **Time-to-Live (TTL):** Challenges expire strictly after 20 seconds.
2. **Single-Use Nonce:** Challenge sessions are immediately consumed upon submission, preventing immediate replay.
3. **Mandatory Random Security Number:** Every phrase contains a randomized 2-digit number (e.g. "54") that must be transcribed by Whisper ASR alongside $\ge 80\%$ token overlap.

### Scope and Adversarial Boundaries:
- **Defeated Attacks:** Static pre-recorded voice clips, pre-synthesized audio files, eavesdropped audio from prior sessions, and static soundboard playback.
- **Known Limitations:** Transcribing the challenge phrase proves **freshness and phrase compliance**, NOT biological human physical presence. It remains vulnerable to:
  - Live human audio relays (e.g. relaying audio through an active phone call to an accomplice).
  - Responsive real-time voice conversion pipelines that ingest the live prompt and stream converted audio within the 20-second window.

---

## 6. Unit Testing vs. Live Operational Security Performance

The unit test suite in [`scripts/test_backend.py`](file:///c:/Projects/Integrated%20Spoof-Aware%20Speaker%20Verification%20for%20Secure%20Voice%20Authentication/scripts/test_backend.py):
- Validates the default operational policy from [`models/live_pipeline_metadata.json`](file:///c:/Projects/Integrated%20Spoof-Aware%20Speaker%20Verification%20for%20Secure%20Voice%20Authentication/models/live_pipeline_metadata.json), confirming that genuine users are correctly **ACCEPTED** (`AUTHENTICATED`), while human impostors and synthetic/replay attacks are **DENIED**.
- Serves as a **software integration and wiring verification suite**. It verifies schema validity, structured reason formatting, session lifetime states, and exception handling deterministically without physical microphone hardware.
- **Does NOT establish live biometric security performance** across real-world diverse microphone populations. Live biometric security claims require continuous multi-channel live audio data collection.
