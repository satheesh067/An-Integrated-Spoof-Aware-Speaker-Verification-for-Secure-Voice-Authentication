import os
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

BACKUP_PATH = Path("Secure-Biometric-Voice-Authentication-Using-NLP-Based-Speaker-Verification-and-Anti-Spoofing.pptx.backup")
TARGET_PATH = Path("Secure-Biometric-Voice-Authentication-Using-NLP-Based-Speaker-Verification-and-Anti-Spoofing.pptx")
DIAGRAM_PATH = Path("scratch/system_architecture_flowchart.png")

prs = Presentation(BACKUP_PATH)

# Colors
C_WHITE = RGBColor(0xF2, 0xF5, 0xFA)
C_LIGHT = RGBColor(0xEB, 0xED, 0xF0)
C_MUTED = RGBColor(0x94, 0xA3, 0xB8)
C_CYAN = RGBColor(0x38, 0xBD, 0xF8)
C_GREEN = RGBColor(0x34, 0xD3, 0x99)
C_RED = RGBColor(0xF8, 0x71, 0x71)
C_ORANGE = RGBColor(0xFB, 0x92, 0x3C)
C_PURPLE = RGBColor(0x81, 0x8C, 0xF8)
C_YELLOW = RGBColor(0xFA, 0xCC, 0x15)

F_HEAD = "Geist Bold"
F_BODY = "Geist"

def set_para(p, text, size=11, color=C_LIGHT, bold=False, space_after=4):
    p.text = text
    p.font.name = F_HEAD if bold else F_BODY
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.space_after = Pt(space_after)

def populate_text_frame(tf, items):
    """
    items is a list of tuples: (text, size, color, bold, space_after)
    """
    tf.word_wrap = True
    paras = tf.paragraphs
    for idx, item in enumerate(items):
        if idx < len(paras):
            p = paras[idx]
        else:
            p = tf.add_paragraph()
        text, size, col, bold, sp = item
        set_para(p, text, size, col, bold, sp)
    # Clear any extra
    for extra_idx in range(len(items), len(paras)):
        paras[extra_idx].text = ""

# ==============================================================================
# Slide 1: Title Slide
# ==============================================================================
s1 = prs.slides[0]
for sh in s1.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Secure Biometric Voice Authentication Using NLP-Based Speaker Verification and Anti-Spoofing", 30, C_WHITE, True, 10),
            ("Review 2 — Comprehensive Project Implementation & Experimental Defense", 16, C_CYAN, False, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("Review 2", 15, C_WHITE, True, 2)
        ])
    elif sh.name == "Text 2":
        populate_text_frame(sh.text_frame, [
            ("Palli Pavan Kumar — 23MID0181", 12, C_LIGHT, False, 4),
            ("Venkata Sateesh M — 23MID0179", 12, C_LIGHT, False, 4),
            ("Mohammed Irfanulla N — 23MID0090", 12, C_LIGHT, False, 4),
            ("Saswat Subhang — 23MID0075", 12, C_LIGHT, False, 4),
        ])

