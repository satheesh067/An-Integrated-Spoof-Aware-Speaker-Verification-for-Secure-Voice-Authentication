"""Regression checks for the browser/calibration input-scale mismatch."""
import io
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.audio_processor import AudioProcessor

class CapturePreprocessing(unittest.TestCase):
    def test_uploaded_bytes_match_enrollment_files(self):
        processor=AudioProcessor()
        for rate,channels in [(16000,1),(48000,2)]:
            t=np.arange(rate,dtype=np.float32)/rate
            samples=.12*np.sin(2*np.pi*440*t)
            if channels==2: samples=np.stack((samples,.5*samples),axis=1)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'recording.wav';sf.write(path,samples,rate,subtype='PCM_16')
                file_wave,file_meta=processor.load_and_preprocess(str(path))
                upload_wave,upload_meta=processor.load_and_preprocess(path.read_bytes())
            np.testing.assert_array_equal(file_wave.numpy(),upload_wave.numpy())
            self.assertEqual(file_meta,upload_meta)
            self.assertAlmostEqual(float(upload_wave.abs().max()),.95,delta=.001)
            self.assertEqual(len(upload_wave),16000)
    def test_normalization_does_not_hide_silent_audio(self):
        out=io.BytesIO();sf.write(out,np.full(16000,.001,dtype=np.float32),16000,format='WAV')
        wave,meta=AudioProcessor().load_and_preprocess(out.getvalue())
        self.assertLess(meta['rms_energy'],.003)
    def test_authentication_passes_normalized_audio_to_models(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from src.core.authentication_pipeline import AuthenticationPipeline
        from src.core.decision_engine import SASVDecisionEngine
        seen=[]
        def score(wave):
            seen.append(wave.detach().cpu().numpy().copy())
            return {'cm_score': 1.0, 'latency_ms': 0.0}
        def embed(wave):
            seen.append(wave.detach().cpu().numpy().copy())
            return np.array([1.0,0.0]), {'latency_ms':0.0}
        with patch('torch.cuda.is_available',return_value=False):
            pipeline=AuthenticationPipeline(audio_processor=AudioProcessor(),
                ecapa_model=SimpleNamespace(extract_embedding=embed),
                aasist_model=SimpleNamespace(score_audio=score),
                enrollment_manager=SimpleNamespace(get_template=lambda u:np.array([1.0,0.0])),
                challenge_manager=SimpleNamespace(),decision_engine=SASVDecisionEngine())
        out=io.BytesIO();sf.write(out,.1*np.sin(np.arange(16000)*.1),16000,format='WAV')
        response=pipeline.authenticate('alice',out.getvalue(),require_challenge=False)
        self.assertEqual(response.decision,'ACCESS_GRANTED')
        self.assertEqual(response.telemetry['audio_metadata']['preprocessing'],'mono_16khz_peak_0.95_v1')
        self.assertEqual(len(seen),2)
        evidence=response.evidence
        self.assertEqual(evidence['speaker']['reference_embedding'],[1.0,0.0])
        f=evidence['fusion']
        self.assertAlmostEqual(f['speaker_contribution']+f['countermeasure_contribution']+f['bias'],response.fused_score,places=4)
        self.assertTrue(f['require_cm_gate'])
        for wave in seen: self.assertAlmostEqual(float(abs(wave).max()),.95,places=5)

    def test_empty_audio_is_rejected(self):
        out=io.BytesIO();sf.write(out,np.empty(0,dtype=np.float32),16000,format='WAV')
        with self.assertRaises(ValueError): AudioProcessor().load_and_preprocess(out.getvalue())

if __name__=='__main__':unittest.main()

