#!/usr/bin/env python3
"""Audit competing scans before asking the owner to approve the right editions.

Unlike automatic OCR harvesting this audit NEVER promotes candidates to verified
or adds any unapproved book to the public search index.
"""
from __future__ import annotations
import csv, re, sys, time, json
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
TARGETS={
  "1828 Enquiry Part I": ["a605286400puseuoft", "historicalenquir0000ebpu"],
  "1830 Enquiry Part II": ["anhistoricalenq00sackgoog", "historicalenquir00puse"],
  "1839 enlarged baptism Tract 67": ["scripturalviews1840puse","scripturalviews1843puse"],
  "1853 Parochial Sermons Vol II": ["bwb_C0-AMM-630","a605396203puseuoft","parochialsermons02puse"],
  "1873 Parochial Sermons Vol III": ["parochialsermon04pusegoog","a605396203puseuoft"],
  "1860 Minor Prophets Vol I": ["bwb_S0-DRH-613","a547289200puseuoft","minorprophetswit1869puse"],
  "1860 Minor Prophets Vol II": ["minorprophetswi01pusegoog","bwb_S0-DRH-613"],
  "1865 Parochial Sermons various occasions": ["parochialsermon00pusegoog","a605400101puseuoft"],
}
FIELDS=['bibliography_entry','archive_id','scan_url','title','creator','publication_year','metadata_volume','publisher','pages','ocr_url','ocr_available','sample_words_read','sample_title_page','edition_clues','volume_clues','error']

def meta_val(v):
    if isinstance(v,list):return " | ".join(map(str,v))
    return str(v or '')

def probe(label,identifier):
    record=dict.fromkeys(FIELDS,'')
    record.update(bibliography_entry=label,archive_id=identifier,scan_url='https://archive.org/details/'+identifier)
    try:
        obj=harvest.get_metadata(identifier)
        md=obj.get('metadata') or {}
        for k,s in [('title','title'),('creator','creator'),('publication_year','year'),('metadata_volume','volume'),('publisher','publisher'),('pages','imagecount')]:
            record[k]=meta_val(md.get(s,''))
        fname=harvest.text_filename(obj)
        if not fname:record['error']='No plain-text file in metadata';return record
        url='https://archive.org/download/'+quote(identifier,safe='')+'/'+quote(fname,safe='/')
        record['ocr_url']=url;record['ocr_available']='listed'
        r=harvest.request(url,stream=True)
        b=bytearray()
        for chunk in r.iter_content(48*1024):
            b.extend(chunk)
            if len(b)>420000:break
        r.close()
        txt,_=harvest.decode_content(bytes(b))
        record['sample_words_read']=len(harvest.words(txt))
        # Keep only a brief auditable sample of title pages.
        record['sample_title_page']=re.sub(r'\s+',' ',txt[:8000]).strip()[:1100]
        pats=[r'(?i)second\s+edition',r'(?i)revised\s+edition',r'(?i)third\s+edition',r'(?i)fifth\s+edition',r'(?i)volume\s+[ivx0-9]+',r'(?i)vol[. ]+\s*[ivx0-9]+',r'(?i)part\s+(?:the\s+)?(?:second|first|[ivx0-9]+)']
        record['edition_clues']=' | '.join(dict.fromkeys(m.group(0) for p in pats for m in list(re.finditer(p,txt[:35000]))[:4]))[:650]
        books=['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']
        clues=[x+':'+str(len(list(re.finditer(r'\b'+x+r'\b',txt[:150000],re.I)))) for x in books]
        record['volume_clues']=' '.join(clues)
        record['ocr_available']='sampled'
    except Exception as exc:
        record['error']=type(exc).__name__+': '+str(exc)[:200]
    return record

def main():
    output=ROOT/'data'/'edition_audit.csv'
    output.parent.mkdir(exist_ok=True,parents=True)
    with output.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        count=0
        for label,ids in TARGETS.items():
            for ident in ids:
                rec=probe(label,ident)
                writer.writerow(rec);f.flush()
                count+=1
                print(str(count).zfill(2),label,ident,'volume=',rec['metadata_volume'],'published=',rec['publication_year'],'ocr=',rec['ocr_available'],'err=',rec['error'],flush=True)
                time.sleep(.3)
    print('Wrote',output,flush=True)

if __name__=='__main__':main()