# ==============================================================================
# Slide 2: Threat Landscape & Limitations of Conventional ASV
# ==============================================================================
s2 = prs.slides[1]
for sh in s2.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Threat Landscape & Limitations of Conventional ASV", 25, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 2":
        populate_text_frame(sh.text_frame, [
            ("Voice Biometric Threat Taxonomy", 15, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 3":
        populate_text_frame(sh.text_frame, [
            ("• Neural TTS Voice Cloning: Modern generative models (ElevenLabs, VITS) synthesize photorealistic human speech from <5s of audio, perfectly cloning target speaker timbre.", 10.5, C_LIGHT, False, 8),
            ("• Voice Conversion (VC): Latent identity transformation mapping attacker prosody onto target speaker embeddings while retaining spoken words.", 10.5, C_LIGHT, False, 8),
            ("• Acoustic Replay Attacks: High-fidelity loudspeaker playback capturing and re-transmitting genuine enrollment utterances into microphones.", 10.5, C_LIGHT, False, 8),
            ("• Zero-Day Vocoder Artifacts: Subtle synthetic artifacts, latent phase incoherencies, and high-frequency roll-offs in generated audio.", 10.5, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("Limitations of Conventional ASV", 15, C_ORANGE, True, 4)
        ])
    elif sh.name == "Text 6":
        populate_text_frame(sh.text_frame, [
            ("• The Fatal Blindspot: Conventional ASV (pure ECAPA-TDNN) measures only acoustic similarity (s_asv). Modern voice clones achieve s_asv > 0.70, causing a 100% false accept vulnerability to targeted deepfakes.", 10.5, C_LIGHT, False, 8),
            ("• Disjoint Architecture: Standalone ASV and Countermeasure (CM) modules operate in isolation without joint score fusion or cross-risk calibration.", 10.5, C_LIGHT, False, 8),
            ("• Absence of Dynamic Liveness: Static passphrases fail completely against recorded audio playback, live replay, and responsive voice generation.", 10.5, C_LIGHT, False, 4)
        ])

# ==============================================================================
# Slide 3: End-to-End System Architecture & Workflow
# ==============================================================================
s3 = prs.slides[2]
for sh in s3.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("End-to-End System Architecture & 5-Stage Verification Flow", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 4": # Step 1
        populate_text_frame(sh.text_frame, [
            ("Stage 1: Signal Diagnostics", 13, C_YELLOW, True, 2),
            ("16 kHz mono standardization, RMS >= 0.003, clipping & duration check.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 3": # Step 2
        populate_text_frame(sh.text_frame, [
            ("Stage 2: Dynamic Liveness", 13, C_CYAN, True, 2),
            ("OpenAI Whisper ASR, 20s TTL session nonce, 2-digit number verification.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 2": # Step 3 & 4
        populate_text_frame(sh.text_frame, [
            ("Stage 3 & 4: Dual Neural Verification", 13, C_GREEN, True, 2),
            ("AASIST Spectro-Temporal GAT (s_cm) + ECAPA-TDNN 192-d Cosine Match (s_asv).", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 1": # Step 5
        populate_text_frame(sh.text_frame, [
            ("Stage 5: Gated Score Fusion", 13, C_PURPLE, True, 2),
            ("Trained Logistic Regression + Non-linear hard countermeasure floor gate.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 5": # Bottom summary
        populate_text_frame(sh.text_frame, [
            ("Multi-Layer Defense Formulation: Jointly resolves Identity (ECAPA-TDNN), Authenticity (AASIST), and Live Presence (Whisper ASR), enforcing a mandatory countermeasure safeguard gate to block 100% of target attacks in <390 ms.", 11, C_WHITE, False, 2)
        ])

# ==============================================================================
# Slide 4: Identity Verification — ECAPA-TDNN
# ==============================================================================
s4 = prs.slides[3]
for sh in s4.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Identity Verification Layer — ECAPA-TDNN", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("SpeechBrain ECAPA-TDNN extracts 192-dimensional L2-normalized speaker embeddings robust to channel noise and acoustic variations, scoring via cosine similarity against enrolled templates.", 11, C_MUTED, False, 4)
        ])
    elif sh.name == "Text 3":
        populate_text_frame(sh.text_frame, [
            ("Architectural Mechanisms", 14, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 4":
        populate_text_frame(sh.text_frame, [
            ("• Res2Net Dilated Convolutions: Hierarchical multi-scale feature maps capture speaker-discriminative vocal tract acoustics.", 10, C_LIGHT, False, 6),
            ("• Squeeze-and-Excitation (SE): Channel-attention blocks dynamically rescale feature channels, suppressing non-speaker noise.", 10, C_LIGHT, False, 6),
            ("• Multi-layer Feature Aggregation (MFA): Concatenates shallow and deep representations for acoustic stability.", 10, C_LIGHT, False, 6),
            ("• Attentive Statistical Pooling (ASP): Weights temporal frames into a 192-d mean & standard deviation vector.", 10, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 6":
        populate_text_frame(sh.text_frame, [
            ("Scoring & Multi-Utterance Enrollment", 14, C_GREEN, True, 4)
        ])
    elif sh.name == "Text 7":
        populate_text_frame(sh.text_frame, [
            ("• Length-Normalized Cosine Similarity:  s_asv = (e_probe · e_enroll) / (||e_probe|| ||e_enroll||)", 10.5, C_WHITE, True, 6),
            ("• Multi-Utterance Enrollment: 3 genuine user recordings quality-checked, normalized, and averaged into an enrolled voice template.", 10, C_LIGHT, False, 6),
            ("• Live Score Dynamics: Target genuine matches score s_asv in [0.35, 0.75]; zero-effort human impostors score s_asv in [-0.10, 0.25].", 10, C_LIGHT, False, 4)
        ])

# ==============================================================================
# Slide 5: Anti-Spoofing Countermeasure — AASIST
# ==============================================================================
s5 = prs.slides[4]
for sh in s5.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Anti-Spoofing Countermeasure — AASIST", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("AASIST processes 16 kHz raw waveforms directly through SincNet filterbanks and heterogeneous spectro-temporal graph attention, exposing synthetic speech boundaries and vocoder phase anomalies.", 11, C_MUTED, False, 4)
        ])
    elif sh.name == "Text 2":
        populate_text_frame(sh.text_frame, [
            ("Raw Waveform & Graph Architecture", 14, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 3":
        populate_text_frame(sh.text_frame, [
            ("• Raw Waveform Input: Operates on 64,600 samples (4.04s) of 16 kHz audio without lossy spectrogram transforms, preserving crucial phase information.", 10, C_LIGHT, False, 6),
            ("• SincNet Bandpass Filterbanks: Learns bandpass filters directly from waveforms to capture frequency-selective artifact modulations.", 10, C_LIGHT, False, 6),
            ("• Heterogeneous Graph Attention: Nodes represent time-frequency patches; edges model spectral adjacency and temporal transitions to detect synthetic vocoder artifacts.", 10, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 4":
        populate_text_frame(sh.text_frame, [
            ("Countermeasure Scoring & Integrity", 14, C_RED, True, 4)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("• Dual Logit Score:  s_cm = logit_bonafide - logit_spoof", 11, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 6":
        populate_text_frame(sh.text_frame, [
            ("• Cryptographic Verification: Pretrained weights verified against Clova AI canonical repository (SHA-256: 51d2d9cf..., 1.28 MB).", 10, C_LIGHT, False, 6),
            ("• Score Behavior: Bona fide human speech yields positive logits (s_cm > 0), whereas synthetic vocoders drive scores strongly negative (s_cm << 0).", 10, C_LIGHT, False, 4)
        ])

# ==============================================================================
# Slide 6: Dynamic Liveness Verification — Whisper ASR
# ==============================================================================
s6 = prs.slides[5]
for sh in s6.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Dynamic Liveness Verification — Whisper ASR", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("Real-time challenge-response verification using server-issued ephemeral nonces and sequence-to-sequence ASR to defeat pre-recorded replay, live relays, and offline deepfakes.", 11, C_MUTED, False, 4)
        ])
    elif sh.name == "Text 4":
        populate_text_frame(sh.text_frame, [
            ("Step 1 — Ephemeral Challenge Nonce", 13, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("• Server generates a random phonetic phrase bound to a 2-digit number (e.g., 'WHISKEY-7-ECHO 42').", 9.5, C_LIGHT, False, 4),
            ("• Enforces a strict 20-second Time-To-Live (TTL); challenge is consumed immediately upon submission to prevent replay.", 9.5, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 8":
        populate_text_frame(sh.text_frame, [
            ("Step 2 — Real-Time Whisper ASR", 13, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 9":
        populate_text_frame(sh.text_frame, [
            ("• OpenAI Whisper (small.en) running on local CUDA GPU transcribes probe audio in ~320 ms latency.", 9.5, C_LIGHT, False, 4),
            ("• Sequence-to-sequence transformer decodes accurately under acoustic background noise and accented articulation.", 9.5, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 12":
        populate_text_frame(sh.text_frame, [
            ("Step 3 — Dual Alignment & Anti-Replay", 13, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 13":
        populate_text_frame(sh.text_frame, [
            ("• Word token overlap >= 60% AND mandatory exact extraction of the 2-digit security number.", 9.5, C_LIGHT, False, 4),
            ("• Defeats pre-recorded audio playback and static voice clones, as attackers cannot predict the dynamic challenge ahead of time.", 9.5, C_LIGHT, False, 4)
        ])

# ==============================================================================
# Slide 7: Learned Score Fusion & Non-Linear Safeguard Gate
# ==============================================================================
s7 = prs.slides[6]
for sh in s7.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Learned Score Fusion & Non-Linear Safeguard Gate", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("Resolving the Voice Clone Leak through trained PyTorch logistic regression, non-linear tandem gating, and calibrated operating policy tiers.", 11, C_MUTED, False, 4)
        ])
    elif sh.name == "Text 3":
        populate_text_frame(sh.text_frame, [
            ("Linear Fusion & The Voice Clone Leak", 14, C_RED, True, 4)
        ])
    elif sh.name == "Text 4":
        populate_text_frame(sh.text_frame, [
            ("• PyTorch Logistic Regression Trained on DEV:  s_fus = 12.7265·s_asv + 0.1767·s_cm - 3.4780", 10.5, C_WHITE, True, 6)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("• The Voice Clone Leak Discovery: High speaker similarity (s_asv = +0.7181) mathematically overwhelms negative CM scores (s_cm = -6.0606), pushing fused score to +4.5899 > tau_fus and leaking access! Pure linear fusion leaks 50% of target attacks.", 10, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 7":
        populate_text_frame(sh.text_frame, [
            ("The Tandem Safeguard Gate & Policy Tiers", 14, C_GREEN, True, 4)
        ])
    elif sh.name == "Text 8":
        populate_text_frame(sh.text_frame, [
            ("• Mandatory Safeguard Gate: Mandates s_cm >= tau_cm hard floor in tandem with s_fus >= tau_fus, blocking 100% (4/4) of target attacks on evaluation trials!", 10.5, C_WHITE, True, 8),
            ("• Calibrated DEV-Only Operating Policy Tiers:", 10.5, C_CYAN, True, 4),
            ("  - Balanced: tau_fus = +0.0783, tau_asv = +0.3130, tau_cm = -4.0694", 9.5, C_LIGHT, False, 3),
            ("  - Strict Security: tau_fus = +0.5052, tau_asv = +0.3237, tau_cm = -4.0694", 9.5, C_LIGHT, False, 3),
            ("  - High Convenience: tau_fus = -0.3486, tau_asv = +0.3024, tau_cm = -6.5000", 9.5, C_LIGHT, False, 3)
        ])

# ==============================================================================
# Slide 8: System Inputs, Outputs & Decision Taxonomy
# ==============================================================================
s8 = prs.slides[7]
for sh in s8.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("System Inputs, Outputs & Decision Taxonomy", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("System Input Specifications", 14, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 2":
        populate_text_frame(sh.text_frame, [
            ("• Audio Stream: 16 kHz 16-bit Mono PCM audio via Web Audio API or WAV upload.", 10, C_LIGHT, False, 6),
            ("• Claimed Identity: Canonical username string (e.g., 'user_alpha').", 10, C_LIGHT, False, 6),
            ("• Dynamic Session Nonce: Cryptographic challenge token (<= 20s TTL).", 10, C_LIGHT, False, 6),
            ("• Operating Policy: Server-enforced 'strict_security' (or balanced/convenience).", 10, C_LIGHT, False, 4)
        ])
    elif sh.name == "Text 4": # Output section title
        populate_text_frame(sh.text_frame, [
            ("7 Granular Decision Verdicts", 13, C_GREEN, True, 2)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("AUTHENTICATED: Target + genuine + fresh challenge. ACCESS GRANTED.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 6":
        populate_text_frame(sh.text_frame, [
            ("Security Denials", 13, C_RED, True, 2)
        ])
    elif sh.name == "Text 7":
        populate_text_frame(sh.text_frame, [
            ("SUSPECTED_SPOOF (Voice matched, AASIST detected clone/replay); SPEAKER_MISMATCH (Genuine voice, but wrong user); DUAL_CRITERIA_FAILURE.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 8":
        populate_text_frame(sh.text_frame, [
            ("Protocol & Diagnostics", 13, C_ORANGE, True, 2)
        ])
    elif sh.name == "Text 9":
        populate_text_frame(sh.text_frame, [
            ("CHALLENGE_FAILED (Expired token or wrong number); POOR_AUDIO_QUALITY (RMS < 0.003); MARGINAL_FUSION_REJECTION (Sub-scores pass, joint fails).", 9.5, C_LIGHT, False, 2)
        ])

# ==============================================================================
# Slide 9: System Architecture Flowchart & Operational Pipeline
# ==============================================================================
s9 = prs.slides[8]
# Replace Image 0 with our new generated architecture diagram
for sh in s9.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("System Architecture Flowchart & Operational Pipeline", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 1":
        populate_text_frame(sh.text_frame, [
            ("End-to-End Multimodal Execution Flow: Client captures 16 kHz audio and initiates a time-bound session. Stage 1 validates signal quality (RMS >= 0.003). Parallel AI streams execute Dynamic Liveness via Whisper ASR (Stage 2), Anti-Spoofing via raw-waveform AASIST (Stage 3), and Deep Speaker Verification via ECAPA-TDNN (Stage 4). Stage 5 applies learned logistic regression score fusion backed by a mandatory countermeasure safeguard gate, outputting 7 granular verdicts and telemetry in <390 ms with guaranteed state restoration.", 10.5, C_LIGHT, False, 6)
        ])
    elif sh.shape_type == 13: # Image 0
        img_left, img_top, img_width, img_height = sh.left, sh.top, sh.width, sh.height

# Remove old image shape and insert the new diagram
old_img = None
for sh in s9.shapes:
    if sh.shape_type == 13:
        old_img = sh
        break

if old_img is not None and DIAGRAM_PATH.exists():
    sp = old_img._element
    sp.getparent().remove(sp)
    # Add new picture with clean positioning
    s9.shapes.add_picture(str(DIAGRAM_PATH), Inches(0.7), Inches(1.8), Inches(7.5), Inches(4.7))

# Adjust Text 1 position to right side
for sh in s9.shapes:
    if sh.name == "Text 1":
        sh.left = Inches(8.4)
        sh.top = Inches(1.8)
        sh.width = Inches(4.4)
        sh.height = Inches(4.7)

# ==============================================================================
# Slide 10: Empirical Benchmarks, Evaluation Results & Hardware Telemetry
# ==============================================================================
s10 = prs.slides[9]
for sh in s10.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("Empirical Benchmarks, Evaluation Results & Hardware Telemetry", 24, C_WHITE, True, 4)
        ])
    elif sh.name == "Text 3":
        populate_text_frame(sh.text_frame, [
            ("Empirical Evaluation Comparison on Pilot EVAL Set (21 Trials across 4 Speakers):", 12, C_CYAN, True, 4),
            ("• Standalone ASV Gate: TAR: 66.7% (2/3) | Impostor Rej: 100.0% (8/8) | Target Spoof Rej: 50.0% (2/4 - Leaks 2 clones!) | Overall Spoof: 80.0%", 10, C_LIGHT, False, 3),
            ("• Standalone CM Gate: TAR: 66.7% (2/3) | Impostor Rej: 25.0% (2/8 - Fails on impostors!) | Target Spoof Rej: 75.0% (3/4) | Overall Spoof: 40.0%", 10, C_LIGHT, False, 3),
            ("• Fused (Pure Linear): TAR: 66.7% (2/3) | Impostor Rej: 100.0% (8/8) | Target Spoof Rej: 25.0% (1/4 - Leaks 3 clones!) | Overall Spoof: 70.0%", 10, C_LIGHT, False, 3),
            ("• Fused Strict Gated (Our System): Impostor Rejection: 100.0% (8/8) | Target Spoof Rej: 100.0% (4/4 BLOCKED) | Non-Target Spoof Rej: 100.0% (6/6) | Overall Spoof Rej: 100.0% (10/10)", 10.5, C_GREEN, True, 3)
        ])
    elif sh.name == "Text 5":
        populate_text_frame(sh.text_frame, [
            ("The Beta Score Inversion Finding", 14, C_YELLOW, True, 4)
        ])
    elif sh.name == "Text 6":
        populate_text_frame(sh.text_frame, [
            ("• Authentic Beta (EVAL-B-GEN): s_cm = -6.2595", 10, C_LIGHT, False, 3),
            ("• Beta Voice Clone (EVAL-B-TSPOOF-SYN): s_cm = -6.0606 [INVERTED]", 10, C_RED, True, 3),
            ("• Beta Replay Attack (EVAL-B-TSPOOF-REP): s_cm = -5.8459 [INVERTED]", 10, C_RED, True, 3),
            ("• Key Finding: Acoustic reverberation/compression caused authentic speech to score more negative than neural clones, proving 1D CM thresholds fail without multi-modal gating.", 9.5, C_LIGHT, False, 2)
        ])
    elif sh.name == "Text 8":
        populate_text_frame(sh.text_frame, [
            ("Live Hardware & Latency Telemetry", 14, C_CYAN, True, 4)
        ])
    elif sh.name == "Text 9":
        populate_text_frame(sh.text_frame, [
            ("• GPU Hardware: NVIDIA GeForce RTX 3050 Laptop GPU (CUDA 12.x)", 10, C_LIGHT, False, 3),
            ("• VRAM Footprint: ~1,011 MB allocated / 4,095 MB budget (lightweight)", 10, C_LIGHT, False, 3),
            ("• Latency Breakdown: ECAPA = 15.2 ms | AASIST = 24.8 ms | Whisper = 321.4 ms | Total E2E = 382.5 ms (real-time sub-second)", 10, C_LIGHT, False, 2)
        ])

# ==============================================================================
# Slide 11: System Implementation, Technology Stack & Summary
# ==============================================================================
s11 = prs.slides[10]
for sh in s11.shapes:
    if sh.name == "Text 0":
        populate_text_frame(sh.text_frame, [
            ("System Implementation, Technology Stack & Summary", 24, C_WHITE, True, 6),
            ("• Production Technology Stack: FastAPI REST server, PyTorch CUDA 12.x, SpeechBrain ECAPA-TDNN, AASIST raw waveform GAT, OpenAI Whisper small.en, and reactive Glassmorphic Web UI (/ui/).", 11, C_LIGHT, False, 5),
            ("• Production Security Controls: Server-controlled strict policy enforcement, outer try...finally state restoration eliminating cross-request memory pollution, and permanent audio audit trail.", 11, C_LIGHT, False, 5),
            ("• Automated Test Coverage: 7 Automated Backend Integration Test Suites passing (100% exit code 0) verifying enrollment, challenges, spoof detection, and threshold policies.", 11, C_LIGHT, False, 5),
            ("• Core Scientific Contribution: Identified the mathematical Voice Clone Leak in linear SASV fusion and proved that non-linear tandem countermeasure gating achieves 100% target attack blocking in <390 ms.", 11, C_CYAN, True, 8),
            ("Thank You! Questions & Discussion.", 20, C_GREEN, True, 4)
        ])

prs.save(TARGET_PATH)
print("Successfully generated and saved updated PPTX to:", TARGET_PATH)
