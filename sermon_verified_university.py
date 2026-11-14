#!/usr/bin/env python3
"""Source-verified pamphlet and OCR sermon boundaries for University Sermons I–II.

These bounds are specific to the two archived clean OCR files. The first
volume is a bound sequence of independently printed sermon pamphlets, some
with substantial original Pusey prefaces or later advertisements. Use whole
pamphlet spans for the per-sermon full-text search, but exclude the volume's
shared introduction/contents and avoid mixing adjacent sermons.

Volume II has several corrupted roman numerals (e.g. SEEMON YIIL,
SEEMONXIII^, SEEMOlSr XYI). Match those *observed* headings, not guesses.
If a future OCR changes, fail closed instead of silently linking a wrong text.
"""
import re

# (entry ID or stop-boundary, expected offset, anchored literal OCR pattern)
US1 = [
 ("m065",30353,r"(?im)^[ \t]*THE\s+HOLY\s+EUCHARIST\s+A\s+COMFORT\s+TO\s+THE\s+PENITENT,\s*$"),
 ("m110",303403,r"(?im)^[ \t]*ENTIEE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT:"),
 ("m144",475222,r"(?im)^[ \t]*ENTIRE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT\.\s*SERMON\s+II\."),
 ("m142",571872,r"(?im)^[ \t]*THE\s+PRESENCE\s+OF\s+CHRIST\s+IN\s+THE\s+HOLY\s+EUCHARIST\."),
 ("m177",700019,r"(?im)^[ \t]*justification,\s*$"),
 ("m166",792083,r"(?im)^[ \t]*THE\s+RULE\s+OF\s+FAITH\s+AS\s+MAINTAINED\s+BY\s+THE\s+FATHERS"),
 ("m137",1065509,r"(?im)^[ \t]*ALL\s+FAITH\s+THE\s+GIFT\s+OF\s+GOD\.\s*REAL\s+FAITH\s+ENTIRE\."),
 # The title page of the jointly printed 1855 pamphlet says both titles.
 # This later heading, KEAL FAITH, is the start of sermon VIII itself.
 ("m118",1139850,r"(?im)^[ \t]*KEAL\s+FAITH\s+ENTIRE\.\s*$"),
 ("m002",1254917,r"(?im)^[ \t]*PATIENCE\s+AND\s+CONFIDENCE\s+THE\s+STRENGTH\s+OF\s+THE\s+CHURCH")
]
US2 = [
 ("m036",238839,r"(?im)^[ \t]*SERMON\s+VI\.\s*$"),
 ("m028",286041,r"(?im)^[ \t]*SERMOX\s+YU\\\s*$"),
 ("m107",327637,r"(?im)^[ \t]*SEEMON\s+YIIL\s*$"),
 ("_gospel_end",365569,r"(?im)^[ \t]*SEEMON\s+IX\.\s*$"),
 ("m119",401107,r"(?im)^[ \t]*SERMON\s+X\.\s*$"),
 ("m030",449647,r'(?im)^[ \t]*seemo:n"\s+XI\.\s*$'),
 ("m148",490481,r"(?im)^[ \t]*SEEMON\s+XII\*\.\s*$"),
 ("m136",526592,r"(?im)^[ \t]*SEEMONXIII\^\s*$"),
 ("m153",564731,r"(?im)^[ \t]*SEEMON\s+XIY\^\s*$"),
 ("m021",596339,r"(?im)^[ \t]*SERMON\s+XV\.\s*$"),
 ("m105",642043,r"(?im)^[ \t]*SEEMOlSr\s+XYI\\\s*$"),
 ("_world_end",677560,r"(?im)^[ \t]*SEEMON\s+xyii«\.\s*$"),
]

PREFACE_CHECKS={
 "m065": (r"(?im)^[ \t]*PREFACE\.[ \t]*$",0,9000),
 "m110": (r"(?im)^[ \t]*PREFACE\.[ \t]*$",0,9000),
 "m142": (r"(?im)^[ \t]*PREFACE\.[ \t]*$",0,6000),
 "m166": (r"(?im)^[ \t]*ADVERTISEMENT\s+TO\s+THE\s+THIRD\s+EDITION\.",0,6500),
}

def explicit_university_spans(sources):
 result={}
 for code,expected_length,spec in (("US1",1362490,US1),("US2",816173,US2)):
  src=sources[code]
  text=src["t"]
  if len(text)!=expected_length:
   raise ValueError(f"{code} OCR changed ({len(text)} vs {expected_length}); "
                    "re-audit printed headings before applying owner-curated sermon links")
  coords=[]
  for key,at,pat in spec:
   matches=[m for m in re.finditer(pat,text) if abs(m.start()-at)<=1600]
   if len(matches)!=1:
    raise ValueError(f"{code}:{key}: expected exactly one scanned heading near "
                     f"{at}, found {len(matches)}; OCR requires re-audit")
   coords.append((key,matches[0].start()))
  points=[at for _,at in coords]
  if sorted(points)!=points or len(set(points))!=len(points):
   raise ValueError(f"{code}: sermon headings out of order or duplicated")
  for n,(key,start) in enumerate(coords):
   if key.startswith("_"):continue
   end=coords[n+1][1] if n+1<len(coords) else len(text)
   length=end-start
   if not 15000<length<320000:
    raise ValueError(f"{code}:{key}: implausible independently bounded text {length}")
   if code=="US1" and key in PREFACE_CHECKS:
    regex,a,b=PREFACE_CHECKS[key]
    if not re.search(regex,text[start+a:start+b]):
     raise ValueError(f"{code}:{key}: documented author preface/advertisement missing")
   result[key]={
      "code":code,"slug":src["slug"],"source_title":src["label"],
      "source_year":src["year"],"start":start,"pinned_end":end,
      "match_score":1.0,
      "method":"Owner-reviewed pamphlet or numbered-sermon OCR boundaries",
      "scope_note":"Includes original Pusey preface/advertisement where present, "
                   "and excludes the following separately printed sermon"
   }
 return result
