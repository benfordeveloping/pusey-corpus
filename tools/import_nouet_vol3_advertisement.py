#!/usr/bin/env python3
"""Add ONLY Pusey's E.B.P.-signed 1846 Advertisement to Nouet Vol. III.

The whole French original / English translation is deliberately excluded.
A wrong title page, wrong edition or missing signature FAILS CLOSED.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import harvest

ARCHIVE_ID='lifejesuschrist03chrigoog'
WORK_ID='1846-the-life-of-jesus-christ-in-glory-on-earth-nouet-vol-iii'
SCOPE='pusey_translator_introduction_only'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((x for x in works if x['id']==WORK_ID),None)
    if not work or work.get('contribution')!='translation':
        raise ValueError('Expected exact Nouet III bibliography entry, translation scope')
    scan=harvest.get_metadata(ARCHIVE_ID)
    md=scan.get('metadata') or {}
    if '1846' not in str(md.get('year','') or md.get('date','')):
        raise ValueError('Scan edition is not 1846')
    if not re.search(r'life.*jesus.*christ',str(md.get('title','')),re.I):
        raise ValueError('Archive catalogue does not identify Nouet work')
    fname=harvest.text_filename(scan)
    if not fname:
        raise ValueError('No OCR text listed in archive metadata')
    url='https://archive.org/download/'+ARCHIVE_ID+'/'+quote(fname,safe='/')
    reply=harvest.request(url,stream=True)
    chunks=[];n=0
    for chunk in reply.iter_content(128*1024):
        if not chunk: continue
        n+=len(chunk)
        if n>40*1024*1024:
            reply.close()
            raise ValueError('OCR unexpectedly oversized')
        chunks.append(chunk)
    reply.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    # The first "Advertisement" in this OCR is boilerplate Google text.
    # Only the true title-page heading is followed by "Many, who have learnt".
    start=re.search(r'(?im)^\s*ADVERTISEMENT\.\s+Many,\s+who\s+have\s+learnt',raw)
    if not start or not 3000<start.start()<12000:
        raise ValueError('Pusey Advertisement and expected opening could not be confirmed')
    signature=re.search(r'\bE\.\s*B\.\s*P\.',raw[start.end():start.start()+40000],re.I)
    if not signature:raise ValueError('No E.B.P. author signature following Advertisement')
    end=start.end()+signature.end()
    block=raw[start.start():end]
    words=len(harvest.words(block))
    if not 1700<words<8000:
        raise ValueError('Advertisement length implausible '+str(words))
    if len(re.findall(r'EASTER|LENT|RISEN',block,re.I))<12:
        raise ValueError('Introduction does not discuss Easter/Lent as expected')
    if re.search(r'\bLIFE OF CHRIST IN GLORY\b',block,re.I):
        raise ValueError('Translated Nouet main text appears inside extracted passage')
    if 'E. B. P.' not in block[-150:]:
        raise ValueError('Excerpt does not end at original E.B.P. signature')
    # Do not include the following translated devotional verse, footnote,
    # or any of Nouet's own meditations.
    cleaned=harvest.clean_ocr(block)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    (harvest.CLEAN/(WORK_ID+'.txt')).write_text(cleaned,encoding='utf8')
    (harvest.RAW/(WORK_ID+'.txt')).write_text(block,encoding='utf8')
    harvest.write_record(work,{
        'status':'downloaded','source':'Internet Archive OCR — Pusey advertisement excerpt only',
        'identifier':ARCHIVE_ID,'scan_url':'https://archive.org/details/'+ARCHIVE_ID,
        'text_url':url,'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'source_title':md.get('title',''),'source_date':'1846',
        'source_creator':'Jacques Nouet (main volume); E. B. Pusey (signed Advertisement only)',
        'original_sha256':hashlib.sha256(block.encode('utf8')).hexdigest(),
        'word_count':len(harvest.words(cleaned)),'raw_ocr_encoding':encoding,
        'scope_verified':True,'content_scope':SCOPE,
        'extraction_boundaries':{
            'start':'True Advertisement heading followed by Many, who have learnt ...',
            'end':'Final period of E. B. P. signature, before decorative verse/translated meditations',
            'raw_ocr_start_char':start.start(),'raw_ocr_end_char':end,
            'original_ocr_characters':len(raw)
        },
        'authorship_review_needed':False,
        'qc':'Pusey signed E.B.P.; exactly one original Advertisement extracted, 1846 scan; main translation excluded'
    })
    register=ROOT/'data/source_registry.csv'
    with register.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); cols=reader.fieldnames; rows=list(reader)
    row=next(x for x in rows if x['id']==WORK_ID)
    row.update({
        'verification_status':'verified_pusey_introduction_only',
        'archive_id':ARCHIVE_ID,
        'scan_url':'https://archive.org/details/'+ARCHIVE_ID,
        'ocr_url':url,'ocr_filename':fname,
        'ia_title':str(md.get('title','')),
        'ia_creator':str(md.get('creator','')),
        'ia_year':'1846',
        'notes':'Only Pusey’s Advertisement signed E.B.P.; raw OCR characters '+str(start.start())+'-'+str(end)+'. Main Nouet translation excluded; Easter 1846.'
    })
    with register.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED PUSEY SIGNED ADVERTISEMENT ONLY',WORK_ID,words,'words. Raw OCR chars',start.start(),end,flush=True)

if __name__=='__main__':
    main()
