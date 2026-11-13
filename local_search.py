#!/usr/bin/env python3
"""Optional completely offline search interface powered by SQLite FTS5.

    python local_search.py build
    python local_search.py serve
    python local_search.py search 'repentance'

No Pagefind, Node or remote web service needed for the local version.
"""
from __future__ import annotations
import argparse, html, json, re, sqlite3, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, quote
from typing import Any
import build
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'pusey_search.sqlite3'
MANIFEST=ROOT/'bibliography.json'

HTML_PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Pusey Corpus — Offline Search</title><style>__CSS__</style></head><body><header><a class="brand" href="/">The Pusey Corpus</a><div class="subtitle">Offline full-text search · E. B. Pusey (1800–1882)</div></header><main class="wrap"><div class="eyebrow">The Digital Concordance</div><h1>Search Pusey's Works</h1><p class="intro">Search every downloaded OCR volume by word or quoted phrase. Results show the title and highlighted context; choose a result to read the surrounding text.</p><section class="search-panel"><div class="query-row"><input id="q" type="search" placeholder="repentance, Eucharist, baptism…" autofocus></div><div class="filter-row"><label for="cat">Works:</label><select id="cat"><option value="">All categories</option>__OPTIONS__</select></div></section><p class="notice" id="summary">Enter a word to begin.</p><ol class="results" id="results"></ol><button class="more" id="more" hidden>Next 40 results</button><p class="notice">This local search uses SQLite; source text may contain OCR errors. The public website uses the same collected texts.</p></main><script>
const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let offset=0,token=0;
async function search(append=false){
 const current=++token;
 const q=$('q').value.trim(); if(!append){offset=0;$('results').replaceChildren();}
 if(!q){$('summary').textContent='Enter a word or phrase to begin.';$('more').hidden=true;return;}
 $('summary').textContent='Searching local corpus…';
 try{
  const params=new URLSearchParams({q,category:$('cat').value,offset:String(offset)});
  const res=await fetch('/api/search?'+params); const obj=await res.json(); if(current!==token)return;
  if(obj.error)throw Error(obj.error);
  $('summary').textContent=`${obj.total.toLocaleString()} matching text sections`;
  for(const item of obj.results){
    const li=document.createElement('li');li.className='result';
    const link='/read?work='+encodeURIComponent(item.work_id)+'&section='+item.section+'&highlight='+encodeURIComponent(q);
    li.innerHTML=`<h3><a href="${link}">${esc(item.title)}</a></h3><div class="meta">${esc(item.year)} · ${esc(item.category)} · Section ${item.section}</div><p class="excerpt">${item.snippet}</p>`;
    $('results').appendChild(li);
  }
  offset+=obj.results.length; $('more').hidden=offset>=obj.total;
 }catch(err){$('summary').textContent='Search error: '+err.message;}
}
let timer;$('q').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>search(),200)});
$('cat').addEventListener('change',()=>search());$('more').addEventListener('click',()=>search(true));
</script></body></html>'''

def all_works():
    return json.loads(MANIFEST.read_text(encoding='utf8'))['works']

def create_db():
    DB.parent.mkdir(exist_ok=True)
    temp=DB.with_suffix('.pending.sqlite3')
    temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp)
    try:
        db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE works(id TEXT PRIMARY KEY, title TEXT, year INTEGER, category TEXT, contribution TEXT, scan_url TEXT);
        CREATE VIRTUAL TABLE sections USING fts5(text, work_id UNINDEXED, section UNINDEXED, tokenize='unicode61 remove_diacritics 2');
        ''')
        n=wc=0
        for w in all_works():
            clean=ROOT/'data'/'clean'/f'{w["id"]}.txt'
            if not clean.exists() or not w.get('index_by_default',True):continue
            rec=ROOT/'data'/'records'/f'{w["id"]}.json'
            extra=json.loads(rec.read_text(encoding='utf8')) if rec.exists() else {}
            db.execute('INSERT INTO works VALUES(?,?,?,?,?,?)',(w['id'],w['title'],w['year'],w['category'],w['contribution'],extra.get('scan_url','')))
            for j,chunk in enumerate(build.make_chunks(clean.read_text(encoding='utf8')),1):
                db.execute('INSERT INTO sections(text,work_id,section) VALUES(?,?,?)',(chunk,w['id'],j))
                wc+=len(chunk.split())
                n+=1
        db.commit()
        print(f'Indexed {n} sections, approximately {wc:,} words; {temp.stat().st_size/1_048_576:.1f} MiB')
    finally:db.close()
    temp.replace(DB)
    print('Local search database:',DB)

def fts_query(q):
    # Safe construction from words and quoted phrases. Prevent FTS syntax injection.
    raw=re.findall(r'"([^"]+)"|(\S+)',q,flags=re.UNICODE)
    phrases=[]
    for quoted,free in raw[:15]:
        terms=re.findall(r'[^\W_]+',quoted or free,flags=re.UNICODE)
        if terms:phrases.append('"'+' '.join(terms)+'"')
    return ' AND '.join(phrases)

