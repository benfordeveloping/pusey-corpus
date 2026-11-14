#!/usr/bin/env python3
"""Independent biography build checks, including total source coverage."""
import json
import re
from pathlib import Path

root=Path(__file__).resolve().parents[1]
data=root/'data'/'liddon'
site=root/'site'/'liddon'
spec={1:range(1,19),2:range(19,35),3:range(1,18),4:range(1,19)}
expected={(v,n) for v,rs in spec.items() for n in rs}
records=list(data.glob('v??-c??.json')) if data.exists() else []
if not records:
    print('LIDDON TEST: source harvest pending (no texts yet)')
    raise SystemExit(0)

assert len(records)==69, f'Expected all 69 chapters, found {len(records)}'
actual=set()
total=0
for path in records:
    rec=json.loads(path.read_text(encoding='utf8'))
    v,n=rec['volume'],rec['chapter']
    actual.add((v,n))
    assert path.name==f'v{v:02d}-c{n:02d}.json'
    assert rec['source_url'].endswith(f'/{v}.{n}.html')
    assert len(rec['text'].split())>=400
    assert re.search(r'\bCHAPTER\s+[IVXLCDM]+\b',rec['text'][:500],re.I),path.name
    page=(site/'chapters'/f'v{v:02d}-c{n:02d}.html')
    assert page.exists(),f'Missing full chapter reader: {page}'
    assert rec['text'].split()[8] in page.read_text(encoding='utf8'),path
    total+=rec['words']
assert actual==expected
index=(site/'index.html').read_text(encoding='utf8')
js=(site/'search.js').read_text(encoding='utf8')
assert 'id="q"' in index and 'id="search-hits"' in index
assert "searchWithOcrVariants(p,text)" in js
assert "import('./pagefind/pagefind.js')" in js
assert 'd.meta?.volume' in js and 'd.meta?.chapter' in js
sections=list((site/'sections').glob('*.html'))
assert len(sections)>=69
for path in (sections[0],sections[len(sections)//2],sections[-1]):
    text=path.read_text('utf8')
    assert 'data-pagefind-body' in text
    assert 'data-pagefind-meta="volume[content]"' in text
    assert 'data-pagefind-meta="chapter[content]"' in text
assert len(sections)>=250, f'Unexpectedly few indexed biography passages: {len(sections)}'
print(f'LIDDON TEST PASSED: {len(records)} chapters / {len(sections)} passages / {total:,} words')
