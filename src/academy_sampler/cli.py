import argparse,json,re
from pathlib import Path
from .config import config,parameters
from .registry import ingest,registered
from .workspace import init,index,batch
from .renderer import render
from .validator import validate
from .progress import progress,STATES
from .printer import print_pages
from .manifest import save,page_numbers
from .terminal_progress import PageProgress, LANGUAGE, default_language, tr, stage, human_bytes

def main(argv=None):
 p=argparse.ArgumentParser(prog='academy'); p.add_argument('--lang',choices=['en','zh'],default=default_language()); p.add_argument('--workspace',type=Path,default=Path.cwd()); subs=p.add_subparsers(dest='command',required=True)
 s=subs.add_parser('init'); s.add_argument('course',type=Path)
 s=subs.add_parser('ingest'); s.add_argument('--new-version',action='store_true')
 s=subs.add_parser('render'); s.add_argument('--lang',choices=['en','zh'],default=argparse.SUPPRESS); s.add_argument('--document'); s.add_argument('--group'); s.add_argument('--input',type=Path); s.add_argument('--pages'); s.add_argument('--preset'); s.add_argument('--long-edge',type=int); s.add_argument('--quality',type=int); s.add_argument('--format',choices=['webp','png','jpg','jpeg']); s.add_argument('--force',action='store_true')
 subs.add_parser('validate'); subs.add_parser('index')
 s=subs.add_parser('progress'); s.add_argument('--page'); s.add_argument('--state',choices=STATES); s.add_argument('--reason')
 s=subs.add_parser('batch'); s.add_argument('--document',required=True); s.add_argument('--size',type=int,default=15); s.add_argument('--pages')
 s=subs.add_parser('print'); s.add_argument('--pages'); s.add_argument('--list',type=Path); s.add_argument('--output',type=Path,default=Path('print/selected.pdf'))
 a=p.parse_args(argv); root=a.workspace.resolve()
 if a.lang not in ('en','zh'): p.error('ACADEMY_SAMPLER_LANG must be en or zh')
 token=LANGUAGE.set(a.lang)
 try:
  if a.command=='init': init(a.course.resolve()); print(a.course); return 0
  c=config(root)
  if a.command=='ingest': result=ingest(root,c,a.new_version); index(root); progress(root); print(json.dumps(result,ensure_ascii=False)); return 0
  if a.command=='render':
   docs=registered(root)
   if a.document: docs=[d for d in docs if d['document_id']==a.document]
   if a.group: docs=[d for d in docs if d['category']==a.group or d.get('source_group')==a.group]
   if a.input: docs=[d for d in docs if (root/d['current_path']).resolve()==(root/a.input).resolve()]
   if not docs: raise ValueError('No matching registered documents; run ingest first')
   totals={'converted':0,'skipped':0,'failed':0,'bytes':0}; errors=[]
   render_params={d['document_id']:parameters(c,d['category'],a.preset or (f"trans_g{d['preset_number']}" if d.get('preset_number') else None),a.long_edge,a.quality,a.format) for d in docs}
   plan={d['document_id']:(len(page_numbers(a.pages,d['total_pages'])),json.dumps(render_params[d['document_id']],sort_keys=True)) for d in docs}
   with PageProgress(sum(n for n,_ in plan.values()),documents=plan,source_bytes=sum(d['source_bytes'] for d in docs)) as bar:
    for d in docs:
     bar.document(d['document_id'],len(page_numbers(a.pages,d['total_pages'])))
     try:
      stats,errs=render(root,d,render_params[d["document_id"]],a.pages,a.force,on_page=bar.advance,on_size=bar.record_size)
      for k,v in stats.items(): totals[k]+=v
      errors.extend(f"{d['document_id']}: {e}" for e in errs)
     except Exception as exc: errors.append(d['document_id']+': '+str(exc))
   index(root); progress(root)
   from .manifest import load
   all_docs=load(root/'sources/index.json')['documents']
   cumulative={'documents':len(all_docs),'pages':sum(len(m['pages']) for m in all_docs),'image_bytes':sum(p['bytes'] for m in all_docs for p in m['pages'])}
   save(root/'reports/conversion_report.json',{'run':totals,'cumulative':cumulative,'errors':errors})
   (root/'reports/conversion_report.md').write_text('# Conversion report\n\n'+json.dumps({'run':totals,'cumulative':cumulative,'errors':errors},indent=2)+'\n',encoding='utf8')
   stage(f"Archive images: {human_bytes(cumulative['image_bytes'])}",f"归档图像: {human_bytes(cumulative['image_bytes'])}")
   print(totals); print('\n'.join(errors)); return int(bool(errors))
  if a.command=='index': index(root); return 0
  if a.command=='validate':
   errors=validate(root); print('\n'.join(errors) if errors else tr('All integrity checks passed','完整性校验全部通过')); return int(bool(errors))
  if a.command=='progress': print(progress(root,a.page,a.state,a.reason)); return 0
  if a.command=='batch': print(json.dumps(batch(root,a.document,a.size,a.pages),indent=2)); return 0
  if a.command=='print':
   requested=a.pages.split(',') if a.pages else []
   if a.list:
    text=(root/a.list).read_text(encoding='utf8')
    requested=json.loads(text) if a.list.suffix=='.json' else re.findall(r'\b[A-Z][A-Z0-9]*-P\d{3,}\b',text)
   print(print_pages(root,[s.strip() for s in requested],root/a.output)); return 0
 except (ValueError,OSError,KeyError,RuntimeError) as exc: print(tr('Error:','错误:'),exc); return 1
 finally: LANGUAGE.reset(token)
if __name__=='__main__': raise SystemExit(main())
