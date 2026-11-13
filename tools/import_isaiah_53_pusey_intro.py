#!/usr/bin/env python3
"""Index only E. B. Pusey's introduction to Isaiah 53 Jewish interpreters.

Owner source: Archive.org fiftythirdchapte02neub, 1877 printing. The
introduction was signed Oxford, December 1876. Preface and translations
by Neubauer/Driver, plus following Brief Extracts, are strictly excluded.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import harvest

WORK_ID='1876-the-fifty-third-chapter-of-isaiah-according-to-the-jewis'
ARCHIVE_ID='fiftythirdchapte02neub'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf-8'))['works']
    work=next((w for w in works if w['id']==WORK_ID),None)
    if not work or work.get('contribution')!='mixed' or work.get('indexing_scope')!='pusey_authored_passages_only':
        raise ValueError('Isaiah introduction entry must be strictly Pusey-only')

    meta=harvest.get_metadata(ARCHIVE_ID)
    md=meta.get('metadata') or {}
    catalogue_title=str(md.get('title',''))
    if not re.search(r'fifty.third.*isaiah|isaiah.*jewish.*interpreters',catalogue_title,re.I):
        raise ValueError('Unexpected archive catalogue title '+catalogue_title[:160])
    date=str(md.get('year','') or md.get('date',''))
    if '1877' not in date:
        raise ValueError('Expected second volume printing date 1877, got '+date)
    fname=harvest.text_filename(meta)
    if not fname:raise ValueError('No OCR download listed')
    url='https://archive.org/download/'+quote(ARCHIVE_ID,safe='')+'/'+quote(fname,safe='/')
    req=harvest.request(url,stream=True)
    chunks=[];bytes_read=0
    for chunk in req.iter_content(128*1024):
        if not chunk:continue
        bytes_read+=len(chunk)
        if bytes_read>50*1024*1024:
            req.close()
            raise ValueError('Source OCR exceeds 50MB')
        chunks.append(chunk)
    req.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    # The OCR prints "INTEODUCTION" on the genuine title; this is the
    # full heading AFTER the Contents page, not its contents listing.
    beginning=re.search(r'(?im)^\s*INTEODUCTION\s*\n\s*TO\s+THE\s*\n\s*ENGLISH\s+TRANSLATION\s*\.',raw)
    if not beginning:
        # Guarded fallback if archive later improves that OCR heading.
        all_heads=list(re.finditer(r'(?im)^\s*INTRODUCTION\s*\n\s*TO\s+THE\s*\n\s*ENGLISH\s+TRANSLATION\s*\.',raw))
        if len(all_heads)!=1:raise ValueError('Could not locate unique start of original introduction')
        beginning=all_heads[0]
    if not 12000<beginning.start()<250000:
        raise ValueError('Unexpected introduction heading location: '+str(beginning.start()))
    tail=raw[beginning.end():]
    sign=re.search(r'(?im)^\s*E\.\s*B\.\s*PUSEY\.\s*\n\s*Oxford,\s*\n\s*December,\s*1876\.',tail)
    if not sign or sign.end()>260000:
        raise ValueError('Pusey signature + signed December 1876 date not found in expected range')
    finish=beginning.end()+sign.end()
    content='Introduction to the English Translation\n\n'+raw[beginning.end():finish].strip()+'\n'
    number_words=len(harvest.words(content))
    if not 12000<number_words<65000:
        raise ValueError('Implausible introduction word count '+str(number_words))
    if not re.search(r'The\s+late\s+pious\s+Dr\.\s+Macbride',content,re.I):
        raise ValueError('Pusey introduction opening text not present')
    if not re.search(r'E\.\s*B\.\s*PUSEY\.\s+Oxford,\s+December,\s*1876\.\s*$',content,re.I):
        raise ValueError('Extract did not terminate at the Pusey signature')
    if re.search(r'Brief\s+Extracts,\s+in\s+which\s+the\s+Jewish',content[-2800:],re.I):
        raise ValueError('Post-introduction anthology leaked into extract')
    cleaned=harvest.clean_ocr(content)
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(WORK_ID+'.txt')).write_text(content,encoding='utf-8')
    (harvest.CLEAN/(WORK_ID+'.txt')).write_text(cleaned,encoding='utf-8')
    harvest.write_record(work,{
        'status':'downloaded',
        'source':'Internet Archive OCR, E.B. Pusey Introduction only',
        'identifier':ARCHIVE_ID,
        'scan_url':'https://archive.org/details/'+ARCHIVE_ID,
        'text_url':url,
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'source_title':catalogue_title,
        'source_creator':'E. B. Pusey (introduction); S. R. Driver and A. Neubauer (surrounding translations, excluded)',
        'source_date':date,
        'source_edition_year':1877,
        'introduction_signed_year':1876,
        'word_count':len(harvest.words(cleaned)),
        'original_sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),
        'encoding':encoding,
        'scope_verified':True,
        'content_scope':'pusey_authored_passages_only',
        'authorship_review_needed':False,
        'extraction_boundaries':{
            'start':"INTEODUCTION TO THE ENGLISH TRANSLATION; The late pious Dr. Macbride...",
            'end':'E. B. PUSEY. Oxford, December, 1876.',
            'raw_ocr_start_char':beginning.start(),
            'raw_ocr_end_char':finish,
            'raw_ocr_total_characters':len(raw)
        },
        'qc':'Index only Pusey signed introduction; Neubauer preface, subsequent Brief Extracts, all Jewish interpreters translations excluded'
    })
    path=ROOT/'data/source_registry.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    row=next(r for r in rows if r['id']==WORK_ID)
    row.update(
        verification_status='verified_pusey_introduction_only',
        archive_id=ARCHIVE_ID,
        scan_url='https://archive.org/details/'+ARCHIVE_ID,
        ocr_url=url,
        ocr_filename=fname,
        ia_title=catalogue_title,
        ia_creator=str(md.get('creator','')),
        ia_year='1877',
        notes='Only Pusey’s Introduction to the English Translation signed Oxford, December 1876; printed 1877. OCR characters '+str(beginning.start())+'–'+str(finish)+'. No surrounding other-author preface or translations.'
    )
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED ISAIAH 53 PUSEY INTRODUCTION ONLY',number_words,'raw words',flush=True)
    print('Original printed 1877; signed December 1876; chars',beginning.start(),finish,flush=True)

if __name__=='__main__':main()
