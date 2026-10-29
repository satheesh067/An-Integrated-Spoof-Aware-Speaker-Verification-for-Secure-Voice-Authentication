import sys,os,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['HF_HUB_DISABLE_XET']='1'
import truststore;truststore.inject_into_ssl()
import numpy as np,soundfile as sf
from src.api.server import get_pipeline
p=get_pipeline();path=sorted(Path('data/voices/testing/pawan').glob('*.wav'),key=lambda p:p.stat().st_mtime)[-1]
w,meta=p.audio_processor.load_and_preprocess(str(path));d,sr=sf.read(path,dtype='float32')
print('LATEST',path,meta,flush=True)
print('TRANSCRIPT',p.challenge.whisper_model.transcribe(w.numpy(),language='en',fp16=True,initial_prompt='A short English phrase with two words and a two-digit number, such as clear star 45.').get('text'),flush=True)
print('NORMALIZED_CM',p.aasist.score_audio(w)['cm_score'],flush=True)
emb,_=p.ecapa.extract_embedding(w);emb=emb.cpu().numpy().squeeze();print('SPEAKER',float(np.dot(emb/np.linalg.norm(emb),p.enrollment.get_template('pawan'))),flush=True)
