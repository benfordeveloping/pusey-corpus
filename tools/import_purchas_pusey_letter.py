#!/usr/bin/env python3
"""Import only Pusey's letter and postscript from Liddon's Purchas Judgment.

Source printed 1871, Pusey contribution pp. 53-71. Liddon's letter and
the rest of the mixed-author pamphlet must be excluded from search.
"""
from __future__ import annotations
import csv,hashlib,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1871-letter-on-the-purchas-judgment-pp-53-71-of-liddon-s-volu'
ARCHIVE='purchasjudgmentl00lidd'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((x for x in works if x['id']==ID),None)
    if not work or work['contribution']!='authored':
        raise ValueError('Expected Pusey-authored Purchas letter')
    archive=harvest.get_metadata(ARCHIVE)
    meta=archive.get('metadata') or {}
    title=str(meta.get('title',''))
    year=str(meta.get('year','') or meta.get('date',''))
    creators=meta.get('creator',[])
    creators=' '.join(creators) if isinstance(creators,list) else str(creators)
    if 'purchas judgment' not in title.lower() or '1871' not in year:
        raise ValueError('Incorrect Purchas source or edition')
    if 'liddon' not in creators.lower() or 'pusey' not in creators.lower():
        raise ValueError('Mixed pamphlet metadata fails author check')
    fname=harvest.text_filename(archive)
    if not fname:raise ValueError('Plain text missing')
    url='https://archive.org/download/'+ARCHIVE+'/'+quote(fname,safe='/')
    req=harvest.request(url,stream=True);chunks=[];size=0
    for block in req.iter_content(128*1024):
        if not block:continue
        chunks.append(block);size+=len(block)
        if size>30*1024*1024:
            req.close();raise ValueError('OCR too large')
    req.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    pattern=r'(?im)^\s*letter\s*\n\s*FROM\s+THE\s+REV,\s+E\.\s+B,\s+PUSEY,\s+D,D\.\s+TO\s+REV,\s+DR,\s+LIDDON,'
    start_hits=list(re.finditer(pattern,raw))
    if len(start_hits)!=1:
        raise ValueError('Unique title-page heading of Pusey letter not found: '+str(len(start_hits)))
    start=start_hits[0].start()
    if not 85000<start<125000:
        raise ValueError('Unusual location of Pusey letter start: '+str(start))
    tail=raw[start:]
    if not re.search(r'My\s+Dearest\s+Liddon',tail[:900],re.I):
        raise ValueError('Expected Pusey salutation absent')
    if not re.search(r'Your\s+most\s+affectionate\s+friend,\s*E\.\s+B\.\s+PUSEY\.',tail,re.I):
        raise ValueError('Pusey author signature missing')
    if not re.search(r'P\.S\.\s*[—\-]\s*And\s+now,\s+when\s+I\s+have',tail,re.I):
        raise ValueError('Pusey postscript missing')
    endings=list(re.finditer(r'Monday\s+in\s+.{0,14}Week,\s*1871\.',tail[-6000:],re.I))
    if len(endings)!=1:
        raise ValueError('Postscript Easter Week 1871 ending ambiguous: '+str(len(endings)))
    end=start+len(tail)-6000+endings[0].end() if len(tail)>=6000 else start+endings[0].end()
    if not 130000<end<145000:
        raise ValueError('Unexpected end offset '+str(end))
    excerpt=raw[start:end].strip()
    if 'J.   OGDEN' in excerpt or re.search(r'printer[s]?\b',excerpt[-750:],re.I):
        raise ValueError('Publisher colophon leaked into Pusey letter')
    if not re.search(r'stand\s+still\s+and\s+see\s+the\s+salvation\s+of\s+God',re.sub(r'[^a-zA-Z ]',' ',excerpt[-2500:]),re.I):
        raise ValueError('Final passage of Pusey postscript missing')
    words=len(harvest.words(excerpt))
    if not 4000<words<8000:
        raise ValueError('Pusey letter length implausible '+str(words))
    content="Letter on the Purchas Judgment (1871)\n\n"+excerpt+'\n'
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(ID+'.txt')).write_text(content,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(content),encoding='utf8')
    harvest.write_record(work,{
      'status':'downloaded',
      'source':'Internet Archive OCR of mixed Liddon/Pusey pamphlet; ONLY Pusey letter',
      'identifier':ARCHIVE,'scan_url':'https://archive.org/details/'+ARCHIVE,
      'text_url':url,
      'source_title':title,'source_creator':'E. B. Pusey (letter); H. P. Liddon (other section excluded)',
      'source_date':'1871',
      'source_edition_year':1871,
      'downloaded_utc':datetime.now(timezone.utc).isoformat(),
      'original_sha256':hashlib.sha256(content.encode()).hexdigest(),
      'word_count':len(harvest.words(content)),
      'scope_verified':True,'content_scope':'full_original_work',
      'extraction_boundaries':{
         'printed_pages':'53–71',
         'start':'Letter from the Rev. E. B. Pusey, D.D., to Rev. Dr. Liddon; My dearest Liddon',
         'end':'Monday in Easter Week, 1871 (end of P.S.)',
         'original_ocr_start_char':start,'original_ocr_end_char':end,
         'excluded':'All of Liddon’s pp 1–52 and the publisher colophon'
      },
      'authorship_review_needed':False,
      'qc':'Owner bibliography specifically pp 53–71; signed Pusey letter and entire P.S. only'
    })
    reg=ROOT/'data/source_registry.csv'
    with reg.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x['id']==ID)
    row.update(verification_status='verified_pusey_letter_only',
        archive_id=ARCHIVE,scan_url='https://archive.org/details/'+ARCHIVE,
        ocr_url=url,ocr_filename=fname,ia_title=title,
        ia_creator='E. B. Pusey (letter); H. P. Liddon (excluded)',ia_year='1871',
        notes='Pusey letter plus Postscript, printed pp 53–71 of Liddon 1871 pamphlet only; excluded Liddon pp 1–52.')
    with reg.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED PURCHAS PUSEY LETTER AND POSTSCRIPT',words,'words',flush=True)

if __name__=='__main__':main()
