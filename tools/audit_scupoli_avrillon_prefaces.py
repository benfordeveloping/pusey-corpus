#!/usr/bin/env python3
"""Audit owner-supplied Pusey prefaces to Scupoli and Avrillon volumes.

Record title pages, dated signatures, OCR heading offsets and boundaries.
Does NOT index translations or approve either excerpt automatically.
"""
from __future__ import annotations
import json,re,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
SOURCES={
    'scupoli_spiritual_combat':'spiritualcombat04scupgoog',
    'avrillon_advent':'aguideforpassin00avrigoog',
}
PATTERNS={
    'preface_headings':r'(?im)^\s*(?:PREFACE|NOTICE\s+(?:BY\s+THE\s+EDITOR|OF\s+THE\s+EDITOR)|ADVERTI[ZS]EMENT)\s*[.\n]',
    'signatures':r'(?i)\bE\s*\.\s*B\s*\.\s*P\s*\.',
    'pusey_dates':r'(?i)Christ\s+Church.{0,130}(?:1844|1846|Quinquagesima|Trinity)',
    'scupoli_next_section':r'(?i)NOTICE\s+OF\s+F\s*\.\s*SCUPOLI',
    'avrillon_next_section':r'(?i)FIRST\s+SUNDAY\s+(?:IN|OF)\s+ADVENT|FIRST\s+DAY\s+OF\s+ADVENT|MEDITATION\s+FOR\s+THE\s+FIRST\s+SUNDAY',
    'year_mentions':r'\b(?:1844|1845|1846|1847|1848|1849)\b'
}
def around(txt,pattern,upto=200000,limit=15,context=450):
    out=[]
    for m in re.finditer(pattern,txt[:upto],re.I|re.M|re.S):
        out.append({'at':m.start(),'match':m.group(0)[:100],
                    'before':txt[max(0,m.start()-context):m.start()],
                    'after':txt[m.end():m.end()+context]})
        if len(out)>=limit:break
    return out
def main():
    result={}
    for key,ident in SOURCES.items():
        try:
            mdobj=harvest.get_metadata(ident)
            md=mdobj.get('metadata') or {}
            fname=harvest.text_filename(mdobj)
            if not fname:raise ValueError('Archive item has no plain OCR text')
            url='https://archive.org/download/'+quote(ident,safe='')+'/'+quote(fname,safe='/')
            req=harvest.request(url,stream=True)
            parts=[];total=0
            for part in req.iter_content(128*1024):
                if not part:continue
                total+=len(part)
                if total>40*1024*1024:
                    req.close();raise ValueError('OCR over 40MB')
                parts.append(part)
            req.close()
            txt,encoding=harvest.decode_content(b''.join(parts))
            entry={'identifier':ident,'ocr_url':url,'metadata':{k:md.get(k) for k in ('title','year','date','publisher','creator','imagecount','description')},
                   'bytes':total,'ocr_characters':len(txt),'ocr_words':len(harvest.words(txt)),
                   'first_text':txt[:5200],'encoding':encoding}
            for typ,pattern in PATTERNS.items():
                entry[typ]=around(txt,pattern,upto=220000,limit=26,context=360)
            result[key]=entry
            print('AUDIT',key,ident,'words',entry['ocr_words'],'date',md.get('date'),flush=True)
            for typ in ('preface_headings','signatures','pusey_dates','scupoli_next_section','avrillon_next_section'):
                print('  ',typ,[p['at'] for p in entry[typ]],flush=True)
        except Exception as exc:
            result[key]={'identifier':ident,'error':type(exc).__name__+': '+str(exc)}
            print('REJECT',key,result[key]['error'],flush=True)
    path=ROOT/'data/scupoli_avrillon_preface_audit.json'
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('Saved',path,flush=True)
if __name__=='__main__':main()
