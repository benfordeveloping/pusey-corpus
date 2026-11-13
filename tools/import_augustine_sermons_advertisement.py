#!/usr/bin/env python3
"""Import only E. B. Pusey's 1844 Advertisement to Augustine NT Sermons.

Source: Library of Fathers XVI, 1844. Translator R.G. Macmullen's
translation is excluded entirely; do not import Augustine sermons.
"""
from __future__ import annotations
import csv,hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest
ROOT=Path(__file__).resolve().parent.parent
ID='1844-preface-to-sermons-on-selected-lessons-of-the-new-testam'
ARCHIVE='16ALibraryOfFathersOfTheHolyCatholicV16'

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((w for w in works if w['id']==ID),None)
    if not work or work['contribution']!='editorial':
        raise ValueError('Expected Pusey editorial preface only')
    meta=harvest.get_metadata(ARCHIVE);md=meta.get('metadata') or {}
    title=str(md.get('title',''))
    if not re.search(r'Augustine.*New Testament',title,re.I):
        raise ValueError('Incorrect source title: '+title)
    filename=harvest.text_filename(meta)
    if not filename:raise ValueError('No OCR source available')
    url='https://archive.org/download/'+ARCHIVE+'/'+quote(filename,safe='/')
    response=harvest.request(url,stream=True);chunks=[];size=0
    for chunk in response.iter_content(128*1024):
        if not chunk:continue
        chunks.append(chunk);size+=len(chunk)
        if size>40*1024*1024:
            response.close();raise ValueError('Too large')
    response.close()
    raw,encoding=harvest.decode_content(b''.join(chunks))
    head=raw[:16000]
    if 'MDCCCXLIV' not in head.upper():
        raise ValueError('1844 printing not confirmed from source title-page')
    begins=list(re.finditer(r'(?im)^\s*ADVERTISEMENT\.\s+The\s+Sermons\s+of\s+S\.\s+Augustine',head))
    if len(begins)!=1:raise ValueError('Pusey original Advertisement heading missing')
    signatures=list(re.finditer(r'E\.\s*B\.\s*P\.\s*Christ\s+Church,\s*Feast\s+of\s+S\.\s+Barnabas,\s*1844\.',head,re.I))
    if len(signatures)!=1:raise ValueError('Signed Feast of St Barnabas 1844 boundary missing')
    start=begins[0].start();end=signatures[0].end()
    if not 4000<start<6500 or not 9500<end<14500:
        raise ValueError('Unexpected frontmatter offsets '+str((start,end)))
    excerpt=raw[start:end].strip()
    words=len(harvest.words(excerpt))
    if not 750<words<2700:
        raise ValueError('Pusey preface word count outside reasonable range '+str(words))
    if not re.search(r'Editors\s+are\s+indebted\s+for\s+the\s+translation\s+to\s+the\s+Rev\.\s+R\.\s+G\.\s+Macmullen',excerpt,re.I):
        raise ValueError('Pusey preface end reference to translator absent')
    if re.search(r'\bSERMON\s+I\.\s*$',excerpt[-500:],re.I):
        raise ValueError('Augustine sermon leaked into excerpt')
    content="Preface to Augustine's Sermons on Selected Lessons of the New Testament\n\n"+excerpt+'\n'
    harvest.RAW.mkdir(exist_ok=True,parents=True)
    harvest.CLEAN.mkdir(exist_ok=True,parents=True)
    (harvest.RAW/(ID+'.txt')).write_text(content,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(content),encoding='utf8')
    harvest.write_record(work,{
      'status':'downloaded',
      'source':'Internet Archive original Library of Fathers vol XVI (1844), Pusey Advertisement only',
      'identifier':ARCHIVE,'scan_url':'https://archive.org/details/'+ARCHIVE,'text_url':url,
      'source_title':title,
      'source_creator':'E. B. Pusey (signed Advertisement); R. G. Macmullen (translations excluded)',
      'source_date':'1844',
      'source_edition_year':1844,
      'downloaded_utc':datetime.now(timezone.utc).isoformat(),
      'original_sha256':hashlib.sha256(content.encode()).hexdigest(),
      'word_count':len(harvest.words(content)),
      'scope_verified':True,'content_scope':'pusey_preface_or_introduction_only',
      'extraction_boundaries':{
          'start':'ADVERTISEMENT. The Sermons of S. Augustine...',
          'end':'E. B. P. Christ Church, Feast of S. Barnabas, 1844.',
          'raw_ocr_start_char':start,'raw_ocr_end_char':end,
          'other_authors_sermons_excluded':True
      },
      'authorship_review_needed':False,
      'qc':'Signed 1844 Pusey Advertisement; full Augustine sermon translations excluded'
    })
    path=ROOT/'data/source_registry.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    row=next(r for r in rows if r['id']==ID)
    row.update(verification_status='verified_pusey_preface_only',
      archive_id=ARCHIVE,scan_url='https://archive.org/details/'+ARCHIVE,
      ocr_url=url,ocr_filename=filename,ia_title=title,
      ia_creator='E. B. Pusey (preface)',ia_year='1844',
      notes='Only Pusey’s Advertisement signed Christ Church Feast of S. Barnabas 1844; vol XVI original printing. Translator Macmullen’s Augustine sermons not indexed.')
    with path.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED AUGUSTINE SERMONS PUSEY ADVERTISEMENT ONLY',words,'words',flush=True)

if __name__=='__main__':main()
