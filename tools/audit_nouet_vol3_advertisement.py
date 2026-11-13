#!/usr/bin/env python3
"""Audit Nouet volume III for E. B. Pusey's signed Advertisement only.

No Nouet translation is ever imported by this script. Audit exact OCR boundaries
to support a separately reviewed extraction of Pusey's personal introduction.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ROOT=Path(__file__).resolve().parent.parent
ID='lifejesuschrist03chrigoog'
def matches(txt,pattern,maxnum=18,radius=1000):
    hits=[]
    for m in re.finditer(pattern,txt,re.I):
        hits.append(dict(offset=m.start(),match=m.group(0),context=txt[max(0,m.start()-radius):m.end()+radius]))
        if len(hits)>=maxnum:break
    return hits
def main():
    meta=harvest.get_metadata(ID)
    md=meta.get('metadata') or {}
    fname=harvest.text_filename(meta)
    if not fname:raise RuntimeError('No OCR plain text in archive')
    url='https://archive.org/download/'+ID+'/'+quote(fname,safe='/')
    reply=harvest.request(url,stream=True)
    chunks=[];total=0
    for chunk in reply.iter_content(chunk_size=128*1024):
        chunks.append(chunk);total+=len(chunk)
        if total>40*1024*1024:
            reply.close();raise RuntimeError('OCR file too large')
    reply.close()
    txt,enc=harvest.decode_content(b''.join(chunks))
    # Include raw line context for boundary confirmation; DO NOT remove line breaks.
    front=txt[:150000]
    results=dict(
        archive_id=ID,
        scan_url='https://archive.org/details/'+ID,
        ocr_url=url,
        metadata={k:md.get(k) for k in ('title','creator','date','year','volume','publisher','imagecount')},
        word_count=len(harvest.words(txt)),
        encoding=enc,
        start_text=front[:7200],
        headings=matches(front,r'\bADVERTISEMENT\b',12,1600),
        signoffs=matches(front,r'(?<![a-z])E\.?\s*B\.?\s*P\.?(?![a-z])',20,1600),
        preface_heads=matches(front,r'\b(?:PREFACE|INTRODUCTION|CONTENTS)\b',20,280),
        full_characters=len(txt)
    )
    out=ROOT/'data/nouet_vol3_advertisement_audit.json'
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Audit',ID,'words',results['word_count'],'chars',len(txt),'headings',len(results['headings']),'signatures',len(results['signoffs']))
    for key in ('headings','signoffs'):
        for x in results[key][:8]:
            print(key,'char',x['offset'],'match',repr(x['match']),'context:',re.sub(r'\s+',' ',x['context'][:500]))
    print('Saved',out)
if __name__=='__main__':main()
