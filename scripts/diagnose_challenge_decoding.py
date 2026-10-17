import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['HF_HUB_DISABLE_XET']='1'
import truststore;truststore.inject_into_ssl()
from src.api.server import get_pipeline
p=get_pipeline();path=Path('data/voices/testing/pawan/pawan_test_20261011_225609_ACCESS_DENIED.wav');w,meta=p.audio_processor.load_and_preprocess(str(path));model=p.challenge.whisper_model
for i in range(3):
 r=model.transcribe(w.numpy(),language='en',fp16=True,temperature=0,beam_size=5,condition_on_previous_text=False,initial_prompt='A short English phrase with two words and a two-digit number, such as clear star 45.')
 print('BEAM',i,r['text'],p.challenge._calculate_phrase_match('calm sky 80',r['text']),flush=True)
