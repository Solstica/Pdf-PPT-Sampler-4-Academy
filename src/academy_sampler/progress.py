import re
from collections import Counter
from .manifest import load,save
from .registry import registered
STATES=('pending','read','extracted','needs_high_resolution','verified','skipped_with_reason')
def refs(root): return {f"{d['document_id']}-P{n:03d}" for d in registered(root) for n in range(1,d['total_pages']+1)}
def progress(root,page=None,state=None,reason=None):
 p=root/'review/progress.json'; data=load(p,{})
 for ref in sorted(refs(root)): data.setdefault(ref,{'state':'pending','reason':''})
 if page:
  if page not in refs(root): raise ValueError('Unknown page reference: '+page)
  if state not in STATES: raise ValueError('Invalid reading state')
  if state in ('needs_high_resolution','skipped_with_reason') and not reason: raise ValueError('This state requires --reason')
  data[page]={'state':state,'reason':reason or ''}
 save(p,data)
 counts=dict(Counter(v['state'] for v in data.values()))
 (root/'review/PROGRESS.md').write_text('# Reading progress\n\n'+str(counts)+'\n\nMachine rendering never marks pages as read. See progress.json.\n',encoding='utf8')
 return counts

def check_progress(root):
 errors=[]; known=refs(root)
 for p,v in load(root/'review/progress.json',{}).items():
  if p not in known or v.get('state') not in STATES: errors.append('Invalid progress: '+p)
  if v.get('state') in ('needs_high_resolution','skipped_with_reason') and not v.get('reason'): errors.append('Missing reason: '+p)
 for path in (root/'review').rglob('*.md'):
  for ref in re.findall(r'\b[A-Z][A-Z0-9]*-P\d{3,}\b',path.read_text(encoding='utf8')):
   if ref not in known: errors.append(f'{path.name}: unknown reference {ref}')
 return errors
