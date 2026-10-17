import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

# Create figure
fig = plt.figure(figsize=(20, 11), dpi=300)
ax = fig.add_subplot(111)
ax.set_xlim(0, 20)
ax.set_ylim(0, 11)
ax.axis('off')

# Background
fig.patch.set_facecolor('#f8fafc')
ax.set_facecolor('#f8fafc')

# Palette
THEMES = {
    'client': {'bg': '#ffffff', 'border': '#3b82f6', 'header': '#1d4ed8', 'badge': '#eff6ff', 'tag': 'LAYER 0 · CLIENT'},
    'api': {'bg': '#ffffff', 'border': '#0284c7', 'header': '#0369a1', 'badge': '#f0f9ff', 'tag': 'GATEWAY & PREP'},
    'asv': {'bg': '#ffffff', 'border': '#6366f1', 'header': '#4338ca', 'badge': '#eef2ff', 'tag': 'ENGINE 1 · BIOMETRICS'},
    'cm': {'bg': '#ffffff', 'border': '#ec4899', 'header': '#be185d', 'badge': '#fdf2f8', 'tag': 'ENGINE 2 · ANTI-SPOOF'},
    'asr': {'bg': '#ffffff', 'border': '#8b5cf6', 'header': '#6d28d9', 'badge': '#f5f3ff', 'tag': 'ENGINE 3 · LIVENESS'},
    'fusion': {'bg': '#ffffff', 'border': '#10b981', 'header': '#047857', 'badge': '#ecfdf5', 'tag': 'DECISION FUSION'},
    'output': {'bg': '#ffffff', 'border': '#0f172a', 'header': '#0f172a', 'badge': '#f8fafc', 'tag': 'ACCESS DECISION'},
    'storage': {'bg': '#ffffff', 'border': '#64748b', 'header': '#334155', 'badge': '#f1f5f9', 'tag': 'DATA & REPOSITORY'},
}

def draw_card(x, y, w, h, theme_key, title, subtitle=None, items=None, r=0.22):
    t = THEMES[theme_key]
    # Drop shadow
    shadow = patches.FancyBboxPatch((x + 0.05, y - 0.05), w, h,
                                    boxstyle=f"round,pad=0.0,rounding_size={r}",
                                    facecolor='#0f172a', alpha=0.04, edgecolor='none')
    ax.add_patch(shadow)
    
    # Card surface
    card = patches.FancyBboxPatch((x, y), w, h,
                                  boxstyle=f"round,pad=0.0,rounding_size={r}",
                                  facecolor=t['bg'], edgecolor=t['border'], linewidth=1.7)
    ax.add_patch(card)
    
    # Tag Pill
    tag_text = t['tag']
    pill_w = len(tag_text) * 0.075 + 0.35
    pill = patches.FancyBboxPatch((x + 0.22, y + h - 0.42), pill_w, 0.28,
                                 boxstyle="round,pad=0.0,rounding_size=0.08",
                                 facecolor=t['badge'], edgecolor=t['border'], linewidth=0.8)
    ax.add_patch(pill)
    ax.text(x + 0.22 + pill_w/2, y + h - 0.28, tag_text,
            fontsize=7.2, fontweight='bold', color=t['header'], ha='center', va='center')
    
    # Title
    ax.text(x + 0.22, y + h - 0.76, title,
            fontsize=11.2, fontweight='bold', color='#0f172a', va='center')
    
    # Subtitle
    cur_y = y + h - 1.06
    if subtitle:
        ax.text(x + 0.22, cur_y, subtitle, fontsize=8.2, color='#64748b', va='center')
        cur_y -= 0.32
        
    # Bullet points
    if items:
        for item in items:
            if item == "---":
                cur_y -= 0.15
                continue
            if item.startswith("  "):
                ax.text(x + 0.55, cur_y, item.strip(), fontsize=7.8, color='#475569', va='center')
            elif item.startswith("•") or item.startswith("✓") or item.startswith("✕"):
                ax.text(x + 0.35, cur_y, item, fontsize=8.0, fontweight='bold', color='#1e293b', va='center')
            else:
                ax.plot([x + 0.32], [cur_y], marker='o', markersize=3.2, color=t['header'])
                ax.text(x + 0.50, cur_y, item, fontsize=8.0, color='#334155', va='center')
            cur_y -= 0.34

