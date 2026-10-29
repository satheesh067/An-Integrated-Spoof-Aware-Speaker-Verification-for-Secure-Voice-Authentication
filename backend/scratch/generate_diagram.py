import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(19, 10.8), dpi=300)
fig.patch.set_facecolor('#0B0F19')
ax.set_facecolor('#0B0F19')

ax.set_xlim(0, 19)
ax.set_ylim(0, 11)
ax.axis('off')

def draw_card(ax, x, y, w, h, bg_color, border_color, title, subtitle="", items=None, title_color="#FFFFFF", title_size=11, item_size=8.5):
    rect = patches.FancyBboxPatch((x, y), w, h,
                                  boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=bg_color, edgecolor=border_color, linewidth=1.8, zorder=2)
    ax.add_patch(rect)
    
    if title:
        ax.text(x + w/2, y + h - 0.28, title, ha='center', va='center',
                fontsize=title_size, fontweight='bold', color=title_color, zorder=3)
    if subtitle:
        ax.text(x + w/2, y + h - 0.58, subtitle, ha='center', va='center',
                fontsize=8, fontstyle='italic', color='#94A3B8', zorder=3)
    
    if items:
        start_y = y + h - (0.92 if subtitle else 0.6)
        spacing = (h - (1.05 if subtitle else 0.75)) / max(len(items), 1)
        for idx, item in enumerate(items):
            cur_y = start_y - idx * spacing
            ax.text(x + 0.2, cur_y, f"{item}", ha='left', va='center',
                    fontsize=item_size, color='#CBD5E1', zorder=3)

# Title banner
ax.text(9.5, 10.6, "Integrated Spoof-Aware Speaker Verification (SASV) Operational Flow",
        ha='center', va='center', fontsize=16, fontweight='bold', color='#F8FAFC')
ax.text(9.5, 10.25, "End-to-End Multimodal Pipeline: Real-Time Capture → Diagnostics → Dual Neural Models → Gated Fusion → Granular Verdict",
        ha='center', va='center', fontsize=10, color='#94A3B8')

# Left Column: User Input & Audio Diagnostics (x = 0.5)
draw_card(ax, 0.5, 6.7, 3.6, 3.2, '#1E293B', '#38BDF8',
          "1. USER & INPUT LAYER", "Real-Time Microphone / Audio Stream",
          ["• 16 kHz 16-bit Mono Audio",
           "• Canonical Claimed Username",
           "• Dynamic Session Nonce (20s TTL)",
           "• Enforced strict_security Policy",
           "• Web Audio API & File Upload"],
          title_color="#38BDF8", title_size=11)

draw_card(ax, 0.5, 3.0, 3.6, 3.3, '#1E293B', '#F59E0B',
          "STAGE 1: AUDIO DIAGNOSTICS", "Signal Quality & Standardization",
          ["• Gain standardization & resampling",
           "• Usable energy: RMS >= 0.003",
           "• Duration >= 0.8s check",
           "• Clipping & silent frame detection",
           "• Fail-fast: POOR_AUDIO_QUALITY"],
          title_color="#F59E0B", title_size=11)

# Arrow from Input to Diagnostics
ax.annotate('', xy=(2.3, 6.3), xytext=(2.3, 6.7),
            arrowprops=dict(arrowstyle="->", color="#38BDF8", lw=2.2, mutation_scale=14), zorder=4)

# Middle Column: Parallel 3 AI Stages (x = 4.6 to 10.0)
draw_card(ax, 4.7, 7.3, 5.4, 2.6, '#132338', '#06B6D4',
          "STAGE 2: DYNAMIC LIVENESS VERIFICATION", "OpenAI Whisper ASR (CUDA small.en)",
          ["• Ephemeral challenge phrase + random 2-digit number",
           "• Single-use nonce consumed immediately upon receipt",
           "• Real-time decoding (~320 ms latency on CUDA)",
           "• Word overlap >= 60% + exact 2-digit number verification",
           "• Defeats pre-recorded replay & offline deepfake clones"],
          title_color="#06B6D4", title_size=10.5)

draw_card(ax, 4.7, 4.4, 5.4, 2.6, '#2A172D', '#EC4899',
          "STAGE 3: ANTI-SPOOFING COUNTERMEASURE", "AASIST Spectro-Temporal Graph Attention",
          ["• Raw 16 kHz waveform input (64,600 samples, 4.04s)",
           "• SincNet bandpass filterbanks (preserves phase cues)",
           "• Heterogeneous Graph Attention (spectral & temporal edges)",
           "• Countermeasure Score: s_cm = logit_bonafide - logit_spoof",
           "• Canonical weights: 51d2d9cf... (Clova AI / ASVspoof 2019 LA)"],
          title_color="#EC4899", title_size=10.5)

draw_card(ax, 4.7, 1.5, 5.4, 2.6, '#142823', '#10B981',
          "STAGE 4: DEEP SPEAKER VERIFICATION", "SpeechBrain ECAPA-TDNN Architecture",
          ["• 1D Dilated Convolutions + Res2Net multi-scale blocks",
           "• Squeeze-and-Excitation (SE) channel-attention pooling",
           "• 192-dimensional L2-normalized x-vector embedding",
           "• Cosine similarity s_asv against enrolled voice template",
           "• Length-normalized scoring: s_asv = e_probe · e_enroll"],
          title_color="#10B981", title_size=10.5)

