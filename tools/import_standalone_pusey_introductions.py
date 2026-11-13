#!/usr/bin/env python3
"""Import independently published Pusey introductions, never the translated books.

Fail closed unless Internet Archive metadata identifies the publication as a
standalone preface/introductory essay and the downloaded text passes OCR QA.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import harvest

SOURCES = {
    'Preface to Essays on the Re-union of Christendom': {
        'archive_id': 'essaysonreunioni0000puse',
        'required_title': ('essays', 're-union', 'introductory'),
        'scope': 'pusey_preface_or_introduction_only',
        'edition_note': 'Separately issued Pusey introductory essay to the 1867 multi-author volume; main essays are not indexed.',
    },
    'Advice for Those Who Exercise the Ministry of Reconciliation': {
        'archive_id': 'onconfessionbein0000puse',
        'required_title': ('confession', 'preface'),
        'scope': 'pusey_translator_introduction_only',
        'edition_note': 'Separately published On Confession, 1906: reprinting only Pusey’s introduction to Gaume, rather than Gaume’s manual.',
    },
}

def contains_title(title, words):
    title = re.sub(r'[^a-z]+', ' ', title.lower().replace('re-union', 'reunion'))
    return all(re.sub(r'[^a-z]+', '', word.lower()) in title.replace(' ', '') for word in words)

def main():
    works = json.loads((ROOT / 'bibliography.json').read_text(encoding='utf-8'))['works']
    register = ROOT / 'data/source_registry.csv'
    with register.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    by_id = {r['id']: r for r in rows}
    imported = 0
    for work in works:
        spec = SOURCES.get(work['title'])
        if spec is None: continue
        slug = work['id']
        if (harvest.CLEAN / (slug + '.txt')).exists():
            print('SKIP already present:', work['title'], flush=True)
            continue
        ident = spec['archive_id']
        print('INSPECT', work['title'], ident, flush=True)
        try:
            md_obj = harvest.get_metadata(ident)
            md = md_obj.get('metadata') or {}
            title = str(md.get('title',''))
            author = md.get('creator', '')
            creators = ' '.join(map(str, author)) if isinstance(author,list) else str(author)
            if 'pusey' not in creators.lower():
                raise ValueError('Author metadata does not identify E. B. Pusey')
            if not contains_title(title, spec['required_title']):
                raise ValueError('Not a separately issued Pusey introduction: '+title[:120])
            if not harvest.text_filename(md_obj):
                raise ValueError('No OCR file available')
            # This file is itself a standalone Pusey preface/essay, not the
            # associated translated or edited book. Do not invoke get_book(),
            # whose whole-book ban rightly protects mixed-author volumes.
            from urllib.parse import quote
            filename = harvest.text_filename(md_obj)
            url = 'https://archive.org/download/' + quote(ident, safe='') + '/' + quote(filename, safe='/')
            response = harvest.request(url, stream=True)
            chunks, nbytes = [], 0
            for chunk in response.iter_content(128*1024):
                if not chunk:
                    continue
                nbytes += len(chunk)
                if nbytes > 40*1024*1024:
                    response.close()
                    raise ValueError('Standalone preface OCR exceeds safe size')
                chunks.append(chunk)
            response.close()
            raw, encoding = harvest.decode_content(b''.join(chunks))
            passed, qc = harvest.assess_ocr(raw)
            if not passed:
                raise ValueError('Standalone preface OCR failed QC: ' + qc)
            cleaned = harvest.clean_ocr(raw)
            harvest.RAW.mkdir(parents=True, exist_ok=True)
            harvest.CLEAN.mkdir(parents=True, exist_ok=True)
            (harvest.RAW / (slug + '.txt')).write_text(raw, encoding='utf-8')
            (harvest.CLEAN / (slug + '.txt')).write_text(cleaned, encoding='utf-8')
            result = {
                'status': 'downloaded',
                'source': 'Internet Archive, separately published Pusey introduction only',
                'identifier': ident,
                'scan_url': 'https://archive.org/details/' + quote(ident, safe=''),
                'text_url': url,
                'word_count': len(harvest.words(cleaned)),
                'qc': qc,
                'encoding': encoding,
                'downloaded_utc': datetime.now(timezone.utc).isoformat(),
                'original_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
                'source_title': title,
                'source_creator': creators,
                'source_date': str(md.get('year','') or md.get('date','')),
                'authorship_review_needed': False
            }
            harvest.write_record(work, result)
            clean_path = harvest.CLEAN / (slug+'.txt')
            full_text = clean_path.read_text(encoding='utf-8')
            # Standalone introductions must have meaningful substantial prose;
            # reject edition/metadata-only artifacts.
            if result['word_count'] < 1500 or result['word_count'] > 90000:
                raise ValueError('Not plausible standalone introduction length: '+str(result['word_count']))
            if work['title'].startswith('Preface to Essays'):
                if len(re.findall(r're.?union|christendom|church', full_text, flags=re.I)) < 15:
                    raise ValueError('Text does not resemble the introductory essay')
            else:
                if len(re.findall(r'confess|absolut|peniten',full_text,flags=re.I)) < 15:
                    raise ValueError('Text does not resemble the Pusey introduction to confession')
            rec_path = harvest.RECORDS / (slug+'.json')
            rec = json.loads(rec_path.read_text(encoding='utf-8'))
            rec.update({
                'scope_verified': True,
                'content_scope': spec['scope'],
                'extraction_boundaries': 'Complete separate publication solely of Pusey preface/introductory essay, not the other author’s primary work.',
                'extraction_method': 'Separately published preface/essay, entire document; scan identified by author and edition title',
                'source_edition_note': spec['edition_note'],
                'authorship_review_needed': False
            })
            rec_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
            by_id[slug].update(
                verification_status='verified_pusey_preface_only',
                archive_id=ident,
                scan_url=result['scan_url'],
                ocr_url=result['text_url'],
                ocr_filename=harvest.text_filename(md_obj),
                ia_title=title,
                ia_creator=creators,
                ia_year=str(md.get('year','') or md.get('date',''))[:28],
                notes=spec['edition_note']
            )
            imported += 1
            print('APPROVED PUSEY INTRODUCTION ONLY', result['word_count'], 'words',flush=True)
        except Exception as exc:
            print('REJECTED:',type(exc).__name__,str(exc)[:240],flush=True)
            # Remove all incomplete files so publishing cannot include them.
            for folder, ext in ((harvest.RAW,'.txt'),(harvest.CLEAN,'.txt'),(harvest.RECORDS,'.json')):
                (folder/(slug+ext)).unlink(missing_ok=True)
    with register.open('w', encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    harvest.csv_report(works)
    print('Standalone Pusey introductions acquired:',imported,flush=True)

if __name__=='__main__':
    main()
