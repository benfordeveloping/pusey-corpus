// Independent full-text search of all four Liddon volumes, as one collection.
import {searchWithOcrVariants} from '../ocr_variants.js';

const q=document.querySelector('#q');
const browser=document.querySelector('#chapter-browser');
const area=document.querySelector('#search-area');
const hits=document.querySelector('#search-hits');
const status=document.querySelector('#search-count');
const more=document.querySelector('#search-more');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let engine=null,all=[],shown=0,sequence=0,timer=null;

async function loadEngine(){
 if(engine)return engine;
 engine=await import('./pagefind/pagefind.js');
 await engine.options({baseUrl:new URL('.',location.href).pathname,highlightParam:'highlight'});
 return engine;
}
function resultLink(raw){
 // Pagefind URLs may be site-root-relative; the chapter's indexed passage
 // has a known canonical filename and lives next to this search page.
 const name=String(raw).match(/(v[0-9]{2}-c[0-9]{2}-s[0-9]{3}[.]html)/);
 if(!name)return new URL('index.html',location.href).href;
 const url=new URL('sections/'+name[1],location.href);
 try{
  const original=new URL(raw,location.origin);
  url.search=original.search;
  url.hash=original.hash;
 }catch(_){}
 return url.href;
}
async function showMore(){
 if(!all.length)return;
 const current=sequence;
 const batch=all.slice(shown,shown+20);
 shown+=batch.length;
 const data=await Promise.all(batch.map(x=>x.data()));
 if(current!==sequence)return;
 for(const d of data){
  const volume=esc(d.meta?.volume||'');
  const chapter=esc(d.meta?.chapter||'');
  const passage=esc(d.meta?.passage||'');
  const title=[volume,chapter].filter(Boolean).join(' · ');
  const li=document.createElement('li');li.className='result';
  li.innerHTML='<h3><a href="'+esc(resultLink(d.url))+'">'+title+'</a></h3>'
   +'<div class="small">'+passage+'</div>'
   +'<p class="excerpt">'+(d.excerpt||'')+'</p>';
  hits.appendChild(li);
 }
 more.hidden=shown>=all.length;
}
async function search(){
 const current=++sequence;
 const text=q.value.trim();
 const link=new URL(location.href);
 if(text)link.searchParams.set('q',text);else link.searchParams.delete('q');
 history.replaceState(null,'',link.pathname+link.search);
 hits.replaceChildren();shown=0;all=[];more.hidden=true;
 area.hidden=!text;
 browser.hidden=!!text;
 if(!text){status.textContent='';return;}
 status.textContent='Searching the complete biography…';
 try{
  const p=await loadEngine();
  const found=await searchWithOcrVariants(p,text);
  if(current!==sequence)return;
  all=found?.results||[];
  status.textContent=all.length
   ?all.length.toLocaleString()+' matching passages across the complete biography.'
   +(found.additional?' Includes possible OCR spelling variations.':'')
   :'No matching passages found. Try another word or phrase.';
  await showMore();
 }catch(err){
  if(current===sequence)status.textContent='The biography search index is unavailable. Please try again after the site finishes publishing.';
 }
}
q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(search,260);});
more.addEventListener('click',showMore);
const initial=new URLSearchParams(location.search).get('q');
if(initial){q.value=initial;search();}
