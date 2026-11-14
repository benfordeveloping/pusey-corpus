#!/usr/bin/env python3
"""Madan-based sermon extraction into a static, auditable subsite.
Never edits original OCR; uncertain boundaries remain unlinked.
"""
import re, json, html, unicodedata, difflib, shutil
from pathlib import Path

VOLUMES = {
 'PS1':('1848-parochial-sermons-vol-i-advent-to-whitsuntide','Parochial Sermons I',1848),
 'PS2':('1853-parochial-sermons-vol-ii','Parochial Sermons II',1853),
 'PS3':('1873-parochial-sermons-vol-iii-revised','Parochial Sermons III',1878),
 'PC':('1882-parochial-and-cathedral-sermons','Parochial and Cathedral Sermons',1882),
 'LS':('1874-lenten-sermons-preached-chiefly-to-young-men','Lenten Sermons',1874),
 'US1':('1859-university-sermons-vol-i-nine-sermons','University Sermons I',1859),
 'US2':('1872-university-sermons-vol-ii-sermons-1859-1872','University Sermons II',1872),
 'US3':('1880-university-sermons-vol-iii-ten-sermons','University Sermons III',1880),
 'OPS':('1865-parochial-sermons-preached-and-printed-on-various-occasi','Occasional Parochial Sermons',1865),
 'SSL':('1845-a-course-of-sermons-on-solemn-subjects-chiefly-bearing-o','St Saviour’s, Leeds',1845)
}
RANGES={'PS1':(None,1848),'PS2':(None,1853),'PS3':(None,1838),'PC':(None,1882),
        'LS':(1858,1874),'US1':(1837,1859),'US2':(1859,1872),
        'US3':(1864,1880),'OPS':(1832,1865),'SSL':(1845,1845)}
HEAD=re.compile(r'(?im)^[ \t]*S(?:ERMON|EKMON|EEMON|EEMOST)[ \t]+([IVXLCDM]{1,9})\s*[,.]?[ \t]*$',re.M)
BAD_START=re.compile(r'(?i)^(?:preached|sermon|first|second|third|fourth|fifth|feast|sunday|christmas|lent|advent|whitsun|st\.|s\.|1 |2 |ps\.|psalm|heb\.|rom\.|isa\.|gal\.|john|matt|luke|acts|rev\.|page|act sermon)')
ROM={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}

def roman(s):
 s=s.upper().replace('VIIL','VIII').replace('IY','IV')
 if not s or any(c not in ROM for c in s):return None
 n=sum((-1 if i+1<len(s) and ROM[c]<ROM[s[i+1]] else 1)*ROM[c] for i,c in enumerate(s))
 return n if 0<n<50 else None

def norm(s):
 s=unicodedata.normalize('NFKD',s).lower().replace('’',"'")
 s=re.sub(r'(?<=\w)[—–-](?=\w)','',s)
 return re.sub(r'[^a-z0-9]+',' ',s).strip()

def similarity(a,b):
 stop={'the','a','an','is','to','for','in','of','and','his','her','our','with','through','from','by','on','at','as','which','that'}
 x={s for s in norm(a).split() if len(s)>2 and s not in stop}
 y={s for s in norm(b).split() if len(s)>2 and s not in stop}
 if not x or not y:return 0.
 return .65*len(x&y)/max(len(x),len(y))+.35*difflib.SequenceMatcher(None,norm(a),norm(b),autojunk=False).ratio()

def headings(t):
 return [{'n':roman(m[1]),'raw':m[1],'at':m.start(),'end':m.end()} for m in HEAD.finditer(t) if roman(m[1])]

def toc_title(t,p):
 lines=[x.strip() for x in t[p:p+440].splitlines() if x.strip()]
 selected=[]
 for line in lines[:5]:
  if len(line)>160 or (selected and BAD_START.match(line)):break
  letters=re.sub('[^A-Za-z]','',line)
  if letters and sum(c.isupper() for c in letters)/len(letters)<.62:break
  selected.append(line)
  if re.search('[.!?]$',line) and len(' '.join(selected))>8:break
 return re.sub(r'[.!?,;\s]+$','', ' '.join(selected))

