import pymupdf as fitz
from .manifest import load,inside,document_folder
from .registry import registered,source
from .renderer import valid_image,dimensions
from .converters import pdf_source

def validate(root):
 errors=[]; manifests=[]
 for d in registered(root):
  mp=document_folder(root,d)/'manifest.json'; m=load(mp)
  if m is None: errors.append(d['document_id']+': missing manifest'); continue
  manifests.append(m)
  try:
   if m['source_sha256']!=d['source_sha256']: raise ValueError('Manifest source hash mismatch')
   with pdf_source(source(root,d)) as (pdf,_,__):
    with fitz.open(pdf) as doc:
     if len(doc)!=m['total_pages'] or len(doc)!=d['total_pages']: raise ValueError('Page count mismatch')
     if [p['original_page'] for p in m['pages']]!=list(range(1,len(doc)+1)): errors.append(d['document_id']+': missing or duplicate page numbers')
     for p in m['pages']:
      path=inside(root,p['repository_path'])
      if path!=mp.parent.joinpath(p['path']).resolve() or not valid_image(path,p): errors.append(p['page_id']+': corrupt image or metadata')
      if dimensions(doc[p['original_page']-1].rect,p['parameters']['long_edge'])!=(p['width'],p['height']): errors.append(p['page_id']+': wrong resolution/aspect ratio')
      if p['page_id']!=f"{d['document_id']}-P{p['original_page']:03d}": errors.append('Invalid page ID')
  except Exception as exc: errors.append(d['document_id']+': '+str(exc))
 index=load(root/'sources/index.json',{})
 if index.get('documents')!=manifests: errors.append('Global index differs from manifests')
 from .progress import check_progress
 errors.extend(check_progress(root))
 return errors
