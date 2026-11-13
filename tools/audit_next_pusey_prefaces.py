#!/usr/bin/env python3
"""Locate safely extractable Pusey passages in four candidate source books.

An audit, not a harvest: no multi-author source can enter public search
without separately checked headings, signoffs and neighboring boundaries.
"""
from __future__ import annotations
import json,re,sys,time
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ROOT=Path(__file__).resolve().parent.parent
SOURCES={
 'purchas_liddon_1871':'purchasjudgmentl00lidd',
 'augustine_selected_lessons_1844':'16ALibraryOfFathersOfTheHolyCatholicV16',
 'justin_martyr_1861':'40ALibraryOfFathersOfTheHolyCatholicV40',
 'cyril_john_1874':'43ALibraryOfFathersOfTheHolyCatholicV43',
}
PATS={
 'pusey_signatures':r'E\.\s*B\.\s*P(?:USEY)?\.',
 'pusey_name':r'\b(?:Dr\.?\s*)?PUSEY\b',
 'preface_heads':r'(?im)^\s*(?:PREFACE|INTRODUCTION|ADVERTISEMENT)\s*\.?\s*$',
 'purchas_letter':r'LETTER\s+OF\s+(?:THE\s+REV\.\s*)?(?:DR\.?\s*)?PUSEY|FROM\s+(?:THE\s+REV\.\s*)?(?:DR\.?\s*)?PUSEY',
 'page_53':r'(?m)^\s*53\s*$',
 'page_71':r'(?m)^\s*71\s*$',
 'main_text_start':r'(?im)^\s*(?:SERMON\s+(?:I|1)\b|BOOK\s+(?:I|1)\b|EPISTLE\s+(?:I|1)\b|LECTURE\s+(?:I|1)\b|THE\s+APOLOGY\b)',
}
def hits(t,pat,limit=20,radius=350):
 out=[]
 for m in re.finditer(pat,t,re.I|re.M):
  out.append({'at':m.start(),'match':m.group(0),'before':t[max(0,m.start()-radius):m.start()],'after':t[m.end():m.end()+radius]})
  if len(out)>=limit:break
 return out

def inspect(label,ident):
 md_obj=harvest.get_metadata(ident); md=md_obj.get('metadata') or {}
 name=harvest.text_filename(md_obj)
 if not name:raise ValueError('No OCR text available')
 url='https://archive.org/download/'+quote(ident,safe='')+'/'+quote(name,safe='/')
 req=harvest.request(url,stream=True)
 pieces=[];count=0
 for chunk in req.iter_content(128*1024):
  if not chunk:continue
  pieces.append(chunk);count+=len(chunk)
  if count>45*1024*1024:
   req.close();raise ValueError('OCR overly large')
 req.close()
 raw,enc=harvest.decode_content(b''.join(pieces))
 section=raw[:240000] if label!='purchas_liddon_1871' else raw
 result={'archive_id':ident,'url':url,
         'metadata':{k:md.get(k) for k in ('title','date','year','creator','publisher','imagecount','volume')},
         'characters':len(raw),'words':len(harvest.words(raw)),'encoding':enc,
         'first_5000':raw[:5000],
         'mid_sample':raw[min(65000,len(raw)//3):min(69000,len(raw)//3+4000)],
         'last_2500':raw[-2500:],
         'found':{key:hits(section,pat,30 if key in ('preface_heads','pusey_name') else 18,350) for key,pat in PATS.items()}}
 print('AUDITED',label,'words',result['words'],'date',result['metadata']['date'],flush=True)
 for key,value in result['found'].items():
  print(key,[h['at'] for h in value[:18]],flush=True)
 return result

def main():
 data={}
 for label,ident in SOURCES.items():
  try:data[label]=inspect(label,ident)
  except Exception as e:
   data[label]={'archive_id':ident,'error':type(e).__name__+': '+str(e)}
   print('REJECT AUDIT',label,data[label]['error'],flush=True)
  time.sleep(.2)
 target=ROOT/'data/multi_preface_source_audit.json'
 target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('AUDIT saved',target,flush=True)

if __name__=='__main__':main()