def load_sources(root):
 results={}
 for code,(slug,label,pubyear) in VOLUMES.items():
  file=root/'data'/'clean'/(slug+'.txt')
  t=file.read_text('utf8') if file.exists() else ''
  hs=headings(t); toc=[]; prev=0
  if code!='SSL' and hs:
   first=hs[0]['at']
   for h in hs:
    if h['at']>first+18000 or len(toc)>43:break
    n=h['n']
    if n>prev+3 and prev>=8 and h['raw'].upper().startswith('X'):n=prev+1
    if toc and n<=prev:break
    toc.append({**h,'n':n,'title':toc_title(t,h['end'])});prev=n
   for j,h in enumerate(toc):
    until=toc[j+1]['at'] if j+1<len(toc) else h['end']+700
    pages=re.findall(r'\bpp?\.?\s*(\d{1,3})\b',t[h['end']:until],re.I)
    h['page']=int(pages[0]) if pages else None
  cutoff=toc[-1]['at'] if toc else 0
  results[code]={'code':code,'slug':slug,'label':label,'year':pubyear,'t':t,'toc':toc,'cutoff':cutoff,'heads':hs}
  if code=='US3':results[code]['pamphlets']=us3_boundaries(t,cutoff) if t else {}
  if code=='LS':results[code]['corrected_starts']=ls_boundaries(t,cutoff) if t else {}
 return results

def title_positions(t,title,cutoff):
 tokens=re.findall('[A-Za-z0-9]+',title.upper())
 if len(''.join(tokens))<6:return []
 pattern=r'(?im)^[ \t]*'+r'[^A-Z0-9]{0,35}'.join(map(re.escape,tokens))+r'[ \t.,!?;:\'"’—–-]*$'
 try:return [m.start() for m in re.finditer(pattern,t[cutoff:],re.M|re.I) if m.start()>30]
 except re.error:return []

def find_start(src,trow,page,known_title):
 t=src['t']; cut=src['cutoff']; n=trow['n']
 heads=[h['at'] for h in src['heads'] if h['n']==n and h['at']>cut+35]
 # Chapter titles are often OCR-corrupted, but a verified ordinal heading
 # together with a TOC match is a strong boundary.
 named=[cut+p for p in title_positions(t,known_title,cut) if cut+p>cut+35]
 if not heads and not named:
  # A stand-alone uppercase title can survive even when the number does not.
  pool=[]
  for m in re.finditer(r'(?m)^[ \t]*[A-Z][A-Z0-9 ,.!?\'"’—–-]{8,110}[ \t]*$',t[cut:],re.M):
   txt=m[0].strip()
   if similarity(txt,known_title)>=.83:pool.append(cut+m.start())
  named=pool
 options=sorted(set(heads+named))
 if not options:return None
 max_pages={'PS1':400,'PS2':400,'PS3':480,'PC':525,'LS':495,'US2':495,'US3':510,'OPS':240}.get(src['code'],450)
 expected=cut+(max(0,page or n*max_pages/max(1,len(src['toc'])))/max_pages)*(len(t)-cut)
 choice=min(options,key=lambda p:abs(p-expected))
 if abs(choice-expected)>max(85000,len(t)*.18) and choice not in heads:return None
 return choice

def extract_leeds(entry,src):
 # Madan's Leeds page references are to ten selected Pusey sermons in
 # SERMON I and XI–XIX; direct page-to-character interpolation is unsafe.
 refs=[x for x in entry["refs"] if x.startswith("SSL:")]
 if not refs:return None
 page=int(refs[0].split(":")[1])
 page_to_ordinal={1:1,173:11,192:12,211:13,237:14,255:15,
                  272:16,289:17,309:18,330:19}
 ordinal=page_to_ordinal.get(page)
 if ordinal is None:return None
 h=next((h for h in src["heads"] if h["n"]==ordinal),None)
 if h is None:return None
 # Preserve independent sermon identity even for two consecutive sermons
 # both beginning at the same scriptural text.
 return {"code":"SSL","slug":src["slug"],"source_title":src["label"],"source_year":src["year"],
         "start":h["at"],"ordinal":ordinal,"printed_page":page,
         "match_score":0.94,"method":"Madan Leeds page → confirmed numbered Pusey sermon"}


