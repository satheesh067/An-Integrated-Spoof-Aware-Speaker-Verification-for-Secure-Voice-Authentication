import json, uuid, re, shutil, threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'data'/'recording_history'
ROOT.mkdir(parents=True,exist_ok=True)
LOCK=threading.RLock()
def path_for(key,suffix):
 if not re.fullmatch(r'[a-f0-9]{32}',key):raise ValueError('Invalid recording identifier')
 return ROOT/(key+suffix)
def save_audio(content,username,name,source):
 from datetime import datetime,timezone
 key=uuid.uuid4().hex
 item={'id':key,'username':username,'name':name[:160],'source_type':source,'created_at':datetime.now(timezone.utc).isoformat(),'result':None}
 with LOCK:
  path_for(key,'.wav').write_bytes(content)
  ref=ROOT.parent/'voices'/'enrolled'/username/'reference.wav'
  if ref.exists():shutil.copyfile(ref,path_for(key,'_reference.wav'))
  write_item(item)
 return item
def write_item(item):
 path=path_for(item['id'],'.json');temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(item),encoding='utf-8');temporary.replace(path)
def get_item(key):return json.loads(path_for(key,'.json').read_text(encoding='utf-8'))
def list_items():
 with LOCK:return sorted([json.loads(p.read_text(encoding='utf-8')) for p in ROOT.glob('*.json')],key=lambda i:i['created_at'],reverse=True)
