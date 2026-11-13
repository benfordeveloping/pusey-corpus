#!/usr/bin/env python3
"""Index only E.B. Pusey's signed 1844 preface to S. Cyprian's Epistles.

The main translated epistles of S. Cyprian and the extant works of S. Pacian
are excluded. The author signs the preface E.B.P., Ember Week after Whitsunday
1844, before the volume's Contents pages begin.
"""
from __future__ import annotations
import csv,hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1844-preface-to-the-epistles-of-st-cyprian'
ARCHIVE='epistlesscypria00cyprgoog'
def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((w for w in works if w['id']==ID),None)
    if not work or work.get('contribution')!='editorial':
        raise ValueError('Not the E.B.P. Cyprian preface entry')
    meta=harvest.get_metadata(ARCHIVE)
    md=meta.get('metadata') or {}
    title=str(md.get('title',''))
    year=str(md.get('year','') or md.get('date',''))
    if not re.search(r'epistles.*cyprian',title,re.I) or '1844' not in year:
        raise ValueError('Unexpected book title/date: '+title+' ('+year+')')
    if not re.search(r'parker',str(md.get('publisher','')),re.I):
        raise ValueError('1844 Parker publisher imprint not present')
    fname=harvest.text_filename(meta)
    if not fname:raise ValueError('No IA OCR text listed')
    url='https://archive.org/download/'+quote(ARCHIVE,safe='')+'/'+quote(fname,safe='/')
    response=harvest.request(url,stream=True);chunks=[];size=0
    for block in response.iter_content(128*1024):
        if not block:continue
        chunks.append(block);size+=len(block)
        if size>40*1024*1024:
            response.close();raise ValueError('Unexpectedly large OCR')
    response.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    header=list(re.finditer(r'(?im)^\s*PREFACE\.\s+The\s+Epistles\s+of\s+S\.\s+Cyprian',raw[:20000]))
    if len(header)!=1:raise ValueError('Expected unique opening of Pusey Cyprian Preface; found '+str(len(header)))
    start=header[0].start()
    signature=list(re.finditer(r'E\.\s*B\.\s*P\.\s*Ember\s+Week\s+after\s+Whi\w+day\W*\s*1844\.',raw[:110000],re.I))
    if len(signature)!=1:raise ValueError('Signed and dated Pusey preface ending not found')
    finish=signature[0].end()
    if not 45000<finish<80000:
        raise ValueError('Unexpected preface length or boundary: '+str(finish))
    excerpt=raw[start:finish].strip()
    wc=len(harvest.words(excerpt))
    if not 6000<wc<16000:
        raise ValueError('Preface word count implausible '+str(wc))
    if 'CONTENTS.' in excerpt[-500:]:
        raise ValueError('Translated epistles contents accidentally included')
    if not re.search(r'The\s+Epistles\s+of\s+S\.\s+Cyprian',excerpt[:300],re.I):
        raise ValueError('Incorrect preface opening')
    if not re.search(r'E\.\s*B\.\s*P\.\s*Ember\s+Week\s+after\s+Whi\w+day\W*\s*1844\.\s*$',excerpt,re.I):
        raise ValueError('Incorrect preface ending')
    content='Preface to the Epistles of St Cyprian\n\n'+excerpt+'\n'
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    (harvest.RAW/(ID+'.txt')).write_text(content,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(content),encoding='utf8')
    harvest.write_record(work,{
      'status':'downloaded','source':'Internet Archive OCR, Pusey prefatory essay alone',
      'identifier':ARCHIVE,'scan_url':'https://archive.org/details/'+ARCHIVE,'text_url':url,
      'source_title':title,'source_creator':'E. B. Pusey (preface); Cyprian and Pacian (translated works excluded)',
      'source_date':'1844','downloaded_utc':datetime.now(timezone.utc).isoformat(),
      'original_sha256':hashlib.sha256(content.encode()).hexdigest(),
      'word_count':len(harvest.words(content)), 'encoding':encoding,
      'scope_verified':True,'content_scope':'pusey_preface_or_introduction_only',
      'extraction_boundaries':{
          'start':'PREFACE. The Epistles of S. Cyprian exhibit in detail ...',
          'end':'E. B. P. Ember Week after Whitsunday, 1844.',
          'raw_ocr_start_char':start,'raw_ocr_end_char':finish,'source_chars':len(raw),
          'other_authors_translations_excluded':True
      },
      'authorship_review_needed':False,
      'qc':'Signed Pusey preface only; contents, Cyprian epistles and Pacian works excluded'
    })
    registry=ROOT/'data/source_registry.csv'
    with registry.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    row=next(r for r in rows if r['id']==ID)
    row.update(verification_status='verified_pusey_preface_only',
        archive_id=ARCHIVE,scan_url='https://archive.org/details/'+ARCHIVE,
        ocr_url=url,ocr_filename=fname,ia_title=title,
        ia_creator='E. B. Pusey (preface)',ia_year='1844',
        notes='Signed E.B.P. preface dated Ember Week after Whitsunday 1844, exact OCR chars '+str(start)+'–'+str(finish)+'. Following translated Cyprian and Pacian excluded.')
    with registry.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED CYPRIAN 1844 PUSEY PREFACE',wc,'words',flush=True)
if __name__=='__main__':main()
