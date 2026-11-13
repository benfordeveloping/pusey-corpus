#!/usr/bin/env python3
"""Import only Pusey's signed Scupoli and Advent Avrillon prefaces.

The entire translated books are NOT indexed. Opening headings, signatures,
editorial dates and physical edition years must ALL match. Fail closed.
Owner-approved source archives:
 - Scupoli, second printing 1849: Notice by the Editor (1846)
 - Avrillon, 1847 printing: Preface (signed 1844)
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest

SOURCES = [
    dict(work_id='1846-the-spiritual-combat-scupoli-preface-and-translation',
         archive_id='spiritualcombat04scupgoog',
         edition_year=1849, signed_year=1846,
         title_pattern=r'spiritual\s+combat',
         start_pattern=r'NOTICE\s+BY\s+THE\s+EDITOR\.\s*(?:<\s*J\s*)?The\s*[\u201c"\s]*Spiritual\s+Combat',
         end_pattern=r'E\.\s*B\.\s*P\.\s*Christ\s+Church,\s*Quinquagesima,\s*1846\.',
         excluded_following=r'NOTICE\s+OF\s+F\.\s*SCUPOLI',
         min_words=3000,max_words=10000,
         label='Scupoli: Notice by the Editor (1846; 1849 reprint)'),
    dict(work_id='1844-a-guide-for-passing-advent-holily-avrillon-preface-and-t',
         archive_id='aguideforpassin00avrigoog',
         edition_year=1847, signed_year=1844,
         title_pattern=r'guide\s+for\s+passing\s+advent\s+holily',
         start_pattern=r'PREFACE\.\s*The\s+Nativity\s+of\s+our\s+Lord',
         end_pattern=r'E\.\s*B\.\s*P\.\s*Christ\s+Church,\s*Twenty[\s\-\^]*fourth\s+Sunday\s+after\s+Trinity,\s*1844\.',
         excluded_following=r'ADDITIONAL\s+NOTES',
         min_words=9000,max_words=26000,
         label='Avrillon Advent: Pusey Preface (1844; 1847 reprint)'),
]

def get_ocr(ident):
    obj=harvest.get_metadata(ident)
    md=obj.get('metadata') or {}
    fname=harvest.text_filename(obj)
    if not fname:raise ValueError('No plain text OCR file listed')
    url='https://archive.org/download/'+quote(ident,safe='')+'/'+quote(fname,safe='/')
    response=harvest.request(url,stream=True)
    parts=[];size=0
    for part in response.iter_content(128*1024):
        if not part:continue
        size+=len(part)
        if size>50*1024*1024:
            response.close()
            raise ValueError('OCR download too large')
        parts.append(part)
    response.close()
    raw,encoding=harvest.decode_content(b''.join(parts))
    return md,fname,url,raw,encoding

def extract(work,spec,md,url,raw,encoding):
    archive_year=str(md.get('date','') or md.get('year',''))
    if str(spec['edition_year']) not in archive_year:
        raise ValueError('Wrong source edition: '+archive_year)
    title=str(md.get('title',''))
    if not re.search(spec['title_pattern'],title,re.I):
        raise ValueError('Archive title does not match target: '+title[:130])
    if spec['archive_id'].startswith('spiritualcombat'):
        # Scupoli's 1849 Roman-numeral imprint is badly OCR'd; the archive
        # metadata identifies 1849 and the title page identifies Second Edition.
        if not re.search(r'Second|Jbeconlr',raw[:9000],re.I):
            raise ValueError('Expected second edition title-page identification')
    elif str(spec['edition_year']) not in raw[:9000]:
        raise ValueError('Avrillon 1847 imprint not visible on OCR title page')
    start=re.search(spec['start_pattern'],raw[:11000],re.I|re.S)
    if not start:
        raise ValueError('Pusey preface heading and known opening were not found')
    # For Scupoli OCR the opening and ending lie within the first 30K
    # characters; for Avrillon the Preface occupies about 90K chars.
    finish=re.search(spec['end_pattern'],raw[start.end():160000],re.I|re.S)
    if not finish:
        raise ValueError('Author’s exact signature and signed date absent')
    end=start.end()+finish.end()
    titleline='Pusey: '+spec['label']
    content=titleline+'\n\n'+raw[start.start():end].strip()+'\n'
    original_word_count=len(harvest.words(content))
    if not spec['min_words']<original_word_count<spec['max_words']:
        raise ValueError('Preface OCR length unexpected: '+str(original_word_count))
    tail=raw[end:end+3500]
    if not re.search(spec['excluded_following'],tail,re.I|re.S):
        raise ValueError('The following non-Pusey section was not found at the expected boundary')
    if spec['archive_id'].startswith('spiritualcombat'):
        if len(re.findall(r'Scupoli|Spiritual\s+Combat|Sales',content,re.I))<10:
            raise ValueError('Source opening lacks the expected Scupoli context')
    else:
        if len(re.findall(r'Advent|Nativity|fast',content,re.I))<25:
            raise ValueError('Source opening lacks the expected Advent context')
    return content,original_word_count,start.start(),end

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf-8'))['works']
    by_id={w['id']:w for w in works}
    reg_path=ROOT/'data/source_registry.csv'
    with reg_path.open(encoding='utf-8-sig',newline='') as file:
        reader=csv.DictReader(file); cols=reader.fieldnames;rows=list(reader)
    reg={row['id']:row for row in rows}
    count=0
    for spec in SOURCES:
        work=by_id[spec['work_id']]
        if work.get('contribution')!='translation' or work.get('indexing_scope')!='pusey_translator_introduction_only':
            raise ValueError('Protected translation scope missing')
        ident=spec['archive_id']
        print('VERIFY',spec['label'],flush=True)
        md,fname,url,raw,encoding=get_ocr(ident)
        text,raw_words,start,end=extract(work,spec,md,url,raw,encoding)
        harvest.RAW.mkdir(parents=True,exist_ok=True)
        harvest.CLEAN.mkdir(parents=True,exist_ok=True)
        cleaned=harvest.clean_ocr(text)
        (harvest.RAW/(work['id']+'.txt')).write_text(text,encoding='utf-8')
        (harvest.CLEAN/(work['id']+'.txt')).write_text(cleaned,encoding='utf-8')
        harvest.write_record(work,{
            'status':'downloaded','source':'Internet Archive verified excerpt of Pusey’s preface ONLY',
            'identifier':ident,'scan_url':'https://archive.org/details/'+ident,'text_url':url,
            'downloaded_utc':datetime.now(timezone.utc).isoformat(),
            'source_title':str(md.get('title','')),
            'source_creator':'E. B. Pusey (introductory text); original devotional treatise by another author, excluded',
            'source_date':str(spec['edition_year'])+' printed; Pusey signed '+str(spec['signed_year']),
            'source_edition_year':spec['edition_year'],'preface_signed_year':spec['signed_year'],
            'word_count':len(harvest.words(cleaned)),
            'original_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),
            'ocr_encoding':encoding,'scope_verified':True,
            'content_scope':'pusey_translator_introduction_only',
            'authorship_review_needed':False,
            'extraction_boundaries':{'start':spec['start_pattern'],'end':spec['end_pattern'],
                                     'original_ocr_start_char':start,'original_ocr_end_char':end,
                                     'original_ocr_characters':len(raw),
                                     'excluded_following_section':spec['excluded_following']},
            'qc':'Pusey-only signed preface; edition and opening/ending verified; all translated text excluded'
        })
        row=reg[work['id']]
        row.update(
            verification_status='verified_pusey_preface_only',
            archive_id=ident,scan_url='https://archive.org/details/'+ident,
            ocr_url=url,ocr_filename=fname,
            ia_title=str(md.get('title','')),
            ia_creator=str(md.get('creator','')),
            ia_year=str(spec['edition_year']),
            notes='Verified Pusey introduction signed '+str(spec['signed_year'])+
                  ', source printing '+str(spec['edition_year'])+'; OCR chars '+str(start)+'–'+str(end)+'. Next section and translation excluded.'
        )
        print('APPROVED PUSEY PREFACE ONLY',spec['label'],raw_words,'words; chars',start,end,flush=True)
        count+=1
    with reg_path.open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=cols,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('VERIFIED PREFACES ADDED:',count,flush=True)

if __name__=='__main__':
    main()
