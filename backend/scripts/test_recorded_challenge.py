"""Model integration regression using the user-confirmed calm sky 80 recording.
The fixed challenge is a test fixture in this process only; production continues
issuing random, single-use challenges and enforcing all gates.
"""
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
import truststore
truststore.inject_into_ssl()
from src.core.authentication_pipeline import AuthenticationPipeline

pipeline=AuthenticationPipeline()
recording=Path('data/voices/testing/pawan/pawan_test_20261011_225609_ACCESS_DENIED.wav')
pipeline.ecapa.load_model();pipeline.aasist.load_weights();pipeline.challenge.whisper_model
pipeline.challenge.generate_phrase=lambda:'calm sky 80'
session=pipeline.challenge.issue_challenge('pawan')
response=pipeline.authenticate('pawan',recording.read_bytes(),session_id=session['session_id'],policy='strict_security')
print(json.dumps(asdict(response),indent=2),flush=True)
assert response.challenge_status['passed'],response.challenge_status
assert response.speaker_matched and response.spoof_passed
assert response.decision=='ACCESS_GRANTED',response.reasons
replay=pipeline.authenticate('pawan',recording.read_bytes(),session_id=session['session_id'],policy='strict_security')
assert replay.decision=='ACCESS_DENIED' and 'Replay Detected' in replay.challenge_status['reason']
pipeline.challenge.generate_phrase=lambda:'calm sky 81'
wrong_session=pipeline.challenge.issue_challenge('pawan')
wrong=pipeline.authenticate('pawan',recording.read_bytes(),session_id=wrong_session['session_id'],policy='strict_security')
assert wrong.decision=='ACCESS_DENIED' and not wrong.challenge_status['number_matched']
Path('scratch/recorded_challenge_validation.json').write_text(json.dumps({'genuine':asdict(response),'replay':asdict(replay),'wrong_number':asdict(wrong)},indent=2),encoding='utf-8')
print('PASS: genuine recorded challenge, mandatory CM/speaker/fusion gates, replay rejection and incorrect-number rejection.',flush=True)
