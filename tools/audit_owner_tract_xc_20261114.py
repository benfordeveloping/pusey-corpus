#!/usr/bin/env python3
"""Audit owner-provided 1865/1866 Tract XC OCR before Pusey-only extraction.

Only a confirmed Historical Preface may enter search. Newman's Tract XC
and Keble's adjacent letter must never be indexed as Pusey's own prose.
"""
import json,re,sys,hashlib
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest
IDENT="tractxcpassages00newmuoft"
OWNER_URL="https://dn760105.eu.archive.org/0/items/tractxcpassages00newmuoft/tractxcpassages00newmuoft.txt"
def main():
    meta=harvest.get_metadata(IDENT);md=meta.get("metadata") or {}
    fname=harvest.text_filename(meta)
    possible=[("https://archive.org/download/"+quote(IDENT)+"/"+quote(fname))] if fname else []
    possible.append(OWNER_URL)
    errors=[];src=None
    for url in possible:
        try:
            with harvest.request(url,stream=True) as r:
                parts=[];size=0
                for p in r.iter_content(131072):
                    if p:parts.append(p);size+=len(p)
                    if size>24*1024*1024:raise ValueError("OCR too large")
            blob=b"".join(parts);raw,enc=harvest.decode_content(blob)
            ok,qc=harvest.assess_ocr(raw)
            if not ok:raise ValueError(qc)
            if "tract" not in raw[:30000].lower():raise ValueError("Opening lacks Tract heading")
            src=url;break
        except Exception as e:
            errors.append(type(e).__name__+": "+str(e)[:240])
    if not src:raise RuntimeError("No verified text: "+"; ".join(errors))
    def hits(pattern,area=160000,n=30,r=650):
        out=[]
        for m in re.finditer(pattern,raw[:area],re.I|re.M):
            out.append(dict(pos=m.start(),match=m.group(0)[:130],before=raw[max(0,m.start()-r):m.start()],after=raw[m.end():m.end()+r]))
            if len(out)>=n:break
        return out
    report={
       "id":"1865-historical-preface-to-tract-xc",
       "owner_url":OWNER_URL,"ocr_source":src,"archive_id":IDENT,"filename":fname,
       "metadata":{k:md.get(k) for k in ("title","creator","year","date","volume","description")},
       "sha256":hashlib.sha256(blob).hexdigest(),
       "characters":len(raw),"words":len(harvest.words(raw)),
       "encoding":enc,"quality_check":qc,
       "opening_14500":raw[:14500],
       "hits":{
          "historical_preface":hits(r"(?:HISTORICAL|HISTORY)\s+PREFACE"),
          "pusey_signature":hits(r"(?:E\.\s*B\.\s*P\.|E\.\s*B\.\s*PUSEY)"),
          "newman_tr act":hits(r"TRACT\s*(?:XC|90)\b",160000,40),
          "preface_headings":hits(r"(?im)^\s*(?:PREFACE|INTRODUCTION|TRACT\s+XC)\s*\.?\s*$"),
          "newman_name":hits(r"JOHN\s+HENRY\s+NEWMAN",160000,18),
          "keble_name":hits(r"JOHN\s+KEBLE",160000,18),
          "page_i_xliii":hits(r"(?m)^\s*(?:xliii|xlii|xli|xl|xxxix)\s*$",160000,20)
       },
       "last_2500":raw[-2500:],
       "status":"AUDIT ONLY. No Newman tract or Keble material indexed until Pusey start/end independently verified."
    }
    out=ROOT/"data/tract_xc_historical_preface_audit_20261114.json"
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("AUDIT TRACT XC",len(raw),"chars",report["words"],"words",md.get("title"),"source",src,flush=True)
    for k,v in report["hits"].items():
        print(k,[(h["pos"],h["match"]) for h in v[:25]],flush=True)

if __name__=="__main__":main()
