#!/usr/bin/env python3
"""Build an auditable one-to-one source register for Pusey's 74 bibliography items.

Runs on GitHub Actions where Internet Archive is reachable. No candidate is silently
accepted as a correct edition. All entries keep explicit verification status.
"""
from __future__ import annotations
import argparse, csv, json, re, sys, time
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest

DATA=ROOT/'data'
REGISTER=DATA/'source_registry.csv'
CANDIDATES=DATA/'source_candidates.csv'
COLUMNS=['id','year','title','category','contribution','verification_status','archive_id','scan_url','ocr_url','ocr_filename','ia_title','ia_creator','ia_year','candidate_archive_id','candidate_score','candidate_ocr_url','notes']
CAN_COLUMNS=['id','year','title','candidate_rank','score','archive_id','scan_url','ocr_url','ocr_filename','ia_title','ia_creator','ia_year','metadata_status']


def rows(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def write_rows(path,fields,items):
    path.parent.mkdir(exist_ok=True,parents=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8',newline='') as f:
        out=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        out.writeheader();out.writerows(items)
    temp.replace(path)


def normalized(year):
    m=re.search(r'\b(?:17|18|19|20)\d{2}\b',str(year))
    return m.group(0) if m else ''


def source_info(identifier):
    meta=harvest.get_metadata(identifier)
    b=meta.get('metadata') or {}
    name=harvest.text_filename(meta)
    return dict(
        archive_id=identifier,scan_url='https://archive.org/details/'+quote(identifier,safe=''),
        ocr_filename=name or '',
        ocr_url=('https://archive.org/download/'+quote(identifier,safe='')+'/'+quote(name,safe='/')) if name else '',
        ia_title=str(b.get('title','')),
        ia_creator=str(b.get('creator','')),
        ia_year=normalized(b.get('year','') or b.get('date','')),
    )


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--limit',type=int,default=74,help='Number of catalogue entries to discover per run')
    ap.add_argument('--start',type=int,default=0,help='Zero-based start index, for chunked recovery')
    ap.add_argument('--pause',type=float,default=0.25,help='Seconds between entries')
    ap.add_argument('--max-candidates',type=int,default=4)
    ap.add_argument('--refresh',action='store_true')
    args=ap.parse_args()
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf-8'))['works']
    if len(works)!=74:raise SystemExit('Bibliography changed size: review the register before continuing')
    previous={r['id']:r for r in rows(REGISTER)}
    previous_candidates=[r for r in rows(CANDIDATES)]
    selected=works[args.start:args.start+args.limit]
    for i,work in enumerate(selected,args.start+1):
        ident=work['id']; prior=previous.get(ident,{})
        if not args.refresh and prior.get('verification_status') in ('verified_ocr','confirmed_scan_ocr_pending','candidate_found','no_candidate','no_ocr_candidate','error') and prior.get('candidate_archive_id'):
            print(f'{i:02d}/74 SKIP {work["title"]}',flush=True)
            continue
        print(f'{i:02d}/74 SEARCH {work["title"]}',flush=True)
        current={key:prior.get(key,'') for key in COLUMNS}
        current.update({k:work[k] for k in ('id','year','title','category','contribution')})
        current.setdefault('notes',work.get('notes',''))
        try:
            # Even the seeded items are checked against Internet Archive metadata.
            if prior.get('archive_id') or work.get('archive_id'):
                rid=prior.get('archive_id') or work['archive_id']
                meta=source_info(rid)
                current.update(meta)
                if meta['ocr_url']:
                    current['verification_status']='ocr_file_listed' if prior.get('verification_status') != 'verified_ocr' else 'verified_ocr'
                else:
                    current['verification_status']='confirmed_scan_no_ocr'
                current['notes']=(prior.get('notes') or 'Matched scan; verify OCR before indexing')
                previous[ident]=current
                continue
            candidates=harvest.search_candidates(work)
            previous_candidates=[r for r in previous_candidates if r['id']!=ident]
            found=[]
            for rank,c in enumerate(candidates[:max(1,args.max_candidates)],1):
                info=dict(archive_id=c['identifier'],scan_url='https://archive.org/details/'+quote(c['identifier'],safe=''),ocr_url='',ocr_filename='',ia_title=str(c.get('title','')),ia_creator=str(c.get('creator','')),ia_year=normalized(c.get('year','') or c.get('date','')))
                status='metadata_unchecked'
                try:
                    info.update(source_info(c['identifier']))
                    status='ocr_file_listed' if info['ocr_url'] else 'no_ocr_file'
                except Exception as exc: status=type(exc).__name__+': '+str(exc)[:90]
                found.append({**info,'id':ident,'year':work['year'],'title':work['title'],'candidate_rank':rank,'score':c['score'],'metadata_status':status})
                time.sleep(.2)
            previous_candidates+=found
            if found:
                best=next((p for p in found if p['ocr_url']),found[0])
                current['candidate_archive_id']=best['archive_id']
                current['candidate_score']=best['score']
                current['candidate_ocr_url']=best['ocr_url']
                current['verification_status']='candidate_found' if best['ocr_url'] else 'no_ocr_candidate'
                current['notes']='Automatic candidate only. Check exact edition, volume and authorship before approval.'
            else:
                current['verification_status']='no_candidate'
                current['notes']='No Archive.org catalogue match; may require manual identification or another provider.'
            previous[ident]=current
        except Exception as exc:
            current['verification_status']='error'
            current['notes']=f'{type(exc).__name__}: {exc}'[:220]
            previous[ident]=current
        finally:
            write_rows(REGISTER,COLUMNS,[previous.get(w['id'],{**w,'verification_status':'unmatched'}) for w in works])
            write_rows(CANDIDATES,CAN_COLUMNS,previous_candidates)
            time.sleep(max(0,args.pause))
    statuses={}
    for row in rows(REGISTER):statuses[row['verification_status']]=statuses.get(row['verification_status'],0)+1
    print('SUMMARY:',statuses,flush=True)
    print('Next step: human review of data/source_candidates.csv; promote confirmed entries to verified_ocr only after inspecting text.')

if __name__=='__main__':main()
