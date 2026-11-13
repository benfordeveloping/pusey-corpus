#!/usr/bin/env python3
"""Audit owner supplied 1836/1840 baptism editions and Pusey's Augustine preface.

Retrieve OCR on the GitHub Actions runner, record front matter, edition markers
and extractable boundaries, but DO NOT add any uncertain text to public index.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
SOURCES={
 'baptism_1836_original':('scripturalviewso00puse','scripturalviewso00puse_djvu.txt'),
 'baptism_1840_enlarged':('scripturalviews1840puse','scripturalviews1840puse_djvu.txt'),
 'augustine_confessions':('in.ernet.dli.2015.99648','2015.99648.The-Confessions-Of--S-Augustine_djvu.txt')
}
def around(s,regex,max_hits=10,radius=340):
 hits=[]
 for m in re.finditer(regex,s,re.I):
  hits.append({'offset':m.start(),'match':m.group(0),'excerpt':s[max(0,m.start()-radius):m.end()+radius]})
  if len(hits)>=max_hits:break
 return hits
def retrieve(key,identifier,preferred):
 obj=harvest.get_metadata(identifier)
 md=obj.get('metadata',{})
 available=[f.get('name','') for f in obj.get('files',[]) if f.get('name','').lower().endswith('.txt')]
 filename=preferred if preferred in available else harvest.text_filename(obj)
 if not filename:raise RuntimeError('No OCR plain text listed for '+identifier)
 url='https://archive.org/download/'+quote(identifier,safe='')+'/'+quote(filename,safe='/')
 response=harvest.request(url,stream=True)
 chunks=[];size=0
 for part in response.iter_content(128*1024):
  if not part:continue
  chunks.append(part);size+=len(part)
  if size>50*1024*1024:
   response.close();raise RuntimeError('OCR >50 MB')
 response.close()
 raw,encoding=harvest.decode_content(b''.join(chunks))
 front=raw[:120000]
 results={
  'identifier':identifier,'source':url,'title_metadata':{k:md.get(k) for k in ('title','year','date','publisher','creator','imagecount','volume','description')},
  'word_count':len(harvest.words(raw)),'chars':len(raw),'encoding':encoding,
  'first_ocr_characters':front[:17000],
  'title_mentions':around(front,r'SCRIPTURAL\s+VIEWS|CONFESSIONS\s+OF|HOLY\s+BAPTISM',10,220),
  'edition_mentions':around(front,r'SECOND\s+EDITION|FIRST\s+EDITION|ENLARGED|REVISED|AMERICAN\s+EDITION|NEW\s+YORK|PHILADELPHIA|MDCCCXL|1839|1840|1836',15,270),
  'volume_mentions':around(front,r'TRACT\s+(?:LXVI[I X]+|6[789])|TRACTS\s+FOR\s+THE\s+TIMES',10,220),
 }
 if 'augustine' in key:
  results.update({
   'pusey_names':around(front,r'PUSEY|E\.?\s*B\.?\s*P\.?',18,300),
   'preface_heading':around(front,r'\bPREFACE\b|\bINTRODUCTION\b|\bADVERTISEMENT\b',28,450),
   'augustine_book1':around(front,r'BOOK\s+(?:I|1|THE FIRST)|LIBER\s+PRIMUS|CONFESSIONS\s+OF\s+ST',12,450),
   'other_intro':around(front,r'\bTHE\s+TRANSLATOR\b|\bTO\s+THE\s+READER\b',6,300),
  })
 if 'baptism' in key:
  results.update({
   'doctrine_start':around(front,r'HOLY\s+BAPTISM|INFANT\s+BAPTISM|REGENERATION',10,250),
   'contents':around(front,r'\bCONTENTS\b|\bAPPENDIX\b|\bNOTES\b',12,300)
  })
 print('AUDITED',key,identifier,'OCR words',results['word_count'],'year',md.get('date') or md.get('year'),flush=True)
 return results
def main():
 data={}
 for key,(identifier,preferred) in SOURCES.items():
  try:data[key]=retrieve(key,identifier,preferred)
  except Exception as exc:
   data[key]={'error':type(exc).__name__+': '+str(exc)}
   print('ERROR',key,data[key]['error'],flush=True)
 out=ROOT/'data/owner_source_audit_20261113.json'
 out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('SAVED',out,flush=True)
if __name__=='__main__':main()