def direct_lookup(entry,code,src,page,ordinal=None):
 """Fallback when OCR damaged the parent volume's numbered contents.

 Only a likely page/ordinal plus an independently found printed title
 is sufficient for extraction. Never extract from an estimated offset.
 """
 t=src["t"];cut=src["cutoff"];book=entry["scripture"].split()[0].lower()
 if book in ("1","2"):book=entry["scripture"].split()[1].lower()
 maxpage={"PS1":400,"PS2":400,"PS3":480,"PC":525,"LS":495,
          "US1":320,"US2":495,"US3":510,"OPS":240}.get(code,450)
 expected=(cut+(page/maxpage)*(len(t)-cut)) if page is not None else (
          cut+(ordinal/max(1,len(src["toc"])+1))*(len(t)-cut) if ordinal else None)
 options=title_positions(t,entry["title"],cut)
 options=[cut+p for p in options if cut+p>cut+45]
 # Reject running heads if a likely title is not followed by a biblical
 # citation nearby; allow titles if OCR has ruined the scripture heading.
 def evidence(pos):
  segment=norm(t[pos:pos+650])
  if book in segment:return True
  return (page is not None and expected is not None and abs(pos-expected)<17000)
 grounded=[p for p in options if evidence(p)]
 if grounded:options=grounded
 if not options:
  # OCR may hyphenate/misspell an individual word in an otherwise clear
  # title. Read only plausible uppercase heading lines near the page.
  if expected is None:return None
  start=max(cut,int(expected)-39000);end=min(len(t),int(expected)+39000)
  for m in re.finditer(r"(?m)^[ \t]*[A-Z][A-Z0-9 ,.!?\'\"’—–-]{8,115}[ \t]*$",t[start:end],re.M):
   label=m.group(0).strip()
   if similarity(label,entry["title"])>=0.76:options.append(start+m.start())
 if not options:return None
 chosen=min(options,key=lambda x:abs(x-expected)) if expected is not None else options[0]
 if expected is not None and abs(chosen-expected)>max(60000,len(t)*0.11):
  return None
 # Distinct Madan page and title evidence; source headings are not guessed.
 return {"code":code,"slug":src["slug"],"source_title":src["label"],"source_year":src["year"],
         "start":chosen,"printed_page":page,"ordinal":ordinal,
         "match_score":0.78 if page is not None else 0.66,
         "method":"Madan title + source page / heading"}

US3_PAMPHLETS=[
 ("m063",r"(?m)^EVEBLASTING PUNISHMENT\.$"),
 ("m058",r"(?m)^THE MIRACLES OF PRATER[,]?$"),
 ("m093",r"(?m)^WILL YE ALSO GO AWAY\?$"),
 ("m064",r"(?m)^A SERMON\s*\n\s*PREACHED BEFORE THE UNIVERSITY\s*\n\s*AT S\. MARY"),
 ("m099",r"(?m)^THE RESPONSIBILITY OF INTELLECT IN\s*\n\s*MATTERS OF FAITH\.$"),
 ("m095",r"(?m)^SINFUL BLINDNESS AMIDST IMAGINED"),
 ("m076",r"(?m)^CHRISTIANITY WITHOUT THE CROSS$"),
 ("m108",r"(?m)^GOD\s*\n\s*AND HUMAN INDEPENDENCE\.$"),
 ("m090",r"(?m)^UN-SCIENCE, NOT SCIENCE,$"),
 ("m178",r"(?m)^PROPHECY OF JESUS$"),
 ("m043",r'(?m)^[ \t]*" BLESSED ARE THE MEEK\."[ \t]*$')]
