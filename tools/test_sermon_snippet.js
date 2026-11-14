#!/usr/bin/env node
// Exercise the actual generated sermon excerpt function, not a copy of it.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const js = fs.readFileSync(path.join(__dirname, '../site/sermons/listing.js'), 'utf8');
const start = js.indexOf('function hitSentence(');
const end = js.indexOf('\nasync function renderMore()', start);
assert.ok(start >= 0 && end > start, 'Generated full-sentence excerpt helper exists');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const hitSentence = vm.runInNewContext(js.slice(start, end) + '\nhitSentence;', {esc: escape});

const text = 'The first sermon is about charity. The preacher said that repentance draws the soul towards God. The congregation listened carefully.';
const wordIndex = [...text.matchAll(/\S+/g)].findIndex(m => m[0] === 'repentance');
assert.ok(wordIndex > 0);
const snippet = hitSentence({content: text, locations: [wordIndex]}, 'repentance');
assert.match(snippet, /<mark>repentance<\/mark>/, 'Search term is visibly highlighted');
assert.match(snippet, /The preacher said that/, 'Snippet displays its actual surrounding sentence');
assert.match(snippet, /towards God\./, 'Snippet includes the end of the sentence');

const safeText = 'Pusey spoke about <charity> in his sermon. The congregation listened.';
const safeLocation = [...safeText.matchAll(/\S+/g)].findIndex(m => m[0].includes('charity'));
const safe = hitSentence({content: safeText, locations: [safeLocation]}, 'charity');
assert.match(safe, /&lt;<mark>charity<\/mark>&gt;/, 'Source text must be escaped');

const fallback = 'OCR displays <mark>grace</mark> in the original context';
assert.equal(hitSentence({content: 'An unrelated word appears here.', locations: [2], excerpt: fallback}, 'grace'),
  fallback, 'Use Pagefind’s highlighted excerpt for OCR/stemming mismatches');

// Regression: Pagefind supplies a site-relative href from a nested search
// page. Directly using it produced /sermons/sermons/m146.html (404).
const linkStart=js.indexOf('function sermonResultUrl(');
const linkEnd=js.indexOf('\nasync function renderMore()',linkStart);
assert.ok(linkStart>=0&&linkEnd>linkStart,'Generated sermon URL resolver exists');
const root='https://benfordeveloping.github.io/pusey-corpus/sermons/';
const href=vm.runInNewContext(js.slice(linkStart,linkEnd)+'\nsermonResultUrl;',{
 URL, location:{href:root+'index.html'}
});
const wanted=root+'m146.html?highlight=love';
for(const form of [
 'sermons/m146.html?highlight=love',
 'm146.html?highlight=love',
 '/pusey-corpus/sermons/m146.html?highlight=love',
]){
 assert.equal(href(form),wanted,'Result URL must always target the local sermon page');
}
assert.ok(!href('sermons/m146.html?highlight=love').includes('/sermons/sermons/'),
 'Never duplicate the sermon directory in result links');

console.log('SERMON SNIPPET TEST: contextual sentences, highlighted hits, escaped text, and Pagefind fallback OK');
