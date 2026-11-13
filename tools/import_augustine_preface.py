#!/usr/bin/env python3
"""Import only Pusey's 1838 preface to St Augustine's Confessions.

The owner-provided 1887 reprint contains all of Augustine's Confessions,
which must NEVER enter the Pusey prose index. The preface is delimited by
its heading and E.B.P.'s Oxford, Feast of St Bartholomew 1838 signature.
"""
from __future__ import annotations
import csv,hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1838-introduction-and-notes-to-the-confessions-of-st-augustin'
ARCHIVE='in.ernet.dli.2015.99648'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((w for w in works if w['id']==ID),None)
    if not work or work.get('contribution')!='editorial':
        raise ValueError('Preface must be catalogued as Pusey editorial contribution only')
    meta=harvest.get_metadata(ARCHIVE)
    md=meta.get('metadata') or {}
    title=str(md.get('title',''))
    creator=str(md.get('creator',''))
    date=str(md.get('year','') or md.get('date',''))
    if not re.search('confessions',title,re.I) or not re.search('augustine',title,re.I):
        raise ValueError('Incorrect Augustine source')
    if 'pusey' not in creator.lower() or '1887' not in date:
        raise ValueError('Expected 1887 Pusey edition with correct source attribution')
    name=harvest.text_filename(meta)
    if not name:raise ValueError('OCR text file missing from archive')
    url='https://archive.org/download/'+quote(ARCHIVE,safe='')+'/'+quote(name,safe='/')
    req=harvest.request(url,stream=True)
    chunks=[];total=0
    for chunk in req.iter_content(128*1024):
        if not chunk:continue
        chunks.append(chunk);total+=len(chunk)
        if total>40*1024*1024:
            req.close();raise ValueError('OCR too large')
    req.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    head=list(re.finditer(r'PREFACE\s+TO\s+THE\s+CONFESSIONS\s+OF\.?\s*ST\.?\s+AUGUSTINE\.',raw[:4000],re.I))
    if len(head)!=1:
        raise ValueError('Expected unique Pusey preface title in opening OCR')
    start=head[0].start()
    sig=list(re.finditer(r'Oxford,\s*Feast\s+of\s+S\.\s*Bartholomeiv\s*,\s*1838\.\s*E\.\s*B\.\s*P\.',raw[:110000],re.I))
    if len(sig)!=1:
        raise ValueError('Expected unique signed 1838 preface ending; got '+str(len(sig)))
    end=sig[0].end()
    if not 50000<end<95000 or start>2500:
        raise ValueError('Preface boundaries unexpectedly different')
    excerpt=raw[start:end].strip()
    if not re.search(r'^\s*PREFACE',excerpt,re.I):
        raise ValueError('Preface heading missing')
    if not re.search(r'The general objects of the',re.sub(r'[^a-zA-Z ]',' ',excerpt[:4000]),re.I):
        # OCR quotes and ligatures vary; allow a conservative standard phrase.
        if not re.search(r'The\s+general\s+objects',excerpt[:4000],re.I):
            raise ValueError('Expected Pusey preface opening not found')
    if re.search(r'\bCONTENTS\s+THE\s+FIRST\s+BOOK\b',excerpt[-1300:],re.I):
        raise ValueError('Augustine contents page leaked into Pusey preface')
    if re.search(r'^\s*BOOK\s+I\.\s*$',excerpt,re.I|re.M):
        raise ValueError('Augustine Book I leaked into indexed Pusey text')
    words=len(harvest.words(excerpt))
    if not 9000<words<20000:
        raise ValueError('Preface word count is implausible '+str(words))
    full='Preface to the Confessions of St Augustine\n\n'+excerpt+'\n'
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(ID+'.txt')).write_text(full,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(full),encoding='utf8')
    harvest.write_record(work,{
       'status':'downloaded',
       'source':'Internet Archive 1887 reprint, Pusey signed preface excerpt ONLY',
       'identifier':ARCHIVE,'scan_url':'https://archive.org/details/'+ARCHIVE,
       'text_url':url,'downloaded_utc':datetime.now(timezone.utc).isoformat(),
       'source_title':title,'source_creator':'E. B. Pusey (signed Preface; Augustine text excluded)',
       'source_date':'1887 reprint of 1838 Pusey preface',
       'source_edition_year':1887,
       'pusey_preface_signed_year':1838,
       'original_sha256':hashlib.sha256(full.encode()).hexdigest(),
       'word_count':len(harvest.words(full)),
       'scope_verified':True,
       'content_scope':'pusey_preface_or_introduction_only',
       'extraction_boundaries':{
           'start':'PREFACE TO THE CONFESSIONS OF ST AUGUSTINE; The general objects of the Library...',
           'end':'Oxford, Feast of S. Bartholomew, 1838. E. B. P.',
           'raw_ocr_start_char':start,'raw_ocr_end_char':end,
           'raw_ocr_characters':len(raw),
           'subsequent_Contents_and_Augustine_books_excluded':True
       },
       'authorship_review_needed':False,
       'qc':'Pusey’s complete signed preface only; edition 1887; no Augustine translation or Pusey notes to the translated books'
    })
    registry=ROOT/'data/source_registry.csv'
    with registry.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x['id']==ID)
    row.update(verification_status='verified_pusey_preface_only',
      archive_id=ARCHIVE,
      scan_url='https://archive.org/details/'+ARCHIVE,ocr_url=url,
      ocr_filename=name,ia_title=title,ia_creator=creator,ia_year='1887',
      notes='Pusey Preface only: signed Oxford Feast of St Bartholomew 1838; 1887 printed reissue, original OCR chars '+str(start)+'-'+str(end)+'. Excludes Augustine’s books.')
    with registry.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED PUSEY AUGUSTINE PREFACE ONLY:',words,'words, 1838 preface / 1887 printing',flush=True)
if __name__=='__main__':main()
