from pathlib import Path
from shutil import copytree
from urllib.parse import quote
from .manifest import load,save,now,document_folder,source_directory
from .registry import registered
ASSETS=Path(__file__).parent/'assets'
def init(path):
 if path.exists() and any(path.iterdir()): raise ValueError('Destination must be empty')
 path.mkdir(parents=True,exist_ok=True)
 for d in ('raw/lectures','raw/notes','raw/homework','raw/exams','sources','review/chapters','review/questions','print','reports'): (path/d).mkdir(parents=True,exist_ok=True)
 for name in ('course.yaml','AGENTS.md','.gitignore'): (path/name).write_text((ASSETS/name).read_text(encoding='utf8'),encoding='utf8')
 for f in (ASSETS/'templates').glob('*.md'): (path/'review'/f.name).write_text(f.read_text(encoding='utf8'),encoding='utf8')
 copytree(ASSETS/'protocols',path/'protocols',dirs_exist_ok=True)
 for name in ('00_综合复习稿.md','01_概念速查.md','02_公式与计算.md','03_易错知识.md'):
  (path/'review'/name).write_text('# '+name[:-3]+'\n\npending — to be filled by the user or AI after visual reading.\n',encoding='utf8')

def index(root):
 manifests=[]; md=['# Page index','']; registry=['# Source registry','']
 for d in registered(root):
  ident=d['document_id']; m=load(document_folder(root,d)/'manifest.json')
  registry.append(f"- {ident}: {d['original_filename']} → {d['current_path']} ({d['total_pages']} pages)" + (f" — group: {d['source_group']}" if 'source_group' in d else ''))
  if m is None: continue
  relative=source_directory(d).removeprefix("sources/"); manifests.append(m); md.extend([f"## {ident} — {d['original_filename']}",f"{d['total_pages']} pages; [manifest]({quote(relative)}/manifest.json)"])
  md.extend(f"- [{p['page_id']}]({quote(relative)}/{quote(p['path'])}) — `{p['repository_path']}`" for p in m['pages'])
 save(root/'sources/index.json',{'schema_version':1,'updated_at':now(),'documents':manifests})
 (root/'sources/INDEX.md').write_text('\n'.join(md)+'\n',encoding='utf8'); (root/'sources/SOURCE_REGISTRY.md').write_text('\n'.join(registry)+'\n',encoding='utf8')

 if any("source_group" in d for d in manifests):
  groups={}
  for d in manifests: groups.setdefault(d.get("source_group","."),[]).append(d)
  lines=["# Source groups", "", "Groups reflect the current raw folder; existing published URLs remain stable.", ""]
  for group, docs in sorted(groups.items()):
   lines.extend(["## "+group,""])
   for d in docs:
    rel=source_directory(d).removeprefix("sources/")
    lines.append(f"- [{d['document_id']} — {d['original_filename']}]({quote(rel)}/manifest.json) — {d['total_pages']} pages, G{d.get('preset_number','?')}")
   lines.append("")
  (root/'sources/GROUPS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

def batch(root,document,size,spec=None):
 from .manifest import page_numbers
 if size<1: raise ValueError('Batch size must be positive')
 d=next((d for d in registered(root) if d['document_id']==document),None)
 if not d: raise ValueError('Unknown document')
 m=load(document_folder(root,d)/'manifest.json')
 if not m: raise ValueError('Document has no rendered manifest')
 nums=page_numbers(spec,m['total_pages']); ps={p['original_page']:p for p in m['pages']}
 if any(n not in ps for n in nums): raise ValueError('Requested pages have not been rendered')
 batches=[[{'page_id':ps[n]['page_id'],'image':ps[n]['repository_path']} for n in nums[i:i+size]] for i in range(0,len(nums),size)]
 save(root/'reports'/f'{document}_batches.json',batches); return batches
