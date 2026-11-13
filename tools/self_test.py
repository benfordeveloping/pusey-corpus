#!/usr/bin/env python3
"""Non-network smoke tests; creates and removes an ephemeral fake OCR file."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest, build

def main():
    works=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    assert len(works)>=60
    assert len(set(x['id'] for x in works))==len(works)
    seeds=[x['archive_id'] for x in works if x.get('archive_id')]
    assert len(seeds)==len(set(seeds))
    ok,msg=harvest.assess_ocr('Image of page 2\n'*300)
    assert not ok and 'placeholder' in msg
    assert 'invisible' in harvest.clean_ocr('invis-\nible')
    selected=next(x for x in works if x['title'].startswith('Daniel the Prophet'))
    slug=selected['id']
    dest=ROOT/'data'/'clean'/f'{slug}.txt'
    record=ROOT/'data'/'records'/f'{slug}.json'
    assert not dest.exists(), 'Stop test: a real Daniel text already exists and must not be overwritten.'
    assert not record.exists(), 'Stop test: metadata already exists and must not be overwritten.'
    dest.parent.mkdir(parents=True,exist_ok=True)
    record.parent.mkdir(parents=True,exist_ok=True)
    # This text is intentionally fake and used ONLY for this test.
    content=('This is a temporary automated test with a searchable keyword metanoia and context.\n\n'*180)
    dest.write_text(content,encoding='utf8')
    record.write_text(json.dumps({'status':'downloaded','scan_url':'https://archive.org/details/a604991500puseuoft'}),encoding='utf8')
    try:
        build.main()
        path=ROOT/'site'/'works'/slug/'0001.html'
        assert path.exists()
        html=path.read_text(encoding='utf8')
        assert 'metanoia' in html and 'data-pagefind-body' in html
        assert 'data-pagefind-filter' in html and 'sourceinfo' in html
        assert 'daniel' in (ROOT/'site'/'index.html').read_text(encoding='utf8').lower()
        print('Smoke tests passed: bibliography, OCR checking, section pages, search metadata.')
    finally:
        dest.unlink(missing_ok=True)
        record.unlink(missing_ok=True)
        build.main()
        # The test's generated sections are deliberately removed.
        folder=ROOT/'site'/'works'/slug
        if folder.exists():
            for p in folder.glob('*.html'):p.unlink()
            folder.rmdir()

if __name__=='__main__':main()
