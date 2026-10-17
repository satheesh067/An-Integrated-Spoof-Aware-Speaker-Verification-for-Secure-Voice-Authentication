import sys,os,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['HF_HUB_DISABLE_XET']='1'
import truststore;truststore.inject_into_ssl()
import numpy as np,torch
from src.api.server import get_pipeline
p=get_pipeline();rows=[]
paths=list(Path('data/voices/testing/pawan').glob('*225024*'))+list(Path('data/voices/testing/pawan').glob('*224833*'))+list(Path('data/pilot/audio').glob('*.wav'))
for path in paths:
 w,m=p.audio_processor.load_and_preprocess(str(path));d=w.numpy();hop=320
 # Detect speech bounds on original amplitude using 20 ms energy; preserve 150 ms of context.
 raw=d*(m['peak_amplitude']/.95);energies=np.array([np.sqrt(np.mean(raw[i:i+hop]**2)) for i in range(0,len(raw),hop)])
 threshold=max(.003,float(energies.max())*.1);active=np.flatnonzero(energies>=threshold)
 start=max(0,int(active[0])*hop-2400) if len(active) else 0;end=min(len(d),(int(active[-1])+1)*hop+2400) if len(active) else len(d)
 crop=d[start:end];score=p.aasist.score_audio(torch.from_numpy(crop))['cm_score']
 emb,_=p.ecapa.extract_embedding(torch.from_numpy(d));template=p.enrollment.get_template('pawan')
 emb=emb.cpu().numpy().squeeze();similarity=float(np.dot(emb/np.linalg.norm(emb),template))
 row={'file':str(path),'bounds':[start/16000,end/16000],'trimmed_cm':score,'pawan_similarity':similarity};rows.append(row);print(json.dumps(row),flush=True)
Path('scratch/speech_bounds_diagnosis.json').write_text(json.dumps(rows,indent=2))
