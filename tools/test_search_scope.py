#!/usr/bin/env python3
"""Offline regression check for category-or-single-work corpus searching."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build


def main():
    old = {name: getattr(build, name) for name in ("ROOT", "SITE", "WORKSDIR", "CLEAN", "RECORDS")}
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build.ROOT = root
            build.SITE = root / "site"
            build.WORKSDIR = build.SITE / "works"
            build.CLEAN = root / "data" / "clean"
            build.RECORDS = root / "data" / "records"
            build.CLEAN.mkdir(parents=True)
            build.RECORDS.mkdir(parents=True)
            works = [
                {"id": "sample-sermon", "year": 1840, "title": "A Sample Sermon",
                 "category": "Sermons", "contribution": "authored"},
                {"id": "sample-introduction", "year": 1847, "title": "B Sample Introduction",
                 "category": "Introductions", "contribution": "editorial"},
                {"id": "still-pending", "year": 1850, "title": "Still Pending",
                 "category": "Sermons", "contribution": "authored"},
            ]
            (root / "bibliography.json").write_text(
                json.dumps({"works": works}), encoding="utf-8"
            )
            (build.CLEAN / "sample-sermon.txt").write_text(
                "repentance and charity " * 60, encoding="utf-8"
            )
            (build.CLEAN / "sample-introduction.txt").write_text(
                "repentance and faith " * 60, encoding="utf-8"
            )
            (build.RECORDS / "sample-introduction.json").write_text(
                json.dumps({
                    "status": "downloaded",
                    "scope_verified": True,
                    "content_scope": "pusey_preface_or_introduction_only",
                    "extraction_boundaries": {"start": "A", "end": "B"},
                }), encoding="utf-8"
            )

            build.main()
            page = (build.SITE / "index.html").read_text(encoding="utf-8")
            options = page.split('<select id="work">', 1)[1].split("</select>", 1)[0]
            assert '<option value="sample-sermon">' in options
            assert '<option value="sample-introduction">' in options
            assert "still-pending" not in options
            assert '<select id="category">' in page
            assert 'class="filter-or"' in page
            for slug in ("sample-sermon", "sample-introduction"):
                section = (build.WORKSDIR / slug / "0001.html").read_text(encoding="utf-8")
                assert f'data-pagefind-filter="work_id[content]" content="{slug}"' in section
                assert 'data-pagefind-filter="category[content]"' in section
            js = (build.SITE / "search.js").read_text(encoding="utf-8")
            assert "filters:{work_id:work.value}" in js
            assert "if(category.value)work.value='';" in js
            assert "if(work.value)category.value='';" in js
            assert "url.searchParams.set('work',work.value)" in js
            print("Search scope regression passed: unique work filters and exclusive dropdowns.")
    finally:
        for name, value in old.items():
            setattr(build, name, value)


if __name__ == "__main__":
    main()
