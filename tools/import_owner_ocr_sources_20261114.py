#!/usr/bin/env python3
"""Import owner-verified University Sermons I and the two Minor Prophets OCR volumes.

The two 1950 Baker Book House Minor Prophets volumes form ONE bibliography item.
Leave the original, pre-correction OCR versions recoverable in git history.
Do not import Tertullian until the editorial-note boundaries are audited.
"""
import csv
import datetime
import hashlib
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
UNIV="1859-university-sermons-vol-i-nine-sermons"
PROPHETS="1860-the-minor-prophets-with-commentary"
URLS={
 "university":"https://archive.org/stream/a605354300puseuoft/a605354300puseuoft_djvu.txt",
 "prophets_1":"https://archive.org/stream/minorprophetscom00puse/minorprophetscom00puse_djvu.txt",
 "prophets_2":"https://archive.org/stream/minorprophetscom00puse_0/minorprophetscom00puse_0_djvu.txt",
}
EXPECTED={
 "university":"f09c18fc38cea954789af72d2215731ef234d5593725baf119fc64d52f164fda",
 "prophets_1":"99e300fba711bfdd1dfb341efb6c8f59b09de819d01c5e2037cd0a3e0c8c87dd",
 "prophets_2":"5ab42cfef11c1d9218919e000bc01a5cce65b21c3d325cb8e16b2525811bc612",
}
REPORT=ROOT/"data"/"owner_ocr_inspection_20261114.json"

def download(key,url):
    endpoints=[url]
    if "/stream/" in url:
        endpoints.append(url.replace("/stream/","/download/",1))
    last=None
    for endpoint in endpoints:
        for attempt in range(3):
            try:
                req=urllib.request.Request(endpoint,headers={
                    "User-Agent":"Pusey-Corpus-Research/1.0 (public-domain research)",
                    "Accept":"text/plain,*/*"})
                with urllib.request.urlopen(req,timeout=125) as res:raw=res.read()
                sha=hashlib.sha256(raw).hexdigest()
                if sha!=EXPECTED[key]:
                    raise ValueError("Source SHA differs from the inspected owner URL for "+key+
                                     ": expected "+EXPECTED[key]+", received "+sha)
                txt=raw.decode("utf-8-sig")
                return txt,raw
            except Exception as exc:
                last=exc
                if isinstance(exc,ValueError):raise
                time.sleep(2*(attempt+1))
    raise RuntimeError("Could not fetch "+key+": "+str(last))

def path(name):
    return ROOT/name

def dump_json(file,data):
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")

