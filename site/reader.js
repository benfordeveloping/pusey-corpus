
// Mark the query in the opened passage. No external libraries required.
const q=new URLSearchParams(location.search).get('highlight');
if(q && 'TreeWalker' in window){
 const tokens=(q.match(/[\p{L}\p{N}]+/gu)||[]).filter(t=>t.length>=2).slice(0,8);
 const root=document.querySelector('.ocr');
 if(root&&tokens.length){
  const rx=new RegExp(tokens.map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'gi');
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
