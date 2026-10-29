"""API contracts and responsiveness without modifying enrolled identities."""
import io
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api import server

@dataclass
class Result:
    decision: str = 'ACCESS_DENIED'
    verdict_type: str = 'CHALLENGE_FAILED'

class ApiContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'history').mkdir()
        self.pipeline = SimpleNamespace(enrollment=SimpleNamespace(is_enrolled=lambda u: u == 'alice'))
        self.patches = [patch.object(server.history_store, 'ROOT', self.root / 'history'), patch.object(server, 'get_pipeline', return_value=self.pipeline),
                        patch.object(server, 'TESTING_VOICES_DIR', self.root / 'probes'),
                        patch.object(server, 'ENROLLED_VOICES_DIR', self.root / 'references')]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.client = TestClient(server.app)
        out = io.BytesIO(); sf.write(out, np.ones(1600, dtype=np.float32)*.1, 16000, format='WAV')
        self.wav = out.getvalue()
    def post(self, data):
        return self.client.post('/api/v1/authenticate', data={'username':'alice','session_id':'token'}, files={'audio_file':('response.wav',data,'audio/wav')})
    def test_bad_audio_returns_actionable_400(self):
        for data in [b'', b'not an audio file']:
            self.assertEqual(self.post(data).status_code, 400)
    def test_inference_does_not_block_health(self):
        started, release = threading.Event(), threading.Event()
        def authenticate(**kwargs):
            self.assertEqual(kwargs['session_id'], 'token')
            self.assertEqual(kwargs['policy'], server.SERVER_POLICY)
            started.set(); release.wait(5); return Result()
        self.pipeline.authenticate = authenticate
        with ThreadPoolExecutor() as pool:
            request = pool.submit(self.post, self.wav)
            self.assertTrue(started.wait(3))
            try:
                self.assertEqual(self.client.get('/health').status_code,200)
                self.assertFalse(request.done())
            finally: release.set()
            response = request.result()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['decision'],'ACCESS_DENIED')
        saved=self.client.get('/api/v1/recordings').json()['recordings']
        self.assertEqual(saved[0]['id'],response.json()['recording_id'])
        self.assertEqual(saved[0]['result']['decision'],'ACCESS_DENIED')
    def test_reference_is_confirmed_and_requires_enrollment(self):
        self.assertEqual(self.client.get('/api/v1/users/alice/reference').status_code,404)
        directory=self.root/'references'/'alice'; directory.mkdir(parents=True)
        (directory/'reference.wav').write_bytes(self.wav)
        response=self.client.get('/api/v1/users/alice/reference')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,self.wav)
        self.assertEqual(self.client.get('/api/v1/users/bob/reference').status_code,404)

    def test_recording_history_persists_audio_and_pending_result(self):
        response=self.client.post('/api/v1/recordings',data={'username':'alice','name':'Fresh recording'},files={'audio_file':('recording.wav',self.wav,'audio/wav')})
        self.assertEqual(response.status_code,200)
        key=response.json()['id']
        records=self.client.get('/api/v1/recordings').json()['recordings']
        self.assertEqual(records[0]['id'],key)
        self.assertIsNone(records[0]['result'])
        self.assertEqual(self.client.get(f'/api/v1/recordings/{key}/audio').content,self.wav)
        self.assertEqual(self.client.get('/api/v1/recordings/invalid/audio').status_code,400)
        self.assertEqual(self.client.get(f'/api/v1/recordings/{key}/unknown').status_code,404)

    def test_demo_uses_bound_fresh_challenge_without_consuming_it(self):
        import time
        record={'username':'alice','phrase':'blue door 37','consumed':False,'expires_at':time.time()+45}
        self.pipeline.challenge=SimpleNamespace(active_challenges={'token':record})
        with patch.object(server,'synthesize_demo',return_value=self.wav) as synth:
            response=self.client.post('/api/v1/demo-voice',json={'username':'alice','session_id':'token','voice':'default'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content,self.wav)
            synth.assert_called_once_with('blue door 37','default')
            self.assertFalse(record['consumed'])
            self.assertEqual(self.client.post('/api/v1/demo-voice',json={'username':'bob','session_id':'token'}).status_code,400)
            record['consumed']=True
            self.assertEqual(self.client.post('/api/v1/demo-voice',json={'username':'alice','session_id':'token'}).status_code,400)
            record['consumed']=False;record['expires_at']=0
            self.assertEqual(self.client.post('/api/v1/demo-voice',json={'username':'alice','session_id':'token'}).status_code,400)

if __name__ == '__main__': unittest.main()
