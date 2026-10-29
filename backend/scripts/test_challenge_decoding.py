"""Keep short-phrase decoding deterministic and the numeric challenge mandatory."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.challenge_manager import ChallengeManager

class ChallengeDecoding(unittest.TestCase):
    def manager(self,transcript):
        manager=ChallengeManager(device='cpu')
        manager.generate_phrase=lambda:'calm sky 80'
        calls=[]
        manager._whisper=SimpleNamespace(transcribe=lambda audio,**kwargs:(calls.append(kwargs) or {'text':transcript}))
        return manager,calls
    def test_correct_phrase_passes_and_replay_fails(self):
        manager,calls=self.manager('Calm sky eighty.')
        session=manager.issue_challenge('alice')
        response=manager.verify_challenge(session['session_id'],'alice',np.ones(16000,dtype=np.float32))
        self.assertTrue(response['passed'])
        self.assertEqual(calls[0]['temperature'],0)
        self.assertEqual(calls[0]['beam_size'],5)
        self.assertFalse(calls[0]['fp16'])
        self.assertNotIn('calm sky 80',calls[0]['initial_prompt'].lower())
        self.assertFalse(manager.verify_challenge(session['session_id'],'alice',np.ones(16000,dtype=np.float32))['passed'])
    def test_missing_or_wrong_number_is_rejected(self):
        for transcript in ['calm sky','calm sky eighty one','calm sky eighty-one','calm sky 81','calm sky 180','remember at']:
            manager,_=self.manager(transcript);session=manager.issue_challenge('alice')
            self.assertFalse(manager.verify_challenge(session['session_id'],'alice',np.ones(16000,dtype=np.float32))['passed'],transcript)

if __name__=='__main__':unittest.main()
