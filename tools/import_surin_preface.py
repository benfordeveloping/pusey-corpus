#!/usr/bin/env python3
"""Import ONLY Pusey's full 1844-signed preface to Surin, printed in 1847.

Source PDF is a 33-page Project Canterbury transcription of Pusey's
preface itself; Surin's devotional book is NOT contained in this PDF.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from pathlib import Path
from datetime import datetime,timezone
import fitz
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1844-the-foundations-of-the-spiritual-life-surin-preface-and'
URL='https://anglicanhistory.org/pusey/surin.pdf'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((w for w in works if w['id']==ID),None)
    if work is None or work.get('contribution')!='translation' or work.get('indexing_scope')!='pusey_translator_introduction_only':
        raise ValueError('Not the Pusey translator-introduction-only entry')
    response=harvest.request(URL)
    content=response.content
    if not content.startswith(b'%PDF') or len(content)<60000:
        raise ValueError('Source is not a real complete PDF')
    doc=fitz.open(stream=content,filetype='pdf')
    if len(doc)!=33:raise ValueError('Expected 33-page independent Pusey preface; got '+str(len(doc)))
    title=doc[0].get_text()
    if 'SURIN' not in title.upper() or '1847' not in title or 'PUSEY' not in title.upper():
        raise ValueError('Preface title page is not the 1847 Pusey/Surin source')
    parts=[]
    for p in range(1,len(doc)):
        text=doc[p].get_text(sort=True)
        # Remove only the typeset editorial top/bottom headers and
        # printed page numbers. Preserve footnotes and Pusey's own prose.
        text=re.sub(r'(?i)Preface to Surin On the Spiritual Life, by E\.B\. Pusey \(1847\)','',text)
        text=re.sub(r'(?i)Project Canterbury AD 2003','',text)
        text=re.sub(r'(?m)^\s*\[\s*\d{1,2}\s*\]\s*$','',text)
        parts.append(text.strip())
    raw='\n\n'.join(parts)
    head=re.search(r'(?im)^\s*PREFACE\.\s*\n\s*THE\s+following\s+book\b',raw)
    if not head:raise ValueError('Original Pusey PREFACE heading and opening missing')
    sig=list(re.finditer(r'(?im)^\s*E\.\s*B\.\s*P\.\s*\n\s*Vigil\s+of\s+St\.\s*James,\s*1844\.',raw))
    if len(sig)!=1:raise ValueError('Exact signed closing date missing or ambiguous')
    extracted='Preface to The Foundations of the Spiritual Life (Surin)\n\n'+raw[head.start():sig[0].end()].strip()+'\n'
    words=len(harvest.words(extracted))
    if not 9000<words<27000:
        raise ValueError('Pusey preface word count implausible: '+str(words))
    if not re.search(r'^\s*PREFACE\.',extracted.split('\n\n',1)[1],re.I):
        raise ValueError('Excerpt did not start at preface')
    if not re.search(r'E\.\s*B\.\s*P\.\s+Vigil\s+of\s+St\.\s*James,\s*1844\.\s*$',extracted,re.I):
        raise ValueError('Excerpt does not end at 1844 signature')
    if re.search(r'CHAPTER\s+I\.\s+OF\s+THE\s+SPIRITUAL\s+LIFE',extracted,re.I):
        raise ValueError('Translated Surin chapters leaked into Pusey preface')
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(ID+'.txt')).write_text(extracted,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(extracted),encoding='utf8')
    harvest.write_record(work,{
        'status':'downloaded',
        'source':'Project Canterbury / Anglican History Pusey-only PDF transcription',
        'identifier':URL,'scan_url':URL,'text_url':URL,
        'source_title':'Preface to The Foundations of the Spiritual Life (Surin)',
        'source_creator':'E. B. Pusey (preface only); F. Surin (original book, excluded)',
        'source_date':'1847 printing; Pusey dated Vigil of St James 1844',
        'source_edition_year':1847,
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'original_sha256':hashlib.sha256(extracted.encode()).hexdigest(),
        'word_count':len(harvest.words(extracted)),
        'scope_verified':True,
        'content_scope':'pusey_translator_introduction_only',
        'authorship_review_needed':False,
        'extraction_boundaries':{
            'pdf_pages':[2,33],
            'start':'PREFACE. THE following book is founded upon one, long prized among us',
            'end':'E. B. P. Vigil of St. James, 1844.',
            'no_translated_surin_material':True
        },
        'qc':'All Pusey preface pages including editorial footnotes; signed end; translated devotional book excluded'
    })
    registry=ROOT/'data/source_registry.csv'
    with registry.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x['id']==ID)
    row.update(verification_status='verified_pusey_preface_only',
        scan_url=URL,ocr_url=URL,ia_title='Pusey preface to Surin',ia_creator='E. B. Pusey',ia_year='1847',
        notes='Pusey’s complete 1844-signed preface, independent 33-page Anglican History PDF, printed 1847; translated Surin book excluded.')
    with registry.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED SURIN PUSEY PREFACE ONLY',words,'words',flush=True)

if __name__=='__main__':
    main()
