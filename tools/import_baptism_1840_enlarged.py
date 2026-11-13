#!/usr/bin/env python3
"""Index the verified enlarged SECOND English edition of Pusey's Tract 67.

Actual scan: New York, Charles Henry, 1840. The American editor attests
in print that it reproduces the second English edition, revised/enlarged
by Pusey. Exclude unrelated opening Tracts-for-the-Times advertisement.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from pathlib import Path
from urllib.parse import quote
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1839-scriptural-views-of-holy-baptism-second-edition-enlarged'
ARCHIVE='scripturalviews1840puse'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((w for w in works if w['id']==ID),None)
    if not work or work.get('contribution')!='authored' or work.get('source_edition_year')!=1840:
        raise ValueError('Expected Pusey-authored enlarged-tract bibliography entry with distinct 1840 printing')
    meta=harvest.get_metadata(ARCHIVE)
    md=meta.get('metadata') or {}
    title=str(md.get('title',''));date=str(md.get('year','') or md.get('date',''))
    publisher=str(md.get('publisher',''));creator=md.get('creator','')
    creator=' '.join(map(str,creator)) if isinstance(creator,list) else str(creator)
    if '1840' not in date or 'new york' not in publisher.lower() or 'charles henry' not in publisher.lower():
        raise ValueError('Not verified 1840 New York Charles Henry imprint')
    if 'pusey' not in creator.lower() or not re.search(r'scriptural views.*baptism',title,re.I):
        raise ValueError('Unexpected title/author metadata')
    fname=harvest.text_filename(meta)
    if not fname:raise ValueError('OCR not listed')
    url='https://archive.org/download/'+quote(ARCHIVE,safe='')+'/'+quote(fname,safe='/')
    r=harvest.request(url,stream=True)
    fragments=[];count=0
    for block in r.iter_content(128*1024):
        if not block:continue
        fragments.append(block);count+=len(block)
        if count>30*1024*1024:
            r.close();raise ValueError('OCR implausibly large')
    r.close()
    raw,encoding=harvest.decode_content(b''.join(fragments))
    front=re.sub(r'\s+',' ',raw[:50000])
    if not re.search(r'The Treatise on Baptism with which this volume begins, is printed\s+from the second English edition, revised and enlarged by the Author',front,re.I):
        raise ValueError('American editor second-English-edition certification absent')
    if not re.search(r'NEW YORK\s*:\s*CHARLES\s+HENRY',front,re.I) or '1840' not in front[:5000]:
        raise ValueError('Physical 1840 title page is not confirmed')
    starts=list(re.finditer(r'TRACTS\s+FOR\s+THE\s+TIMES,\s*[^\w]{0,6}\s*No\.\s*67,\s*\(?Ad\s+Clerum',raw[:80000],re.I))
    if len(starts)!=1:
        raise ValueError('Cannot identify unique start of enlarged No. 67; matches: '+str(len(starts)))
    start=starts[0].start()
    body=raw[start:]
    if not re.search(r'SCRIPTURAL\s+VIEWS\s+OF\s+HOLY\s+BAPTISM',body[:2500],re.I):
        raise ValueError('Pusey tract 67 heading absent at extracted start')
    all_words=len(harvest.words(body))
    if not 125000<all_words<220000:
        raise ValueError('Enlarged text word count implausible: '+str(all_words))
    # This is one source edition of Pusey's authored tract. Retain his
    # notes and appended theological apparatus, but remove publisher
    # advertising if separated after a final explicit THE END marker.
    terminal=list(re.finditer(r'(?im)^\s*THE\s+END\.?\s*$',body))
    if terminal and terminal[-1].start()>len(body)*.70:
        following=body[terminal[-1].end():]
        if re.search(r'\b(?:CATALOGUE|PUBLISHER|PUBLISHED BY|WORKS RECENTLY)\b',following,re.I):
            body=body[:terminal[-1].end()]
    # Publisher's separate prefatory advertisement is BEFORE start.
    if 'In completing the second volume of a publication' in body[:3000]:
        raise ValueError('Non-Pusey advertisement was included')
    cleaned=harvest.clean_ocr('Scriptural Views of Holy Baptism — Second Edition Enlarged (American printing 1840)\n\n'+body)
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(ID+'.txt')).write_text(body,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(cleaned,encoding='utf8')
    harvest.write_record(work,{
        'status':'downloaded',
        'source':'Internet Archive OCR; US reproduction of second enlarged UK Tract 67',
        'identifier':ARCHIVE,'scan_url':'https://archive.org/details/'+ARCHIVE,
        'text_url':url,'source_title':title,'source_creator':creator,
        'source_date':'1840 (New York, Charles Henry); second enlarged English edition originally 1839',
        'source_edition_year':1840,
        'original_first_enlarged_edition_year':1839,
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'original_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'encoding':encoding,'word_count':len(harvest.words(cleaned)),
        'content_scope':'full_original_work',
        'authorship_review_needed':False,
        'extraction_boundaries':{
            'start':"TRACTS FOR THE TIMES, No. 67, (Ad Clerum), after American Editor's note",
            'ocr_start_char':start,
            'ocr_end_char':start+len(body),
            'original_chars':len(raw),
            'excluded':'Introductory advertisement from the broader Tracts series, not Pusey',
            'included':"Pusey's revised/enlarged tract and original endnotes"
        },
        'qc':'Second edition identification from American editor’s printed note; NY 1840 title page verified; first 1836 Tracts 67–69 stored separately'
    })
    reg=ROOT/'data/source_registry.csv'
    with reg.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x['id']==ID)
    row.update(verification_status='verified_ocr',
               archive_id=ARCHIVE,scan_url='https://archive.org/details/'+ARCHIVE,
               ocr_url=url,ocr_filename=fname,ia_title=title,ia_creator=creator,ia_year='1840',
               notes='Owner-approved 1840 New York Charles Henry scan reproduces enlarged second English edition (1839) of Tract 67. American editor certifies revised and enlarged; prefatory series advertisement excluded.')
    with reg.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED ENLARGED BAPTISM TRACT 67',all_words,'words, 1840 American printing',flush=True)

if __name__=='__main__':
    main()
