#!/usr/bin/env node
// Regression tests for both corpus search interfaces' conservative OCR fallback.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('site/ocr_variants.js','utf8')
  .replace(/\bexport\s+(?=(?:async\s+)?function)/g,'');
const api=vm.runInNewContext(source+'\n({ocrVariants,searchWithOcrVariants})');
const variants=Array.from(api.ocrVariants('love'));
assert.ok(variants.includes('1ove'),'OCR l-to-1 should find 1ove');
assert.ok(variants.includes('iove'),'OCR l-to-i should find iove');
assert.ok(variants.includes('l0ve'),'OCR o-to-0 should find l0ve');
assert.ok(variants.length<=4,'Variants must be bounded');
assert.deepEqual(Array.from(api.ocrVariants('')),[]);
assert.deepEqual(Array.from(api.ocrVariants('a very long query containing lots of words')).length<=4?[true]:[false],[true]);
const calls=[];
const engine={search:async(q,opts)=>{
 calls.push({q,opts});
 if(q==='love')return {results:[{id:'correct'},{id:'dup'}]};
 if(q==='1ove')return {results:[{id:'dup'},{id:'ocr-only'}]};
 return {results:[]};
}};
(async()=>{
 const opts={filters:{category:'Sermons'}};
 const result=await api.searchWithOcrVariants(engine,'love',opts);
 assert.deepEqual(Array.from(result.results,x=>x.id),['correct','dup','ocr-only'],
  'Exact hits must come first and OCR-only results must be appended once');
 assert.equal(result.additional,1);
 assert.ok(calls.length<=5,'Search should not issue excessive OCR alternatives');
 assert.ok(calls.every(x=>x.opts===opts),'Both searches must retain category/work filters');
 console.log('OCR VARIANTS TEST: conservative expansions, exact-first order, deduplication and scoped filters OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
