#!/usr/bin/env python3
"""Static contract tests for the independent Sermons search and browse UI."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
site = root / "site"
sermons = site / "sermons"
catalogue = json.loads((sermons / "catalogue.json").read_text(encoding="utf-8"))
entries = catalogue["entries"]
available = [entry for entry in entries if entry["status"] == "available"]
missing = [entry for entry in entries if entry["status"] != "available"]

assert len(entries) >= 190, "The Madan index unexpectedly lost entries"
assert len(available) >= 100, "Too few available sermons to build a useful full-text index"
assert len(available) + len(missing) == len(entries)

main = (sermons / "index.html").read_text(encoding="utf-8")
js = (sermons / "listing.js").read_text(encoding="utf-8")
assert 'id="q"' in main and 'Search the full text of the sermons' in main
assert 'id="search-hits"' in main and 'id="sermon-browse"' in main
assert 'id="browse-q"' not in main, "Remove the redundant catalogue query box"
assert 'id="sort"' in main and 'Chronological / date range' in main
assert 'Title A–Z' in main and 'Scripture (Madan order)' in main
assert 'id="scope"' in main and "querySelector('#sort')" in js and 'browseQ' not in js
assert 'type="module" src="listing.js"' in main
assert "import('./pagefind/pagefind.js')" in js, "Sermon search must use its own Pagefind index"
assert "searchWithOcrVariants(p,query)" in js, "Search sermon text, including bounded OCR variants"
assert "from '../ocr_variants.js'" in js, "Use shared OCR search helper"
assert "function hitSentence(d,query)" in js, "Compute contextual sermon sentences"
assert "d.locations" in js, "Use Pagefind's actual match location in the OCR"
assert "hitSentence(d,q.value.trim())" in js, "Display the highlighted sentence below each result"
assert "sermonResultUrl(d.url)" in js, "Resolve sermon links against their canonical location"
assert "<mark>" in js and "d.excerpt" in js, "Highlight terms and retain Pagefind fallback"
assert "const initial=new URLSearchParams" in js, "Search links must be shareable"
assert "browse.hidden=!!query" in js and "searchArea.hidden=!query" in js
assert 'id="search-more"' in main and "batch=all.slice(shown,shown+20)" in js

sample = [available[0], available[len(available)//2], available[-1]]
for sermon in sample:
    page = (sermons / (sermon["id"] + ".html")).read_text(encoding="utf-8")
    assert '<article id="sermon-text" class="ocr" data-pagefind-body' in page
    assert '<meta data-pagefind-meta="sermon_title[content]"' in page
    assert '<meta data-pagefind-meta="scripture[content]"' in page
    assert '<meta data-pagefind-meta="sermon_date[content]"' in page
    assert '<meta data-pagefind-meta="source[content]"' in page
    assert 'src="../reader.js" defer' in page, "Search result should highlight its terms"
    assert "src=\"within.js\" defer" in page, "Maintain per-sermon find"
    assert len(re.findall(r"\w+", page)) > 1000, "Extracted sermon seems too short"

generated = sorted(p.name for p in sermons.glob("m???.html"))
expected = sorted(e["id"] + ".html" for e in available)
assert generated == expected, "Sermon HTML should exist for all and only available sermons"
print(f"SERMON SEARCH TEST: {len(available)} individually searchable sermons; "
      f"{len(missing)} unresolved entries remain browsable; independent search UI OK")
