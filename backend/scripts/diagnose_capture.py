import sys,os,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['HF_HUB_DISABLE_XET']='1'
import truststore; truststore.inject_into_ssl()
import numpy as np,soundfile as sf,torch
from src.api.server import get_pipeline
p=get_pipeline(); rows=[]
paths=list(Path('data/voices/testing/pawan').glob('*225024*'))+list(Path('data/voices/testing/pawan').glob('*224833*'))+list(Path('data/voices/enrolled/pawan').glob('*202435*'))+list(Path('data/pilot/audio').glob('*spoof*'))
for path in paths:
 d,sr=sf.read(path,dtype='float32');d=d.mean(axis=1) if d.ndim>1 else d
 if sr!=16000:
  from scipy.signal import resample
  d=resample(d,int(len(d)*16000/sr)).astype('float32')
 raw=p.aasist.score_audio(torch.from_numpy(d))['cm_score']
 w,m=p.audio_processor.load_and_preprocess(str(path));norm=p.aasist.score_audio(w)['cm_score']
 row={'file':str(path),'rate':sr,'duration':len(d)/16000,'rms':float(np.sqrt(np.mean(d*d))),'peak':float(abs(d).max()),'raw_cm':raw,'normalized_cm':norm}
 rows.append(row);print(json.dumps(row),flush=True)
Path('scratch/anti_spoof_diagnosis.json').write_text(json.dumps(rows,indent=2))
