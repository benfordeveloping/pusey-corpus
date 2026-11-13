#!/usr/bin/env python3
"""Import Pusey's Hints for a First Confession as an independently indexed work.

This public-domain Anglican History HTML transcription prints the original
1851 work in its 1884 Penitence reprint. Exclude site navigation and the small
verse after Pusey's signature.
"""
from __future__ import annotations
import csv, hashlib, html, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest

WORK_ID='1851-hints-for-a-first-confession'
URL='https://anglicanhistory.org/pusey/pusey1.html'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf-8'))['works']
    work=next((w for w in works if w['id']==WORK_ID),None)
    if work is None or work.get('contribution')!='authored':
        raise RuntimeError('Expected separately catalogued Pusey-authored 1851 work')
    res=harvest.request(URL)
    res.encoding=res.apparent_encoding or res.encoding
    soup=BeautifulSoup(res.text,'html.parser')
    if 'Hints for a First Confession' not in soup.get_text(' ',strip=True):
        raise RuntimeError('Incorrect work title returned')
    text=html.unescape(soup.get_text('\n',strip=True))
    text=text.translate(str.maketrans({'\x91':'‘','\x92':'’','\x93':'“','\x94':'”','\x97':'—','\x96':'–'}))
    start=re.search(r'O\s+Lord,\s+we\s+beseech\s+Thee,\s+mercifully',text,re.I)
    end=re.search(r'\bE\.\s?B\.\s?P\.',text[start.end():] if start else '',re.I)
    if not start or not end:
        raise RuntimeError('Signed main text not found in page; fail closed')
    stop=start.end()+end.end()
    content='Hints for a First Confession\n\n'+text[start.start():stop]
    content=re.sub(r'\n{3,}','\n\n',content).strip()+'\n'
    words=len(harvest.words(content))
    if not 650<words<6500:
        raise RuntimeError('Unreasonable extracted word count: '+str(words))
    if not re.search(r'It is very desirable that the First Confession',content,re.I):
        raise RuntimeError('The substantive opening of the source is missing')
    if not content.strip().endswith('E.B.P.') and not re.search(r'E\.\s?B\.\s?P\.\s*$',content):
        raise RuntimeError('Excerpt does not end at author signature')
    if 'Lord, too late have I loved Thee' in content:
        raise RuntimeError('The following devotional verse was accidentally included')
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    harvest.RAW.joinpath(WORK_ID+'.txt').write_text(content,encoding='utf-8')
    harvest.CLEAN.joinpath(WORK_ID+'.txt').write_text(content,encoding='utf-8')
    harvest.write_record(work,{
        'status':'downloaded','source':'Project Canterbury, Anglican History public-domain transcription',
        'identifier':URL,'scan_url':URL,'text_url':URL,
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'source_title':'Hints for a First Confession','source_creator':'E. B. Pusey',
        'source_date':'1884 reprint of 1851 original','original_sha256':hashlib.sha256(content.encode()).hexdigest(),
        'word_count':words,'qc':'Standalone Pusey-authored text verified from opening prayer to E.B.P. signature',
        'content_scope':'full_original_work','extraction_boundaries':'Opening prayer to E.B.P. signature; subsequent verse excluded',
        'authorship_review_needed':False
    })
    reg=ROOT/'data/source_registry.csv'
    with reg.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    rec=next(x for x in rows if x['id']==WORK_ID)
    rec.update(verification_status='verified_transcription',scan_url=URL,ocr_url=URL,
               ia_title='Hints for a First Confession',ia_creator='E. B. Pusey',
               ia_year='1884',notes='First printed 1851; signed E.B.P.; text is a transcription of reprint in Penitence (London: Walter Smith, 1884), not newly generated OCR.')
    with reg.open('w',encoding='utf-8',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');wr.writeheader();wr.writerows(rows)
    harvest.csv_report(works)
    print('INDEXED Hints for a First Confession:',words,'Pusey words, first 1851 / source 1884',flush=True)
if __name__=='__main__':main()