# Connect Diagnostics to the 3 parallel branches
ax.plot([4.1, 4.4], [4.65, 4.65], color="#F59E0B", lw=2, zorder=1)
ax.plot([4.4, 4.4], [2.8, 8.6], color="#F59E0B", lw=2, zorder=1)

ax.annotate('', xy=(4.7, 8.6), xytext=(4.4, 8.6),
            arrowprops=dict(arrowstyle="->", color="#06B6D4", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(4.7, 5.7), xytext=(4.4, 5.7),
            arrowprops=dict(arrowstyle="->", color="#EC4899", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(4.7, 2.8), xytext=(4.4, 2.8),
            arrowprops=dict(arrowstyle="->", color="#10B981", lw=2, mutation_scale=13), zorder=4)

# Column 3: Learned Score Fusion & Safeguard Gate (x = 10.6 to 14.4)
draw_card(ax, 10.6, 2.8, 3.8, 7.1, '#1E1B4B', '#818CF8',
          "STAGE 5: FUSION & SAFEGUARD", "Learned Score Fusion & Non-Linear Gate",
          ["Trained Logistic Regression on DEV:",
           "  s_fus = 12.7265·s_asv + 0.1767·s_cm - 3.4780",
           "",
           "CRITICAL FINDING: THE CLONE LEAK",
           "• Beta synthetic clone has high similarity:",
           "    s_asv = +0.7181, s_cm = -6.0606",
           "• Voice similarity overwhelms CM warning:",
           "    s_fus = +4.5899 > tau_fus",
           "• Pure linear fusion leaks 50% target clones!",
           "",
           "THE SAFEGUARD GATE SOLUTION",
           "• Mandates s_cm >= tau_cm hard floor",
           "• In tandem with s_fus >= tau_fus",
           "• Rejects 100% of target attacks on EVAL (4/4)!",
           "",
           "DEV-Calibrated Operating Tiers:",
           "• Balanced: tau_fus=0.0783, tau_cm=-4.0694",
           "• Strict: tau_fus=0.5052, tau_cm=-4.0694",
           "• Convenience: tau_fus=-0.3486, tau_cm=-6.50"],
          title_color="#818CF8", title_size=11, item_size=8.2)

# Connect branches to Fusion
ax.annotate('', xy=(10.6, 8.6), xytext=(10.1, 8.6),
            arrowprops=dict(arrowstyle="->", color="#06B6D4", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(10.6, 5.7), xytext=(10.1, 5.7),
            arrowprops=dict(arrowstyle="->", color="#EC4899", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(10.6, 3.8), xytext=(10.1, 2.8),
            arrowprops=dict(arrowstyle="->", color="#10B981", lw=2, mutation_scale=13), zorder=4)

# Column 4: 7-Class Decision State Space & Output Telemetry (x = 14.8 to 18.5)
draw_card(ax, 14.8, 6.9, 3.7, 3.0, '#064E3B', '#10B981',
          "ACCESS GRANTED (VERIFIED)", "Verdict: AUTHENTICATED",
          ["• Enrolled identity verified (s_asv >= tau)",
           "• Bona fide human audio (s_cm >= tau)",
           "• Dynamic challenge passed (<= 20s TTL)",
           "• Fused score meets policy threshold",
           "• Telemetry + full audit evidence returned"],
          title_color="#34D399", title_size=10.5, item_size=8.0)

draw_card(ax, 14.8, 3.7, 3.7, 2.9, '#7F1D1D', '#EF4444',
          "SECURITY THREAT REJECTIONS", "Verdicts: SUSPECTED_SPOOF / MISMATCH",
          ["• SUSPECTED_SPOOF: Target voice match, but AASIST detected synthetic / replay cues",
           "• SPEAKER_MISMATCH: Genuine voice, but similarity below enrolled identity template",
           "• DUAL_CRITERIA_FAILURE: Both identity and countermeasure checks failed"],
          title_color="#F87171", title_size=10.5, item_size=8.0)

draw_card(ax, 14.8, 0.6, 3.7, 2.8, '#451A03', '#F97316',
          "PROTOCOL & SIGNAL REJECTIONS", "Verdicts: CHALLENGE_FAILED / QUALITY",
          ["• CHALLENGE_FAILED: Expired token (>20s), wrong phrase, or missed 2-digit number",
           "• POOR_AUDIO_QUALITY: Energy < 0.003 RMS, excessive clipping, or near silence",
           "• MARGINAL_FUSION_REJECTION: Sub-metrics pass, joint score below operating tier"],
          title_color="#FB923C", title_size=10.5, item_size=8.0)

# Connect Stage 5 to Column 4
ax.plot([14.4, 14.6], [6.35, 6.35], color="#818CF8", lw=2, zorder=1)
ax.plot([14.6, 14.6], [2.0, 8.4], color="#818CF8", lw=2, zorder=1)

ax.annotate('', xy=(14.8, 8.4), xytext=(14.6, 8.4),
            arrowprops=dict(arrowstyle="->", color="#10B981", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(14.8, 5.15), xytext=(14.6, 5.15),
            arrowprops=dict(arrowstyle="->", color="#EF4444", lw=2, mutation_scale=13), zorder=4)
ax.annotate('', xy=(14.8, 2.0), xytext=(14.6, 2.0),
            arrowprops=dict(arrowstyle="->", color="#F97316", lw=2, mutation_scale=13), zorder=4)

plt.tight_layout()
plt.savefig("scratch/system_architecture_flowchart.png", dpi=300, facecolor='#0B0F19', bbox_inches='tight')
plt.close()
print("Regenerated 4-column scratch/system_architecture_flowchart.png")
