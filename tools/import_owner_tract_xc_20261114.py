#!/usr/bin/env python3
"""Index Pusey's 1865 Historical Preface and signed 1866 Postscript to Tract XC.

Authenticates the OCR against the previously committed SHA/boundary audit.
Excludes Newman's Tract XC and Keble's separate essay. Source edition is 1890.
"""
import csv,hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest
ID="1865-historical-preface-to-tract-xc"
ARCH="tractxcpassages00newmuoft"
AUDIT=ROOT/"data/tract_xc_historical_preface_audit_20261114.json"
SOURCE_URL="https://archive.org/download/tractxcpassages00newmuoft/tractxcpassages00newmuoft.txt"

def main():
    check=json.loads(AUDIT.read_text(encoding="utf8"))
    r=harvest.request(SOURCE_URL,stream=True);parts=[];size=0
    try:
        for part in r.iter_content(131072):
            if part:parts.append(part);size+=len(part)
            if size>20*1024*1024:raise ValueError("Unexpected oversized Tract XC OCR")
    finally:r.close()
    binary=b"".join(parts)
    raw,codec=harvest.decode_content(binary)
    digest=hashlib.sha256(binary).hexdigest()
    if digest!=check["sha256"]:
        raise ValueError("OCR changed since exact first-pass audit; re-audit before importing")
    starts=[m for m in re.finditer(r"(?im)^[ \t]*PREFACE\.[ \t]*\r?$",raw)
             if 3000<m.start()<5000 and re.search(r"A\s+QUARTER\s+of\s+a\s+century",raw[m.end():m.end()+240],re.I)]
    if len(starts)!=1:raise ValueError("Cannot uniquely identify Pusey's Historical Preface start: "+str(len(starts)))
    start=starts[0].start()
    rest=raw[start:]
    # The original 1865 text signs Advent and then an 1866 second-edition postscript;
    # keep both Pusey-written parts and no following Newman tract.
    signed=list(re.finditer(r"E\.\s*B\.\s*P\.\s*Easter,\s*1866\.",rest,re.I))
    if len(signed)!=1:raise ValueError("Cannot uniquely identify Pusey postscript signature")
    end=start+signed[0].end()
    selection=raw[start:end].replace("\r\n","\n").replace("\r","\n")
    if not re.search(r"POSTSCR(?:IPT|WT)",selection,re.I):raise ValueError("Postscript absent")
    if not re.search(r"E\.\s*B\.\s*P\.\s*Advent,\s*186[b5]\.",selection,re.I):
        raise ValueError("First preface signature not found; source may have changed")
    tail=raw[end:end+1700]
    if not re.search(r"No\.\s*90\.\]\s*TRACTS\s+FOR",tail,re.I|re.S):
        raise ValueError("Newman Tract XC boundary not following Pusey postscript")
    words=len(harvest.words(selection))
    if not 9500<words<24000 or not 70000<end<98000:
        raise ValueError("Tract XC Pusey-only portion implausible: "+str((words,start,end)))
    works=json.loads((ROOT/"bibliography.json").read_text(encoding="utf8"))
    w=next(x for x in works["works"] if x["id"]==ID)
    w["notes"]="Pusey's signed Historical Preface (Advent 1865), plus his 1866 second-edition Postscript (Easter 1866). Source is the 1890 composite reprint; Newman Tract XC and Keble's essay strictly excluded. The brief 1890 Advertisement before the PREFACE is also excluded."
    w["source_edition_year"]=1890
    w["source_edition_id"]=ARCH
    harvest.RAW.mkdir(parents=True,exist_ok=True)
    harvest.CLEAN.mkdir(parents=True,exist_ok=True)
    (harvest.RAW/(ID+".txt")).write_text(selection.strip()+"\n",encoding="utf8")
    cleaned=harvest.clean_ocr(selection)
    (harvest.CLEAN/(ID+".txt")).write_text(cleaned,encoding="utf8")
    harvest.write_record(w,{
       "status":"downloaded","source":"Owner-provided 1890 Internet Archive composite scan, Pusey signed Preface and Postscript only",
       "identifier":ARCH,"scan_url":"https://archive.org/details/"+ARCH,
       "text_url":SOURCE_URL,"source_edition_year":1890,
       "preface_date":"Advent 1865","postscript_date":"Easter 1866",
       "word_count":len(harvest.words(cleaned)),"source_ocr_sha256":digest,
       "scope_verified":True,"content_scope":"pusey_authored_preface_and_postscript_only",
       "authorship_review_needed":False,
       "extraction_boundaries":{"source_char_start":start,"source_char_end":end,
          "start_heading":"PREFACE. A QUARTER of a century has all but elapsed",
          "first_signoff":"E. B. P. / Advent, 1865 (OCR says 186b)",
          "postscript_signoff":"E. B. P. / Easter, 1866",
          "excluded_preceding":"1890 Advertisement",
          "excluded_following":"No. 90.] TRACTS FOR THE TIMES — Newman's Tract XC, then Keble essay"},
       "qc":"Signatures, distinct Postscript, following Newman heading checked against audited SHA; OCR not proofread."
    })
    regpath=ROOT/"data/source_registry.csv"
    with regpath.open(encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    row=next(x for x in rows if x["id"]==ID)
    row.update(verification_status="verified_pusey_preface_and_postscript_only",archive_id=ARCH,
       scan_url="https://archive.org/details/"+ARCH,ocr_url=SOURCE_URL,ocr_filename="tractxcpassages00newmuoft.txt",
       ia_title="Tract XC: On Certain Passages in the XXXIX Articles (Newman; historical preface by E. B. Pusey; Keble essay)",
       ia_creator="E. B. Pusey (Preface, Postscript); J. H. Newman and John Keble excluded",ia_year="1890",
       notes="Pusey signed 1865 Preface and 1866 Postscript ONLY, "+str(words)+" OCR words, source char range "+str(start)+"–"+str(end)+". Source reprint 1890. Newman and Keble excluded.")
    with regpath.open("w",encoding="utf8",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");wr.writeheader();wr.writerows(rows)
    ledgerpath=ROOT/"data/owner_source_ledger_20261113.json"
    ledger=json.loads(ledgerpath.read_text(encoding="utf8"))
    obj={"bibliography_id":ID,"label":"Historical Preface to Tract XC (1865) and second-edition Postscript (1866)",
      "user_supplied_url":"https://dn760105.eu.archive.org/0/items/tractxcpassages00newmuoft/tractxcpassages00newmuoft.txt",
      "github_source_url":"https://archive.org/details/"+ARCH,
      "ingestion_status":"verified_pusey_preface_and_postscript_only",
      "github_raw_path":"data/raw/"+ID+".txt","github_clean_path":"data/clean/"+ID+".txt",
      "source_notes":"SHA-checked 1890 composite OCR. Extract Pusey-only section from PREFACE through E.B.P. Easter 1866; exclude Newman, Keble, and preceding Advertisement."}
    found=next((x for x in ledger["entries"] if x.get("bibliography_id")==ID),None)
    if found:found.update(obj)
    else:ledger["entries"].append(obj)
    ledger["updated_utc"]="2026-11-14"
    ledgerpath.write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (ROOT/"bibliography.json").write_text(json.dumps(works,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    harvest.csv_report(works["works"])
    print("IMPORTED PUSEY-ONLY TRACT XC HISTORICAL PREFACE AND 1866 POSTSCRIPT",words,"words",start,end,flush=True)

if __name__=="__main__":main()