def us3_boundaries(text,cutoff):
 anchors={}
 for eid,pattern in US3_PAMPHLETS:
  hits=[m.start() for m in re.finditer(pattern,text) if m.start()>cutoff+50]
  if hits:anchors[eid]=hits[0]
 if len(anchors)!=11:
  print("SERMON WARNING: US3 headings missing "+repr([eid for eid,_ in US3_PAMPHLETS if eid not in anchors]))
  return {}
 positions=[anchors[eid] for eid,_ in US3_PAMPHLETS]
 if positions!=sorted(positions) or len(set(positions))!=11:
  print("SERMON WARNING: US3 pamphlets out of order")
  return {}
 return anchors


# Five Lenten Sermons have severely misread printed sermon numbers/titles.
# These literal line headings are observable in the owner-approved OCR and
# are independently supported by Madan's printed pages.
LS_CORRECTED_HEADINGS=[
 ("m004",r"(?m)^SEKMON IVa\.$"), # Balaam, p.69
 ("m079",r"(?m)^SEEMON Xa\.$"), # Prodigal son on Luke 15:24, p.194
 ("m078",r"(?m)^SEKMON XI\.$"), # Prodigal son on Luke 15:17,20, p.205
 ("m138",r"(?m)^SEBMON XIXa\.$"), # Love of Jesus, p.364
 ("m195",r"(?m)^SEKMON XXIII"), # Worship, p.437
]
def ls_boundaries(text,cutoff):
 starts={}
 for eid,regex in LS_CORRECTED_HEADINGS:
  found=[m.start() for m in re.finditer(regex,text) if m.start()>cutoff+50]
  if len(found)==1:starts[eid]=found[0]
  else:print('SERMON WARNING: LS heading mismatch '+eid+' '+str(len(found)))
 return starts

def locate(entry,sources):
 candidates=[]
 for ref in entry["refs"]:
  code=ref.split(":")[0]
  if code not in sources:continue
  src=sources[code];t=src["t"]
  if len(t)<2000:continue
  if code=="SSL":
   hit=extract_leeds(entry,src)
   if hit:candidates.append(hit)
   continue
  if code=="LS" and entry["id"] in src.get("corrected_starts",{}):
   candidates.append({"code":code,"slug":src["slug"],"source_title":src["label"],
     "source_year":src["year"],"start":src["corrected_starts"][entry["id"]],
     "printed_page":int(ref.split(":")[1]) if ":" in ref else None,
     "match_score":0.99,"method":"Madan page + independently checked OCR sermon heading"})
   continue
  if code=="US3" and src.get("pamphlets"):
   pos=src["pamphlets"].get(entry["id"])
   if pos is not None:
    candidates.append({"code":code,"slug":src["slug"],"source_title":src["label"],
     "source_year":src["year"],"start":pos,"printed_page":None,
     "match_score":0.99,"method":"separately printed sermon pamphlet heading"})
   continue
  page=int(ref.split(":")[1]) if ":" in ref and ref.split(":")[1].isdigit() else None
  ranked=[]
  for h in src["toc"]:
   score=similarity(entry["title"],h["title"])
   if page is not None and h["page"] is not None and abs(page-h["page"])<=2:
    score=max(score,.89-.07*abs(page-h["page"]))
   ranked.append((score,h))
  choice=max(ranked,key=lambda x:x[0]) if ranked else None
  if choice and choice[0]>=.57:
   score,h=choice
   start=find_start(src,h,page or h["page"],h["title"])
   if start is not None:
    candidates.append({"code":code,"slug":src["slug"],"source_title":src["label"],
       "source_year":src["year"],"ordinal":h["n"],"printed_page":page or h["page"],
       "start":start,"match_score":round(score,3),"method":"volume TOC and sermon heading"})
  # Directly check Madan's printed page and title where the TOC has bad OCR.
  fallback=direct_lookup(entry,code,src,page,choice[1]["n"] if choice and choice[0]>.55 else None)
  if fallback:candidates.append(fallback)
 return max(candidates,key=lambda c:c["match_score"],default=None)
