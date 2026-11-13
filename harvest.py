#!/usr/bin/env python3
"""Harvest public-domain OCR for bibliography items from Internet Archive.

Usage:
    python -m pip install -r requirements.txt
    python harvest.py --limit 8
    python harvest.py --all
    python harvest.py --work daniel

Safety: never guesses a source silently; ambiguous matches go to review report.
Original text, normalised text and provenance are saved separately.
"""
from __future__ import annotations
import argparse, csv, difflib, hashlib, json, random, re, sys, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RAW, CLEAN, RECORDS = (DATA / v for v in ('raw','clean','records'))
API = 'https://archive.org'
UA = 'PuseyCorpusResearch/0.2 (historical scholarship; sequential requests; info via project README)'
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': UA, 'Accept': '*/*'})
STOP = set('the a an of to in on for by and or is it his at from with under as part volume vol ii iii iv v into before after with our new ed edition letter works their some'.split())

def request(url, params=None, stream=False):
    """Retry transient errors; rate-limit requests to avoid burdening IA."""
    for attempt in range(4):
        try:
            r = SESSION.get(url, params=params, timeout=(20,110), stream=stream)
            if r.status_code in (429, 500, 502, 503, 504):
                r.close()
                raise requests.HTTPError(f'transient HTTP {r.status_code}')
            r.raise_for_status()
            return r
        except (requests.RequestException, OSError) as exc:
            if attempt == 3: raise
            nap = min(25, 2 ** (attempt + 1) + random.random())
            print(f'    retry after {type(exc).__name__}: {nap:.1f}s', flush=True)
            time.sleep(nap)

def words(s):
    return re.findall(r'[a-z][a-z0-9]+', unicodedata.normalize('NFKD',s.lower()))

def source_score(work, result):
    title = result.get('title','') or ''
    creator = result.get('creator','') or ''
    if isinstance(creator,list): creator = ' '.join(map(str,creator))
    target = set(words(work['search'])) - STOP
    found = set(words(title)) - STOP
    overlap = len(target & found) / max(1,len(target))
    precision = len(target & found) / max(1,len(found))
    compact = difflib.SequenceMatcher(None, ' '.join(words(work['search'])), ' '.join(words(title))).ratio()
    score = 0.59*overlap+0.20*precision+0.21*compact
    if 'pusey' in creator.lower(): score += .11
    else: score -= .13
    year_match = re.search(r'\b(18\d\d|19\d\d|20\d\d)\b',str(result.get('year','') or result.get('date','')))
    if year_match:
        delta = abs(int(year_match.group(1))-work['year'])
        if delta <= 4: score += .04
        if delta > 65: score -= .08  # a modern edition may still be legitimate but check
    if 'volume' in work['title'].lower() or 'vol.' in work['title'].lower():
        # Volume matching is too unreliable to infer automatically from IA titles.
        pass
    return round(score,3)

def search_candidates(work):
    target = [x for x in words(work['search']) if x not in STOP and len(x)>2]
    # The archive search endpoint is Lucene-based. Use a compact set of terms;
    # then a more permissive fallback. Scores are checked separately.
    qs = [
      'title:('+' AND '.join(target[:3])+') AND (creator:(pusey) OR title:(pusey))',
      'title:('+' AND '.join(target[:2])+') AND creator:(pusey)',
      'creator:(pusey) AND title:('+target[0]+')',
    ] if target else ['creator:(pusey)']
    docs = {}
    for q in qs:
        try:
            resp = request(API+'/advancedsearch.php',params={'q':q,'fl[]':['identifier','title','creator','year','date','mediatype'], 'rows':40, 'page':1,'output':'json'})
            data=resp.json()
            for d in data.get('response',{}).get('docs',[]):
                ident=d.get('identifier','')
                if ident: docs[ident]=d
        except (requests.RequestException,ValueError) as exc:
            print(f'    catalogue query failed: {str(exc)[:140]}')
        if len(docs)>25: break
        time.sleep(.35)
    ranked=sorted(docs.values(),key=lambda d: source_score(work,d),reverse=True)
    return [{'score':source_score(work,c),**c} for c in ranked[:12]]

def get_metadata(identifier):
    return request(API+'/metadata/'+quote(identifier,safe='')).json()

def text_filename(meta):
    files = meta.get('files') or []
    candidates=[]
    for f in files:
        name=f.get('name','')
        low=name.lower()
        if not low.endswith('.txt'): continue
        if any(t in low for t in ('_meta.','_abbyy.','_scandata.','_log.','_reviews.','_full_text_search.')): continue
        weight = (8 if low.endswith('_djvu.txt') else 7 if low.endswith('_text.txt') else 2)
        candidates.append((weight, int(f.get('size',0) or 0),name))
    candidates.sort(reverse=True)
    return candidates[0][2] if candidates else None

def decode_content(blob):
    for codec in ('utf-8-sig','utf-16','cp1252','latin-1'):
        try:
            txt=blob.decode(codec)
            if '\x00' in txt[:10000]: continue
            return txt,codec
        except UnicodeError: pass
    return blob.decode('utf-8','replace'),'utf-8-replace'

def assess_ocr(text):
    w=words(text)
    count=len(w)
    placeholders=len(re.findall(r'(?im)^\s*Image of page\s+\S+',text))
    actual_lines=sum(1 for l in text.splitlines() if len(l.strip())>35 and not l.lstrip().startswith('Image of page'))
    if count<180: return False,f'only {count} words'
    if placeholders>80 and actual_lines<placeholders//3: return False,f'{placeholders} image-page placeholders, only {actual_lines} content lines'
    if '<html' in text[:1000].lower():return False,'HTML returned where text was expected'
    if count>10000 and len(set(w))<150: return False,'implausibly repetitive text'
    return True, f'{count:,} words; {placeholders} page placeholders'

def clean_ocr(raw):
    s=unicodedata.normalize('NFC',raw).replace('\r\n','\n').replace('\r','\n')
    s=s.replace('\u00ad','').replace('\u200b','')
    # Join line-wrap hyphenation; keep an untouched original alongside this text.
    s=re.sub(r'(?<=[a-z])-[ \t]*\n[ \t]*(?=[a-z])','',s)
    s=re.sub(r'[ \t]+',' ',s)
    s=re.sub(r'(?m)^ +| +$','',s)
    s=re.sub(r'\n{4,}','\n\n\n',s)
    return s.strip()+'\n'

def write_record(work, extra):
    RECORDS.mkdir(parents=True,exist_ok=True)
    obj={k:v for k,v in work.items() if k not in ('search',)}
    obj.update(extra)
    p=RECORDS/(work['id']+'.json')
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf8')

def get_book(work, candidate=None):
    slug=work['id']
    if candidate:
        identifier=candidate['identifier']
        score=candidate.get('score')
    else:
        identifier=work['archive_id']
        score='verified-seed'
    print(f'    metadata for {identifier}',flush=True)
    meta=get_metadata(identifier)
    fname=text_filename(meta)
    if not fname: raise ValueError('No plain-text OCR file available for that scan')
    url=f'{API}/download/{quote(identifier,safe="")}/{quote(fname,safe="/")}'
    print(f'    downloading OCR {fname}',flush=True)
    r=request(url,stream=True)
    chunks=[]
    size=0
    for chunk in r.iter_content(chunk_size=128*1024):
        if not chunk: continue
        chunks.append(chunk);size+=len(chunk)
        if size>55*1024*1024:raise ValueError('OCR over 55 MB: stop to inspect manually')
    r.close()
    text,encoding=decode_content(b''.join(chunks))
    valid,description=assess_ocr(text)
    if not valid:raise ValueError('OCR rejected: '+description)
    print('    accepted: '+description,flush=True)
    RAW.mkdir(parents=True,exist_ok=True)
    CLEAN.mkdir(parents=True,exist_ok=True)
    (RAW/(slug+'.txt')).write_text(text,encoding='utf-8')
    cleaned=clean_ocr(text)
    (CLEAN/(slug+'.txt')).write_text(cleaned,encoding='utf-8')
    info={
        'status':'downloaded', 'source':'Internet Archive OCR',
        'identifier': identifier,'scan_url':f'{API}/details/{identifier}',
        'text_url':url,'downloaded_utc':datetime.now(timezone.utc).isoformat(),
        'source_title':meta.get('metadata',{}).get('title',''),
        'source_creator':meta.get('metadata',{}).get('creator',''),
        'source_date':meta.get('metadata',{}).get('date',''),
        'source_score':score,'encoding':encoding,
        'original_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),
        'word_count':len(words(cleaned)),
        'qc':description,
        'authorship_review_needed':work.get('contribution') in ('mixed','editorial','translation'),
        'volume_review_needed': ('Vol.' in work['title'] or 'Volume' in work['title'])
    }
    write_record(work,info)
    return info

def csv_report(manifest):
    DATA.mkdir(parents=True,exist_ok=True)
    output=DATA/'harvest_report.csv'
    with output.open('w',newline='',encoding='utf-8-sig') as f:
        cols=['year','title','category','contribution','status','word_count','scan_url','issue']
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        for work in manifest:
            record_file=RECORDS/(work['id']+'.json')
            rec=json.loads(record_file.read_text(encoding='utf8')) if record_file.exists() else {}
            writer.writerow({**{k:work.get(k,'') for k in cols},**{k:rec.get(k,work.get(k,'')) for k in cols}})
    print(f'\nReport: {output}')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    grp=ap.add_mutually_exclusive_group()
    grp.add_argument('--all',action='store_true',help='Attempt all unharvested works')
    grp.add_argument('--limit',type=int,default=5,help='Maximum works to attempt in this run (default 5)')
    ap.add_argument('--work',help='Only titles containing this text')
    ap.add_argument('--lookup',action='store_true',help='Discover candidate sources, without downloading OCR')
    ap.add_argument('--refresh',action='store_true',help='Redownload even if text exists')
    ap.add_argument('--retry-unresolved',action='store_true',help='Revisit works previously flagged for review or missing OCR')
    ap.add_argument('--threshold',type=float,default=.64,help='Minimum automatic matching score')
    ap.add_argument('--pause',type=float,default=1.2,help='Seconds to pause between works')
    ap.add_argument('--source-map',help='JSON object mapping work IDs to manually verified Internet Archive IDs')
    args=ap.parse_args()
    manifest=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    overrides=json.loads(Path(args.source_map).read_text(encoding='utf8')) if args.source_map else {}
    if args.work:manifest=[w for w in manifest if args.work.lower() in (w['id']+' '+w['title']).lower()]
    if not manifest:ap.error('No works matched --work')
    tried=success=0
    for work in manifest:
        slug=work['id']
        if not args.refresh and (CLEAN/(slug+'.txt')).exists():continue
        rp=RECORDS/(slug+'.json')
        if not args.retry_unresolved and not args.refresh and rp.exists():
            try:
                prior=json.loads(rp.read_text(encoding='utf8'))
                if prior.get('status') in ('needs_review','needs_source','error'):continue
            except (ValueError,OSError):pass
        if not args.all and tried>=args.limit:break
        tried+=1
        print(f'[{tried}] {work["year"]} — {work["title"]}',flush=True)
        try:
            if slug in overrides:
                work={**work,'archive_id':overrides[slug]}
            if args.lookup:
                candidates=search_candidates(work)
                print('    candidates:', [(c['identifier'],c['score'],str(c.get('title',''))[:55]) for c in candidates[:5]])
                write_record(work,{'status':'discovered','candidates':candidates[:8]})
            elif work.get('archive_id'):
                get_book(work);success+=1
            else:
                candidates=search_candidates(work)
                if not candidates:
                    write_record(work,{'status':'needs_source','issue':'No Internet Archive catalogue matches'})
                    print('    no candidates')
                else:
                    best=candidates[0]
                    # Require good title match AND a lead over the next candidate;
                    # otherwise fail closed so that a wrong book never enters corpus.
                    next_score=candidates[1]['score'] if len(candidates)>1 else 0
                    if best['score']>=args.threshold and (best['score']-next_score>=.07 or len(candidates)==1):
                        try: get_book(work,best);success+=1
                        except Exception as exc:
                            write_record(work,{'status':'needs_review','issue':str(exc),'candidates':candidates[:8]})
                            print('    needs review: '+str(exc)[:180])
                    else:
                        write_record(work,{'status':'needs_review','issue':'Ambiguous or weak title match; choose a source manually','candidates':candidates[:8]})
                        print(f'    needs review: best score {best["score"]}, second {next_score}')
        except Exception as exc:
            write_record(work,{'status':'error','issue':f'{type(exc).__name__}: {exc}'})
            print('    error: '+str(exc)[:180])
        time.sleep(max(0,args.pause))
    csv_report(json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works'])
    print(f'Attempted {tried} work(s); downloaded {success}. Previously downloaded works were skipped.')

if __name__=='__main__':main()