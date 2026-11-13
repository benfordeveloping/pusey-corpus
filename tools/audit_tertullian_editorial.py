#!/usr/bin/env python3
"""Audit original Pusey preface, lettered Notes, Additional Notes in Tertullian V10.

Never import Tertullian's translated treatises. The immediate editor E.B.P.
signed the preface and assumed responsibility for the Notes. This audit
inspects OCR boundaries and writes a report for a separate validated importer.
"""
from __future__ import annotations
import json,re,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ROOT=Path(__file__).resolve().parent.parent
IDENT='10ALibraryOfFathersOfTheHolyCatholicV10'
OUT=ROOT/'data/tertullian_editorial_audit.json'
LETTERS='ABCDEFGHIKLMNOPQR'

def finds(txt,pattern,limit=60,radius=350):
 result=[]
 for m in re.finditer(pattern,txt,re.I|re.M):
  result.append(dict(at=m.start(),match=m.group(0),
             before=txt[max(0,m.start()-radius):m.start()],
             after=txt[m.end():m.end()+radius]))
  if len(result)>=limit:break
 return result

def main():
 obj=harvest.get_metadata(IDENT);md=obj.get('metadata') or {}
 filename=harvest.text_filename(obj)
 if not filename:raise ValueError('Missing whole-volume OCR')
 url='https://archive.org/download/'+quote(IDENT,safe='')+'/'+quote(filename,safe='/')
 r=harvest.request(url,stream=True)
 parts=[];size=0
 for part in r.iter_content(128*1024):
  if not part:continue
  size+=len(part)
  if size>50*1024*1024:
   r.close();raise ValueError('Unexpected large OCR >50MB')
  parts.append(part)
 r.close()
 txt,encoding=harvest.decode_content(b''.join(parts))
 report={'identifier':IDENT,'url':url,'metadata':{k:md.get(k) for k in ('title','creator','year','date','publisher','imagecount')},
   'encoding':encoding,'ocr_characters':len(txt),'ocr_words':len(harvest.words(txt)),
   'opening_text':txt[:11500],
   'preface_headings':finds(txt[:95000],r'^\s*P\s*R\s*E\s*F\s*A\s*C\s*E\s*[.\n]',30,460),
   'pusey_signatures':finds(txt[:115000],r'\bE\.?\s*B\.?\s*P\.\s*',20,700),
   'notes':{},'additional':finds(txt,r'\bADDITIONAL\s+NOTES?\b',35,340),
   'chapter_heading':finds(txt,r'^\s*(?:I\.\s*)?(?:THE\s+)?APOLOGY\s*(?:OF\s+TERTULLIAN)?\.?\s*$',12,280)}
 for letter in LETTERS:
  # Separate the printed Contents occurrence from the actual note heading.
  pat=rf'^\s*NOTE\s+{letter}(?:[.\:\-]|\s*\n)\s*'
  report['notes'][letter]=finds(txt,pat,32,500)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('META:',md.get('title'), 'creator',md.get('creator'),'date',md.get('date'),flush=True)
 print('OCR:',len(txt),'characters',report['ocr_words'],'words',flush=True)
 for k in ('preface_headings','pusey_signatures','chapter_heading','additional'):
  print('HITS:',k,[x['at'] for x in report[k]],flush=True)
 for letter in LETTERS:
  hits=report['notes'][letter]
  print('LETTER',letter,'hits',len(hits),'offsets',[x['at'] for x in hits],
        'excerpts',[(x['after'][:115].replace('\n',' ')) for x in hits[-3:]],flush=True)
 print('Saved',OUT,flush=True)
if __name__=='__main__':main()
