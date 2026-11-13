#!/usr/bin/env python3
"""Conservative first batch: independently validate archive title, author and usable OCR
for individually identified, distinct Pusey works. Never approve ambiguous volumes."""
from __future__ import annotations
import csv, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import harvest

ROOT=Path(__file__).resolve().parent.parent
REGISTER=ROOT/'data/source_registry.csv'
CURATED={
  "Remarks on the Prospective and Past Benefits of Cathedral Institutions": {
    "archive_id": "remarksonprospe00pusegoog",
    "anchors": [
      "remarks",
      "cathedral",
      "institutions"
    ]
  },
  "Appendices to the Sermon of 5 November 1837": {
    "archive_id": "appendicestoser00pusegoog",
    "anchors": [
      "appendices",
      "sermon",
      "november"
    ]
  },
  "A Letter to the Bishop of Oxford on the Tendency to Romanism": {
    "archive_id": "alettertorichar00pusegoog",
    "anchors": [
      "letter",
      "oxford",
      "romanism"
    ]
  },
  "The Articles Treated on in Tract 90 Reconsidered": {
    "archive_id": "10775823bsb",
    "anchors": [
      "articles",
      "tract",
      "reconsidered"
    ]
  },
  "A Letter on the Proposed Change to the Laws of Marriage of Near Kin": {
    "archive_id": "letteronproposed00puse",
    "anchors": [
      "letter",
      "marriage",
      "kin"
    ]
  },
  "A Course of Sermons on Solemn Subjects, chiefly bearing on Repentance": {
    "archive_id": "courseofsermonso00puseuoft",
    "anchors": [
      "sermons",
      "solemn",
      "repentance"
    ]
  },
  "Marriage with a Deceased Wife's Sister Prohibited by Holy Scripture": {
    "archive_id": "b29349412",
    "anchors": [
      "marriage",
      "sister",
      "scripture"
    ]
  },
  "The Royal Supremacy Not an Arbitrary Authority": {
    "archive_id": "a605411600puseuoft",
    "anchors": [
      "royal",
      "supremacy",
      "authority"
    ]
  },
  "The Church of England Leaves Her Children Free to Whom to Open Their Griefs": {
    "archive_id": "churchofenglandl00puse",
    "anchors": [
      "church",
      "children",
      "griefs"
    ]
  },
  "Collegiate and Professorial Teaching and Discipline": {
    "archive_id": "collegiateandpr00pusegoog",
    "anchors": [
      "collegiate",
      "professorial",
      "discipline"
    ]
  },
  "The Real Presence of the Body and Blood of Christ: Doctrine of the English Church": {
    "archive_id": "10399201bsb",
    "anchors": [
      "real",
      "presence",
      "blood",
      "church"
    ]
  },
  "Eleven Addresses during a Retreat of the Companions of the Love of Jesus": {
    "archive_id": "elevenaddresses00pusegoog",
    "anchors": [
      "eleven",
      "addresses",
      "retreat"
    ]
  },
  "Eirenicon, Part III: Is Healthful Reunion Impossible?": {
    "archive_id": "a6052907c200puseuoft",
    "anchors": [
      "healthful",
      "reunion",
      "impossible"
    ]
  },
  "Lenten Sermons Preached Chiefly to Young Men": {
    "archive_id": "a605295900puseuoft",
    "anchors": [
      "lenten",
      "sermons",
      "young"
    ]
  },
  "What Is of Faith as to Everlasting Punishment?": {
    "archive_id": "whatisfaithasto00pusegoog",
    "anchors": [
      "faith",
      "everlasting",
      "punishment"
    ]
  },
  "Parochial and Cathedral Sermons": {
    "archive_id": "a6053928c100puseuoft",
    "anchors": [
      "parochial",
      "cathedral",
      "sermons"
    ]
  },
  "The Doctrine of the Real Presence, as Contained in the Fathers": {"archive_id": "thedoctrineofthe00puseuoft", "anchors": ["doctrine","presence","fathers"]},
  "A Letter to the Bishop of London": {"archive_id": "letterlordbishop00puseuoft", "anchors": ["letter","bishop","london"]},
  "The Councils of the Church from Jerusalem to Constantinople": {"archive_id": "councilsofchur00puse", "anchors": ["councils","jerusalem","constantinople"]},
  "University Sermons, Vol. I: Nine Sermons": {"archive_id": "ninesermonsprea00pusegoog", "anchors": ["nine","sermons","oxford"]},
  "University Sermons, Vol. II: Sermons 1859–1872": {"archive_id": "sermonspreachedb00puse", "anchors": ["sermons","university","oxford"]},
  "University Sermons, Vol. III: Ten Sermons": {"archive_id": "tensermonspreach00puseuoft", "anchors": ["ten","sermons","oxford"]},
  "Eirenicon, Part I: The Church of England a Portion of Christ's Church": {"archive_id": "churchofenglandp00puseuoft", "anchors": ["church","england","catholic"]},
  "Eirenicon, Part II: First Letter to J. H. Newman": {"archive_id": "firstlettertove00pusegoog", "anchors": ["first","letter","newman"]},
  "Parochial Sermons, Vol. I (Advent to Whitsuntide)": {"archive_id": "a605469400puseuoft", "anchors": ["sermons","advent","whitsuntide"]},
  "A Letter to the Archbishop of Canterbury": {"archive_id": "a605297400puseuoft", "anchors": ["letter","archbishop","canterbury"]},
  "On the Clause “And the Son” in Regard to the Eastern Church": {"archive_id": "a605360400puseuoft", "anchors": ["clause","son","eastern"]},
  "Unlaw in Judgments of the Judicial Committee and Its Remedies": {"archive_id": "unlawinjudgement00puse", "anchors": ["unlaw","judgements","committee"]},
  "Tracts 67–69: Scriptural Views of Holy Baptism": {"archive_id": "scripturalviewso00puse", "anchors": ["scriptural","views","baptism"]}
}

