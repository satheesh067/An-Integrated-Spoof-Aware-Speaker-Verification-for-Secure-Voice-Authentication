"""Recover a display reference only when archived enrollment reproduces metadata and template."""
import os,sys,json,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ.setdefault('HF_HUB_DISABLE_XET','1')
import truststore;truststore.inject_into_ssl()
import numpy as np,soundfile as sf
from src.api.server import get_pipeline
p=get_pipeline()
for username in ['pawan','satheesh']:
 meta=json.loads(Path(f'data/enrolled_users/{username}_meta.json').read_text());template=p.enrollment.get_template(username);directory=Path('data/voices/enrolled')/username
 if (directory/'reference.wav').exists():continue
 groups={}
 for path in directory.glob('*.wav'):
  match=re.fullmatch(re.escape(username)+r'_enroll_(\d{8}_\d{6})_(\d+)\.wav',path.name)
  if match:groups.setdefault(match[1],{})[int(match[2])]=path
 for stamp,group in sorted(groups.items(),reverse=True):
  if sorted(group)!=list(range(meta['num_recordings'])):continue
  embeddings=[];reports_ok=True
  for index,path in sorted(group.items()):
   wave,quality=p.audio_processor.load_and_preprocess(str(path));report=meta['clip_reports'][index]
   cm=p.aasist.score_audio(wave)['cm_score']
   if abs(cm-report['cm_score'])>.02 or abs(quality['rms_energy']-report['rms'])>.0002:reports_ok=False;break
   emb,_=p.ecapa.extract_embedding(wave);emb=emb.cpu().numpy().squeeze();embeddings.append(emb/(np.linalg.norm(emb)+1e-12))
  if not reports_ok:continue
  mean=np.mean(embeddings,axis=0);mean/=np.linalg.norm(mean)+1e-12
  error=float(np.max(abs(mean-template)))
  if error>1e-4:continue
  data,rate=sf.read(group[0],dtype='float32');sf.write(directory/'reference.wav',data,rate,subtype='PCM_16')
  (directory/'reference_provenance.json').write_text(json.dumps({'source':str(group[0]),'matched_enrollment_files':[str(group[i]) for i in sorted(group)],'template_max_abs_error':error,'cm_and_rms_match':True},indent=2))
  print(username,'confirmed enrollment reference recovered; template error',error,flush=True);break
 else:print(username,'no exact archived enrollment match; reference not created',flush=True)
