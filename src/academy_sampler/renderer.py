import pymupdf as fitz
import PIL
from PIL import Image
from .converters import pdf_source
from .manifest import load,save,now,sha,page_numbers,document_folder,source_directory
from .registry import source

def dimensions(rect,edge):
 return (edge,max(1,round(edge*rect.height/rect.width))) if rect.width>=rect.height else (max(1,round(edge*rect.width/rect.height)),edge)
def valid_image(path,p):
 try:
  with Image.open(path) as im:
   im.load()
   return im.size==(p['width'],p['height']) and im.mode=='RGB' and path.stat().st_size==p['bytes']>0 and sha(path)==p['image_sha256']
 except (OSError,KeyError): return False

def render(root,d,params,spec=None,force=False):
 src=source(root,d); folder=document_folder(root,d); mp=folder/'manifest.json'
 m=load(mp,{**d,'pages':[]}); entries={p['original_page']:p for p in m['pages']}; stats={'converted':0,'skipped':0,'failed':0,'bytes':0}; errors=[]
 with pdf_source(src) as (pdf,expected,warnings):
  converter={'backend':'pdf' if src.suffix.lower()=='.pdf' else 'office-pdf','pymupdf':fitz.VersionBind,'pillow':PIL.__version__,'pipeline':1,'export_warnings':warnings}
  with fitz.open(pdf) as doc:
   if len(doc)!=d['total_pages']: raise ValueError('PDF page count changed')
   if expected is not None and expected!=len(doc): warnings.append(f'Slide count mismatch: {expected} vs {len(doc)}')
   warnings.append('For office export, visually check font substitution and hidden slides.') if src.suffix.lower()!='.pdf' else None
   m.update({**d,'source_sha256':d['source_sha256'],'converter':converter,'warnings':warnings,'updated_at':now()})
   for n in page_numbers(spec,len(doc)):
    prior=entries.get(n); path=folder/prior['path'] if prior else None
    if not force and prior and prior.get('parameters')==params and prior.get('converter')==converter and valid_image(path,prior): stats['skipped']+=1; continue
    try:
     page=doc[n-1]; scale=params['long_edge']/max(page.rect.width,page.rect.height)
     pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csRGB,alpha=False)
     im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples); size=dimensions(page.rect,params['long_edge'])
     if im.size!=size: im=im.resize(size,Image.Resampling.LANCZOS)
     name=f"{n:03d}.{params['format']}"; folder.mkdir(parents=True,exist_ok=True); path=folder/name; temp=folder/(name+'.tmp')
     options={'quality':params['quality'],'method':6} if params['format']=='webp' else ({'quality':params['quality'],'subsampling':0} if params['format']=='jpg' else {})
     im.save(temp,format={'webp':'WEBP','png':'PNG','jpg':'JPEG'}[params['format']],**options); temp.replace(path)
     p={'page_id':f"{d['document_id']}-P{n:03d}",'original_page':n,'path':name,'repository_path':f"{source_directory(d)}/{name}",'width':im.width,'height':im.height,'bytes':path.stat().st_size,'image_sha256':sha(path),'parameters':params,'converter':converter,'status':'complete','converted_at':now()}
     if not valid_image(path,p): raise ValueError('Image validation failed')
     entries[n]=p; stats['converted']+=1; stats['bytes']+=p['bytes']
    except Exception as exc:
     stats['failed']+=1; errors.append(f'{n}: {exc}'); entries.pop(n,None)
    m['pages']=sorted(entries.values(),key=lambda p:p['original_page']); m['status']='complete' if len(entries)==len(doc) and not errors else 'partial'; m['errors']=errors
    save(mp,m)  # per-page checkpoint, including failures
   save(mp,m)  # also persist metadata updates when every page was cached
 return stats,errors
