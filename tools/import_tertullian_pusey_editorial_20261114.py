#!/usr/bin/env python3
"""Import Pusey's signed 1842 Tertullian preface and 17 lettered editorial notes.

Fail closed: exact previously inspected OCR hash, verified starts and ends.
Never put C. Dodgson's translated Tertullian or uncertain Additional Notes
in data/clean. The entire original OCR remains preserved in data/raw.
"""
import csv
import datetime
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
IDENT="1842-introduction-and-notes-to-tertullian"
ARCHIVE_ID="10ALibraryOfFathersOfTheHolyCatholicV10"
URL="https://archive.org/stream/"+ARCHIVE_ID+"/"+ARCHIVE_ID+"_djvu.txt"
DIRECT=URL.replace("/stream/","/download/")
EXPECTED_SHA="3726854cad7ce4716791750d72e6e218412cecb65dbb9f0f40bf3a5d4f2a8171"

# Exact character offsets apply ONLY to this sha256-confirmed OCR text.
# Starts are lettered headings; ends are the NEXT EDITORIAL NOTE or the
# first line of a TRANSLATED TREATISE, as independently audited 2026-11-14.
EDITS=[
 ("A",410781,421510,"Note B"),
 ("B",421510,449829,"Note C"),
 ("C",449829,465508,"Note D"),
 ("D",465508,506297,"Of the Witness of the Soul (translated; excluded)"),
 ("E",675012,683981,"Of Public Shows (translated; excluded)"),
 ("F",885528,893769,"Of Baptism (translated; excluded)"),
 ("G",982724,1051656,"Of Prayer (translated; excluded)"),
 ("H",1128955,1141481,"Note I"),
 ("I",1141481,1148716,"Of Patience (translated; excluded)"),
 ("K",1275537,1304578,"Note L"),
 ("L",1304578,1317808,"Note M"),
 ("M",1317808,1434462,"The First Book to His Wife (translated; excluded)"),
 ("N",1469725,1472538,"The Second Book to His Wife (translated; excluded)"),
 ("O",1506820,1512236,"On Prescription Against Heretics (translated; excluded)"),
 ("P",1671183,1723306,"Note Q"),
 ("Q",1723306,1743896,"Note R"),
 ("R",1743896,1750731,"Additional Notes (attribution not yet confirmed; excluded)")
]

def fetch():
    for url in [DIRECT,URL]:
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"Pusey-Corpus-Research/1.0","Accept":"text/plain"})
                with urllib.request.urlopen(req,timeout=120) as r:raw=r.read()
                if raw[:300].lstrip().lower().startswith((b"<!doctype html",b"<html")):
                    raise ValueError("Archive returned HTML rather than OCR")
                digest=hashlib.sha256(raw).hexdigest()
                if digest!=EXPECTED_SHA:
                    raise ValueError("OCR changed! Refuse to reuse verified offsets: "+digest)
                return raw.decode("utf-8-sig")
            except Exception as exc:
                print("Tertullian fetch retry",url,attempt,str(exc),flush=True)
                time.sleep(2*(attempt+1))
    raise RuntimeError("Exact inspected Tertullian OCR not accessible")

def save_json(filename,value):
    p=ROOT/filename
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf8")

def update_registry():
    filename=ROOT/"data/source_registry.csv"
    with filename.open(encoding="utf8",newline="") as f:
        reader=csv.DictReader(f)
        headers=reader.fieldnames
        rows=list(reader)
    for r in rows:
        if r["id"]!=IDENT:continue
        r["verification_status"]="verified_pusey_signed_preface_and_lettered_notes"
        r["archive_id"]=ARCHIVE_ID
        r["scan_url"]="https://archive.org/details/"+ARCHIVE_ID
        r["ocr_url"]=URL
        r["ocr_filename"]=ARCHIVE_ID+"_djvu.txt"
        r["ia_year"]="1842"
        r["notes"]=(
            "Owner-supplied 1842 Library of Fathers vol. X, translator C. Dodgson. "
            "Clean file includes only the signed E. B. P. Preface and all "
            "17 independently bounded Notes A-I and K-R; no Note J exists. "
            "Each text range vetted with sha256 "+EXPECTED_SHA+
            " and explicit next-section boundaries in data/tertullian_note_boundary_inspection_20261114.json. "
            "The original complete OCR is preserved as raw, but NOT searchable. "
            "Translated Tertullian entirely excluded; unsigned Additional Notes "
            "(pp. 499-502) excluded pending explicit authorship corroboration."
        )
    with filename.open("w",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=headers,lineterminator="\n")
        writer.writeheader();writer.writerows(rows)

