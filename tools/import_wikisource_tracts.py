#!/usr/bin/env python3
"""Import complete public-domain Wikisource transcriptions of Pusey's Tracts 18 and 66.

Source provenance is preserved. This does not claim to be Archive.org OCR.
Includes an explicit title/content check and never imports unrelated navigation.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest

SOURCES={
    'Tract 18: Thoughts on the Benefits of Fasting':'https://en.wikisource.org/wiki/Tracts_for_the_Times/Tract_18',
    'Tract 66: Supplement to Tract XVIII on Fasting':'https://en.wikisource.org/wiki/Tracts_for_the_Times/Tract_66',
}

def extract(url):
    r=harvest.request(url)
    soup=BeautifulSoup(r.text,'html.parser')
    content=soup.select_one('.mw-parser-output')
    if content is None:raise ValueError('Wikisource content container not found')
    for s in content.select('.mw-editsection, .noprint, .reference, style, script, nav, table, .catlinks, .printfooter, .wst-work-metadata'):
        s.decompose()
    chunks=[]
    for el in content.find_all(['h2','h3','p','li','blockquote']):
        if el.find_parent(['li','blockquote']) and el.name in ('p','li'):continue
        txt=re.sub(r'\s+',' ',el.get_text(' ',strip=True)).strip()
        if len(txt)>12 and txt not in chunks:
            chunks.append(txt)
    return '\n\n'.join(chunks).strip()+'\n'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    register=ROOT/'data/source_registry.csv'
    with register.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames; rows=list(reader)
    index={r['id']:r for r in rows}
    ok=0
    for work in works:
        url=SOURCES.get(work['title'])
        if not url:continue
        if (harvest.CLEAN/(work['id']+'.txt')).exists():
            print('SKIP already in corpus:',work['title'],flush=True);continue
        print('IMPORT',work['title'],url,flush=True)
        try:
            txt=extract(url)
            word_count=len(harvest.words(txt))
            if word_count<800:raise ValueError('Transcription too short: '+str(word_count))
            if len(re.findall('fasting',txt,re.I))<5:raise ValueError('Transcription fails expected topic check')
            harvest.RAW.mkdir(parents=True,exist_ok=True)
            harvest.CLEAN.mkdir(parents=True,exist_ok=True)
            (harvest.RAW/(work['id']+'.txt')).write_text(txt,encoding='utf-8')
            clean=harvest.clean_ocr(txt)
            (harvest.CLEAN/(work['id']+'.txt')).write_text(clean,encoding='utf-8')
            harvest.write_record(work,{
                'status':'downloaded','source':'Wikisource public-domain transcription',
                'identifier':url.rsplit('/',1)[-1], 'scan_url':url,
                'text_url':url,'downloaded_utc':datetime.now(timezone.utc).isoformat(),
                'source_title':work['title'],'source_creator':'E. B. Pusey',
                'original_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
                'word_count':len(harvest.words(clean)),
                'qc':'Full web transcription; source title verified; not OCR'
            })
            index[work['id']].update(
                verification_status='verified_transcription',
                scan_url=url,ocr_url=url,
                ia_title=work['title'],ia_creator='E. B. Pusey',
                notes='Exact Pusey tract imported from public-domain Wikisource text; not Internet Archive OCR.',
            )
            print('IMPORTED',word_count,'words',flush=True)
            ok+=1
        except Exception as exc:
            print('FAILED',type(exc).__name__,str(exc)[:200],flush=True)
    with register.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader();w.writerows(rows)
    harvest.csv_report(works)
    print('Imported',ok,'new public-domain tracts',flush=True)

if __name__=='__main__':
    main()