def assign_dates(row):
 date=row.get('date')
 if date and re.fullmatch('1[678][0-9]{2}',str(date)):
  y=int(date);return {'label':str(y),'earliest':y,'latest':y,'precision':'Madan, sermon date'}
 code=row.get('code')
 lo,hi=RANGES.get(code,(None,None))
 if lo==hi and lo is not None:label=str(lo)
 elif lo is None and hi:label='by '+str(hi)
 elif lo is not None and hi is not None:label=f'{lo}–{hi}'
 else:label='date unknown'
 return {'label':label,'earliest':lo,'latest':hi,'precision':'volume-level range, not verified individual date'}

def find_entries(root):
 data=json.loads((root/'data'/'sermons'/'madan_catalogue.json').read_text('utf8'))
 src=load_sources(root)
 rows=[]
 for e in data['entries']:
  row=dict(e)
  match=locate(e,src)
  if match:row.update(match);row['status']='candidate'
  else:row.update(status='missing',reason='Source text or reliable sermon boundary not yet located')
  rows.append(row)
 # A single passage cannot be assigned to two Madan entries.
 positions={}
 for e in rows:
  if e['status']=='candidate':positions.setdefault((e['code'],e['start']),[]).append(e)
 for duplicates in positions.values():
  if len(duplicates)>1:
   for e in duplicates:e.update(status='missing',reason='Ambiguous duplicate position; needs review')
 for code,source in src.items():
  selected=sorted((e for e in rows if e['status']=='candidate' and e.get('code')==code),key=lambda x:x['start'])
  for i,e in enumerate(selected):
   pos=e['start']
   following=[selected[i+1]['start']] if i+1<len(selected) else []
   # Also stop before a known numbered heading even if that sermon was not matched.
   following += [h['at'] for h in source['heads'] if h['at']>pos+1700 and h['at']>source['cutoff']]
   if code=='US3' and source.get('pamphlets'):
    following += [p for p in source['pamphlets'].values() if p>pos]
   if code=='LS':following += [p for p in source.get('corrected_starts',{}).values() if p>pos]
   end=min(following+[len(source['t'])])
   length=end-pos
   cap=155000 if code=='US3' and source.get('pamphlets') else 75000
   if length<2500 or length>cap:
    e.update(status='missing',reason=f'Unverified end boundary ({length:,} characters)')
   else:
    e.update(status='available',end=end,characters=length,word_count=len(source['t'][pos:end].split()),
             verification='Automated segmentation checked; OCR proofreading pending')
 for e in rows:e['date_info']=assign_dates(e)
 return rows,src

