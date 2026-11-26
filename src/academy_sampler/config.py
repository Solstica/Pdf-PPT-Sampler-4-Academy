import re
import yaml
from .manifest import inside
PRESETS={'compact':{'long_edge':1024,'quality':70},'balanced':{'long_edge':1280,'quality':75},'detailed':{'long_edge':1920,'quality':90},'inspection':{'long_edge':2560,'quality':95}}
def config(root):
 p=root/'course.yaml'
 if not p.exists(): raise ValueError('No course.yaml: run academy init COURSE, then enter it')
 c=yaml.safe_load(p.read_text(encoding='utf8'))
 if not isinstance(c,dict) or not c.get('groups'): raise ValueError('course.yaml requires groups')
 prefixes=[]
 for name,g in c['groups'].items():
  inside(root,g['path'])
  if not re.fullmatch('[A-Z][A-Z0-9]*',g['prefix']): raise ValueError('Group prefix must be uppercase ASCII')
  prefixes.append(g['prefix'])
 if len(prefixes)!=len(set(prefixes)): raise ValueError('Prefixes must be unique')
 return c
def parameters(c,group,preset=None,edge=None,quality=None,format=None):
 g=c['groups'][group]; presets={k:dict(v) for k,v in PRESETS.items()}
 
 for key,value in c.get('presets',{}).items(): presets[key]={**presets.get(key,{}),**value}
 name=preset or g.get('preset','balanced')
 if name not in presets: raise ValueError('Unknown preset: '+name)
 p={**presets[name],'format':format or g.get('format','webp'),'method':6,'color':'RGB','background':'white'}
 if edge is not None: p['long_edge']=edge
 if quality is not None: p['quality']=quality
 if p['long_edge']<1 or not 1<=p['quality']<=100: raise ValueError('Invalid resolution or quality')
 if p['format']=='jpeg': p['format']='jpg'
 if p['format'] not in ('webp','png','jpg'): raise ValueError('Invalid image format')
 return p
