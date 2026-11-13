#!/usr/bin/env python3
"""Import ONLY Pusey's ten sermons (I and XI–XIX) from the Leeds collection.

Other sermons (II–X) and separately printed editorial preface are excluded.
Uses the editor-provided Project Canterbury text transcription with page
provenance for each sermon, not an unverified OCR scan of the mixed volume.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
ID='1845-a-course-of-sermons-on-solemn-subjects-chiefly-bearing-o'
NUMBERS=[1]+list(range(11,20))
ROMAN={1:'I',11:'XI',12:'XII',13:'XIII',14:'XIV',15:'XV',16:'XVI',17:'XVII',18:'XVIII',19:'XIX'}
INDEX='https://anglicanhistory.org/pusey/leeds/'

def one_sermon(n):
    url=INDEX+'sermon'+str(n)+'.html'
    result=harvest.request(url)
    result.encoding=result.apparent_encoding or result.encoding
    soup=BeautifulSoup(result.text,'html.parser')
    for item in soup.select('script, style, nav, .navigation, .navbar'):
        item.decompose()
    body=soup.body
    if not body:raise ValueError('HTML body missing: '+url)
    text=body.get_text('\n',strip=True)
    if not re.search(r'A Course of Sermons on Solemn Subjects',text,re.I):
        raise ValueError('Page is not the Leeds 1845 collection: '+url)
    expected=ROMAN[n]
    marker=re.search(r'(?im)^\s*SERMON\s+'+expected+r'\.\s*$',text)
    if not marker:raise ValueError('Sermon number '+expected+' heading not found: '+url)
    preface=text[:marker.start()]
    # A large majority of these pages carry "by E. B. Pusey" in the
    # HTML title and/or on the accompanying publisher line.
    author=(soup.title.get_text(' ',strip=True) if soup.title else '')+' '+preface[:1100]
    if not re.search(r'\bPusey\b',author,re.I):
        raise ValueError('Cannot confirm Pusey attribution: '+url)
    content=text[marker.start():]
    # The footer links back to Project Canterbury, following a decorative
    # divider. Do not admit the site footer into indexed prose.
    footer=re.search(r'(?s)\n\s*\*\s*\*\s*\*\s*\n\s*Project Canterbury\s*$',content,re.I)
    if footer:content=content[:footer.start()]
    else:
        last=content.rfind('Project Canterbury')
        if last>len(content)-350 and last>0:content=content[:last]
    content=content.strip()
    words=len(harvest.words(content))
    if not 1500<words<12000:
        raise ValueError('Unexpected sermon length '+str(words)+' for '+url)
    if re.search(r'(?im)^\s*SERMON\s+(?:II|III|IV|V|VI|VII|VIII|IX|X)\.\s*$',content):
        raise ValueError('Other-author sermon leaked into Pusey text: '+url)
    print('VERIFIED',expected,words,'words',url,flush=True)
    return content,{'number':n,'roman':expected,'source_url':url,'words':words,
                    'start':'SERMON '+expected+'.', 'end':'End of individual sermon page before Project Canterbury footer'}

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    work=next((x for x in works if x['id']==ID),None)
    if not work or work.get('contribution')!='mixed' or work.get('indexing_scope')!='pusey_authored_passages_only':
        raise ValueError('Solemn Subjects not configured to exclude other authors')
    if work.get('included_sermons')!=NUMBERS:
        raise ValueError('Owner-selected Pusey sermon list changed')
    texts=[];sources=[]
    for n in NUMBERS:
        txt,record=one_sermon(n)
        texts.append(txt);sources.append(record)
    combined='Sermons on Solemn Subjects (Pusey’s Contributions)\n\n'+'\n\n\n'.join(texts)+'\n'
    if len(harvest.words(combined))<22000:
        raise ValueError('Ten-sermon corpus implausibly short')
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    (harvest.RAW/(ID+'.txt')).write_text(combined,encoding='utf8')
    (harvest.CLEAN/(ID+'.txt')).write_text(harvest.clean_ocr(combined),encoding='utf8')
    harvest.write_record(work,{
        'status':'downloaded',
        'source':'Project Canterbury / Anglican History human-proofread web transcripts',
        'identifier':'https://anglicanhistory.org/pusey/leeds/',
        'scan_url':INDEX,
        'text_url':INDEX,
        'source_title':'A Course of Sermons on Solemn Subjects, chiefly bearing on Repentance and Amendment of Life',
        'source_creator':'E. B. Pusey (sermons I and XI–XIX ONLY; other contributors excluded)',
        'source_date':'1845',
        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'original_sha256':hashlib.sha256(combined.encode()).hexdigest(),
        'word_count':len(harvest.words(combined)),
        'scope_verified':True,
        'content_scope':'pusey_authored_passages_only',
        'extraction_boundaries':sources,
        'authorship_review_needed':False,
        'qc':'Only ten specifically owner-identified Pusey sermons; other nine excluded'
    })
    reg=ROOT/'data/source_registry.csv'
    with reg.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x['id']==ID)
    row.update(verification_status='verified_pusey_sermons_only',scan_url=INDEX,ocr_url=INDEX,
               ia_title=work['title'],ia_creator='E. B. Pusey, sermons I & XI–XIX',ia_year='1845',
               notes='User identified ten Pusey sermons (I and XI–XIX). Downloaded each individual 1845 human-proofread Anglican History sermon. Nine other authors’ sermons and site editorial material excluded.')
    with reg.open('w',encoding='utf8',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');wr.writeheader();wr.writerows(rows)
    harvest.csv_report(works)
    print('APPROVED 10 PUSEY-ONLY SERMONS;',len(harvest.words(combined)),'words',flush=True)
if __name__=='__main__':
    main()
