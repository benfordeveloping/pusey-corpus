#!/usr/bin/env python3
"""Build static corpus reader and Pagefind-ready pages from downloaded OCR.

    python build.py
    npx -y pagefind --site site
    python -m http.server 8000 -d site
"""
from __future__ import annotations
import html, json, re, shutil, sys
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent
SITE=ROOT/'site'
WORKSDIR=SITE/'works'
CLEAN=ROOT/'data'/'clean'
RECORDS=ROOT/'data'/'records'
CHUNK_WORDS=1000

CSS='''
:root{--ink:#25303b;--muted:#64717d;--line:#dcd8cf;--paper:#fcfbf8;--white:#fff;--accent:#765438;--soft:#f3eee5}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{font:16px/1.65 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--paper);margin:0}
a{color:#77502d}a:hover{color:#4c3117}header{background:#fff;border-bottom:1px solid var(--line);padding:15px max(24px,calc((100vw - 1050px)/2))}header .brand{font:700 22px/1.3 Georgia,serif;color:#2f302f;text-decoration:none}
header .subtitle{font-size:12px;color:var(--muted)}.wrap{max-width:1000px;margin:0 auto;padding:32px 24px 75px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
h1,h2,h3{font-family:Georgia,Cambria,serif;line-height:1.2}h1{font-size:clamp(30px,4.5vw,49px);margin:8px 0 12px;font-weight:500}h2{font-size:24px;font-weight:500}p.intro{color:#52616e;max-width:720px;font-size:18px}.stats{font-size:13px;color:var(--muted);margin:17px 0 28px}
.search-panel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:21px;box-shadow:0 3px 16px #30201008}.query-row{display:flex;gap:12px}.query-row input{flex:1;min-width:0;padding:12px 15px;font-size:19px;border:1px solid #c9c8c3;border-radius:7px;background:white}.query-row input:focus{outline:2px solid #9c8064}.filter-row{display:flex;gap:15px;align-items:center;margin-top:12px;flex-wrap:wrap;color:var(--muted);font-size:13px}.filter-row select{max-width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;background:white}
.notice{color:var(--muted);font-size:13px;margin:18px 0}.results{list-style:none;padding:0;margin:0}.result{border-bottom:1px solid var(--line);padding:23px 0}.result h3{font-size:20px;margin:0 0 2px}.result h3 a{text-decoration:none}.result .meta{font-size:13px;color:var(--muted)}.result .excerpt{font-family:Georgia,Cambria,serif;font-size:17px;line-height:1.8;color:#34322e;margin:10px 0 0}.result mark,mark{background:#ffe4a5;border-radius:2px;padding:0 2px}.more{border:1px solid var(--line);background:#fff;padding:10px 18px;border-radius:7px;cursor:pointer;font:inherit;margin:24px 0}
.catalogue{margin-top:60px}.catalogue .item{display:grid;grid-template-columns:68px 1fr auto;gap:16px;align-items:start;border-bottom:1px solid var(--line);padding:12px 0}.catalogue .item .date{color:var(--muted);font-size:13px}.catalogue .item .name{font-weight:600}.catalogue .item .source{font-size:12px;color:var(--muted)}.state{font-size:12px;white-space:nowrap;color:var(--muted)}.state.ready{color:#27664a}
.reading{max-width:780px}.reading h1{font-size:32px}.reading .breadcrumbs{font-size:13px;color:var(--muted)}.reading .ocr{font:18px/1.78 Georgia,Cambria,serif;overflow-wrap:anywhere}.reading .ocr p{margin:1.05em 0}.reading .nav{display:flex;justify-content:space-between;gap:16px;padding:20px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:30px 0}.reading .sourceinfo{font-size:13px;color:var(--muted)}
@media(max-width:600px){header{padding:15px 20px}.wrap{padding:26px 18px 60px}.query-row input{font-size:16px}.catalogue .item{grid-template-columns:45px 1fr;gap:10px}.catalogue .item .state{grid-column:2}.result .excerpt{font-size:16px}}
'''

