import re
import pymupdf as fitz
from .manifest import load,save,sha,inside
from .converters import pdf_source

def natural(p): return [(0,int(s)) if s.isdigit() else (1,s.casefold()) for s in re.split(r'(\d+)',p)]
def ingest(root,c,new_version=False):
 path=root/'sources/source_registry.json'; reg=load(path,{'schema_version':1,'documents':[],'duplicates':[]}); docs=reg['documents']; seen=[]
 for category,g in c['groups'].items():
  folder=inside(root,g['path']); order=g.get('order',[])
  files=sorted([p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.pdf','.ppt','.pptx')],key=lambda p:(order.index(p.relative_to(folder).as_posix()) if p.relative_to(folder).as_posix() in order else len(order),natural(p.relative_to(folder).as_posix())))
  for src in files:
   rel=src.relative_to(root).as_posix(); digest=sha(src); seen.append(rel)
   same=next((d for d in docs if d['current_path']==rel and d['source_sha256']==digest),None)
   if same: same['available']=True; continue
   changed=next((d for d in reversed(docs) if d['current_path']==rel and d.get('available',True)),None)
   if changed and not new_version: raise ValueError(f'{rel}: content changed; use ingest --new-version to allocate a new ID')
   moved=next((d for d in docs if d['source_sha256']==digest and not inside(root,d['current_path']).exists() and d['category']==category),None)
   if moved:
    moved['current_path']=rel; moved['path_history'].append(rel); moved['available']=True; continue
   ident=g['prefix']+f"{1+max((d['sequence'] for d in docs if d['category']==category),default=0):02d}"
   with pdf_source(src) as (pdf,expected,warnings):
    with fitz.open(pdf) as doc: total=len(doc)
   if changed: changed['available']=False
   record={'document_id':ident,'sequence':int(ident[len(g['prefix']):]),'category':category,'teacher':g.get('teacher'),'original_filename':src.name,'original_path':rel,'current_path':rel,'path_history':[rel],'source_sha256':digest,'source_bytes':src.stat().st_size,'total_pages':total,'available':True,'version_of':changed['document_id'] if changed else None,'warnings':warnings}
   docs.append(record); save(path,reg)
 for d in docs: d['available']=d['current_path'] in seen and inside(root,d['current_path']).exists() and sha(inside(root,d['current_path']))==d['source_sha256']
 hashes={}
 for d in docs: hashes.setdefault(d['source_sha256'],[]).append(d['document_id'])
 reg['duplicates']=[v for v in hashes.values() if len(v)>1]; save(path,reg); return reg

def registered(root): return load(root/'sources/source_registry.json',{'documents':[]})['documents']
def source(root,d):
 p=inside(root,d['current_path'])
 if not p.exists() or sha(p)!=d['source_sha256']: raise ValueError(d['document_id']+': source missing or changed; ingest a new version')
 return p
