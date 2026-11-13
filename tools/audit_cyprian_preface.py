#!/usr/bin/env python3
"""Audit E. B. Pusey's 1844 preface to the Epistles of St Cyprian.

Exclude the main translations of Cyprian and Pacian. Identify the preface
in the volume, its E.B.P. signature, and the first page of the Epistles.
"""
import json,re,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ID='epistlesscypria00cyprgoog'
OUT=Path(__file__).resolve().parent.parent/'data/cyprian_epistles_preface_audit.json'
def locate(t,p,maxn=20,radius=400):
 res=[]
 for m in re.finditer(p,t,re.I|re.M):
  res.append({'offset':m.start(),'match':m.group(0),'near':t[max(0,m.start()-radius):m.end()+radius]})
  if len(res)>=maxn:break
 return res
def main():
 meta=harvest.get_metadata(ID)
 md=meta.get('metadata') or {}
 fn=harvest.text_filename(meta)
 if not fn:raise ValueError('No OCR file listed')
 url='https://archive.org/download/'+quote(ID,safe='')+'/'+quote(fn,safe='/')
 r=harvest.request(url,stream=True);chunks=[];size=0
 for b in r.iter_content(128*1024):
  if not b:continue
  chunks.append(b);size+=len(b)
  if size>40*1024*1024:
   r.close();raise ValueError('Source too large')
 r.close();t,enc=harvest.decode_content(b''.join(chunks))
 front=t[:230000]
 report={'identifier':ID,'ocr_url':url,'metadata':{k:md.get(k) for k in ('title','date','year','creator','publisher','imagecount')},
 'encoding':enc,'chars':len(t),'words':len(harvest.words(t)),
 'front_6000':t[:6000],
 'preface_titles':locate(front,r'^\s*(?:P\s*R\s*E\s*F\s*A\s*C\s*E|PREFACE)[.:]?\s*$',20),
 'pusey_signatures':locate(front,r'\bE\.\s*B\.\s*P\.',15,650),
 'epistles_titles':locate(front,r'^\s*(?:(?:THE|S\.)\s*)?EPISTLES\s+OF\s+(?:S\.\s*)?CYPRIAN\b',15),
 'chapters':locate(front,r'^\s*(?:EPISTLE|EPISTLES|LETTER)\s+(?:I|1|II|2)\s*[.:]?\s*$',12),
 'position_40000':t[36000:43000],
 'position_65000':t[61000:68000],
 'position_90000':t[86000:93000]
 }
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('CYPRIAN',md.get('title'),md.get('date'),len(t),flush=True)
 for name in ('preface_titles','pusey_signatures','epistles_titles','chapters'):
  print(name,[(x['offset'],x['match'][:60]) for x in report[name]],flush=True)
 print('Saved',OUT)
if __name__=='__main__':main()
