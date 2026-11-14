#!/usr/bin/env python3
"""Diagnostic anchors and segment status for requested US1/US2 Madan entries."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import sermon_library as sl
TARGETS=['m065','m110','m144','m166','m177','m137','m142','m136','m119','m107','m105']
TITLE_PATTERNS={
 'US1':[
  ("eucharist comfort",r"THE\s+HOLY\s+EUCHARIST\s+A\s+COMFORT\s+TO\s+THE\s+PENITENT"),
  ("absolution",r"ENTIRE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT"),
  ("rule",r"THE\s+RULE\s+OF\s+FAITH"),
  ("justification",r"(?im)^[ \t]*JUSTIFICATION[,.\s]*$"),
  ("all faith",r"ALL\s+FAITH\s+THE\s+GIFT\s+OF\s+GOD"),
  ("presence",r"THE\s+PRESENCE\s+OF\s+CHRIST\s+IN\s+THE\s+HOLY\s+EUCHARIST"),
  ("preface standalone",r"(?im)^[ \t]*PREFACE[,.\s]*$"),
  ("preface advertisement",r"(?im)^[ \t]*ADVERTISEMENT\s+TO\s+THE\s+(?:THIRD|SECOND|FOURTH)\s+EDITION"),
  ("independent title",r"(?im)^[ \t]*(?:A\s+SERMON|THE\s+HOLY\s+EUCHARIST|ENTIRE\s+ABSOLUTION|THE\s+RULE\s+OF\s+FAITH|JUSTIFICATION|ALL\s+FAITH)"),
  ("sermon roman",r"(?im)^[ \t]*S(?:ERMON|EKMON|EEMON|EEMOST)[ \t]+[IVXLCDM]{1,9}\s*[,.]?[ \t]*$")
 ],
 'US2':[
  ("sermon roman",r"(?im)^[ \t]*S(?:ERMON|EKMON|EEMON|EEMOST)[ \t]+[IVXLCDM]{1,9}\s*[,.]?[ \t]*$"),
  ("atonement",r"(?im)^.{0,24}[Dd]octrine\s+of\s+the\s+Atonement[,.\s]*$"),
  ("judgment",r"(?im)^.{0,28}[Tt]error\s+of\s+the\s+[Dd]ay\s+of\s+[Jj]udg"),
  ("gospel",r"(?im)^.{0,28}[Tt]he\s+[Gg]ospel\s+could\s+not"),
  ("world",r"(?im)^.{0,28}[Tt]he\s+[Ww]orld[,]?\s+an\s+ever"),
 ]
}
def short(t,start,before=350,after=550):
 return t[max(0,start-before):start+after].replace("\r","").replace("\n"," | ")
def main():
 src=sl.load_sources(ROOT);rows,_=sl.find_entries(ROOT)
 wanted={e["id"]:e for e in rows if e["id"] in TARGETS}
 report={"source_meta":{},"targets":{},"matches":{}}
 for code in ["US1","US2"]:
  s=src[code];t=s["t"]
  report["source_meta"][code]={"characters":len(t),"toc":s["toc"],"cutoff":s["cutoff"],
   "headings":[{**h,"context":short(t,h["at"],70,180)} for h in s["heads"]][:180]}
  matches={}
  for label,pat in TITLE_PATTERNS[code]:
   entries=[]
   for m in re.finditer(pat,t,re.I|re.M):
    entries.append({"at":m.start(),"text":m.group(0)[:115],"context":short(t,m.start(),230,440)})
    if len(entries)>=75:break
   matches[label]=entries
  report["matches"][code]=matches
 for id,e in wanted.items():
  t=src[e.get("code") or ("US1" if "US1" in e["refs"][0] else "US2")]["t"]
  report["targets"][id]={k:e.get(k) for k in ("id","title","scripture","refs","status","reason","code","start","end","characters","match_score","method","word_count")}
  if isinstance(e.get("start"),int):report["targets"][id]["start_context"]=short(t,e["start"],1300,2400)
  if isinstance(e.get("end"),int):report["targets"][id]["end_context"]=short(t,e["end"],900,1400)
 out=ROOT/"data/sermons/owner_us1_us2_boundary_audit_20261114.json"
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print("SERMON DIAGNOSTIC",json.dumps({key:{k:v for k,v in row.items() if k not in ("start_context","end_context")} for key,row in report["targets"].items()},ensure_ascii=False),flush=True)
 print("MATCH COUNTS",json.dumps({code:{key:len(items) for key,items in tests.items()} for code,tests in report["matches"].items()}),flush=True)
if __name__=="__main__":main()