JS='''
const input = document.querySelector('#query');
const category = document.querySelector('#category');
const count = document.querySelector('#result-count');
const results = document.querySelector('#results');
const more = document.querySelector('#more');
const initial = new URLSearchParams(location.search).get('q');
if (initial) input.value=initial;
let engine=null, all=[], shown=0, sequence=0, timer=null;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function loadEngine(){
  if(engine) return engine;
  try {
    // Relative import makes this compatible with GitHub Pages project subpaths.
    engine=await import('./pagefind/pagefind.js');
    const base=new URL('.',location.href).pathname;
    await engine.options({baseUrl:base,highlightParam:'highlight'});
    return engine;
  } catch(e) {
    count.textContent='The search index has not yet been generated. Run Pagefind after harvesting the texts.';
    throw e;
  }
}
async function renderMore(){
  if(!all.length) return;
  const mySequence=sequence;
  const batch=all.slice(shown,shown+20);
  shown+=batch.length;
  const data=await Promise.all(batch.map(x=>x.data()));
  if(mySequence!==sequence) return;
  for(const d of data){
    const li=document.createElement('li');li.className='result';
    // Pagefind guarantees escaped excerpt except for its own <mark> spans.
    const title=esc(d.meta?.work || d.meta?.title || 'Untitled work');
    const label=esc(d.meta?.section || '');
    const year=esc(d.meta?.year||'');
    const href=esc(d.url);
    li.innerHTML=`<h3><a href="${href}">${title}</a></h3><div class="meta">${year}${year&&label?' · ':''}${label}</div><p class="excerpt">${d.excerpt||''}</p>`;
    results.appendChild(li);
  }
  more.hidden = shown>=all.length;
}
async function runSearch(){
  const mySequence=++sequence;
  results.replaceChildren();shown=0;all=[];more.hidden=true;
  const q=input.value.trim();
  const url=new URL(location.href);
  if(q)url.searchParams.set('q',q);else url.searchParams.delete('q');
  history.replaceState(null,'',url.pathname+url.search);
  if(!q){count.textContent='Enter a word or phrase to search the indexed texts.';return;}
  count.textContent='Searching…';
  try{
    const p=await loadEngine();
    const options=category.value ? {filters:{category:category.value}} : {};
    const found=await p.search(q,options);
    if(mySequence!==sequence)return;
    all=found?.results||[];
    count.textContent=`${all.length.toLocaleString()} matching text sections. Each result identifies the work and opens the full passage.`;
    await renderMore();
  }catch(err){if(mySequence===sequence)count.textContent='Search not yet available. Finish the harvesting and indexing steps first.';}
}
input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(runSearch,250)});
category.addEventListener('change',runSearch);
more.addEventListener('click',renderMore);
if(initial)runSearch();
'''

READER_JS='''
// Mark the query in the opened passage. No external libraries required.
const q=new URLSearchParams(location.search).get('highlight');
if(q && 'TreeWalker' in window){
 const tokens=(q.match(/[\\p{L}\\p{N}]+/gu)||[]).filter(t=>t.length>=2).slice(0,8);
 const root=document.querySelector('.ocr');
 if(root&&tokens.length){
  const rx=new RegExp(tokens.map(x=>x.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')).join('|'),'gi');
  const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const found=[];
  while(walk.nextNode())if(walk.currentNode.textContent && rx.test(walk.currentNode.textContent)){found.push(walk.currentNode);rx.lastIndex=0;}
  for(const node of found){
   const frag=document.createDocumentFragment();let at=0;const s=node.textContent;rx.lastIndex=0;
   for(const m of s.matchAll(rx)){
    if(m.index>at)frag.appendChild(document.createTextNode(s.slice(at,m.index)));
    const mark=document.createElement('mark');mark.textContent=m[0];frag.appendChild(mark);at=m.index+m[0].length;
   }
   if(at<s.length)frag.appendChild(document.createTextNode(s.slice(at)));
   node.parentNode.replaceChild(frag,node);
  }
  document.querySelector('mark')?.scrollIntoView({block:'center'});
 }
}
'''

def make_chunks(text,target=CHUNK_WORDS):
    # OCR line wrapping is not paragraph structure; reflow single newlines only.
    text=text.replace('\f','\n\n')
    text=re.sub(r'(?<!\n)\n(?!\n)',' ',text)
    text=re.sub(r'[ \t]{2,}',' ',text)
    matches=list(re.finditer(r'\S+',text))
    for i in range(0,len(matches),target):
        span=matches[i:i+target]
        if not span:break
        yield text[span[0].start():span[-1].end()]

