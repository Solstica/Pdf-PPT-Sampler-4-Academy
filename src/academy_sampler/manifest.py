import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def load(p,default=None): return json.loads(p.read_text(encoding='utf8')) if p.exists() else default

def save(p,data):
 p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp')
 tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8'); tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def page_numbers(spec,n):
 if not spec: return list(range(1,n+1))
 result=set()
 for part in spec.split(','):
  if not re.fullmatch(r'\d+(?:-\d+)?',part.strip()): raise ValueError('Invalid page range: '+part)
  ends=list(map(int,part.split('-'))); a,b=ends[0],ends[-1]
  if not 1<=a<=b<=n: raise ValueError(f'Page range outside 1-{n}: {part}')
  result.update(range(a,b+1))
 return sorted(result)
def inside(root,path):
 p=(root/path).resolve()
 if not p.is_relative_to(root.resolve()): raise ValueError('Path escapes workspace: '+str(path))
 return p
