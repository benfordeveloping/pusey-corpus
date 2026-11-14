#!/usr/bin/env python3
"""Inspect all editorial Note A–R cut lines without indexing translated Tertullian."""
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

URL="https://archive.org/download/10ALibraryOfFathersOfTheHolyCatholicV10/10ALibraryOfFathersOfTheHolyCatholicV10_djvu.txt"
INSPECTED="3726854cad7ce4716791750d72e6e218412cecb65dbb9f0f40bf3a5d4f2a8171"

def download():
 for url in [URL,URL.replace("/download/","/stream/")]:
  for attempt in range(3):
   try:
    req=urllib.request.Request(url,headers={"User-Agent":"Pusey-Corpus-Research/1.0","Accept":"text/plain"})
    with urllib.request.urlopen(req,timeout=120) as r:raw=r.read()
    if raw[:200].lstrip().lower().startswith((b"<!doctype html",b"<html")):
     raise ValueError("Archive served HTML instead of OCR")
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=INSPECTED: raise ValueError("OCR text hash changed "+sha+" vs "+INSPECTED)
    return raw.decode("utf-8-sig")
   except Exception as e:
    print("retry",attempt,url,str(e),flush=True)
    time.sleep(2)
 raise RuntimeError("Could not obtain same text as prior inspected Tertullian OCR")

def snippet(s,p,r=160):
 return re.sub(r"\s+"," ",s[max(0,p-r):p+r])[:r*2]

def main():
 t=download()
 report={"ocr_chars":len(t),"sha256":INSPECTED,
    "preface":{"opening":snippet(t,6955,180),"signature":snippet(t,61027,220),"after":snippet(t,62000,240)}}
 regions=[
   ("NOTES_A_B_C_D",405000,515000),
   ("NOTE_E",670000,700000),
   ("NOTE_F",878000,920000),
   ("NOTE_G",974000,1045000),
   ("NOTES_H_I",1120000,1172000),
   ("NOTES_K_L_M",1260000,1395000),
   ("NOTE_N",1460000,1495000),
   ("NOTE_O",1500000,1545000),
   ("NOTES_P_Q_R_ADDITIONAL",1660000,1765000)
 ]
 for name,start,end in regions:
  block=t[start:end]
  heads=[]
  # Printed headings are often spaced or OCR-corrupted; list all headings
  # in the likely print-page transition regions, not inline footnote mentions.
  for m in re.finditer(r"(?m)^[ \t]*[A-Za-z][^\n]{2,95}[ \t]*$",block):
   line=" ".join(m.group(0).split())
   letters=[c for c in line if c.isalpha()]
   up=sum(c.isupper() for c in letters)
   if len(letters)<4 or (up/len(letters)<0.80 and not re.search(r"(?i)note\s+[a-r]\b",line)):continue
   if len(line)>90:continue
   if re.search(r"(?i)Digitized|google|university|london|oxford|rivington",line):continue
   p=start+m.start()
   if re.search(r"(?i)note|millen|witness|of public|of baptism|of prayer|of patience|of repentance|his wife|prescription|index|addit|church|image",line):
    heads.append({"at":p,"heading":line,"context":snippet(t,p,80)})
  report[name]={"span":[start,end],"candidate_headings":heads[:90],"candidate_count":len(heads)}
  print(name,"candidate headings",len(heads),flush=True)
 # Locate the exact opening of the translated works after editorial notes.
 # They are hard STOP markers: never include translated Tertullian with Pusey.
 critical={
  "G_to_Of_Prayer":(r"(?im)^\s*OF\s+PRAYER\s*[\.,]?\s*$",980000,1130000),
  "M_to_First_Wife":(r"(?im)^\s*THE\s+FIRST\s+BOOK\s+TO\s+HIS\s+WIFE\s*[\.,]?\s*$",1310000,1475000),
  "D_to_Witness":(r"(?im)^\s*OF\s+THE\s+WITNESS\s+OF\s+THE\s+SOUL\s*[\.,]?\s*$",465000,530000),
  "E_to_Shows":(r"(?im)^\s*OF\s+PUBLIC\s+SHOWS\s*[\.,*]?\s*$",673000,720000),
  "F_to_Baptism":(r"(?im)^\s*OF\s+BAPTISM\s*[\.,]?\s*$",884000,930000),
  "I_to_Patience":(r"(?im)^\s*OF\s+PATIENCE\s*[\.,]?\s*$",1140000,1190000),
  "N_to_Second_Wife":(r"(?im)^\s*THE\s+SECOND\s+BOOK\s+TO\s+HIS\s+WIFE\s*[\.,]?\s*$",1460000,1490000),
  "O_to_Prescription":(r"(?im)^\s*ON\s+PRESCRIPTION\s+AGAINST\s+HERETICS\s*[\.,]?\s*$",1500000,1550000),
  "Additional_to_Index":(r"(?im)^\s*INDEX\s*[\.,]?\s*$",1750000,1780000)
 }
 report["next_translation_boundaries"]={}
 for k,(pattern,start,end) in critical.items():
  hits=[m.start() for m in re.finditer(pattern,t[start:end])]
  report["next_translation_boundaries"][k]=[
    {"at":start+pos,"context":snippet(t,start+pos,130)} for pos in hits[:8] ]
  print("BOUNDARY",k,report["next_translation_boundaries"][k],flush=True)
 # For gaps between the notes and translations, capture page-number/heading
 # contexts at evenly spaced points to allow conservative manual cut decisions.
 targets=[449829,457000,464000,473000,487000,500000,
          675012,687000,885528,896000,982724,1008000,1029000,
          1128955,1141481,1158000,1275537,1304578,1317808,
          1390000,1469725,1478000,1506820,1517000,
          1671183,1723306,1743896,1750731,1757000,1760000]
 report["spotchecks"]=[{"pos":p,"context":snippet(t,p,300)} for p in targets]
 (Path("data")/"tertullian_note_boundary_inspection_20261114.json").write_text(
  json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print("TERTULLIAN BOUNDARY AUDIT READY",len(report["spotchecks"]),"spotchecks",flush=True)
if __name__=="__main__":main()
