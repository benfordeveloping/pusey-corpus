#!/usr/bin/env python3
"""Locate Pusey's 1838 introduction in the 1887 Confessions reprint.

No Augustine book content is imported. This audit records OCR boundary
candidates and surrounding textual evidence for author-only indexing.
"""
import json,re,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ROOT=Path(__file__).resolve().parent.parent
IA='in.ernet.dli.2015.99648'
OUT=ROOT/'data/augustine_preface_boundaries.json'
def sample(txt,pat,limit=30,radius=350):
  result=[]
  for m in re.finditer(pat,txt,re.I|re.M):
    result.append(dict(at=m.start(),match=m.group(0),context=txt[max(0,m.start()-radius):m.end()+radius]))
    if len(result)>=limit:break
  return result

def main():
  meta=harvest.get_metadata(IA)
  md=meta.get('metadata') or {}
  fname=harvest.text_filename(meta)
  if not fname:raise ValueError('No Archive.org OCR listed')
  url='https://archive.org/download/'+quote(IA,safe='')+'/'+quote(fname,safe='/')
  req=harvest.request(url,stream=True)
  bits=[];n=0
  for b in req.iter_content(128*1024):
    if not b:continue
    bits.append(b);n+=len(b)
    if n>40*1024*1024:
      req.close();raise ValueError('OCR unexpectedly large')
  req.close()
  t,encoding=harvest.decode_content(b''.join(bits))
  prefix=t[:350000]
  report=dict(
    archive_id=IA,source_url=url,
    metadata={k:md.get(k) for k in ('title','creator','date','year','publisher','imagecount')},
    original_characters=len(t),original_words=len(harvest.words(t)),encoding=encoding,
    start_text=t[:3500],
    preface_heading=sample(prefix,r'PREFACE\s+TO\s+THE\s+CONFESSIONS(?:\s+OF\.?\s+ST\.?\s+AUGUSTINE)?',8,250),
    signature=sample(prefix,r'\bE\.\s*B\.\s*P\.\s*',25,350),
    next_section=sample(prefix,r'^\s*(?:LIFE\s+OF\s+(?:ST\.?\s*)?AUGUSTINE|BOOK\s+(?:I|1|THE\s+FIRST)|CONFESSIONS\s+OF\s+ST\.?\s+AUGUSTINE|ANALYSIS|CONTENTS|INTRODUCTION\s+TO\s+BOOK\s+I)\s*$',
      40,280),
    book1_phrase=sample(prefix,r'Great\s+art\s+Thou,\s+O\s+Lord',10,600),
    unusual_end=sample(prefix,r'(?:THE\s+END\s+OF\s+THE\s+PREFACE|TO\s+THE\s+READER|FINIS)\b',10,350),
    passage_near_60k=t[56000:64000],
    passage_near_80k=t[76000:85000],
    passage_near_110k=t[105000:114000],
    passage_near_140k=t[135000:144000],
  )
  OUT.parent.mkdir(parents=True,exist_ok=True)
  OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  print('Augustine source words',report['original_words'],'chars',len(t),flush=True)
  for key in ('preface_heading','signature','next_section','book1_phrase','unusual_end'):
    print(key,[(z['at'],z['match'][:55]) for z in report[key]],flush=True)
  print('Saved',OUT,flush=True)

if __name__=='__main__':main()
