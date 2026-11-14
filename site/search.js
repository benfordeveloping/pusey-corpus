
import {searchWithOcrVariants} from './ocr_variants.js';
const input = document.querySelector('#query');
const category = document.querySelector('#category');
const work = document.querySelector('#work');
const count = document.querySelector('#result-count');
const results = document.querySelector('#results');
const more = document.querySelector('#more');
const params = new URLSearchParams(location.search);
const initial = params.get('q');
if (initial) input.value=initial;
// Restore shareable search scope, with a single work taking precedence.
const requestedWork = params.get('work');
const requestedCategory = params.get('category');
if (requestedWork && Array.from(work.options).some(o => o.value === requestedWork)) {
  work.value = requestedWork;
} else if (requestedCategory && Array.from(category.options).some(o => o.value === requestedCategory)) {
  category.value = requestedCategory;
}
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
  if(work.value)url.searchParams.set('work',work.value);else url.searchParams.delete('work');
  if(category.value)url.searchParams.set('category',category.value);else url.searchParams.delete('category');
  history.replaceState(null,'',url.pathname+url.search);
  if(!q){count.textContent='Enter a word or phrase to search the indexed texts.';return;}
  count.textContent='Searching…';
  try{
    const p=await loadEngine();
    const options=work.value ? {filters:{work_id:work.value}} : category.value ? {filters:{category:category.value}} : {};
    const found=await searchWithOcrVariants(p,q,options);
    if(mySequence!==sequence)return;
    all=found?.results||[];
    const selectedWork = work.options[work.selectedIndex]?.textContent || '';
    const scope = work.value ? ` within “${selectedWork}”` : category.value ? ` in ${category.value}` : ' across the corpus';
    count.textContent=`${all.length.toLocaleString()} matching text sections${scope}. Each result identifies the work and opens the full passage.${found.additional?' Includes '+found.additional+' extra sections found through likely OCR misreadings.':''}`;
    await renderMore();
  }catch(err){if(mySequence===sequence)count.textContent='Search not yet available. Finish the harvesting and indexing steps first.';}
}
input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(runSearch,250)});
category.addEventListener('change',()=>{
  if(category.value)work.value='';
  runSearch();
});
work.addEventListener('change',()=>{
  if(work.value)category.value='';
  runSearch();
});
more.addEventListener('click',renderMore);
if(initial)runSearch();