def query_db(q,category='',offset=0,limit=40)->dict[str,Any]:
    if not DB.exists():return {'error':'Local database not built yet: run python local_search.py build'}
    search=fts_query(q)
    if not search:return {'total':0,'results':[]}
    where='sections MATCH ?'
    params=[search]
    if category:
        where+=' AND works.category=?';params.append(category)
    # Bounded public-facing pagination; no arbitrary SQL from requests.
    offset=max(0,min(int(offset),100000))
    with sqlite3.connect(DB) as db:
        total=db.execute(f'''SELECT count(*) FROM sections JOIN works ON works.id=sections.work_id WHERE {where}''',params).fetchone()[0]
        data=db.execute(f'''
          SELECT sections.work_id, sections.section, works.title, works.year, works.category,
                 snippet(sections,0,char(57344),char(57345),' … ',28)
          FROM sections JOIN works ON works.id=sections.work_id
          WHERE {where} ORDER BY bm25(sections) LIMIT ? OFFSET ?''',params+[limit,offset]).fetchall()
    items=[]
    for wid,part,title,year,cat,excerpt in data:
        excerpt=html.escape(excerpt).replace(chr(57344),'<mark>').replace(chr(57345),'</mark>')
        items.append({'work_id':wid,'section':part,'title':title,'year':year,'category':cat,'snippet':excerpt})
    return {'total':total,'results':items}

def reading_html(work_id,section,highlight=''):
    obj=next((w for w in all_works() if w['id']==work_id and w.get('index_by_default',True)),None)
    if not obj:return None
    p=ROOT/'data'/'clean'/f'{work_id}.txt'
    if not p.exists():return None
    parts=list(build.make_chunks(p.read_text(encoding='utf8')))
    if section<1 or section>len(parts):return None
    source=parts[section-1]
    safe=html.escape(source)
    terms=re.findall(r'[^\W_]+',highlight,flags=re.UNICODE)[:7]
    if terms:
        rx=re.compile('|'.join(re.escape(html.escape(t)) for t in terms if len(t)>1),re.I)
        safe=rx.sub(lambda m:'<mark>'+m.group(0)+'</mark>',safe)
    paragraphs='\n'.join('<p>'+p.strip()+'</p>' for p in re.split(r'\n\s*\n',safe) if p.strip())
    link=lambda j:f'/read?work={quote(work_id)}&section={j}&highlight={quote(highlight)}'
    prev=f'<a href="{link(section-1)}">← Previous</a>' if section>1 else ''
    nextt=f'<a href="{link(section+1)}">Next →</a>' if section<len(parts) else ''
    content=f'''<main class="wrap reading"><div class="breadcrumbs"><a href="/">Back to search</a> · Section {section} of {len(parts)}</div><h1>{html.escape(obj['title'])}</h1><p class="sourceinfo">{obj['year']} · {obj['category']}</p><div class="nav">{prev}<span></span>{nextt}</div><article class="ocr">{paragraphs}</article><div class="nav">{prev}<span></span>{nextt}</div></main>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(obj['title'])}</title><style>{build.CSS}</style></head><body><header><a class="brand" href="/">The Pusey Corpus</a></header>{content}</body></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path);qs=parse_qs(path.query)
        param=lambda k,d='':qs.get(k,[d])[0]
        if path.path=='/':
            cats=sorted({w['category'] for w in all_works()})
            choices=''.join(f'<option value="{html.escape(c,quote=True)}">{html.escape(c)}</option>' for c in cats)
            return self.send(200,HTML_PAGE.replace('__CSS__',build.CSS).replace('__OPTIONS__',choices),'text/html; charset=utf-8')
        if path.path=='/api/search':
            try:obj=query_db(param('q'),param('category'),int(param('offset','0')))
            except (ValueError,sqlite3.Error) as e:obj={'error':str(e)}
            return self.send(200,json.dumps(obj,ensure_ascii=False),'application/json; charset=utf-8')
        if path.path=='/read':
            try:page=reading_html(param('work'),int(param('section','1')),param('highlight'))
            except ValueError:page=None
            if page:return self.send(200,page,'text/html; charset=utf-8')
        return self.send(404,'Not found','text/plain; charset=utf-8')
    def send(self,status,body,mime):
        payload=body.encode('utf8')
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['build','search','serve'])
    ap.add_argument('query',nargs='*')
    ap.add_argument('--port',type=int,default=8765)
    args=ap.parse_args()
    if args.command=='build':create_db()
    elif args.command=='search':
        res=query_db(' '.join(args.query))
        if res.get('error'):print(res['error']);sys.exit(1)
        print(f'{res["total"]} matching sections')
        for x in res['results']:
            print(f'\n[{x["year"]}] {x["title"]} · section {x["section"]}\n'+re.sub('<[^>]*>','',x['snippet']))
    elif args.command=='serve':
        if not DB.exists():print('No database yet. Run: python local_search.py build');sys.exit(1)
        print(f'Offline search at http://127.0.0.1:{args.port}/')
        ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__':main()
