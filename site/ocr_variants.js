// Conservative OCR-tolerant searching shared by the corpus and sermon interfaces.
// Search exactly first, then only a few likely one-error OCR spellings; do not
// change historical source text, or use broad spelling correction (false positives).
const CONFUSIONS = [
 ['l','1'],['l','i'],['i','1'],['o','0'],['m','rn'],['rn','m'],
 ['d','cl'],['cl','d'],['u','v'],['v','u'],['w','vv'],['vv','w'],
 ['h','b'],['e','c'],['c','e'],['s','5']
];
export function ocrVariants(query, maxVariants=4){
 const text=String(query||'').trim();
 if(!text || text.length>120)return [];
 // Keep each phrase intact; introduce at most one OCR-like substitution.
 const words=[...text.matchAll(/[\p{L}]{4,24}/gu)];
 const variants=[],seen=new Set([text.toLocaleLowerCase()]);
 for(const match of words){
  const word=match[0],lower=word.toLocaleLowerCase();
  for(const [from,to] of CONFUSIONS){
   let start=0,at;
   while((at=lower.indexOf(from,start))!==-1){
    start=at+1;
    const variant=text.slice(0,match.index+at)+to+text.slice(match.index+at+from.length);
    const key=variant.toLocaleLowerCase();
    if(!seen.has(key)){
     seen.add(key);variants.push(variant);
     if(variants.length>=maxVariants)return variants;
    }
   }
  }
 }
 return variants;
}

export async function searchWithOcrVariants(pagefind, query, options={}){
 const exact=await pagefind.search(query,options);
 const variants=ocrVariants(query);
 if(!variants.length)return {results:exact?.results||[],variants:[],additional:0};
 // Individual OCR variants are OR-ed at the document level, while Pagefind
 // preserves its normal AND behavior for multiword phrases inside each query.
 const extra=await Promise.all(variants.map(q=>pagefind.search(q,options).catch(()=>null)));
 const results=[...(exact?.results||[])],ids=new Set(results.map(x=>x.id));
 let additional=0;
 for(const group of extra)for(const hit of group?.results||[]){
  if(!ids.has(hit.id)){ids.add(hit.id);results.push(hit);additional++;}
 }
 // Exact matches remain first; variant matches follow without duplicates.
 return {results,variants,additional};
}
