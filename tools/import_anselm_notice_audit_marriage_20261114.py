#!/usr/bin/env python3
"""Extract Pusey's signed 1856 Anselm Historical Notice; audit marriage OCR alternative.

Fail closed: verify BOTH start and end boundaries, author signature and date,
and next heading. The Anselm devotional text must never enter corpus search.
"""
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
import harvest
from import_hampden_audit_anselm_20261114 import source, registry_update
ANSELM='1855-preface-to-meditations-and-prayers-of-st-anselm'
MARRIAGE='1849-marriage-with-a-deceased-wife-s-sister-prohibited-by-hol'

def save_json(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf8')

def import_anselm(works):
    w=next(x for x in works if x['id']==ANSELM)
    if w.get('indexing_scope')!='pusey_preface_or_introduction_only' or w.get('contribution')!='editorial':
        raise ValueError('Anselm Pusey-only scope not correctly protected')
    audit=json.loads((ROOT/'data/anselm_historical_notice_audit_20261114.json').read_text(encoding='utf8'))
    md,filename,url,raw,enc,sha,qc=source('meditationsandp00ansegoog')
    if sha!=audit['sha256']:raise ValueError('Anselm OCR changed since verified section-boundary audit')
    starts=[
        m for m in re.finditer(r'(?im)^[ \t]*HISTORICAL[ \t]+NOTICE\.[ \t]*$',raw)
        if re.search(r'The\s+Meditations\s+of\s+S\.\s+Anselm',raw[m.end():m.end()+210],re.I)
    ]
    if len(starts)!=1:raise ValueError('Expected one unique Historical Notice heading with Pusey opening: '+str(len(starts)))
    start=starts[0].start()
    signatures=list(re.finditer(
        r'E\.\s*B\.\s*P\.\s*CHRIST\s+CHURCH\.\s*September\s+Ember\s+Week,\s*1856\.',
        raw[start:start+95000],re.I))
    if len(signatures)!=1:raise ValueError('Expected one Pusey 1856 sign-off, found '+str(len(signatures)))
    end=start+signatures[0].end()
    excerpt=raw[start:end].strip()+'\n'
    after=raw[end:end+650]
    if not re.search(r'MEDITATION\s+I\s*\.',after,re.I):
        raise ValueError('Anselm Meditation I does not follow immediately after Pusey signature')
    if re.search(r'(?im)^\s*MEDITATION\s+I\s*\.',excerpt):
        raise ValueError('Anselm devotional chapter entered the excerpt')
    words=len(harvest.words(excerpt))
    if not 1700<words<9500 or not 2400<start<5000 or not 18000<end<30000:
        raise ValueError('Unexpected Pusey-only excerpt boundary or word count: '+repr((start,end,words)))
    if '1856' not in str(md.get('year','') or md.get('date','')):
        raise ValueError('Source edition year is not 1856')
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    (harvest.RAW/(ANSELM+'.txt')).write_text(excerpt,encoding='utf8')
    cleaned=harvest.clean_ocr(excerpt)
    (harvest.CLEAN/(ANSELM+'.txt')).write_text(cleaned,encoding='utf8')
    # Keep stable 1855-preface... ID to avoid breaking URLs, correct the
    # bibliographic title and date based on the signed contemporary source.
    w['year']=1856
    w['title']='Historical Notice to Meditations and Prayers of St Anselm'
    w['notes']='Pusey Historical Notice signed September Ember Week 1856; existing 1855-preface ID retained for link stability. Only Pusey’s introductory text is searchable, not Anselm’s meditations.'
    w['source_edition_year']=1856
    w['source_document_url']='https://archive.org/details/meditationsandp00ansegoog'
    w['indexing_scope']='pusey_preface_or_introduction_only'
    save_json(ROOT/'bibliography.json',{'works':works})
    harvest.write_record(w,{
        'status':'downloaded','source':'Owner-supplied 1856 Google Books / Internet Archive scan: Pusey signed Historical Notice ONLY',
        'identifier':'meditationsandp00ansegoog',
        'scan_url':'https://archive.org/details/meditationsandp00ansegoog',
        'text_url':url,
        'source_title':md.get('title'),
        'source_creator':'E. B. Pusey (Historical Notice); St Anselm (excluded main text)',
        'source_edition_year':1856,
        'original_bibliography_year':1855,
        'signed_date':'September Ember Week, 1856',
        'scope_verified':True,'authorship_review_needed':False,
        'content_scope':'pusey_preface_or_introduction_only',
        'extraction_boundaries':{
          'ocr_sha256':sha,
          'ocr_start_char':start,'ocr_end_char':end,
          'start_heading':'HISTORICAL NOTICE.',
          'opening':'The Meditations of S. Anselm were his own communings with God',
          'end_signature':'E. B. P. / CHRIST CHURCH. / September Ember Week, 1856.',
          'excluded_next_section':'MEDITATION I. — OF THE DIGNITY AND MISERY OF MANS CONDITION',
          'source_ocr_characters':len(raw)},
        'word_count':len(harvest.words(cleaned)),
        'original_sha256':hashlib.sha256(excerpt.encode('utf8')).hexdigest(),
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'qc':qc+'; Pusey only; both heading and exact dated signature checked; following Meditation I excluded; OCR proofreading pending'
    })
    registry_update(ANSELM,{
        'year':'1856','title':w['title'],
        'verification_status':'verified_pusey_preface_only',
        'archive_id':'meditationsandp00ansegoog',
        'scan_url':'https://archive.org/details/meditationsandp00ansegoog',
        'ocr_url':url,'ocr_filename':filename,
        'ia_title':str(md.get('title') or ''),
        'ia_creator':str(md.get('creator') or ''),
        'ia_year':'1856',
        'notes':'Signed Historical Notice ONLY, September Ember Week 1856; source chars '+str(start)+'-'+str(end)+'. Anselm MEDITATION I and all prayers excluded; legacy 1855 ID retained.'
    })
    ledgerpath=ROOT/'data/owner_source_ledger_20261113.json'
    ledger=json.loads(ledgerpath.read_text(encoding='utf8'))
    for row in ledger.get('entries',[]):
        if row.get('bibliography_id')==ANSELM and 'meditationsandp00ansegoog' in (row.get('user_supplied_url') or ''):
            row['ingestion_status']='verified_pusey_historical_notice_only'
            row['github_clean_path']='data/clean/'+ANSELM+'.txt'
            row['source_notes']='Signed September Ember Week 1856; the Historical Notice alone is extracted from OCR chars '+str(start)+'-'+str(end)+'. The book and its meditations/prayers excluded. Existing 1855 bibliography ID retained.'
    save_json(ledgerpath,ledger)
    print('IMPORTED ANSELM HISTORICAL NOTICE',words,'words; chars',start,end,flush=True)

def measure(text):
    words=harvest.words(text)
    return {
        'ocr_characters':len(text),'ocr_words':len(words),
        'replacement_characters':text.count('\ufffd'),
        'letters_to_characters':round(sum(c.isalpha() for c in text)/max(1,len(text)),4),
        'hyphenated_line_endings':len(re.findall(r'[a-z]-\s*\n',text)),
        'blank_only_line_count':len(re.findall(r'(?m)^\s*$',text)),
        'sample_beginning':text[:1600],
        'sample_middle':text[len(text)//2:len(text)//2+1600]
    }

def audit_marriage():
    existing_path=ROOT/'data/raw/'+MARRIAGE+'.txt'
    if not existing_path.exists():raise ValueError('Previously verified 1849 marriage OCR missing')
    ident='marriagewithade00pusegoog'
    md,filename,url,raw,enc,sha,qc=source(ident)
    title=str(md.get('title',''))
    if not re.search(r'marriage\s+with\s+a\s+deceased\s+wife',title,re.I):
        raise ValueError('Wrong marriage book: '+title)
    existing=existing_path.read_text(encoding='utf8')
    result={
       'bibliography_id':MARRIAGE,
       'status':'alternative_edition_ocr_compared; do not duplicate',
       'current_source_id':'b29349412',
       'current_source_provenance':'data/records/'+MARRIAGE+'.json',
       'owner_supplied_alternative_id':ident,'alternative_ocr_url':url,
       'alternative_metadata_title':title,
       'alternative_sha256':sha,
       'alternative_quality_check':qc,
       'current':measure(existing),
       'alternative':measure(raw),
       'conclusion':'Retain currently verified and indexed source unless a documented qualitative comparison warrants replacement; these are not two separate Pusey works.'
    }
    save_json(ROOT/'data/marriage_ocr_alternative_audit_20261114.json',result)
    print('MARRIAGE OCR ALTERNATIVE AUDITED: current',result['current']['ocr_words'],'alternate',result['alternative']['ocr_words'],flush=True)

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    import_anselm(works)
    audit_marriage()
    harvest.csv_report(works)
    print('Anselm Pusey-only notice imported; marriage alternative reviewed',flush=True)

if __name__=='__main__':main()
