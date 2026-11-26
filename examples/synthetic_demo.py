"""Generate synthetic-only source PDFs, never real teaching data."""
import sys
from pathlib import Path
import pymupdf as fitz
from academy_sampler.workspace import init

def pdf(path):
 path.parent.mkdir(parents=True,exist_ok=True)
 with fitz.open() as d:
  for w,h in ((720,405),(405,720),(600,600)):
   p=d.new_page(width=w,height=h)
   p.insert_text((20,40),'Synthetic academy: E = mc',fontsize=16)
   p.insert_text((224,32),'2',fontsize=9)
   p.insert_text((20,80),'合成测试：中文与公式',fontname='china-s',fontsize=16)
   p.draw_line((20,110),(w-20,110),color=(0,0,1),width=.2)
   p.draw_circle((w/2,h/2),30,color=(1,0,0))
  d.new_page(width=720,height=405)
  d.save(path)
def demo(path):
 init(path); pdf(path/'raw/lectures/递归 空格/讲义 2.pdf'); pdf(path/'raw/homework/exercise.pdf')
if __name__=='__main__': demo(Path(sys.argv[1]))