def draw_arrow(x1, y1, x2, y2, label=None, color='#64748b', rad=0.0, label_pos=0.5, label_dy=0.22):
    style = f"arc3,rad={rad}"
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.8, shrinkA=3, shrinkB=3,
                                mutation_scale=13, connectionstyle=style, capstyle='round'))
    if label:
        mx = x1 + (x2 - x1) * label_pos
        my = y1 + (y2 - y1) * label_pos + label_dy
        ax.text(mx, my, label, fontsize=7.5, fontweight='bold', color=color,
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.22', facecolor='#ffffff', edgecolor='#cbd5e1', lw=0.7))

# ==================== HEADER ====================
ax.text(10.0, 10.35, "VoiceGuard AI: System Architecture",
        fontsize=22, fontweight='heavy', color='#0f172a', ha='center', va='center')
ax.text(10.0, 9.95, "Integrated Spoof-Aware Speaker Verification (SASV) · Tri-Layer Deep Neural Architecture",
        fontsize=10.5, color='#64748b', ha='center', va='center')

# ==================== 1. CLIENT LAYER (X: 0.7 -> 3.6) ====================
draw_card(0.7, 5.0, 2.9, 4.4, 'client',
          "Client Interface", "Browser Web Audio & UI",
          ["Interactive Recording Studio",
           "Guided Sentence Prompts",
           "16-bit PCM WAV Downsampler",
           "Native 16 kHz Resampling",
           "Real-Time Waveform Monitor",
           "Dynamic Challenge View",
           "Audit Review & Diagnostics"])

draw_card(0.7, 0.9, 2.9, 3.6, 'storage',
          "Persistent Vault", "Local File Storage & DB",
          ["Enrolled Voiceprints (.npy)",
           "Speaker Metadata (JSON)",
           "Audio Reference Recordings",
           "Cryptographic Nonce Cache",
           "Verification Audit History",
           "Calibrated Policy Metadata"])

# ==================== 2. API GATEWAY & PREPROCESSING (X: 4.2 -> 6.9) ====================
draw_card(4.2, 5.0, 2.7, 4.4, 'api',
          "FastAPI Gateway", "API Routing & Signal Prep",
          ["REST API Endpoints (/api/v1)",
           "Multi-Utterance Enrollment",
           "Voice Activity Detection (VAD)",
           "RMS Energy & Clipping Check",
           "Anti-Aliased 16kHz Filter",
           "Security Policy Controller",
           "Session HMAC Validation"])

# Template reference matcher card below API
draw_card(4.2, 0.9, 2.7, 3.6, 'storage',
          "Template Manager", "Enrollment Repository",
          ["Multi-Utterance Template Mean",
           "L2-Normalized 192-d Vectors",
           "Speaker Registry Catalog",
           "Reference Audio Retrieval",
           "Atomic Enrollment Storage",
           "Calibrated Anti-Spoof Gate"])

# ==================== 3. THREE PARALLEL VERIFICATION ENGINES (X: 7.6 -> 11.2) ====================
# Engine 1: ECAPA-TDNN (Top)
draw_card(7.6, 6.8, 3.6, 2.6, 'asv',
          "Speaker Verification", "ECAPA-TDNN Architecture",
          ["192-Dimensional Bottleneck",
           "Squeeze-Excitation Blocks",
           "Cosine Similarity vs Template",
           "Output Score: S_asv in [-1.0, +1.0]"])

# Engine 2: AASIST (Middle)
draw_card(7.6, 3.9, 3.6, 2.6, 'cm',
          "Anti-Spoof Countermeasure", "AASIST Graph Neural Network",
          ["Raw Waveform Spectral Graph",
           "Heterogeneous Attention Graph",
           "Detects TTS, Voice Cloning, Replay",
           "Output Score: S_cm (Log-Likelihood)"])

# Engine 3: Whisper ASR (Bottom)
draw_card(7.6, 1.0, 3.6, 2.6, 'asr',
          "Challenge Liveness ASR", "OpenAI Whisper (small.en)",
          ["Dynamic Randomized Challenge",
           "Single-Use Nonce & TTL (45s)",
           "Speech-to-Text Transcription",
           "Defeats Pre-Recorded Replay"])

# ==================== 4. DECISION FUSION ENGINE (X: 11.9 -> 15.4) ====================
draw_card(11.9, 1.0, 3.5, 8.4, 'fusion',
          "Decision Fusion Engine", "Multi-Tier Policy & Gating",
          ["Logistic Regression Score Fusion:",
           "  S_fus = w_asv·S_asv + w_cm·S_cm + b",
           "---",
           "Triple-Gate Security Enforcement:",
           "• Gate 1: Spoken Challenge Pass",
           "  Matches target words & numbers",
           "• Gate 2: Anti-Spoof Gate (AASIST)",
           "  Requires: S_cm >= Threshold_cm",
           "• Gate 3: Biometric Identity Match",
           "  Requires: S_asv >= Threshold_asv",
           "• Gate 4: Combined Fusion Metric",
           "  Requires: S_fus >= Threshold_fus",
           "---",
           "Explainable Diagnostics Engine:",
           "• Detailed Verdict Breakdown",
           "• Real-Time Processing Telemetry",
           "• Granular Failure Reasons"])

# ==================== 5. FINAL ACCESS VERDICT (X: 16.1 -> 19.3) ====================
draw_card(16.1, 3.0, 3.2, 5.0, 'output',
          "Access Decision", "Final Authentication Verdict",
          ["✓ ACCESS GRANTED",
           "  • Identity Verified (S_asv)",
           "  • Genuine Human Voice (S_cm)",
           "  • Fresh Spoken Challenge (ASR)",
           "---",
           "✕ ACCESS DENIED",
           "  • Suspected Synthetic/Spoof",
           "  • Speaker Voice Mismatch",
           "  • Stale / Incorrect Challenge",
           "---",
           "Audit Telemetry & JSON Export"])

# ==================== CLEAN FLOW ARROWS ====================
# Client -> Gateway
draw_arrow(3.6, 7.2, 4.2, 7.2, "16kHz Audio", color='#1d4ed8', label_dy=0.24)

# Storage <-> Template Manager
draw_arrow(3.6, 2.7, 4.2, 2.7, "Enrolled Vault", color='#475569')

# Gateway -> 3 Engines (Clean divergence)
draw_arrow(6.9, 7.8, 7.6, 8.1, "Processed Audio", color='#4338ca', rad=0.03)
draw_arrow(6.9, 7.0, 7.6, 5.2, "Raw Waveform", color='#be185d', rad=0.0)
draw_arrow(6.9, 6.2, 7.6, 2.3, "Challenge Audio", color='#6d28d9', rad=-0.08)

# Template Manager -> Decision Engine (Clean direct feed from below)
draw_arrow(6.9, 2.7, 7.6, 2.7, "", color='#475569') # subtle link to bottom
draw_arrow(6.9, 1.8, 11.9, 1.8, "Enrolled Speaker Template Vector", color='#4338ca', rad=-0.12, label_dy=-0.28, label_pos=0.45)

# 3 Engines -> Decision Fusion
draw_arrow(11.2, 8.1, 11.9, 7.6, "S_asv Score", color='#4338ca')
draw_arrow(11.2, 5.2, 11.9, 5.2, "S_cm Score", color='#be185d')
draw_arrow(11.2, 2.3, 11.9, 3.2, "ASR Verification", color='#6d28d9')

# Decision Fusion -> Output
draw_arrow(15.4, 5.5, 16.1, 5.5, "Verdict & Scores", color='#047857', label_dy=0.25)

# Save figure
out_dir = Path("d:/S_NLP/Integrated Spoof-Aware Speaker Verification for Secure Voice Authentication")
out_img = out_dir / "system_architecture.png"
plt.tight_layout()
plt.savefig(str(out_img), bbox_inches='tight', dpi=300, facecolor='#f8fafc')
plt.close()
print(f"Refined system architecture diagram generated at: {out_img}")