def normalized(x):
    return set(re.findall(r'[a-z]{3,}',str(x).lower()))

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    with REGISTER.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    index={r['id']:r for r in rows}
    done=failed=skipped=0
    for work in works:
        spec=CURATED.get(work['title'])
        if spec is None:continue
        reg=index[work['id']]
        if reg['verification_status']=='verified_ocr' and (harvest.CLEAN/(work['id']+'.txt')).exists():
            skipped+=1;continue
        ident=spec['archive_id']
        print('CHECK',work['title'],ident,flush=True)
        try:
            # Reject mixed contributions and edition ambiguities from this first batch.
            if work.get('contribution')!='authored':
                raise ValueError('Contribution is not entirely authored by Pusey')
            if ('Vol.' in work['title'] and work['title'] not in { 'Parochial Sermons, Vol. I (Advent to Whitsuntide)', 'University Sermons, Vol. I: Nine Sermons', 'University Sermons, Vol. II: Sermons 1859–1872', 'University Sermons, Vol. III: Ten Sermons' }) or ('Part ' in work['title'] and 'Eirenicon' not in work['title']):
                raise ValueError('Volume identity requires manual verification')
            meta=harvest.get_metadata(ident)
            md=meta.get('metadata') or {}
            ia_title=str(md.get('title') or '')
            creators=md.get('creator') or ''
            creator=' '.join(str(x) for x in creators) if isinstance(creators,list) else str(creators)
            if 'pusey' not in creator.lower():
                raise ValueError('Catalogue creator does not identify Pusey')
            if len(normalized(ia_title).intersection(spec['anchors'])) < max(2,len(spec['anchors'])-1):
                raise ValueError('Catalogue title does not match distinctive expected title words: '+ia_title[:110])
            fname=harvest.text_filename(meta)
            if not fname:raise ValueError('No OCR .txt file listed in archive metadata')
            # This is a real OCR download and QC, not merely a metadata match.
            selected={**work,'archive_id':ident}
            rec=harvest.get_book(selected)
            if rec['word_count'] < 1500:
                raise ValueError('OCR too short to be relied upon: '+str(rec['word_count']))
            clean=harvest.CLEAN/(work['id']+'.txt')
            excerpt=clean.read_text(encoding='utf8')[:50000]
            present=len(normalized(excerpt).intersection(spec['anchors']))
            if present < 2:
                raise ValueError('Downloaded OCR opening lacks recognizable title words')
            reg.update(
                verification_status='verified_ocr',
                archive_id=ident,
                scan_url=rec['scan_url'],
                ocr_url=rec['text_url'],
                ocr_filename=fname,
                ia_title=ia_title,
                ia_creator=creator,
                ia_year=str(md.get('year','') or md.get('date',''))[:24],
                notes='Title/creator matched; actual '+str(rec['word_count'])+'-word OCR downloaded and passed initial content checks. Further scholarly edition review possible.',
            )
            done+=1
            print('APPROVED',rec['word_count'],'words',flush=True)
        except Exception as exc:
            failed+=1
            print('REJECTED',work['title'],type(exc).__name__,str(exc)[:180],flush=True)
            # Do not index partial or rejected OCR.
            for folder,suffix in [(harvest.RAW,'.txt'),(harvest.CLEAN,'.txt'),(harvest.RECORDS,'.json')]:
                (folder/(work['id']+suffix)).unlink(missing_ok=True)
        time.sleep(0.7)
    with REGISTER.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    harvest.csv_report(works)
    print('BATCH SUMMARY: verified',done,'rejected',failed,'already present',skipped,flush=True)

if __name__=='__main__':
    main()