def update_bibliography():
    filename=ROOT/"bibliography.json"
    obj=json.loads(filename.read_text(encoding="utf8"))
    w=next(x for x in obj["works"] if x["id"]==IDENT)
    w["notes"]=(
        "Pusey-only editorial text imported: the complete signed Preface "
        "(Feast of St. John the Baptist, 1842), and Notes A-I, K-R "
        "(17 notes; no J). Extracted by exact audited boundaries from "
        "Library of Fathers Vol X (1842). Charles Dodgson's translations and "
        "unsigned Additional Notes are excluded pending attribution. "
        "OCR remains unproofread; see data/records and "
        "data/tertullian_note_boundary_inspection_20261114.json."
    )
    w["editorial_notes_imported"]=[row[0] for row in EDITS]
    w["additional_notes_indexed"]=False
    save_json("bibliography.json",obj)

def update_tracking(wordcount):
    report=ROOT/"data/harvest_report.csv"
    with report.open(newline="",encoding="utf8") as fh:
        rows=list(csv.reader(fh))
    for row in rows:
        if len(row)>2 and row[1].startswith("Introduction and Notes to Tertullian"):
            while len(row)<8:row.append("")
            row[4]="downloaded"
            row[5]=str(wordcount)
            row[7]="Signed Pusey preface + all 17 lettered editorial Notes; translation and unsigned Additional Notes excluded"
    with report.open("w",newline="",encoding="utf8") as fh:
        csv.writer(fh,lineterminator="\n").writerows(rows)
    ledger=ROOT/"data/owner_source_ledger_20261113.json"
    if ledger.exists():
        obj=json.loads(ledger.read_text(encoding="utf8"))
        for e in obj.get("entries",[]):
            if e.get("bibliography_id")==IDENT:
                e["ingestion_status"]="verified_pusey_preface_and_17_editorial_notes"
                e["github_source_url"]="https://archive.org/details/"+ARCHIVE_ID
                e["github_clean_path"]="data/clean/"+IDENT+".txt"
                e["github_raw_path"]="data/raw/"+IDENT+".txt"
                e["source_notes"]=(
                    "Imported signed 1842 E.B.P. preface and Notes A-I, K-R as 18 "
                    "audited Pusey-editorial segments. Full raw translated source "
                    "preserved but excluded from indexed clean text. Unsigned Additional "
                    "Notes remain unindexed until authorship is verified.")
        save_json("data/owner_source_ledger_20261113.json",obj)

