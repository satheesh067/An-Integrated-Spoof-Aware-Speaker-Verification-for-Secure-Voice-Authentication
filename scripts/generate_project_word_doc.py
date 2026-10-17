import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_background(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_document():
    doc = docx.Document()
    
    # Page setup - 1 inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
    
    # Color palette
    COLOR_PRIMARY = RGBColor(30, 64, 175)     # Deep Blue (#1E40AF)
    COLOR_SECONDARY = RGBColor(15, 23, 42)    # Dark Slate (#0F172A)
    COLOR_MUTED = RGBColor(100, 116, 139)     # Cool Gray (#64748B)
    COLOR_DARK = RGBColor(51, 65, 85)         # Charcoal (#334155)
    
    # ------------------ TITLE & HEADER ------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    run_title = title_p.add_run("VoiceGuard AI: Project Summary")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = COLOR_PRIMARY
    
    subtitle_p = doc.add_paragraph()
    subtitle_p.paragraph_format.space_before = Pt(0)
    subtitle_p.paragraph_format.space_after = Pt(14)
    run_sub = subtitle_p.add_run("Integrated Spoof-Aware Speaker Verification (SASV) for Secure Voice Authentication")
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(11)
    run_sub.font.color.rgb = COLOR_MUTED
    
    # Divider line
    divider = doc.add_paragraph()
    divider.paragraph_format.space_before = Pt(0)
    divider.paragraph_format.space_after = Pt(12)
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '12')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '2563EB')
    pBdr.append(bottom)
    divider._p.get_or_add_pPr().append(pBdr)

    def add_section_header(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(title)
        r.font.name = "Calibri"
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = COLOR_PRIMARY
        return p

    def add_body_p(text, bold_prefix="", italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_b = p.add_run(bold_prefix)
            r_b.font.name = "Calibri"
            r_b.font.size = Pt(10.5)
            r_b.font.bold = True
            r_b.font.color.rgb = COLOR_SECONDARY
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(10.5)
        r.font.italic = italic
        r.font.color.rgb = COLOR_DARK
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_b = p.add_run(bold_prefix)
            r_b.font.name = "Calibri"
            r_b.font.size = Pt(10.5)
            r_b.font.bold = True
            r_b.font.color.rgb = COLOR_SECONDARY
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(10.5)
        r.font.color.rgb = COLOR_DARK
        return p

    # ------------------ 1. PROJECT OVERVIEW ------------------
    add_section_header("1. Project Overview")
    add_body_p(
        "VoiceGuard AI is an advanced biometric security system designed to protect voice authentication against generative AI deepfakes, synthetic speech, replay attacks, and human impersonation. While conventional voice authentication checks only whether an audio sample matches the user's voice, VoiceGuard AI simultaneously verifies three essential security dimensions: identity, liveness, and authenticity."
    )
    add_bullet("Problem Addressed: ", "Modern AI voice cloning tools (such as ElevenLabs and neural vocoders) can clone a human voice using just 3 to 5 seconds of sample audio. Traditional voice recognition is completely vulnerable to these synthetic voice attacks.")
    add_bullet("Solution: ", "An integrated SASV (Spoof-Aware Speaker Verification) pipeline combining neural voiceprint comparison, raw-waveform anti-spoofing graph neural networks, and dynamic spoken challenge-response liveness.")

    # ------------------ 2. PROGRAMMING LANGUAGES USED ------------------
    add_section_header("2. Programming Languages Used")
    
    lang_table = doc.add_table(rows=1, cols=3)
    lang_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    lang_table.autofit = False
    
    headers = ["Language", "Role / Usage", "Key Modules"]
    col_widths = [Inches(1.5), Inches(3.2), Inches(2.0)]
    
    hdr_cells = lang_table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        hdr_cells[i].paragraphs[0].runs[0].font.name = "Calibri"
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(10)
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(hdr_cells[i], "1E40AF")
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)

    languages_data = [
        ("Python 3.10+", "Backend API, deep learning inference, model orchestration, audio signal processing", "PyTorch, FastAPI, SpeechBrain, Whisper"),
        ("JavaScript (ES6+)", "Frontend client, browser microphone recording (Web Audio API / MediaRecorder), UI reactivity", "app.js (Live enrollment wizard, dynamic prompts)"),
        ("HTML5 & CSS3", "Modern user interface, responsive layout, dark theme, interactive biometric dashboards", "index.html, styles.css (Glassmorphism & animations)"),
        ("PowerShell", "Automated deployment, environment bootstrapping, model weight verification, test automation", "start_project.ps1, test runners")
    ]

    for row_idx, (lang, role, mods) in enumerate(languages_data):
        row = lang_table.add_row()
        bg = "F8FAFC" if row_idx % 2 == 0 else "FFFFFF"
        for i, val in enumerate([lang, role, mods]):
            cell = row.cells[i]
            cell.text = val
            p = cell.paragraphs[0]
            r = p.runs[0]
            r.font.name = "Calibri"
            r.font.size = Pt(9.5)
            r.font.color.rgb = COLOR_SECONDARY if i == 0 else COLOR_DARK
            if i == 0:
                r.font.bold = True
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    for row in lang_table.rows:
        for i, w in enumerate(col_widths):
            row.cells[i].width = w

    # ------------------ 3. TECHNOLOGIES & FRAMEWORKS USED ------------------
    add_section_header("3. Technologies & Frameworks Used")
    
    add_bullet("PyTorch & TorchAudio: ", "Core deep learning runtime powering model inference, tensor operations, and GPU acceleration on NVIDIA CUDA.")
    add_bullet("SpeechBrain (ECAPA-TDNN): ", "State-of-the-art speaker recognition architecture using Squeeze-and-Excitation (SE) channel attention and Attentive Statistical Pooling to extract 192-dimensional identity voiceprints.")
    add_bullet("AASIST (Graph Neural Network): ", "Raw-waveform spectro-temporal graph attention network analyzing high-frequency synthesis artifacts directly from 16 kHz audio without lossy spectrogram transforms.")
    add_bullet("OpenAI Whisper (small.en): ", "Automatic speech recognition (ASR) engine verifying that spoken challenge phrases and dynamic security numbers are recited correctly in real time.")
    add_bullet("FastAPI & Uvicorn: ", "High-performance asynchronous REST backend providing authenticated API endpoints for live enrollment, real-time verification, and system telemetry.")
    add_bullet("Web Audio API & MediaRecorder: ", "In-browser native audio capture capturing 16 kHz, 16-bit PCM single-channel WAV recordings without requiring external recording tools.")

    # ------------------ 4. DATASETS USED ------------------
    add_section_header("4. Datasets Used")
    
    data_table = doc.add_table(rows=1, cols=3)
    data_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    data_table.autofit = False
    
    headers_d = ["Dataset", "Size / Scope", "Purpose in Project"]
    col_widths_d = [Inches(1.8), Inches(2.2), Inches(2.7)]
    
    hdr_cells_d = data_table.rows[0].cells
    for i, title in enumerate(headers_d):
        hdr_cells_d[i].text = title
        hdr_cells_d[i].paragraphs[0].runs[0].font.name = "Calibri"
        hdr_cells_d[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells_d[i].paragraphs[0].runs[0].font.size = Pt(10)
        hdr_cells_d[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(hdr_cells_d[i], "1E40AF")
        set_cell_margins(hdr_cells_d[i], top=100, bottom=100, left=120, right=120)

    datasets_data = [
        ("VoxCeleb 1 & 2", "1.2 Million+ utterances from 7,000+ real speakers", "Pretraining the ECAPA-TDNN speaker embedding model for acoustic identity extraction across diverse real-world conditions."),
        ("ASVspoof 2019 LA", "121,461 evaluation trials (19 speech synthesis & voice conversion attack algorithms A01–A19)", "Training and benchmark calibration of the AASIST anti-spoofing countermeasure model to detect synthetic speech and replays."),
        ("SASV 2022 Benchmark", "102,579 official evaluation trials crossing VoxCeleb speakers with spoof attacks", "Evaluating integrated SASV fusion models under joint speaker verification and spoofing attack conditions."),
        ("Local Live Audio Dataset", "Real-time user voice recordings collected via interactive browser enrollment wizard", "Live enrollment templates, dynamic challenge verification, and real-time validation.")
    ]

    for row_idx, (ds, scope, purpose) in enumerate(datasets_data):
        row = data_table.add_row()
        bg = "F8FAFC" if row_idx % 2 == 0 else "FFFFFF"
        for i, val in enumerate([ds, scope, purpose]):
            cell = row.cells[i]
            cell.text = val
            p = cell.paragraphs[0]
            r = p.runs[0]
            r.font.name = "Calibri"
            r.font.size = Pt(9.5)
            r.font.color.rgb = COLOR_SECONDARY if i == 0 else COLOR_DARK
            if i == 0:
                r.font.bold = True
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    for row in data_table.rows:
        for i, w in enumerate(col_widths_d):
            row.cells[i].width = w

    # ------------------ 5. METHODOLOGY USED ------------------
    add_section_header("5. Methodology Used")
    add_body_p(
        "The project follows a 5-stage sequential and parallel pipeline combining signal processing, deep neural networks, and multi-gate decision logic:"
    )
    
    add_bullet("Stage 1 - Voice Input & Challenge Prompt: ", "The user requests an authentication session and receives a randomized, time-limited challenge phrase (e.g., 'Verify authorization code 48'). The user recites the phrase, captured as 16 kHz 16-bit PCM WAV.")
    add_bullet("Stage 2 - Audio Preprocessing & Quality Assurance: ", "The incoming signal passes through Voice Activity Detection (VAD) to trim silence, normalize volume energy, and reject corrupted or low-amplitude inputs.")
    add_bullet("Stage 3 - Tri-Layer Neural Verification (Parallel Execution): ", "")
    
    # Sub-bullets for Stage 3
    for sub_title, sub_desc in [
        ("   a) Speaker Verification (ASV): ", "ECAPA-TDNN computes a 192-dimensional vector embedding of the voice and evaluates cosine similarity against the user's enrolled template (yielding score S_asv)."),
        ("   b) Anti-Spoofing Countermeasure (CM): ", "AASIST processes the raw waveform through Graph Attention Networks to detect synthetic vocoder artifacts, deepfakes, or loudspeaker replay (yielding score S_cm)."),
        ("   c) Spoken Challenge Liveness (ASR): ", "OpenAI Whisper transcribes the spoken phrase to ensure the user actively recited the live phrase in real time, preventing pre-recorded audio replays.")
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        r_b = p.add_run(sub_title)
        r_b.font.name = "Calibri"
        r_b.font.size = Pt(10)
        r_b.font.bold = True
        r_b.font.color.rgb = COLOR_SECONDARY
        r = p.add_run(sub_desc)
        r.font.name = "Calibri"
        r.font.size = Pt(10)
        r.font.color.rgb = COLOR_DARK

    add_bullet("Stage 4 - Decision Fusion & Multi-Gate Enforcement: ", "The system performs linear score fusion (S_fused = w1·S_asv + w2·S_cm + b) and enforces triple independent safeguard gates: (1) Liveness must match, (2) Anti-spoof score must meet threshold, (3) Speaker similarity must meet threshold.")
    add_bullet("Stage 5 - Final Authentication Verdict: ", "Access is granted only when all three security checks succeed simultaneously. If any check fails, access is denied with a specific diagnostic code (e.g., SUSPECTED_SPOOF, IMPOSTOR_HUMAN, or CHALLENGE_MISMATCH).")

    # Embed architecture diagram if it exists
    img_path = Path("system_architecture.png")
    if img_path.exists():
        p_img = doc.add_paragraph()
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(4)
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(str(img_path), width=Inches(6.2))
        
        p_cap = doc.add_paragraph()
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(10)
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 1: High-Level System Architecture and Block-Wise Verification Pipeline")
        r_cap.font.name = "Calibri"
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = COLOR_MUTED

    # ------------------ 6. KEY SPECIFICATIONS SUMMARY ------------------
    add_section_header("6. Key System Specifications")
    
    spec_table = doc.add_table(rows=1, cols=2)
    spec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    spec_table.autofit = False
    
    spec_hdr = spec_table.rows[0].cells
    spec_hdr[0].text = "Metric / Parameter"
    spec_hdr[1].text = "Value / Standard"
    for cell in spec_hdr:
        cell.paragraphs[0].runs[0].font.name = "Calibri"
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(10)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1E40AF")
        set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
    
    specs = [
        ("Audio Input Format", "16,000 Hz, 16-bit Mono PCM WAV"),
        ("Live Challenge Window", "20-second dynamic TTL single-use phrase"),
        ("Speaker Verification Model", "ECAPA-TDNN (192-dimensional vector embedding)"),
        ("Anti-Spoofing Model", "AASIST Raw Waveform Graph Neural Network"),
        ("Liveness ASR Model", "OpenAI Whisper (small.en)"),
        ("Verification Latency", "< 950 ms on GPU (Real-time verification)"),
        ("Decision Strategy", "Triple-Gate Verification + Linear Logistic Regression Fusion")
    ]
    
    for row_idx, (param, val) in enumerate(specs):
        row = spec_table.add_row()
        bg = "F8FAFC" if row_idx % 2 == 0 else "FFFFFF"
        for i, text_val in enumerate([param, val]):
            cell = row.cells[i]
            cell.text = text_val
            p = cell.paragraphs[0]
            r = p.runs[0]
            r.font.name = "Calibri"
            r.font.size = Pt(9.5)
            r.font.color.rgb = COLOR_SECONDARY if i == 0 else COLOR_DARK
            if i == 0:
                r.font.bold = True
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=70, bottom=70, left=120, right=120)

    for row in spec_table.rows:
        row.cells[0].width = Inches(2.8)
        row.cells[1].width = Inches(3.9)

    out_file = Path("VoiceGuard_AI_Project_Summary.docx")
    doc.save(str(out_file))
    print(f"Document created successfully at: {out_file.resolve()}")

if __name__ == "__main__":
    create_document()