def render_paragraphs(s):
    parts=re.split(r'\n\s*\n+',s.strip())
    return '\n'.join(f'<p>{html.escape(p.strip())}</p>' for p in parts if p.strip())

def frame(title,content,script='',metadata=''):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>{metadata}<link rel="stylesheet" href="{script}style.css"></head><body><header><a class="brand" href="{script}index.html">The Pusey Corpus</a><div class="subtitle">A full-text concordance of the works of E. B. Pusey (1800–1882)</div></header>{content}</body></html>'''

def main():
    catalog=json.loads((ROOT/'bibliography.json').read_text(encoding='utf8'))['works']
    # Rebuild reading pages from scratch: obsolete pages must never remain searchable.
    # Especially important when a full translated work has been replaced by an
    # approved introduction-only excerpt.
    SITE.mkdir(exist_ok=True)
    if WORKSDIR.exists():
        shutil.rmtree(WORKSDIR)
    WORKSDIR.mkdir(exist_ok=True)
    (SITE/'style.css').write_text(CSS,encoding='utf8')
    (SITE/'search.js').write_text(JS,encoding='utf8')
    (SITE/'reader.js').write_text(READER_JS,encoding='utf8')
    (SITE/'.nojekyll').touch()
    indexed=[];rows=[];total_words=0;section_total=0
    for work in catalog:
        slug=work['id']
        txt=CLEAN/(slug+'.txt')
        rec_file=RECORDS/(slug+'.json')
        rec=json.loads(rec_file.read_text(encoding='utf8')) if rec_file.exists() else {}
        status=rec.get('status','not downloaded')
        # Fail closed on texts written by other authors. A translated or edited
        # volume is not Pusey's prose merely because he wrote its introduction.
        # Such entries are indexed ONLY when a separately extracted, reviewed
        # passage has been supplied, with explicit scope and provenance.
        scope_required = {
            'translation': 'pusey_translator_introduction_only',
            'editorial': 'pusey_preface_or_introduction_only',
            'mixed': 'pusey_authored_passages_only',
        }.get(work.get('contribution', 'authored'))
        excerpt_approved = (not scope_required or (
            rec.get('scope_verified') is True
            and rec.get('content_scope') == scope_required
            and bool(rec.get('extraction_boundaries'))
        ))
        if txt.exists() and work.get('index_by_default',True) and excerpt_approved:
            source=txt.read_text(encoding='utf8')
            chunks=list(make_chunks(source))
            if not chunks: status='empty text'
            else:
                place=WORKSDIR/slug
                place.mkdir(exist_ok=True)
                # Remove obsolete numbered pages on rebuild.
                for old in place.glob('*.html'):old.unlink()
                wc=len(re.findall(r'\b\w+\b',source))
                total_words+=wc
                section_total+=len(chunks)
                indexed.append({'id':slug,'title':work['title'],'year':work['year'],'category':work['category'],'words':wc,'sections':len(chunks),'source':rec.get('scan_url','')})
                for i,chunk in enumerate(chunks,1):
                    meta=f'''<meta data-pagefind-meta="work[content]" content="{html.escape(work['title'],quote=True)}"><meta data-pagefind-meta="year[content]" content="{work['year']}"><meta data-pagefind-meta="section[content]" content="Section {i} of {len(chunks)}"><meta data-pagefind-filter="category[content]" content="{html.escape(work['category'],quote=True)}">'''
                    navleft=f'<a href="{i-1:04d}.html">← Previous section</a>' if i>1 else '<span></span>'
                    navright=f'<a href="{i+1:04d}.html">Next section →</a>' if i<len(chunks) else '<span></span>'
                    scan=f'<a href="{html.escape(rec["scan_url"],quote=True)}" target="_blank" rel="noopener">Original scanned edition</a>' if rec.get('scan_url') else 'Source scan not recorded'
                    edition_notice = f' · OCR source printed {work["source_edition_year"]} (reprint)' if work.get('source_edition_year') else ''
                    body=f'''<main class="wrap reading"><div class="breadcrumbs"><a href="../../index.html">Search corpus</a> / {work['year']} / Section {i} of {len(chunks)}</div><h1>{html.escape(work['title'])}</h1><p class="sourceinfo">First published {work['year']}{edition_notice} · {html.escape(work['category'])} · {scan}</p><div class="nav">{navleft}{navright}</div><article class="ocr" data-pagefind-body>{render_paragraphs(chunk)}</article><div class="nav">{navleft}{navright}</div></main><script src="../../reader.js" defer></script>'''
                    (place/f'{i:04d}.html').write_text(frame(f'{work["title"]} — {i}',body,'../../',meta),encoding='utf8')
                status='indexed'
        elif txt.exists() and not excerpt_approved:
            status='excluded: needs verified Pusey-only excerpt'
        elif txt.exists() and not work.get('index_by_default',True):
            status='downloaded, excluded duplicate'
        rows.append({'year':work['year'],'title':work['title'],'status':status,'category':work['category'],'id':slug,'scan_url':rec.get('scan_url',''),'source_edition_year':work.get('source_edition_year')})
    (SITE/'catalogue.json').write_text(json.dumps({'bibliography_count':len(catalog),'indexed_works':len(indexed),'word_count':total_words,'section_count':section_total,'works':rows},indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    blocks=[]
    for row in rows:
        ready=row['status']=='indexed'
        text=html.escape(row['title'])
        if ready:text=f'<a href="works/{row["id"]}/0001.html">{text}</a>'
        label='Indexed' if ready else ('Pusey introduction only: awaiting extraction' if 'needs verified Pusey-only excerpt' in row['status'] else ('Duplicate edition' if 'duplicate' in row['status'] else 'Awaiting OCR'))
        blocks.append(f'''<div class="item"><span class="date">{row['year']}</span><div class="name">{text}<div class="source">{html.escape(row['category'])}{' · OCR source: '+str(row['source_edition_year'])+' reprint' if row.get('source_edition_year') else ''}</div></div><span class="state {'ready' if ready else ''}">{label}</span></div>''')
    cats=sorted({w['category'] for w in catalog})
    select=''.join(f'<option value="{html.escape(c,quote=True)}">{html.escape(c)}</option>' for c in cats)
    if indexed:
        search='''<section class="search-panel"><label for="query" class="eyebrow">Search the corpus</label><div class="query-row"><input id="query" type="search" placeholder="Enter a word or phrase…" autocomplete="off" spellcheck="false"></div><div class="filter-row"><label for="category">Limit search:</label><select id="category"><option value="">All categories</option>'''+select+'''</select><span>Original OCR; occasional recognition errors are expected.</span></div></section><p id="result-count" class="notice" role="status">Enter a word or phrase to search the indexed texts.</p><ol id="results" class="results"></ol><button id="more" class="more" hidden>Show 20 more results</button><script type="module" src="search.js"></script>'''
    else:
        search='<section class="search-panel"><p><strong>Corpus is not indexed yet.</strong> The collection framework and bibliography are in place. Run the harvester to download OCR and rebuild the site, then run Pagefind to enable search.</p></section>'
    body=f'''<main class="wrap"><div class="eyebrow">The Digital Concordance</div><h1>The Works of E. B. Pusey</h1><p class="intro">Search Pusey’s own writings across theology, sermons, tracts, commentary, and correspondence. For translated or edited works, only his personally written introduction or preface is included. Search results identify the work immediately and open the text in full context.</p><div class="stats">{len(indexed)} works indexed · {total_words:,} searchable words · {section_total:,} reading sections · {len(catalog)} bibliography items</div>{search}<section class="catalogue"><h2>Bibliography &amp; collection progress</h2><p class="notice">Based on the <a href="https://sites.google.com/view/drpusey/works">bibliography of major works</a>. Multi-volume entries are counted separately. Repeated editions are listed but may be excluded from the default search.</p>{''.join(blocks)}</section></main>'''
    (SITE/'index.html').write_text(frame('The Pusey Corpus | Search',body),encoding='utf8')
    print(f'Built {len(indexed)} works / {section_total} HTML sections / {total_words:,} words into {SITE}')
    if not indexed:print('Search index not generated: first harvest OCR using harvest.py.')
    else:print('NEXT: npx -y pagefind --site site   (needs Node.js and network access to npm)')

if __name__=='__main__':main()