def main():
    inspection=json.loads((ROOT/"data/tertullian_note_boundary_inspection_20261114.json").read_text("utf8"))
    assert inspection["sha256"]==EXPECTED_SHA
    text=fetch()
    print("TERTULLIAN OCR VERIFIED",len(text),"characters",flush=True)
    # Signed Pusey PREFACE begins immediately after the volume's contents,
    # and ends before 'THE BOOK OF APOLOGY AGAINST THE HEATHEN'.
    openings=[m.start() for m in re.finditer(r"(?im)^\s*PREFACE\s*\.",text[:14000])]
    openings=[p for p in openings if 6800<p<9000]
    if len(openings)!=1:raise RuntimeError("Pusey preface opening ambiguous "+repr(openings))
    start=openings[0]
    sign=re.search(r"E\s*\.\s*B\s*\.\s*P\s*\.",text[57000:64000],re.I)
    if not sign:raise RuntimeError("Pusey signature not found in signed preface")
    signature_pos=57000+sign.start()
    next_work=re.search(r"THE\s+BOOK\s+OF\s+APOLOGY",text[signature_pos:signature_pos+4000],re.I)
    if not next_work:raise RuntimeError("Unable to verify the end of Preface")
    end=signature_pos+next_work.start()
    preface=text[start:end]
    if not (40000<len(preface)<85000 and "1842" in preface[-1700:] and "E.  B.  P." in preface[-2100:]):
        raise RuntimeError("Preface text is not the complete signed 1842 piece")
    # Keep all editor's closing footnotes; trim only the next translated title.
    clean_sections=["E. B. Pusey — Preface and Editorial Notes to Tertullian (1842)",
      "[SIGNED PREFACE — E. B. P.; Feast of St. John the Baptist, 1842]\n"+preface.strip()]
    ranges=[{"section":"Pusey signed Preface","start":start,"end":end,
             "ends_before":"The Book of Apology"}]
    for letter,a,b,stop in EDITS:
        excerpt=text[a:b]
        if not (800<len(excerpt)<130000):
            raise RuntimeError("Note "+letter+" extraction length invalid: "+str(len(excerpt)))
        if not re.match(r"\s*Note\s+"+letter+r"\b",excerpt[:110],re.I):
            raise RuntimeError("Expected Note "+letter+" heading missing at audited start: "+repr(excerpt[:140]))
        # Do not accidentally include the heading of the next translated work.
        if stop.endswith("(translated; excluded)"):
            forbidden=stop.split(" (translated;")[0]
            # Full uppercase heading of next treatise must be at the beginning
            # of the excluded text, not inside the Note section.
            after=text[b:b+180]
            if not re.search(re.escape(forbidden.split(" (")[0][:10]),after,re.I):
                raise RuntimeError("Translated work boundary for Note "+letter+" shifted: "+repr(after[:100]))
        clean_sections.append("[EDITORIAL NOTE "+letter+"]\n"+excerpt.strip())
        ranges.append({"section":"Note "+letter,"start":a,"end":b,
                       "end_boundary":stop,"characters":len(excerpt)})
    # Explicitly exclude uncertain Additional Notes and all translations.
    if text[1750731:1758804].strip().upper().find("ADDITIONAL")<0:
        raise RuntimeError("Additional Notes boundary shifted")
    clean="\n\n\n".join(clean_sections).rstrip()+"\n"
    if len(ranges)!=18:raise RuntimeError("Incorrect Pusey editorial section count")
    raw=ROOT/"data/raw"/(IDENT+".txt")
    raw.parent.mkdir(parents=True,exist_ok=True)
    raw.write_text(text,encoding="utf8")
    cleaned=ROOT/"data/clean"/(IDENT+".txt")
    cleaned.parent.mkdir(parents=True,exist_ok=True)
    cleaned.write_text(clean,encoding="utf8")
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_json("data/records/"+IDENT+".json",{
       "id":IDENT,"year":1842,"title":"Introduction and Notes to Tertullian (1842)",
       "category":"Introductions","contribution":"editorial","status":"downloaded",
       "source":"Owner-supplied IA OCR; Library of Fathers Vol. X, Tertullian Vol. I (1842)",
       "archive_id":ARCHIVE_ID,"identifier":ARCHIVE_ID,
       "scan_url":"https://archive.org/details/"+ARCHIVE_ID,"text_url":URL,
       "source_title":"Tertullian, Apologetic and Practical Treatises, Library of Fathers X (1842)",
       "source_creator":"E. B. Pusey (signed preface, editorial notes); C. Dodgson (translation excluded)",
       "source_date":"1842","original_sha256":EXPECTED_SHA,
       "downloaded_utc":now,"word_count":len(clean.split()),
       "authorship_review_needed":False,
       "scope_verified":True,"content_scope":"pusey_preface_or_introduction_only",
       "extraction_boundaries":{"included_sections":ranges,
            "editorial_notes":["A","B","C","D","E","F","G","H","I","K","L","M","N","O","P","Q","R"],
            "excluded_translations":"All Tertullian treatises, translated by C. Dodgson",
            "excluded_additional_notes":"Unsigned pp. 499–502 pending corroboration"},
       "qc":"18 nonoverlapping, independently inspected segments, complete signed preface, all 17 lettered Notes; no translated treatises; OCR proofreading pending."
    })
    update_registry();update_bibliography()
    update_tracking(len(clean.split()))
    # Audit the actual Pusey-only extract lengths, not the mixed-source raw OCR.
    print("TERTULLIAN EDITORIAL IMPORT",json.dumps({
      "preface_characters":len(preface),"lettered_notes":len(EDITS),
      "clean_characters":len(clean),"words":len(clean.split()),
      "excluded_additional_notes":True
    }),flush=True)

if __name__=="__main__":
    main()
