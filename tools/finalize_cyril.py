#!/usr/bin/env python3
"""One-time conservative publication of E. B. Pusey's 1874 Cyril preface.

A public transcription of the exact first-volume preface is used because
the IA full-volume OCR can be intermittently inaccessible. The transcription
is explicitly identified as such in the catalogue; no automatic candidate
match is promoted to a verified Internet Archive OCR.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SLUG = "1874-preface-to-st-cyril-s-commentary-on-the-gospel-of-john"
TRANSCRIPTION = "https://www.ecatholic2000.com/cyril2/untitled-03.shtml"
ARCHIVE = "https://archive.org/details/commentaryongosp01cyri"
OCR = "https://archive.org/stream/commentaryongosp01cyri/commentaryongosp01cyri_djvu.txt"

# The securely attributed bracketed second portion of the 1874 Preface.
# P. E. Pusey says on p. ix that the bracketed portion, printed pp. xxi-end,
# is "wholly" his father's. Leave pp. vii-xx out of the index, even though
# some theological passages there are E. B.'s.
FIRST = "The relation of the Three Divine Persons, Father, Son, and Holy Ghost"
LAST = "should forfeit the belief itself, and become misbelievers in our God."
USER_AGENT = "PuseyCorpusOneTimeCompletion/1.0 (public-domain historical bibliography)"

def fetch(url):
    r = requests.get(url, timeout=(20, 120), headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.text

def build_excerpt():
    page = fetch(TRANSCRIPTION)
    soup = BeautifulSoup(page, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    # The web transcription supplies its complete first-volume preface on a
    # single page, so fixed, independently checked start/end markers are safer
    # than relying on the host site's changeable DIV/CSS structure.
    all_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    assert "To him too is due the Theological portion" in all_text, (
        "The primary-source authorship note is missing; do not publish")
    assert "xxi to end is wholly his" in all_text, (
        "Printed page authorship boundary is missing; do not publish")
    start = all_text.find(FIRST)
    end = all_text.find(LAST, start)
    assert start >= 0 and end > start, "Missing verified text markers"
    end += len(LAST)
    excerpt = all_text[start:end]
    assert excerpt.startswith(FIRST) and excerpt.endswith(LAST)
    wc = len(re.findall(r"\b[\w’'-]+\b", excerpt))
    assert 6000 < wc < 40000, f"Implausible preface size: {wc} words"
    for phrase in ("Gregory of Nyssa", "Athanasius", "Holy Ghost", "Council of Florence"):
        assert phrase in excerpt, f"Expected original preface phrase missing: {phrase}"
    assert "Copyright ©" not in excerpt and "S. CYRIL ARCHBISHOP OF ALEXANDRIA VOL. II" not in excerpt
    return excerpt + "\n", wc

def main():
    excerpt, wc = build_excerpt()
    src_raw = ROOT / "data/raw" / (SLUG + ".txt")
    src_clean = ROOT / "data/clean" / (SLUG + ".txt")
    src_record = ROOT / "data/records" / (SLUG + ".json")
    for p in (src_raw, src_clean, src_record):
        p.parent.mkdir(parents=True, exist_ok=True)
    src_raw.write_text(excerpt, encoding="utf-8")
    src_clean.write_text(excerpt, encoding="utf-8")

    record = {
        "id": SLUG,
        "year": 1874,
        "title": "Preface to St Cyril's Commentary on the Gospel of John",
        "category": "Introductions",
        "contribution": "editorial",
        "status": "downloaded",
        "source": "Verified public-domain transcription of the 1874 preface; E. B. Pusey portion only",
        "identifier": "commentaryongosp01cyri",
        "scan_url": ARCHIVE,
        "text_url": TRANSCRIPTION,
        "owner_supplied_ocr_url": OCR,
        "source_edition_year": 1874,
        "source_title": "Commentary on the Gospel according to S. John, vol. I (John I–VIII), 1874",
        "source_creator": "E. B. Pusey (bracketed pp. xxi-end); P. E. Pusey (other preface and translation excluded)",
        "word_count": wc,
        "original_sha256": hashlib.sha256(excerpt.encode("utf8")).hexdigest(),
        "scope_verified": True,
        "content_scope": "pusey_preface_or_introduction_only",
        "extraction_boundaries": {
            "printed_start_page": "xxi",
            "printed_end_page": "end of Preface (before separate Introduction by Cyril)",
            "start": FIRST,
            "end": LAST,
            "other_authors_excluded": True
        },
        "authorship_review_needed": False,
        "qc": ("Public transcription checked for complete quoted passage and p. ix author note; "
               "not represented as authenticated full-volume IA OCR; printed-page images "
               "were not newly examined in this automated import.")
    }
    src_record.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

    registry = ROOT / "data/source_registry.csv"
    with registry.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        rows = list(reader)
    matches = [r for r in rows if r["id"] == SLUG]
    assert len(matches) == 1, "Registry row missing or duplicated"
    row = matches[0]
    assert row["verification_status"] == "candidate_found", "Unexpected status: check manually"
    row["verification_status"] = "verified_pusey_transcription_only"
    row["archive_id"] = "commentaryongosp01cyri"
    row["scan_url"] = ARCHIVE
    row["ocr_url"] = TRANSCRIPTION
    row["ocr_filename"] = ""
    row["ia_title"] = record["source_title"]
    row["ia_creator"] = "E. B. Pusey and P. E. Pusey (preface; see attribution)"
    row["ia_year"] = "1874"
    row["notes"] = (
        "Exact 1874 vol. I established from owner-supplied IA source; published E. B. "
        "Pusey's explicitly attributed bracketed pp. xxi-end only, from independently "
        "available public transcription " + TRANSCRIPTION + ". The main IA OCR link " +
        OCR + " is retained as a lead but is not misrepresented as newly verified "
        "OCR. Son's preface/translation and Cyril's Introduction excluded."
    )
    with registry.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)

    report = ROOT / "data/harvest_report.csv"
    with report.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        reportcols = reader.fieldnames
        reportrows = list(reader)
    matches = [r for r in reportrows if r["title"] == record["title"] and str(r["year"]) == "1874"]
    assert len(matches) == 1, "Harvest-report row missing or duplicated"
    matches[0].update(status="downloaded", word_count=str(wc), scan_url=ARCHIVE, issue="")
    with report.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reportcols)
        writer.writeheader()
        writer.writerows(reportrows)

    print(f"Prepared securely attributed Cyril preface: {wc:,} words.")
    print(f"Source: {TRANSCRIPTION}")
    print(f"First: {excerpt[:100]} / Last: {excerpt[-130:]}")

if __name__ == "__main__":
    main()
