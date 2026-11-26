from contextlib import ExitStack
import pymupdf as fitz
from .registry import registered,source
from .converters import pdf_source
from .progress import refs
from .manifest import save

def print_pages(root,requested,output):
 if not requested: raise ValueError('No pages requested')
 known=refs(root); docs={d['document_id']:d for d in registered(root)}
 for ref in requested:
  if ref not in known: raise ValueError('Unknown page reference: '+ref)
 if output.resolve().is_relative_to((root/'raw').resolve()): raise ValueError('Printing into raw is forbidden')
 if any(output.resolve()==source(root,d).resolve() for d in docs.values() if d.get('available')): raise ValueError('Cannot overwrite source')
 output.parent.mkdir(parents=True,exist_ok=True)
 with ExitStack() as stack:
  pdfs={}; dest=stack.enter_context(fitz.open())
  for ref in requested:
   ident,num=ref.rsplit('-P',1)
   if ident not in pdfs:
    pdf,expected,warnings=stack.enter_context(pdf_source(source(root,docs[ident])))
    src=stack.enter_context(fitz.open(pdf)); pdfs[ident]=src
    if expected is not None and expected!=len(src): raise ValueError('Slide count mismatch')
    if warnings: save(output.with_suffix('.warnings.json'),warnings)
   n=int(num)-1; dest.insert_pdf(pdfs[ident],from_page=n,to_page=n)
  tmp=output.with_suffix('.tmp.pdf'); dest.save(tmp,garbage=4,deflate=True); tmp.replace(output)
 return str(output)
