import json,shutil,subprocess,sys
from pathlib import Path
import pytest
import pymupdf as fitz
from academy_sampler.workspace import init,index,batch
from academy_sampler.config import config,parameters
from academy_sampler.registry import ingest,registered
from academy_sampler.renderer import render
from academy_sampler.validator import validate
from academy_sampler.manifest import sha,load
from academy_sampler.progress import progress,check_progress
from academy_sampler.printer import print_pages
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples'))
from synthetic_demo import pdf

@pytest.fixture
def course(tmp_path):
 root=tmp_path/'course'; init(root); pdf(root/'raw/lectures/中文 空格/lecture 2.pdf'); pdf(root/'raw/homework/same.pdf'); return root

def test_full_pipeline(course):
 root=course;c=config(root);reg=ingest(root,c); assert len(reg['documents'])==2
 original={p:sha(p) for p in (root/'raw').rglob('*.pdf')}
 for d in reg['documents']:
  stats,errors=render(root,d,parameters(c,d['category'])); assert stats['converted']==4 and not errors
 index(root);progress(root);assert not validate(root)
 assert all(p.exists() and sha(p)==h for p,h in original.items())
 assert len(ingest(root,c)['documents'])==2
 d=reg['documents'][0]; params=parameters(c,d['category']); stats,_=render(root,d,params);assert stats['skipped']==4
 im=root/'sources'/d['document_id']/'001.webp';before=sha(im)
 render(root,d,parameters(c,d['category'],'inspection'),'2',True); assert sha(im)==before
 index(root);assert not validate(root)
 im.write_bytes(b'broken');assert validate(root)
 stats,_=render(root,d,params);assert stats['converted']==2 # corrupt page + overridden inspection page
 index(root);assert not validate(root)
 assert len(batch(root,d['document_id'],3))==2
 assert set(progress(root))=={'pending'}
 progress(root,'L01-P001','read');assert progress(root)['read']==1
 with pytest.raises(ValueError):progress(root,'L99-P001','read')
 with pytest.raises(ValueError):progress(root,'L01-P001','skipped_with_reason')
 (root/'review/README.md').write_text('L99-P001');assert check_progress(root)
 output=root/'print/result.pdf';print_pages(root,['H01-P003','L01-P001','H01-P003'],output)
 with fitz.open(output) as doc:
  assert len(doc)==3 and doc[0].get_drawings() and doc[1].get_fonts() and not doc[0].get_images()
 with pytest.raises(ValueError):print_pages(root,['L01-P999'],output)

def test_identity_and_versions(course):
 root=course;c=config(root);reg=ingest(root,c);d=reg['documents'][0]; src=root/d['current_path'];dest=src.with_name('renamed.pdf');src.rename(dest)
 reg=ingest(root,c);assert reg['documents'][0]['document_id']==d['document_id'] and len(reg['documents'])==2
 shutil.copyfile(dest,dest.with_name('duplicate.pdf'));reg=ingest(root,c);assert len(reg['documents'])==3 and reg['duplicates']
 dest.write_bytes(dest.read_bytes()+b'\n%changed')
 with pytest.raises(ValueError,match='content changed'):ingest(root,c)
 reg=ingest(root,c,True);assert len(reg['documents'])==4 and reg['documents'][-1]['version_of']

def test_formats_cli_and_git(course,tmp_path):
 root=course;c=config(root);d=ingest(root,c)['documents'][0]
 for fmt in ('png','jpg'):
  stats,errs=render(root,d,parameters(c,d['category'],format=fmt),'1');assert stats['converted']==1 and not errs
 from academy_sampler.cli import main
 assert main(['--workspace',str(root),'render','--document','NOTFOUND'])==1
 assert main(['--workspace',str(root),'batch','--document','L01','--size','0'])==1
 assert main(['--workspace',str(root),'progress','--page','L01-P001','--state','read'])==0
 subprocess.run(['git','init',str(root)],check=True,capture_output=True)
 for path in ('raw/test.pdf','sources/source_registry.json','sources/L01/001.webp','review/notes.md','print/out.pdf','reports/test.json'):
  assert subprocess.run(['git','-c',f'safe.directory={root.as_posix()}','check-ignore',path],cwd=root,capture_output=True).returncode==0
 for cmd in ('init','ingest','render','validate','index','progress','batch','print'):
  run=subprocess.run([sys.executable,'-m','academy_sampler.cli',cmd,'--help'],capture_output=True); assert run.returncode==0

def test_failure_checkpoint(course,monkeypatch):
 root=course;c=config(root);d=ingest(root,c)['documents'][0]
 from PIL import Image
 save=Image.Image.save
 def fail(self,fp,*a,**kw):
  if str(fp).endswith('002.webp.tmp'): raise OSError('synthetic failure')
  return save(self,fp,*a,**kw)
 monkeypatch.setattr(Image.Image,'save',fail)
 stats,errors=render(root,d,parameters(c,d['category']));assert stats['converted']==3 and stats['failed']==1 and errors
 assert len(load(root/'sources/L01/manifest.json')['pages'])==3
 monkeypatch.setattr(Image.Image,'save',save)
 stats,errors=render(root,d,parameters(c,d['category']));assert stats['converted']==1 and stats['skipped']==3


def test_custom_order_and_states(course):
 import yaml
 root=course; c=config(root)
 pdf(root/'raw/lectures/first.pdf')
 c['groups']['lectures']['prefix']='LECT'
 c['groups']['lectures']['order']=['first.pdf']
 c['presets']={'balanced':{'quality':80}}
 (root/'course.yaml').write_text(yaml.safe_dump(c),encoding='utf8')
 c=config(root); docs=[d for d in ingest(root,c)['documents'] if d['category']=='lectures']
 assert docs[0]['document_id']=='LECT01' and docs[0]['original_filename']=='first.pdf'
 assert parameters(c,'lectures')['quality']==80
 progress(root)
 for state in ('read','extracted','needs_high_resolution','verified','skipped_with_reason'):
  progress(root,'LECT01-P001',state,'synthetic evidence')
 assert not check_progress(root)
