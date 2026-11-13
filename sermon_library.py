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
 t=src['t'];ref=next((x for x in entry['refs'] if x.startswith('SSL')),None)
 if not ref:return None
 page=int(ref.split(':')[1]) if ':' in ref else 0
 if not page:return None
 guess=(page/350)*len(t)
 h=min(src['heads'],key=lambda x:abs(x['at']-guess),default=None)
 if not h or abs(h['at']-guess)>49000:return None
 # A scripture-specific preliminary match: the source has only 10 sermons.
 book=entry['scripture'].split(' ')[-2].lower() if entry['scripture'].startswith('1 ') else entry['scripture'].split()[0].lower()
 if book=='ps':book='ps'
 if book not in norm(t[h['at']:h['at']+750]):return None
 return {'code':'SSL','slug':src['slug'],'source_title':src['label'],'source_year':src['year'],
         'start':h['at'],'ordinal':h['n'],'printed_page':page,'match_score':.77,'method':'Leeds heading/printed page'}

def locate(entry,sources):
 candidates=[]
 for ref in entry['refs']:
  code=ref.split(':')[0]
  if code not in sources:continue
  src=sources[code];t=src['t']
  if len(t)<2000:continue
  if code=='SSL':
   result=extract_leeds(entry,src)
   if result:candidates.append(result)
   continue
  page=int(ref.split(':')[1]) if ':' in ref and ref.split(':')[1].isdigit() else None
  ranked=[]
  for h in src['toc']:
   score=similarity(entry['title'],h['title'])
   if page is not None and h['page'] is not None and abs(page-h['page'])<=2:
    score=max(score,.89-.07*abs(page-h['page']))
   ranked.append((score,h))
  if not ranked:continue
  score,h=max(ranked,key=lambda x:x[0])
  if score<.57:continue
  start=find_start(src,h,page or h['page'],h['title'])
  if start is None:continue
  candidates.append({'code':code,'slug':src['slug'],'source_title':src['label'],
     'source_year':src['year'],'ordinal':h['n'],'printed_page':page or h['page'],
     'start':start,'match_score':round(score,3),'method':'volume TOC and sermon heading'})
 return max(candidates,key=lambda c:c['match_score'],default=None)

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
   end=min(following+[len(source['t'])])
   length=end-pos
   if length<2500 or length>75000:
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
  h+='<title>'+escape(e['title'])+' — Pusey Sermons</title><link rel="stylesheet" href="../style.css"></head><body>'
  h+='<header><a class="brand" href="../index.html">The Pusey Corpus</a> · <a href="index.html">Sermons</a></header>'
  h+='<main class="wrap" style="max-width:850px"><p><a href="index.html">← Sermon catalogue</a></p>'
  h+='<h1>'+escape(e['title'])+'</h1><p class="notice">'+escape(e['scripture'])+' · '+escape(e['date_info']['label'])+' · '+escape(e['source_title'])+'</p>'
  h+='<p class="notice">'+escape(e['date_info']['precision'])+' · '+escape(e.get('word_count'))+' words · OCR text not yet fully proofread</p>'
  h+='<p><a href="../works/'+escape(e['slug'])+'/0001.html">Read the complete original volume</a></p>'
  h+='<label for="searchin">Find within this sermon</label> <input id="searchin" type="search" placeholder="Search this sermon" style="padding:8px"><span id="hits" class="notice"></span>'
  h+='<article id="sermon-text" style="font:18px/1.8 Georgia,serif">'+text+'</article><p><a href="index.html">← Sermon catalogue</a></p></main>'
  h+='<script src="within.js"></script></body></html>'
  (out/(e['id']+'.html')).write_text(h,encoding='utf8')
 rows_json=json.dumps(rows,ensure_ascii=False).replace('</','<\\/')
 intro='<main class="wrap"><p><a href="../index.html">← Corpus search</a></p><div class="eyebrow">The Digital Sermon Library</div>'
 intro+='<h1>The Published Sermons of E. B. Pusey</h1><p class="intro">A Scripture-ordered catalogue based on Falconer Madan’s Appendix B (1897), with individual sermons linked wherever safe extraction from existing volumes is possible.</p>'
 intro+='<div class="stats">'+str(len(rows))+' entries · '+str(len(available))+' readable sermon texts · '+str(len(missing))+' unresolved</div>'
 intro+='<section class="search-panel"><label for="q">Find a sermon</label><div class="query-row"><input id="q" type="search" placeholder="Title, Scripture, year, volume…"></div><div class="filter-row">'
 intro+='<label for="sort">Sort by:</label><select id="sort"><option value="scripture">Scripture (Madan order)</option><option value="date">Chronological / date range</option><option value="title">Title A–Z</option></select>'
 intro+='<label for="scope">Show:</label><select id="scope"><option value="">All sermons</option><option value="available">Readable texts</option><option value="missing">Not yet located</option></select>'
 intro+='<a href="missing.html">Unresolved list</a></div></section><p id="count" class="notice"></p><ol id="list" style="padding-left:0"></ol>'
 intro+='<p class="notice">Preaching years are taken from Madan where stated; otherwise the interface gives a documented volume-level range rather than an invented year. The original sermon volumes remain available in the main corpus.</p>'
 intro+='<script type="application/json" id="data">'+rows_json+'</script><script src="listing.js"></script></main>'
 page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pusey Sermons | Digital Corpus</title><link rel="stylesheet" href="../style.css"></head><body><header><a class="brand" href="../index.html">The Pusey Corpus</a> · <b>Sermons</b></header>'+intro+'</body></html>'
 (out/'index.html').write_text(page,encoding='utf8')
 li=''.join('<li style="padding:7px 0"><b>'+escape(e['title'])+'</b> — '+escape(e['scripture'])+' · '+escape(', '.join(e['refs']) or 'no source cited')+' · '+escape(e.get('reason'))+'</li>' for e in missing)
 missingpage='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unresolved Pusey sermons</title><link rel="stylesheet" href="../style.css"></head><body><header><a class="brand" href="../index.html">The Pusey Corpus</a> · <a href="index.html">Sermons</a></header><main class="wrap"><p><a href="index.html">← Sermons</a></p><h1>Sermons not yet located</h1><p>'+str(len(missing))+' entries from Madan’s 1897 index do not yet have a safely verified extraction. Additional scans and page identifications can help complete them.</p><p><a href="match_report.json">Matching audit (JSON)</a></p><ol>'+li+'</ol></main></body></html>'
 (out/'missing.html').write_text(missingpage,encoding='utf8')
 (out/'catalogue.json').write_text(json.dumps({'entries':rows},indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 (out/'match_report.json').write_text(json.dumps([{k:e.get(k) for k in ('id','title','scripture','refs','status','code','start','end','word_count','match_score','method','reason')} for e in rows],indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 (out/'listing.js').write_text("""const data=JSON.parse(document.querySelector('#data').textContent),q=document.querySelector('#q'),sort=document.querySelector('#sort'),scope=document.querySelector('#scope'),list=document.querySelector('#list'),count=document.querySelector('#count');
function draw(){let items=data.filter(x=>(!scope.value||x.status===scope.value)&&(!q.value||[x.title,x.scripture,x.date_info.label,x.refs.join(' ')].join(' ').toLowerCase().includes(q.value.toLowerCase())));
if(sort.value==='title')items.sort((a,b)=>a.title.localeCompare(b.title)||a.order-b.order);
else if(sort.value==='date')items.sort((a,b)=>(a.date_info.earliest??a.date_info.latest??9999)-(b.date_info.earliest??b.date_info.latest??9999)||(a.date_info.latest??9999)-(b.date_info.latest??9999)||a.order-b.order);
else items.sort((a,b)=>a.order-b.order);
list.replaceChildren();const frag=document.createDocumentFragment();for(const x of items){const li=document.createElement('li');li.style.cssText='list-style:none;padding:10px 0;border-bottom:1px solid #dcd8cf';const info=document.createElement('span');info.textContent=x.scripture+' · '+x.date_info.label+' · '+x.refs.join(', ');info.style.cssText='display:block;color:#64717d;font-size:13px';const title=document.createElement(x.status==='available'?'a':'span');title.textContent=x.title;if(x.status==='available')title.href=x.id+'.html';else info.textContent+=' · Text not yet located';title.style.cssText='font:600 18px Georgia,serif';li.append(title,info);frag.append(li)}list.append(frag);count.textContent=items.length+' sermons shown'}
q.addEventListener('input',draw);sort.addEventListener('change',draw);scope.addEventListener('change',draw);draw();
""",encoding='utf8')
 (out/'within.js').write_text("""const box=document.querySelector('#sermon-text'),input=document.querySelector('#searchin'),msg=document.querySelector('#hits'),original=box.textContent;
input.addEventListener('input',()=>{const query=input.value.trim().toLowerCase();box.textContent=original;if(!query){msg.textContent='';return;}const f=document.createDocumentFragment(),lower=original.toLowerCase();let last=0,n=0,at;
while((at=lower.indexOf(query,last))>=0){f.append(document.createTextNode(original.slice(last,at)));const m=document.createElement('mark');m.textContent=original.slice(at,at+query.length);f.append(m);last=at+query.length;n++;}f.append(document.createTextNode(original.slice(last)));box.replaceChildren(f);msg.textContent=' '+n+' matches';box.querySelector('mark')?.scrollIntoView({block:'center'});});
""",encoding='utf8')
 stats={'total':len(rows),'available':len(available),'missing':len(missing),'volumes_with_text':sum(len(x['t'])>2000 for x in sources.values())}
 print('SERMON LIBRARY '+json.dumps(stats));return stats

if __name__=='__main__':
 root=Path(__file__).resolve().parent;write_site(root,root/'site')
