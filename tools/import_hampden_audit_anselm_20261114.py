#!/usr/bin/env python3
"""Import owner's Hampden OCR; audit Anselm's embedded Historical Notice only.

The whole Anselm book is never indexed. A separate reviewed boundary extraction
is required before the Historical Notice can enter the Pusey-only search.
"""
import csv, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest
H='1836-dr-hampden-s-theological-statements-and-the-thirty-nine'
A='1855-preface-to-meditations-and-prayers-of-st-anselm'

def source(ident):
    metadata=harvest.get_metadata(ident)
    filename=harvest.text_filename(metadata)
    if not filename: raise ValueError("No listed OCR")
    url='https://archive.org/download/'+quote(ident,safe='')+'/'+quote(filename,safe='/')
    r=harvest.request(url,stream=True)
    chunks=[];size=0
    try:
        for part in r.iter_content(131072):
            if not part:continue
            chunks.append(part);size+=len(part)
            if size>45*1024*1024:raise ValueError("OCR too large")
    finally:r.close()
    blob=b''.join(chunks)
    txt,enc=harvest.decode_content(blob)
    ok,qc=harvest.assess_ocr(txt)
    if not ok:raise ValueError("Invalid OCR: "+qc)
    return metadata['metadata'],filename,url,txt,enc,hashlib.sha256(blob).hexdigest(),qc

def registry_update(id,fields):
    file=ROOT/'data/source_registry.csv'
    with file.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);header=reader.fieldnames;rows=list(reader)
    found=False
    for row in rows:
        if row['id']==id:
            row.update(fields);found=True
    if not found:raise ValueError("Missing registry ID: "+id)
    with file.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=header,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)

def do_hampden(work):
    ident='a604992800puseuoft'
    dest=harvest.CLEAN/(H+'.txt')
    if dest.exists():
        print('Hampden text already present; not overwriting',flush=True)
        return
    md,filename,url,raw,enc,sha,qc=source(ident)
    title=str(md.get('title',''))
    if not re.search('hampden',title,re.I) or not re.search('statement|articles',title,re.I):
        raise ValueError('Hampden metadata mismatch: '+title)
    if not re.search(r'HAMPDEN',raw[:40000],re.I) or not re.search(r'THIRTY[\s-]*NINE|XXXIX',raw[:40000],re.I):
        raise ValueError('Hampden pamphlet title absent from OCR opening')
    words=len(harvest.words(raw))
    if not 3500<words<125000:raise ValueError('Implausible Hampden pamphlet length: '+str(words))
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    (harvest.RAW/(H+'.txt')).write_text(raw,encoding='utf8')
    dest.write_text(harvest.clean_ocr(raw),encoding='utf8')
    harvest.write_record(work,{
        'status':'downloaded','source':'Owner-supplied Internet Archive OCR',
        'identifier':ident,'scan_url':'https://archive.org/details/'+ident,
        'text_url':url,'source_title':title,'source_creator':md.get('creator'),
        'source_date':md.get('year') or md.get('date'),
        'word_count':words,'encoding':enc,'original_sha256':sha,
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'qc':qc+'; original pamphlet contains quoted propositions from Hampden',
        'authorship_review_needed':False,'volume_review_needed':False
    })
    registry_update(H,{
        'verification_status':'verified_ocr','archive_id':ident,
        'scan_url':'https://archive.org/details/'+ident,
        'ocr_url':url,'ocr_filename':filename,'ia_title':title,
        'ia_creator':str(md.get('creator') or ''),
        'ia_year':str(md.get('year') or md.get('date') or ''),
        'notes':'Owner 2026-11-14 verified original comparative pamphlet including Hampden quotations; '+str(words)+' OCR words; proofreading pending.'
    })
    print('IMPORTED HAMPDEN',words,'words',flush=True)

def hits(raw,pattern,max_hits=24):
    out=[]
    for m in re.finditer(pattern,raw,re.I|re.M):
        at=m.start()
        out.append({'offset':at,'match':m.group(0)[:100],
                    'before':raw[max(at-350,0):at],
                    'after':raw[m.end():m.end()+1000]})
        if len(out)>=max_hits:break
    return out

def do_anselm(work):
    if work.get('indexing_scope')!='pusey_preface_or_introduction_only':
        raise ValueError('Pusey-only Anselm scope must be enforced')
    ident='meditationsandp00ansegoog'
    md,filename,url,raw,enc,sha,qc=source(ident)
    title=str(md.get('title',''))
    if not re.search('anselm|meditations',title,re.I):
        raise ValueError('Wrong Anselm volume metadata: '+title)
    audit={
        'bibliography_id':A,'archive_id':ident,'ocr_url':url,
        'ocr_filename':filename,'source_title':title,'source_creator':md.get('creator'),
        'source_year':md.get('year') or md.get('date'),
        'whole_volume_words_not_to_index':len(harvest.words(raw)),
        'sha256':sha,'encoding':enc,'quality':qc,'first_12000_chars':raw[:12000],
        'historical_notice_headings':hits(raw[:220000],r'(?m)^\s*(?:AN\s+)?HISTORICAL\s+NOTICE\b[^\n]{0,80}'),
        'historical_notice_all':hits(raw[:220000],r'HISTORICAL\s+NOTICE'),
        'meditation_headings':hits(raw[:260000],r'(?m)^\s*(?:THE\s+)?MEDITATIONS?\s+(?:I|II|1|2|AND\s+PRAYERS)\b[^\n]{0,75}'),
        'prayers_headings':hits(raw[:260000],r'(?m)^\s*(?:THE\s+)?PRAYERS?\s+(?:TO|OF|I|1)\b[^\n]{0,75}'),
        'pusey_signatures':hits(raw[:260000],r'E\.\s*B\.\s*P\.'),
        'status':'AUDIT ONLY: exclude entire Anselm work until Pusey Historical Notice boundaries verified'
    }
    (ROOT/'data/anselm_historical_notice_audit_20261114.json').write_text(
        json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    registry_update(A,{
        'verification_status':'confirmed_scan_excerpt_pending',
        'archive_id':ident,'scan_url':'https://archive.org/details/'+ident,
        'ocr_url':url,'ocr_filename':filename,'ia_title':title,
        'ia_creator':str(md.get('creator') or ''),
        'ia_year':str(md.get('year') or md.get('date') or ''),
        'notes':'Owner confirmed Anselm book OCR. Extract ONLY Pusey Historical Notice after reviewing data/anselm_historical_notice_audit_20261114.json. Do not index Anselm prayers or devotional book.'
    })
    print('ANSELM OCR INSPECTED; ONLY AUDIT SAVED',audit['whole_volume_words_not_to_index'],flush=True)

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    by_id={w['id']:w for w in works}
    errors=[]
    for label,fn,id in [('Hampden',do_hampden,H),('Anselm',do_anselm,A)]:
        try:fn(by_id[id])
        except Exception as exc:
            errors.append(label+': '+type(exc).__name__+' '+str(exc))
            print('FAILED',errors[-1],flush=True)
    harvest.csv_report(works)
    if errors:print('REVIEW NEEDED:',errors,flush=True)
    else:print('Owner source check complete: Hampden imported, Anselm boundaries audited',flush=True)

if __name__=='__main__':main()
