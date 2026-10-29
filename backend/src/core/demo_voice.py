"""Offline generic synthetic speech for adversarial demonstration, not voice cloning."""
import json
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'synthesize_demo.ps1'

def synthesize_demo(phrase: str, voice: str = 'default') -> bytes:
    if voice not in {'default','female','male'}:
        raise ValueError('Choose default, female, or male synthetic voice.')
    if not phrase or len(phrase) > 200:
        raise ValueError('Demo phrase must contain 1–200 characters.')
    with tempfile.TemporaryDirectory(prefix='voiceguard_demo_') as directory:
        request = Path(directory) / 'request.json'
        output = Path(directory) / 'speech.wav'
        request.write_text(json.dumps({'phrase':phrase,'voice':voice}),encoding='utf-8')
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(SCRIPT),'-RequestPath',str(request),'-OutputPath',str(output)],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode or not output.is_file():
            raise RuntimeError('Local synthetic voice is unavailable. Check installed Windows speech voices.')
        return output.read_bytes()