def update_registry(data):
    filename=path("data/source_registry.csv")
    with filename.open(newline="",encoding="utf8") as fh:
        reader=csv.DictReader(fh)
        headers=reader.fieldnames
        rows=list(reader)
    for row in rows:
        if row["id"]==UNIV:
            row.update({
                "verification_status":"verified_owner_replacement_ocr",
                "archive_id":"a605354300puseuoft",
                "scan_url":"https://archive.org/details/a605354300puseuoft",
                "ocr_url":URLS["university"],
                "ocr_filename":"a605354300puseuoft_djvu.txt",
                "ia_title":"University Sermons, Vol. I: Nine Sermons, preached before the University of Oxford",
                "ia_creator":"Edward Bouverie Pusey",
                "ia_year":"1859",
                "notes":"Owner-supplied new, better OCR, SHA-256 "+EXPECTED["university"]+
                    ". Replaces the earlier ninesermonsprea00pusegoog source (retained in git history). "
                    "This scan's edition date needs detailed verification; 1859 is the work's bibliographical year. "
                    "All nine sermons' contents are visible. Source was inspected before import."
            })
        elif row["id"]==PROPHETS:
            row.update({
                "verification_status":"verified_two_owner_ocr_volumes",
                "archive_id":"minorprophetscom00puse;minorprophetscom00puse_0",
                "scan_url":"https://archive.org/details/minorprophetscom00puse",
                "ocr_url":URLS["prophets_1"]+" ; "+URLS["prophets_2"],
                "ocr_filename":"minorprophetscom00puse_djvu.txt ; minorprophetscom00puse_0_djvu.txt",
                "ia_title":"The Minor Prophets: a Commentary, Explanatory and Practical, 2 volumes",
                "ia_creator":"Edward Bouverie Pusey",
                "ia_year":"1950",
                "notes":"TWO OWNER-SUPPLIED 1950 Baker Book House reprint OCRs joined as ONE Pusey commentary. "
                    "Volume I covers Hosea–Jonah; II covers Micah–Malachi. "
                    "Exact URLs: "+URLS["prophets_1"]+" AND "+URLS["prophets_2"]+
                    "; SHA-256 "+EXPECTED["prophets_1"]+" and "+EXPECTED["prophets_2"]+
                    ". 1950 is source-reprint date, not Pusey's work date. Separate originals in data/raw."
            })
    with filename.open("w",newline="",encoding="utf8") as fh:
        writer=csv.DictWriter(fh,fieldnames=headers,lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def update_bibliography():
    filename=path("bibliography.json")
    obj=json.loads(filename.read_text(encoding="utf8"))
    for item in obj["works"]:
        if item["id"]==UNIV:
            item["source_edition_id"]="a605354300puseuoft"
            item["source_document_url"]="https://archive.org/details/a605354300puseuoft"
            item["notes"]=("Owner-supplied clearer OCR of all nine sermons replaced "
                           "ninesermonsprea00pusegoog. The new scan is a later 'New Edition'; "
                           "verify its exact printing date before labelling the source edition.")
        elif item["id"]==PROPHETS:
            item["source_edition_year"]=1950
            item["source_edition_note"]="Baker Book House 1950 reprint; original composition/publication belongs to the 1860s"
            item["source_components"]=[
                {"name":"Volume I","expected_contents":"Hosea, Joel, Amos, Obadiah, Jonah",
                 "verification_status":"verified_owner_supplied_ocr",
                 "source_id":"minorprophetscom00puse","ocr_url":URLS["prophets_1"]},
                {"name":"Volume II","expected_contents":"Micah, Nahum, Habakkuk, Zephaniah, Haggai, Zechariah, Malachi",
                 "verification_status":"verified_owner_supplied_ocr",
                 "source_id":"minorprophetscom00puse_0","ocr_url":URLS["prophets_2"]}
            ]
    dump_json(filename,obj)

def update_harvest(wordcounts):
    filename=path("data/harvest_report.csv")
    lines=filename.read_text(encoding="utf8").splitlines()
    reader=csv.reader(lines)
    rows=list(reader)
    header=rows[0] if rows else []
    for i,row in enumerate(rows[1:],1):
        if len(row)<5:continue
        if "University Sermons, Vol. I" in row[1]:
            row[4]="downloaded"
            if len(row)>5:row[5]=str(wordcounts["university"])
            if len(row)>7:row[7]="Owner replacement OCR: a605354300puseuoft; exact inspected SHA; original source preserved in git history"
        elif "Minor Prophets with a Commentary" in row[1]:
            row[4]="downloaded"
            if len(row)>5:row[5]=str(wordcounts["prophets"])
            if len(row)>7:row[7]="Both 1950 Baker House volumes; Hosea–Jonah and Micah–Malachi; single combined record"
    with filename.open("w",encoding="utf8",newline="") as fh:
        writer=csv.writer(fh,lineterminator="\n")
        writer.writerows(rows)

def main():
    inspected=json.loads(REPORT.read_text(encoding="utf8"))
    for k,expected in EXPECTED.items():
        lookup={"university":"university_i","prophets_1":"minor_first","prophets_2":"minor_second"}[k]
        if inspected[lookup].get("sha256")!=expected:
            raise RuntimeError("Inspection audit does not match "+k)
    texts={}
    for k,url in URLS.items():
        txt,raw=download(k,url)
        texts[k]=txt
        print("OWNER OCR VERIFIED:",k,len(raw),"bytes",len(txt.split()),"words",flush=True)
    univ=texts["university"]
    p1=texts["prophets_1"]
    p2=texts["prophets_2"]
    assert "NINE SERMONS" in univ[:9000].upper()
    assert "SERMON I" in univ[:90000].upper()
    assert "SERMON IX" in univ[:90000].upper()
    assert "HOSEA" in p1[:25000].upper() and "JONAH" in p1[:25000].upper()
    assert "END OF VOL. I" in p1[-20000:].upper()
    assert "MICAH" in p2[:17000].upper() and "MALACHI" in p2[:19000].upper()
    assert "1950" in p1[:12000] and "1950" in p2[:12000]
    joined=(
        "[VOLUME I — Hosea, Joel, Amos, Obadiah, Jonah]\n"
        "[Baker Book House 1950 reprint; Archive OCR: "+URLS["prophets_1"]+"]\n\n"+
        p1.strip()+
        "\n\n\n[END VOLUME I]\n\n\n"+
        "[VOLUME II — Micah, Nahum, Habakkuk, Zephaniah, Haggai, Zechariah, Malachi]\n"
        "[Baker Book House 1950 reprint; Archive OCR: "+URLS["prophets_2"]+"]\n\n"+
        p2.strip()+"\n"
    )
    # Raw files hold exact OCR text; clean retains Pusey-authored original
    # content without aggressive or unreviewed spelling fixes.
    for kind,blob in (
        ("data/raw/"+UNIV+".txt",univ),
        ("data/clean/"+UNIV+".txt",univ),
        ("data/raw/"+PROPHETS+"-vol-i.txt",p1),
        ("data/raw/"+PROPHETS+"-vol-ii.txt",p2),
        ("data/raw/"+PROPHETS+".txt",joined),
        ("data/clean/"+PROPHETS+".txt",joined)
    ):
        dest=path(kind)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(blob,encoding="utf8")
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_univ={
       "id":UNIV,"year":1859,"title":"University Sermons, Vol. I: Nine Sermons",
       "category":"Sermons","contribution":"authored","status":"downloaded",
       "source":"Owner-supplied Internet Archive OCR (improved scan)",
       "archive_id":"a605354300puseuoft","identifier":"a605354300puseuoft",
       "scan_url":"https://archive.org/details/a605354300puseuoft",
       "text_url":URLS["university"],"source_title":"Nine Sermons, preached before the University of Oxford",
       "source_creator":"E. B. Pusey",
       "bibliographical_year":1859,"source_edition_year":None,
       "source_edition_year_status":"New Edition on title page; precise year not yet verified",
       "previous_ocr_id":"ninesermonsprea00pusegoog",
       "original_sha256":EXPECTED["university"],"downloaded_utc":now,
       "word_count":len(univ.split()),"authorship_review_needed":False,
       "volume_review_needed":False,
       "qc":"Nine sermons visible in contents; newer source chosen by owner. OCR requires proofreading."
    }
    dump_json(path("data/records/"+UNIV+".json"),new_univ)
    dump_json(path("data/records/"+PROPHETS+".json"),{
       "id":PROPHETS,"year":1860,"title":"The Minor Prophets with a Commentary",
       "category":"Commentaries","contribution":"authored","status":"downloaded",
       "source":"Two owner-supplied Archive OCR volumes combined in canonical prophet order",
       "archive_id":"minorprophetscom00puse;minorprophetscom00puse_0",
       "scan_url":"https://archive.org/details/minorprophetscom00puse",
       "text_url":URLS["prophets_1"]+" ; "+URLS["prophets_2"],
       "source_creator":"E. B. Pusey",
       "bibliographical_year":1860,"source_edition_year":1950,
       "source_edition_note":"Baker Book House 1950 reprint of nineteenth-century commentary",
       "source_volumes":[
         {"volume":"I","contents":"Hosea, Joel, Amos, Obadiah, Jonah",
          "scan_url":"https://archive.org/details/minorprophetscom00puse",
          "text_url":URLS["prophets_1"],"sha256":EXPECTED["prophets_1"],"words":len(p1.split())},
         {"volume":"II","contents":"Micah, Nahum, Habakkuk, Zephaniah, Haggai, Zechariah, Malachi",
          "scan_url":"https://archive.org/details/minorprophetscom00puse_0",
          "text_url":URLS["prophets_2"],"sha256":EXPECTED["prophets_2"],"words":len(p2.split())}
       ],
       "original_sha256_merged":hashlib.sha256(joined.encode("utf8")).hexdigest(),
       "word_count":len(joined.split()),"downloaded_utc":now,
       "authorship_review_needed":False,"volume_review_needed":False,
       "qc":"Both complete physical volumes from separately inspected IA scans; no OCR proofreading yet."
    })
    update_registry({});update_bibliography()
    update_harvest({"university":len(univ.split()),"prophets":len(joined.split())})
    print("OWNER OCR IMPORT SUCCESS",json.dumps({
        "university_words":len(univ.split()),"minor_prophets_words":len(joined.split()),
        "minor_volumes":2,"minor_bibliography_items":1
    }),flush=True)

if __name__=="__main__":
    main()
