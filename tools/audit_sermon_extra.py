#!/usr/bin/env python3
"""Verify specific printed pamphlet boundaries for owner requested sermon links."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sermon_library as sl
sources=sl.load_sources(ROOT)
queries={
'US1':{
  'm065':r'(?im)^\s*THE\s+HOLY\s+EUCHARIST\s+A\s+COMFORT\s+TO\s+THE\s+PENITENT[,\.]?\s*$',
  'm110':r'(?im)^\s*ENTIEE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT[:\.]?',
  'm144':r'(?im)^\s*ENTIRE\s+ABSOLUTION\s+OF\s+THE\s+PENITENT\.\s*SERMON\s+II\.',
  'm142':r'(?im)^\s*THE\s+PRESENCE\s+OF\s+CHRIST\s+IN\s+THE\s+HOLY\s+EUCHARIST\.',
  'm177':r'(?im)^\s*justification,\s*$',
  'm166':r'(?im)^\s*THE\s+RULE\s+OF\s+FAITH\s+AS\s+MAINTAINED\s+BY\s+THE\s+FATHERS',
  'm137':r'(?im)^\s*ALL\s+FAITH\s+THE\s+GIFT\s+OF\s+GOD\.\s*REAL\s+FAITH\s+ENTIRE\.',
  'real_faith_separate':r'(?im)^\s*REAL\s+FAITH\s+ENTIRE[.,]?\s*$',
  'real_faith_scripture':r'(?im)^\s*ROM(?:ANS)?\.\s*i\.\s*4\.',
  'm002':r'(?im)^\s*PATIENCE\s+AND\s+CONFIDENCE\s+THE\s+STRENGTH\s+OF\s+THE\s+CHURCH',
  'first_preface':r'(?im)^\s*PREFACE\.\s*$',
  'second_preface':r'(?im)^\s*PREFACE\.\s*$',
  'rule_advertisement':r'(?im)^\s*ADVERTISEMENT\s+TO\s+THE\s+THIRD\s+EDITION\.',
},
'US2':{
  'm107':r'(?im)^\s*SEEMON\s+YIIL[,.]?\s*$',
  'm107_end':r'(?im)^\s*SEEMON\s+IX\.\s*$',
  'm119':r'(?im)^\s*SERMON\s+X\.\s*$',
  'm119_end':r'(?im)^\s*seemo[:n"\\ ]+\s*XI\.\s*$',
  'm136':r'(?im)^\s*SEEMONXIII\^\s*$',
  'm136_end':r'(?im)^\s*SEEMON\s+XIY\^\s*$',
  'm105':r'(?im)^\s*SEEMO[IlL1]Sr?\s+XYI',
  'm105_end':r'(?im)^\s*SEEMON\s+XVII',
 }
}
report={}
rows,_=sl.find_entries(ROOT)
for code,spec in queries.items():
 t=sources[code]['t'];out={}
 for key,pattern in spec.items():
  found=list(re.finditer(pattern,t,re.M|re.I))
  out[key]=[{'at':m.start(),'match':m.group(0)[:100],
             'prior':t[max(0,m.start()-370):m.start()].replace('\n',' | '),
             'following':t[m.end():m.end()+900].replace('\n',' | ')} for m in found[:18]]
 report[code]={'anchors':out,'existing_links':[
  {k:e.get(k) for k in ('id','title','status','start','end','reason','match_score','method')}
  for e in rows if (e.get('code')==code or any(ref.startswith(code) for ref in e['refs']))]}
p=ROOT/'data/sermons/owner_sermon_additional_boundaries_20261114.json'
p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
for code,result in report.items():
 print(code,'anchor_counts',json.dumps({k:len(v) for k,v in result['anchors'].items()}))
 print(code,'currently_linked',sum(x['status']=='available' for x in result['existing_links']))
