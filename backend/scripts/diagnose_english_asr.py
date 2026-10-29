import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['HF_HUB_DISABLE_XET']='1'
import truststore;truststore.inject_into_ssl()
import whisper
from src.core.audio_processor import AudioProcessor
w,_=AudioProcessor().load_and_preprocess('data/voices/testing/pawan/pawan_test_20261011_225609_ACCESS_DENIED.wav')
model=whisper.load_model('small.en',device='cuda')
for i in range(2):
 r=model.transcribe(w.numpy(),language='en',fp16=False,temperature=0,beam_size=5,condition_on_previous_text=False,initial_prompt='An English voice challenge: an adjective, a noun, and a number from eleven to ninety-nine.')
 print('SMALL_EN',i,r['text'],flush=True)
