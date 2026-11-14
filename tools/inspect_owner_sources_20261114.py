#!/usr/bin/env python3
"""Inspect owner-supplied Internet Archive OCRs before any corpus replacement.

Read-only against corpus text. Writes only a compact, auditable inspection report.
"""
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

URLS = {
 "university_i": "https://archive.org/stream/a605354300puseuoft/a605354300puseuoft_djvu.txt",
 "minor_first": "https://archive.org/stream/minorprophetscom00puse/minorprophetscom00puse_djvu.txt",
 "minor_second": "https://archive.org/stream/minorprophetscom00puse_0/minorprophetscom00puse_0_djvu.txt",
 "tertullian": "https://archive.org/stream/10ALibraryOfFathersOfTheHolyCatholicV10/10ALibraryOfFathersOfTheHolyCatholicV10_djvu.txt"
}

def download(url):
    alternatives = [url]
    if "/stream/" in url:
        parts = url.split("/stream/", 1)[1].split("/")
        alternatives.append("https://archive.org/download/" + "/".join(parts))
    last = None
    for endpoint in alternatives:
        for attempt in range(3):
            try:
                req = urllib.request.Request(endpoint, headers={
                    "User-Agent": "Pusey-Corpus-Research/1.0 (public domain scholarly transcription; GitHub Actions)",
                    "Accept": "text/plain,*/*"
                })
                with urllib.request.urlopen(req, timeout=120) as response:
                    payload = response.read()
                if len(payload) < 20_000:
                    raise RuntimeError("Only %s bytes returned" % len(payload))
                text = payload.decode("utf-8-sig", errors="replace")
                if "<html" in text[:1500].lower() or "captcha" in text[:800].lower():
                    raise RuntimeError("Returned HTML rather than OCR text")
                return endpoint, payload, text
            except Exception as exc:
                last = str(exc)
                time.sleep(2*(attempt+1))
    raise RuntimeError("Cannot fetch "+url+": "+str(last))

def near(text,term,lower=0,limit=5):
    out=[]
    for m in re.finditer(term,text,re.I|re.M):
        if m.start() < lower:continue
        out.append({"offset":m.start(),"text":re.sub(r"\s+"," ",text[max(lower,m.start()-100):m.end()+190])[:310]})
        if len(out)>=limit:break
    return out

def inspect_source(key,url):
    endpoint,payload,txt=download(url)
    findings={
        "requested_url":url,"fetched_url":endpoint,
        "size_bytes":len(payload),"characters":len(txt),
        "sha256":hashlib.sha256(payload).hexdigest(),
        "word_count":len(txt.split()),
        "head":re.sub(r"\s+"," ",txt[:2000])[:470],
        "tail":re.sub(r"\s+"," ",txt[-1100:])[-420:],
        "pusey_mentions":len(re.findall(r"\bPusey\b",txt,re.I))
    }
    if key.startswith("minor"):
        findings["volume_labels"]=near(txt,r"\b(?:VOLUME|VOL\.)\s*(?:I{1,3}|1|2|3)\b",0,9)
        findings["title_mentions"]=near(txt,r"MINOR\s+PROPHETS",0,8)
        findings["prophet_headings"]={p:near(txt,r"(?m)^\s*(?:THE\s+BOOK\s+OF\s+)?"+p+r"\b",0,3) for p in (
            "HOSEA","JOEL","AMOS","OBADIAH","JONAH","MICAH","NAHUM",
            "HABAKKUK","ZEPHANIAH","HAGGAI","ZECHARIAH","MALACHI")}
        findings["printed_pages"]=near(txt,r"\b(?:PREFACE|CONTENTS|INTRODUCTION)\b",0,8)
    elif key=="university_i":
        findings["toc_headings"]=near(txt,r"SERMON\s+(?:I|II|III|IV|V|VI|VII|VIII|IX)\b",0,12)
        findings["dedication_and_title"]=near(txt,r"NINE\s+SERMONS|UNIVERSITY OF OXFORD|1859",0,7)
        findings["sermon_markers"]=len(re.findall(r"SERMON\s+(?:I|II|III|IV|V|VI|VII|VIII|IX)\b",txt,re.I))
    elif key=="tertullian":
        findings["preface_headings"]=near(txt,r"(?m)^\s*PREFACE\s*\.",0,4)
        findings["pusey_signatures"]=near(txt,r"E\s*\.\s*B\s*\.\s*P\s*\.",0,6)
        findings["note_headings"]={}
        for letter in list("ABCDEFGHI")+list("KLMNOPQR"):
            p=r"(?m)^\s*NOTE\s+"+letter+r"\s*[\.\-,]"
            hits=list(re.finditer(p,txt,re.I|re.M))
            findings["note_headings"][letter]=[
                {"offset":m.start(),"context":re.sub(r"\s+"," ",txt[m.start():m.start()+160])[:150]}
                for m in hits[:12] ]
        findings["additional_notes"]=near(txt,r"ADDITIONAL\s+NOTES",0,8)
        findings["other_sections"]=near(txt,r"THE\s+BOOK\s+OF\s+APOLOGY|OF\s+THE\s+WITNESS\s+OF\s+THE\s+SOUL|INDEX",0,5)
    return findings

def main():
    out={}
    for name,url in URLS.items():
        try:
            result=inspect_source(name,url)
            out[name]=result
            print(name, "OK",result["size_bytes"],"bytes",result["word_count"],"words",result["sha256"][:16],flush=True)
        except Exception as exc:
            out[name]={"requested_url":url,"status":"FETCH_ERROR","error":str(exc)}
            print(name,"ERROR",str(exc),flush=True)
    if all(v.get("sha256") for v in out.values()):
        out["comparison"]={
         "minor_distinct":out["minor_first"]["sha256"]!=out["minor_second"]["sha256"],
         "minor_lengths":[out["minor_first"]["word_count"],out["minor_second"]["word_count"]]
        }
    path=Path("data/owner_ocr_inspection_20261114.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INSPECTION COMPLETE",json.dumps({k:{"status":v.get("status","OK"),"words":v.get("word_count")} for k,v in out.items() if k!="comparison"}),flush=True)

if __name__=="__main__":
    main()