def write_site(root,site):
 # Synthetic build tests intentionally omit the historical sermon catalogue.
 if not (root/'data'/'sermons'/'madan_catalogue.json').exists():
  return {'total':0,'available':0,'missing':0,'volumes_with_text':0}
 rows,sources=find_entries(root)
 out=site/'sermons';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True,exist_ok=True)
 def escape(x):return html.escape(str(x or ''))
 available=[e for e in rows if e['status']=='available'];missing=[e for e in rows if e['status']!='available']
 for e in available:
  data=sources[e['code']]['t'][e['start']:e['end']]
  text='<p>'+escape(data).replace('\n\n','</p><p>').replace('\n',' ')+'</p>'
  h='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
  h+='<title>'+escape(e['title'])+' — Pusey Sermons</title><link rel="stylesheet" href="../style.css">'
  # Let the separate Pagefind index read the full sermon text and its source metadata.
  h+='<meta data-pagefind-meta="sermon_title[content]" content="'+escape(e['title'])+'">'
  h+='<meta data-pagefind-meta="scripture[content]" content="'+escape(e['scripture'])+'">'
  h+='<meta data-pagefind-meta="sermon_date[content]" content="'+escape(e['date_info']['label'])+'">'
  h+='<meta data-pagefind-meta="source[content]" content="'+escape(e['source_title'])+'">'
  h+='<meta data-pagefind-filter="collection[content]" content="sermons">'
  h+='</head><body>'
  h+='<header><a class="brand" href="../index.html">The Pusey Corpus</a> · <a href="index.html">Sermons</a></header>'
  h+='<main class="wrap" style="max-width:850px"><p><a href="index.html">← Sermon catalogue</a></p>'
  h+='<h1>'+escape(e['title'])+'</h1><p class="notice">'+escape(e['scripture'])+' · '+escape(e['date_info']['label'])+' · '+escape(e['source_title'])+'</p>'
  h+='<p class="notice">'+escape(e['date_info']['precision'])+' · '+escape(e.get('word_count'))+' words · OCR text not yet fully proofread</p>'
  h+='<p><a href="../works/'+escape(e['slug'])+'/0001.html">Read the complete original volume</a></p>'
  h+='<label for="searchin">Find within this sermon</label> <input id="searchin" type="search" placeholder="Search this sermon" style="padding:8px"><span id="hits" class="notice"></span>'
  h+='<article id="sermon-text" class="ocr" data-pagefind-body style="font:18px/1.8 Georgia,serif">'+text+'</article><p><a href="index.html">← Sermon catalogue</a></p></main>'
  h+='<script src="../reader.js" defer></script><script src="within.js" defer></script></body></html>'
  (out/(e['id']+'.html')).write_text(h,encoding='utf8')
 rows_json=json.dumps(rows,ensure_ascii=False).replace('</','<\\/')
 intro='<main class="wrap"><p><a href="../index.html">← Corpus search</a></p><div class="eyebrow">The Digital Sermon Library</div>'
 intro+='<h1>The Published Sermons of E. B. Pusey</h1><p class="intro">A Scripture-ordered catalogue based on Falconer Madan’s Appendix B (1897), with individual sermons linked wherever safe extraction from existing volumes is possible.</p>'
 intro+='<div class="stats">'+str(len(rows))+' entries · '+str(len(available))+' readable sermon texts · '+str(len(missing))+' unresolved</div>'
 intro+='<section class="search-panel"><label for="q" class="eyebrow">Search the full text of the sermons</label>'
 intro+='<div class="query-row"><input id="q" type="search" placeholder="Enter a word or phrase…" autocomplete="off" spellcheck="false"></div>'
 intro+='<div class="filter-row"><span>Searches every word of the '+str(len(available))+' available sermons and shows matching passages, just like the main corpus search.</span></div></section>'
 intro+='<section id="sermon-search-results" hidden><p id="search-count" class="notice" role="status" aria-live="polite"></p>'
 intro+='<ol id="search-hits" class="results"></ol><button id="search-more" class="more" hidden>Show 20 more results</button></section>'
 intro+='<section id="sermon-browse"><h2>Browse the sermon catalogue</h2>'
 intro+='<div class="search-panel"><label for="browse-q">Filter by title or Scripture</label><div class="query-row"><input id="browse-q" type="search" placeholder="Title, biblical reference, year, volume…" autocomplete="off"></div>'
 intro+='<div class="filter-row"><label for="sort">Sort by:</label><select id="sort"><option value="scripture">Scripture (Madan order)</option><option value="date">Chronological / date range</option><option value="title">Title A–Z</option></select>'
 intro+='<label for="scope">Show:</label><select id="scope"><option value="">All sermons</option><option value="available">Readable texts</option><option value="missing">Not yet located</option></select>'
 intro+='<a href="missing.html">Unresolved-sermon list</a></div></div><p id="count" class="notice"></p><ol id="list" style="padding-left:0"></ol></section>'
 intro+='<p class="notice">Preaching years are taken from Madan where stated; otherwise the interface gives a documented volume-level range rather than an invented year. OCR text is not fully proofread; the original sermon volumes remain available in the main corpus.</p>'
 intro+='<script type="application/json" id="data">'+rows_json+'</script><script type="module" src="listing.js"></script></main>'
 page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pusey Sermons | Digital Corpus</title><link rel="stylesheet" href="../style.css"></head><body><header><a class="brand" href="../index.html">The Pusey Corpus</a> · <b>Sermons</b></header>'+intro+'</body></html>'
 (out/'index.html').write_text(page,encoding='utf8')
 li=''.join('<li style="padding:7px 0"><b>'+escape(e['title'])+'</b> — '+escape(e['scripture'])+' · '+escape(', '.join(e['refs']) or 'no source cited')+' · '+escape(e.get('reason'))+'</li>' for e in missing)
 missingpage='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unresolved Pusey sermons</title><link rel="stylesheet" href="../style.css"></head><body><header><a class="brand" href="../index.html">The Pusey Corpus</a> · <a href="index.html">Sermons</a></header><main class="wrap"><p><a href="index.html">← Sermons</a></p><h1>Sermons not yet located</h1><p>'+str(len(missing))+' entries from Madan’s 1897 index do not yet have a safely verified extraction. Additional scans and page identifications can help complete them.</p><p><a href="match_report.json">Matching audit (JSON)</a></p><ol>'+li+'</ol></main></body></html>'
 (out/'missing.html').write_text(missingpage,encoding='utf8')
 (out/'catalogue.json').write_text(json.dumps({'entries':rows},indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 (out/'match_report.json').write_text(json.dumps([{k:e.get(k) for k in ('id','title','scripture','refs','status','code','start','end','word_count','match_score','method','reason')} for e in rows],indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 (out/'listing.js').write_text("""// The catalog remains browsable, while Pagefind searches the full text
// of individual sermons in a completely separate sermon-only index.
const data=JSON.parse(document.querySelector('#data').textContent);
const q=document.querySelector('#q'),browseQ=document.querySelector('#browse-q');
const sort=document.querySelector('#sort'),scope=document.querySelector('#scope');
const browse=document.querySelector('#sermon-browse'),list=document.querySelector('#list'),count=document.querySelector('#count');
const searchArea=document.querySelector('#sermon-search-results'),hits=document.querySelector('#search-hits');
const searchCount=document.querySelector('#search-count'),more=document.querySelector('#search-more');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let engine=null,all=[],shown=0,sequence=0,timer=null;

function drawBrowse(){
 let items=data.filter(x=>(!scope.value||x.status===scope.value)
  &&(!browseQ.value||[x.title,x.scripture,x.date_info.label,x.refs.join(' ')]
    .join(' ').toLowerCase().includes(browseQ.value.toLowerCase().trim())));
 if(sort.value==='title')items.sort((a,b)=>a.title.localeCompare(b.title)||a.order-b.order);
 else if(sort.value==='date')items.sort((a,b)=>(a.date_info.earliest??a.date_info.latest??9999)
 -(b.date_info.earliest??b.date_info.latest??9999)||(a.date_info.latest??9999)
 -(b.date_info.latest??9999)||a.order-b.order);
 else items.sort((a,b)=>a.order-b.order);
 list.replaceChildren();
 const frag=document.createDocumentFragment();
 for(const x of items){
  const li=document.createElement('li');
  li.style.cssText='list-style:none;padding:10px 0;border-bottom:1px solid #dcd8cf';
  const info=document.createElement('span');
  info.textContent=x.scripture+' · '+x.date_info.label+' · '+x.refs.join(', ');
  info.style.cssText='display:block;color:#64717d;font-size:13px';
  const title=document.createElement(x.status==='available'?'a':'span');
  title.textContent=x.title;
  if(x.status==='available')title.href=x.id+'.html';
  else info.textContent+=' · Text not yet located';
  title.style.cssText='font:600 18px Georgia,serif';
  li.append(title,info);frag.append(li);
 }
 list.append(frag);count.textContent=items.length+' sermons shown';
}
async function loadEngine(){
 if(engine)return engine;
 engine=await import('./pagefind/pagefind.js');
 await engine.options({baseUrl:new URL('.',location.href).pathname,highlightParam:'highlight'});
 return engine;
}
async function renderMore(){
 if(!all.length)return;
 const current=sequence,batch=all.slice(shown,shown+20);
 shown+=batch.length;
 const details=await Promise.all(batch.map(result=>result.data()));
 if(current!==sequence)return;
 for(const d of details){
  const li=document.createElement('li');li.className='result';
  const title=esc(d.meta?.sermon_title||d.meta?.title||'Untitled sermon');
  const scripture=esc(d.meta?.scripture||'');
  const year=esc(d.meta?.sermon_date||'');
  const source=esc(d.meta?.source||'');
  li.innerHTML='<h3><a href="'+esc(d.url)+'">'+title+'</a></h3>'
   +'<div class="meta">'+[scripture,year,source].filter(Boolean).join(' · ')+'</div>'
   +'<p class="excerpt">'+(d.excerpt||'')+'</p>';
  hits.appendChild(li);
 }
 more.hidden=shown>=all.length;
}
async function runSearch(){
 const current=++sequence,query=q.value.trim();
 const url=new URL(location.href);
 if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');
 history.replaceState(null,'',url.pathname+url.search);
 hits.replaceChildren();shown=0;all=[];more.hidden=true;
 browse.hidden=!!query;searchArea.hidden=!query;
 if(!query){searchCount.textContent='';return;}
 searchCount.textContent='Searching sermon texts…';
 try{
  const p=await loadEngine();
  const result=await p.search(query);
  if(current!==sequence)return;
  all=result?.results||[];
  searchCount.textContent=all.length.toLocaleString()
   +' sermons with matching full-text passages. Open a result to read the sermon in context.';
  if(!all.length)searchCount.textContent='No available sermon texts match that search. Try a different word or phrase.';
  await renderMore();
 }catch(err){
  if(current===sequence)searchCount.textContent='Sermon search is currently unavailable. The full-text index may still be building.';
 }
}
q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(runSearch,250)});
for(const control of [browseQ,sort,scope]){
 control.addEventListener(control===browseQ?'input':'change',drawBrowse);
}
more.addEventListener('click',renderMore);
const initial=new URLSearchParams(location.search).get('q');
if(initial)q.value=initial;
drawBrowse();if(initial)runSearch();
""",encoding='utf8')
 (out/'within.js').write_text("""const box=document.querySelector('#sermon-text'),input=document.querySelector('#searchin'),msg=document.querySelector('#hits'),original=box.textContent;
input.addEventListener('input',()=>{const query=input.value.trim().toLowerCase();box.textContent=original;if(!query){msg.textContent='';return;}const f=document.createDocumentFragment(),lower=original.toLowerCase();let last=0,n=0,at;
while((at=lower.indexOf(query,last))>=0){f.append(document.createTextNode(original.slice(last,at)));const m=document.createElement('mark');m.textContent=original.slice(at,at+query.length);f.append(m);last=at+query.length;n++;}f.append(document.createTextNode(original.slice(last)));box.replaceChildren(f);msg.textContent=' '+n+' matches';box.querySelector('mark')?.scrollIntoView({block:'center'});});
""",encoding='utf8')
 stats={'total':len(rows),'available':len(available),'missing':len(missing),'volumes_with_text':sum(len(x['t'])>2000 for x in sources.values())}
 print('SERMON LIBRARY '+json.dumps(stats))
 by_code={}
 for e in rows:
  key=e.get('code') or (e['refs'][0].split(':')[0] if e['refs'] else 'NONE')
  x=by_code.setdefault(key,{'available':0,'missing':0})
  x[e['status']]+=1
 print('SERMON SOURCE COUNTS '+json.dumps(by_code,sort_keys=True))
 for e in missing:
  print('SERMON MISSING: '+json.dumps({'id':e['id'],'refs':e['refs'],'title':e['title'],'reason':e.get('reason'),'matched_source':e.get('code'),'score':e.get('match_score')}))
 return stats

if __name__=='__main__':
 root=Path(__file__).resolve().parent;write_site(root,root/'site')
