#!/usr/bin/env python3
"""Audit actual Library of Fathers 47 scan for E.B. Pusey's 1881 continuation.

P.E. Pusey's original preface (roman i–xxxvi) is NOT E.B. Pusey text.
Only the E.B.P. explanatory bracket and his subsequent continuation from
xxxvii to Christmas Eve 1881 may be indexed after verifying all boundaries.
"""
import json,re,sys,hashlib
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import harvest
SOURCES=["fivetomesagainst0047cyri","fivetomesagains00cyrigoog","47ALibraryOfFathersOfTheHolyCatholicV47"]
PATS={
  "son_finished_preface":r"(?:my|MY)\s+son\s+had\s+had",
  "larger_whole":r"fragments\s+of\s+a\s+larger\s+whole",
  "special_form":r"special\s+form\s+of\s+the\s+disease",
  "nestorius":r"Nestorius",
  "e_b_p_signatures":r"E\.\s*B\.\s*P\.",
  "christmas_eve_1881":r"Christmas\s+Eve,\s*1881",
  "cyril_five_tomes":r"(?:FIVE\s+TOMES\s+AGAINST\s+NESTORIUS|FIRST\s+TOME)",
  "main_text_start":r"(?m)^\s*(?:TOME\s+I\.|TOME\s+I\b|FIVE\s+TOMES\s+AGAINST\s+NESTORIUS|BOOK\s+I\b)",
  "pages_roman":r"(?im)^\s*(?:xxxvi|xxxvii|xxxviii|civ|cv)\s*$"
}
def inspect(ident):
    mdall=harvest.get_metadata(ident);md=mdall.get("metadata") or {}
    fname=harvest.text_filename(mdall)
    if not fname:raise ValueError("No plain-text OCR in "+ident)
    url="https://archive.org/download/"+quote(ident)+"/"+quote(fname,safe="/")
    resp=harvest.request(url,stream=True);b=[];size=0
    try:
        for x in resp.iter_content(131072):
            if not x:continue
            b.append(x);size+=len(x)
            if size>28*1024*1024:raise ValueError("Too much OCR")
    finally:resp.close()
    blob=b"".join(b);raw,enc=harvest.decode_content(blob)
    if not re.search(r"Cyril|Nestorius",str(md.get("title","")),re.I):
        raise ValueError("Wrong title: "+str(md.get("title","")))
    matches={}
    for name,pattern in PATS.items():
        hs=[]
        for m in re.finditer(pattern,raw,re.I|re.M):
            hs.append(dict(char=m.start(),match=m.group(0),before=raw[max(0,m.start()-700):m.start()],after=raw[m.end():m.end()+1200]))
            if len(hs)>=24:break
        matches[name]=hs
    return dict(archive_id=ident,ocr_url=url,ocr_filename=fname,sha256=hashlib.sha256(blob).hexdigest(),
        encoding=enc,characters=len(raw),words=len(harvest.words(raw)),
        metadata={k:md.get(k) for k in ("title","year","date","creator","imagecount")},
        opening=raw[:3500],matches=matches,final_1000=raw[-1000:],
        indexing_status="AUDIT ONLY — no joint P.E. Pusey text indexed")

def main():
    reports={}
    for id in SOURCES:
        try:
            x=inspect(id);reports[id]=x
            print("VERIFIED",id,x["words"],"words",flush=True)
            for k,v in x["matches"].items():
                print(k,[p["char"] for p in v[:12]],flush=True)
        except Exception as exc:
            reports[id]={"archive_id":id,"error":type(exc).__name__+": "+str(exc)}
            print("REJECT",id,repr(exc),flush=True)
    path=ROOT/"data/lfc47_cyril_pusey_authorship_audit_20261114.json"
    path.write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    if not any("matches" in v and v["matches"]["christmas_eve_1881"] for v in reports.values()):
        raise RuntimeError("No verified source contained the signed 1881 Pusey ending")

if __name__=="__main__":main()
