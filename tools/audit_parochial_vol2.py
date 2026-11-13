#!/usr/bin/env python3
"""Inspect the candidate Pusey Parochial Sermons II scan before indexing.

Records title page / table of contents evidence; does NOT ingest OCR into the
search index until this audit has been interpreted.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
from urllib.parse import quote
ARCHIVE_ID='parochialsermons02puse'
ROOT=Path(__file__).resolve().parent.parent
def nearby(text,needle,size=200,limit=5):
    return [re.sub(r'\s+',' ',text[max(0,m.start()-size):m.end()+size])[:2*size+len(needle)]
            for m in list(re.finditer(needle,text,re.I))[:limit]]
def main():
    obj=harvest.get_metadata(ARCHIVE_ID)
    md=obj.get('metadata',{})
    filename=harvest.text_filename(obj)
    if not filename:raise ValueError('No OCR file')
    url='https://archive.org/download/'+ARCHIVE_ID+'/'+quote(filename,safe='/')
    response=harvest.request(url,stream=True)
    data=bytearray()
    for chunk in response.iter_content(128*1024):
        data.extend(chunk)
        if len(data)>8*1024*1024:raise ValueError('OCR too long for audit')
    response.close()
    raw,encoding=harvest.decode_content(bytes(data))
    normalized=re.sub(r'\s+',' ',raw)
    front=normalized[:38000]
    data={
        'archive_id':ARCHIVE_ID,
        'scan_url':'https://archive.org/details/'+ARCHIVE_ID,
        'ocr_url':url,
        'source_metadata':{k:md.get(k) for k in ('title','year','date','volume','publisher','creator','imagecount','notes')},
        'ocr_word_count':len(harvest.words(raw)),
        'opening_text':front[:12000],
        'volume_markers':nearby(raw,r'\bVOL(?:UME)?[\.\s]*II\b',250,8),
        'wrong_volume_markers':nearby(raw,r'\bVOL(?:UME)?[\.\s]*(?:I|III)\b',120,8),
        'year_1883':nearby(raw,r'\b1883\b',180,8),
        'year_1853':nearby(raw,r'\b1853\b',180,8),
        'year_1868':nearby(raw,r'\b1868\b',180,8),
        'contents_heading':nearby(raw,r'\bCONTENTS\b',250,3),
        'sermon_victory_besetting':nearby(raw,r'VICTORY\s+OVER\s+THE\s+BESETTING',180,6),
        'sermon_recreation_penitent':nearby(raw,r'RE[\-\s]?CREATION\s+OF\s+THE\s+PENITENT',180,6),
        'sermon_loving_faith':nearby(raw,r'VICTORY\s+THROUGH\s+LOVING\s+FAITH',180,6),
        'sermon_circumcision':nearby(raw,r'NEITHER\s+CIRCUMCISION',180,6),
        'encoding':encoding
    }
    path=ROOT/'data/parochial_vol2_source_audit.json'
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Archive catalog volume: ',md.get('volume'),'OCR words',data['ocr_word_count'])
    for k in ('volume_markers','year_1883','year_1853','year_1868','sermon_victory_besetting','sermon_recreation_penitent','sermon_loving_faith','sermon_circumcision'):
        print(k, len(data[k]),json.dumps(data[k][:1],ensure_ascii=False)[:460])
    print('Audit saved:',path)
if __name__=='__main__':main()
