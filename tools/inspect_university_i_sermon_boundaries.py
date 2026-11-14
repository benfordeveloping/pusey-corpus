#!/usr/bin/env python3
"""Locate the nine individual sermons in owner-replaced University Sermons I OCR."""
import json
import re
from pathlib import Path

slug="1859-university-sermons-vol-i-nine-sermons"
text=Path("data/clean",slug+".txt").read_text(encoding="utf8")
terms={
 "I Holy Eucharist comfort":r"HOLY\s+EUCHARIST\s+A\s+COMFORT",
 "II/III Absolution penitent":r"ENTIRE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT",
 "IV Presence in Eucharist":r"PRESENCE\s+OF\s+CHRIST\s+IN\s+THE\s+HOLY\s+EUCHARIST",
 "V Justification":r"(?m)^\s*JUSTIFICATION\s*[\.,]?\s*$",
 "VI Rule of Faith":r"THE\s+RULE\s+OF\s+FAITH",
 "VII All faith the gift":r"ALL\s+FAITH\s+THE\s+GIFT\s+OF\s+GOD",
 "VIII Real faith entire":r"REAL\s+FAITH\s+ENTIRE",
 "IX Patience Confidence":r"PATIENCE\s+AND\s+CONFIDENCE",
}
def clip(p,n=190):
 return re.sub(r"\s+"," ",text[max(0,p-n):p+n])[:2*n]
report={"source":slug,"characters":len(text),"terms":{},"heads":[]}
for label,p in terms.items():
 matches=list(re.finditer(p,text,re.I|re.M))
 report["terms"][label]=[{"at":m.start(),"context":clip(m.start())} for m in matches[:24]]
for m in re.finditer(r"(?im)^[ \t]*S(?:ERMON|EKMON|EEMON|EEMOST)[ \t]+([IVXLCDM]{1,9})\s*[.,]?[ \t]*$",text,re.M):
 report["heads"].append({"num":m.group(1),"at":m.start(),"context":clip(m.start(),150)})
report["heads"]=report["heads"][:120]
report["suggested_cutoff"]=35000
Path("data/sermons").mkdir(parents=True,exist_ok=True)
Path("data/sermons/university_i_headings_audit.json").write_text(
 json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("UNIVERSITY I AUDIT",len(text),"characters",len(report["heads"]),"numbered headings")
for name,results in report["terms"].items():
 print("US1",name,len(results),[x["at"] for x in results[:8]])
