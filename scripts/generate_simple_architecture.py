import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

# Set up clean canvas (16:9 widescreen, clean high-DPI)
fig = plt.figure(figsize=(16, 9), dpi=300)
ax = fig.add_subplot(111)
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis('off')

# Clean background
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#ffffff')

def draw_block(x, y, w, h, title, subtitle="", detail="", color='#3b82f6', bg='#f8fafc', r=0.18):
    # Soft shadow
    shadow = patches.FancyBboxPatch((x + 0.04, y - 0.04), w, h,
                                    boxstyle=f"round,pad=0.0,rounding_size={r}",
                                    facecolor='#0f172a', alpha=0.06, edgecolor='none')
    ax.add_patch(shadow)
    
    # Block surface
    box = patches.FancyBboxPatch((x, y), w, h,
                                 boxstyle=f"round,pad=0.0,rounding_size={r}",
                                 facecolor=bg, edgecolor=color, linewidth=2.0)
    ax.add_patch(box)
    
    # Content centering
    if subtitle and detail:
        ax.text(x + w/2, y + h*0.72, title, fontsize=12.5, fontweight='bold', color='#0f172a', ha='center', va='center')
        ax.text(x + w/2, y + h*0.46, subtitle, fontsize=10.0, fontweight='semibold', color=color, ha='center', va='center')
        ax.text(x + w/2, y + h*0.22, detail, fontsize=8.5, color='#64748b', ha='center', va='center')
    elif subtitle:
        ax.text(x + w/2, y + h*0.62, title, fontsize=13.0, fontweight='bold', color='#0f172a', ha='center', va='center')
        ax.text(x + w/2, y + h*0.35, subtitle, fontsize=9.5, color=color, ha='center', va='center')
    else:
        ax.text(x + w/2, y + h/2, title, fontsize=13.5, fontweight='bold', color='#0f172a', ha='center', va='center')

def draw_arrow(x1, y1, x2, y2, label="", color='#475569', lw=2.2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, shrinkA=2, shrinkB=2,
                                mutation_scale=16, capstyle='round'))
    if label:
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        ax.text(mx, my, label, fontsize=8.5, fontweight='bold', color=color,
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#ffffff', edgecolor='#cbd5e1', lw=1.0))

# ==================== MAIN TITLE ====================
ax.text(8.0, 8.45, "System Architecture: VoiceGuard AI",
        fontsize=21, fontweight='heavy', color='#0f172a', ha='center', va='center')
ax.text(8.0, 8.10, "Integrated Spoof-Aware Speaker Verification (SASV) · End-to-End Block Flow",
        fontsize=10.5, color='#64748b', ha='center', va='center')

# ==================== STAGE 1: VOICE INPUT ====================
# (Centered at top)
draw_block(x=5.2, y=6.7, w=5.6, h=1.0,
           title="1. Voice Input & Challenge Response",
           subtitle="Browser Microphone Capture (16 kHz, 16-bit PCM WAV)",
           color='#2563eb', bg='#eff6ff')

# Arrow: Input -> Preprocessing
draw_arrow(8.0, 6.7, 8.0, 5.7, label="Raw Audio")

# ==================== STAGE 2: PREPROCESSING ====================
draw_block(x=5.2, y=4.7, w=5.6, h=1.0,
           title="2. Audio Preprocessing Pipeline",
           subtitle="Voice Activity Detection (VAD) · Energy & Quality Checks · Resampling",
           color='#0284c7', bg='#f0f9ff')

# ==================== STAGE 3: 3 PARALLEL NEURAL ENGINES ====================
# Horizontal distribution line
y_bus = 4.15
ax.plot([2.5, 13.5], [y_bus, y_bus], color='#64748b', lw=2.0)
ax.plot([8.0, 8.0], [4.7, y_bus], color='#64748b', lw=2.0)

# Arrows down to each of the 3 engines
draw_arrow(2.5, y_bus, 2.5, 3.7)
draw_arrow(8.0, y_bus, 8.0, 3.7)
draw_arrow(13.5, y_bus, 13.5, 3.7)

# Engine 1 (Left): ASV
draw_block(x=0.8, y=2.4, w=3.4, h=1.3,
           title="Speaker Verification",
           subtitle="ECAPA-TDNN Model",
           detail="192-d Voiceprint vs Enrolled Template",
           color='#4f46e5', bg='#eef2ff')

# Engine 2 (Center): CM
draw_block(x=6.3, y=2.4, w=3.4, h=1.3,
           title="Anti-Spoof Countermeasure",
           subtitle="AASIST Graph Neural Net",
           detail="Detects Synthetic AI, TTS & Replays",
           color='#db2777', bg='#fdf2f8')

# Engine 3 (Right): Liveness ASR
draw_block(x=11.8, y=2.4, w=3.4, h=1.3,
           title="Spoken Challenge Liveness",
           subtitle="OpenAI Whisper (small.en)",
           detail="Verifies Fresh Dynamic Spoken Phrase",
           color='#7c3aed', bg='#f5f3ff')

# ==================== STAGE 4: FUSION & GATING ====================
# Arrows from 3 engines down to fusion
y_gather = 1.95
ax.plot([2.5, 13.5], [y_gather, y_gather], color='#64748b', lw=2.0)
ax.plot([2.5, 2.5], [2.4, y_gather], color='#4f46e5', lw=2.0)
ax.plot([8.0, 8.0], [2.4, y_gather], color='#db2777', lw=2.0)
ax.plot([13.5, 13.5], [2.4, y_gather], color='#7c3aed', lw=2.0)

# Labels on engine outputs
ax.text(2.5, 2.15, "Speaker Score (S_asv)", fontsize=7.8, fontweight='bold', color='#4f46e5', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#cbd5e1', lw=0.6))
ax.text(8.0, 2.15, "Spoof Score (S_cm)", fontsize=7.8, fontweight='bold', color='#db2777', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#cbd5e1', lw=0.6))
ax.text(13.5, 2.15, "Liveness Status (Pass/Fail)", fontsize=7.8, fontweight='bold', color='#7c3aed', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#cbd5e1', lw=0.6))

# Arrow into Decision Fusion
draw_arrow(8.0, y_gather, 8.0, 1.45)

draw_block(x=4.0, y=0.55, w=8.0, h=0.9,
           title="4. Decision Fusion & Multi-Gate Security Engine",
           subtitle="Score Fusion: S_fused = w1·S_asv + w2·S_cm + b  ·  Triple-Gate Enforcement",
           color='#059669', bg='#ecfdf5')

# ==================== STAGE 5: FINAL OUTPUT (LEFT & RIGHT OF FUSION) ====================
# Arrow Left -> Denied
draw_arrow(4.0, 1.0, 2.7, 1.0, label="Failed Gates", color='#dc2626')
draw_block(x=0.5, y=0.55, w=2.2, h=0.9,
           title="✕ Access Denied",
           subtitle="Spoof / Mismatch",
           color='#dc2626', bg='#fef2f2')

# Arrow Right -> Granted
draw_arrow(12.0, 1.0, 13.3, 1.0, label="All Passed", color='#16a34a')
draw_block(x=13.3, y=0.55, w=2.2, h=0.9,
           title="✓ Access Granted",
           subtitle="Authenticated",
           color='#16a34a', bg='#f0fdf4')

# Save file
out_path = Path("d:/S_NLP/Integrated Spoof-Aware Speaker Verification for Secure Voice Authentication/system_architecture.png")
plt.tight_layout()
plt.savefig(str(out_path), bbox_inches='tight', dpi=300, facecolor='#ffffff')
plt.close()
print("Clean, simple system architecture generated successfully at:", out_path)
