#!/usr/bin/env python3
"""Independent full-text collection and search pages for Liddon's Life of E. B. Pusey.

The corpus of Pusey's own works is never read or changed here.
Source: https://anglicanhistory.org/pusey/liddon/ (69 transcribed chapters).
Commands:
    python liddon_library.py fetch     # one-time, checks every chapter
    python liddon_library.py build     # offline, from committed JSON text
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "liddon"
SITE = ROOT / "site"
SOURCE = "https://anglicanhistory.org/pusey/liddon/"
VOLUME_CHAPTERS = {1: range(1, 19), 2: range(19, 35),
                   3: range(1, 18), 4: range(1, 19)}
ROMANS = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX",
          "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII",
          "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI",
          "XXVII", "XXVIII", "XXIX", "XXX", "XXXI", "XXXII",
          "XXXIII", "XXXIV")
EXPECTED = {(v, n) for v, nums in VOLUME_CHAPTERS.items() for n in nums}
CSS = """
:root{--ink:#25303b;--muted:#64717d;--line:#dcd8cf;--paper:#fcfbf8;--accent:#765438}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font:16px/1.7 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:#77502d}a:hover{color:#4c3117}
header{padding:16px max(24px,calc((100vw - 1050px)/2));background:#fff;border-bottom:1px solid var(--line)}
.brand{font:700 22px Georgia,serif;text-decoration:none;color:#34312e}
.subbrand{font-size:13px;color:var(--muted)}
main{max-width:1000px;margin:auto;padding:34px 24px 80px}
h1,h2,h3{font-family:Georgia,Cambria,serif;line-height:1.2;font-weight:500}
h1{font-size:clamp(31px,5vw,47px);margin:8px 0 12px}
h2{font-size:24px;margin-top:32px}h3{font-size:20px}
.kicker{color:var(--accent);font-size:12px;font-weight:700;letter-spacing:.15em;text-transform:uppercase}
.intro{font-size:18px;color:#52616e;max-width:790px}
.muted,.count,.small{color:var(--muted);font-size:13px}
.search-panel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px;margin:23px 0 24px;box-shadow:0 3px 16px #30201008}
input[type=search]{width:100%;border:1px solid #c9c8c3;border-radius:7px;padding:13px 15px;font:19px system-ui}
input:focus{outline:2px solid #9c8064}
.results{list-style:none;margin:0;padding:0}.result{padding:19px 0;border-bottom:1px solid var(--line)}
.result h3{margin:0 0 4px}.result h3 a{text-decoration:none}
.excerpt{font:17px/1.75 Georgia,serif;color:#373430;margin:9px 0 0}
mark{background:#ffe4a5;padding:0 2px;border-radius:2px}
button{font:inherit;background:#fff;border:1px solid var(--line);padding:10px 18px;border-radius:6px;cursor:pointer}
.volume{margin:30px 0}.chapters{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:4px 24px}
.chapters li{border-bottom:1px solid var(--line);padding:7px 0}
.reader{max-width:790px}.reader h1{font-size:36px}
.prose{font:18px/1.86 Georgia,Cambria,serif;color:#302f2d;margin-top:30px}
.prose p{margin:0 0 1.1em;white-space:pre-wrap;overflow-wrap:anywhere}
.reader-nav{display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap;padding:22px 0;border-bottom:1px solid var(--line)}
.source-note{border-top:1px solid var(--line);margin-top:38px;padding-top:15px}
[hidden]{display:none!important}
@media(max-width:550px){main{padding:25px 18px}.prose{font-size:17px}.chapters{display:block}}
"""

def key(volume: int, chapter: int) -> str:
    return f"v{volume:02d}-c{chapter:02d}"

def label(volume: int, chapter: int) -> str:
    return f"Volume {ROMANS[volume]} · Chapter {ROMANS[chapter]}"

def fetch_html(url: str) -> bytes:
    last_error = None
    for attempt in range(4):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PuseyCorpus-Research/1.0)",
                                        "Accept": "text/html"})
            with urlopen(req, timeout=45) as response:
                content = response.read()
            if len(content) < 600:
                raise ValueError(f"Unexpectedly short HTML ({len(content)} bytes)")
            return content
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt * 2)
    raise RuntimeError(f"Cannot download {url}: {last_error}")

def source_chapters():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fetch_html(SOURCE), "html.parser")
    links = {}
    for a in soup.select("a[href]"):
        url = urljoin(SOURCE, a["href"])
        hit = re.fullmatch(r"https://anglicanhistory[.]org/pusey/liddon/([1-4])[.]([0-9]+)[.]html", url)
        if hit:
            spec = (int(hit.group(1)), int(hit.group(2)))
            if spec in links and links[spec] != url:
                raise RuntimeError(f"Ambiguous source link: {spec}")
            links[spec] = url
    if set(links) != EXPECTED:
        raise RuntimeError(f"TOC mismatch: missing={sorted(EXPECTED - set(links))}, unexpected={sorted(set(links) - EXPECTED)}")
    return links

def extract_text(payload: bytes, volume: int, chapter: int) -> str:
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(payload, "html.parser")
    for tag in soup.select("script,style,noscript"):
        tag.decompose()
    # Some Project Canterbury chapters contain irregular or repeated BODY tags.
    # Extract the entire parsed document rather than the first BODY subtree.
    body = soup
    # Preserve all text nodes, including letters, block quotations and notes.
    # The original HTML uses some unconventional 2002-era heading markup.
    for tag in list(body.find_all(["p", "div", "blockquote", "h1", "h2", "h3", "h4", "li", "tr", "br"])):
        if tag.name == "br":
            tag.replace_with(NavigableString("\n"))
        else:
            tag.append(NavigableString("\n\n"))
    text = html.unescape(body.get_text(separator="")).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    source_words = len(text.split())

    # Do not match the *first occurrence anywhere* of 'Chapter XIX', because
    # the narrative itself contains chapter references. Begin immediately
    # after the transcription credit, and locate the near-opening heading.
    credit = re.search(r"\bAD\s*2002\b", text, re.I)
    beginning = text[credit.end():] if credit else text
    heading = re.search(r"\bCHAPTER\b", beginning[:3500], re.I)
    if not heading:
        raise ValueError(f"No opening chapter heading in {key(volume,chapter)}; "
                         f"source text begins {beginning[:200]!r}")
    text = beginning[heading.start():]

    # Strip only the FINAL Project Canterbury footer. An internal ornament
    # or cross-reference should never terminate a chapter prematurely.
    footers = list(re.finditer(r"\n\s*\* *\* *\*\s*\n\s*Project Canterbury\b", text, re.I))
    if footers and footers[-1].start() > len(text) * .70:
        text = text[:footers[-1].start()]
    elif text.rstrip().endswith("Project Canterbury"):
        text = text[:text.rfind("Project Canterbury")]
    text = text.strip()
    extracted = len(text.split())
    if extracted < 400 or extracted < source_words * .85:
        raise ValueError(f"Possible truncated chapter {key(volume,chapter)}: "
                         f"{extracted} extracted versus {source_words} source words")
    return text

def harvest() -> None:
    links = source_chapters()
    DATA.mkdir(parents=True, exist_ok=True)
    files = []
    for idx, ((volume, chapter), url) in enumerate(sorted(links.items()), 1):
        original = fetch_html(url)
        text = extract_text(original, volume, chapter)
        record = {
            "volume": volume, "chapter": chapter, "label": label(volume, chapter),
            "source_url": url, "source_html_sha256": hashlib.sha256(original).hexdigest(),
            "words": len(text.split()), "text": text,
            "transcription_credit": "Transcribed by the Revd R. D. Hacking, Project Canterbury (2002)"
        }
        target = DATA / f"{key(volume, chapter)}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n", "utf-8")
        files.append(target)
        print(f"LIDDON {idx:02d}/69 {label(volume,chapter)}: {record['words']:,} words", flush=True)
        time.sleep(0.15)
    if len(files) != 69:
        raise RuntimeError(f"Expected 69 chapters; saved {len(files)}")
    print("LIDDON IMPORT COMPLETE 69 chapters, " +
          f"{sum(json.loads(f.read_text('utf8'))['words'] for f in files):,} words", flush=True)

def paragraphs(text: str) -> list[str]:
    # Paragraphs are taken from the edition's own HTML block boundaries.
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

def sections(paras: list[str], target_words: int = 900) -> list[list[str]]:
    result, batch, count = [], [], 0
    for para in paras:
        n = len(para.split())
        if batch and count + n > target_words:
            result.append(batch)
            batch, count = [], 0
        # A long original block is not discarded or truncated.
        if n > target_words * 2:
            words = para.split()
            for offset in range(0, len(words), target_words):
                if batch:
                    result.append(batch)
                    batch, count = [], 0
                result.append([" ".join(words[offset:offset + target_words])])
        else:
            batch.append(para)
            count += n
    if batch:
        result.append(batch)
    return result

def page(title: str, body: str) -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(title) + '</title><style>' + CSS + '</style></head><body>'
            '<header><a class="brand" href="../index.html">The Pusey Corpus</a>'
            '<div class="subbrand">Liddon’s Life of Edward Bouverie Pusey · independent biography search</div>'
            '</header>' + body + '</body></html>')

def prose(paras: list[str]) -> str:
    return '<div class="prose">' + ''.join('<p>' + html.escape(p) + '</p>' for p in paras) + '</div>'

def read_records() -> list[dict]:
    docs = []
    for volume, nums in VOLUME_CHAPTERS.items():
        for chapter in nums:
            filename = DATA / f"{key(volume,chapter)}.json"
            if not filename.exists():
                return []
            record = json.loads(filename.read_text("utf-8"))
            if record["volume"] != volume or record["chapter"] != chapter:
                raise ValueError(f"Bad chapter metadata: {filename}")
            if not record["text"] or len(record["text"].split()) < 400:
                raise ValueError(f"Truncated chapter: {filename}")
            docs.append(record)
    if len(docs) != 69:
        raise RuntimeError("Liddon import must have exactly 69 chapters")
    return docs

def build() -> dict:
    out = SITE / "liddon"
    out.mkdir(parents=True, exist_ok=True)
    docs = read_records()
    if not docs:
        placeholder = ('<main><div class="kicker">Liddon</div>'
                       '<h1>Liddon’s Life of Edward Bouverie Pusey</h1>'
                       '<p>The independent transcription harvest has not completed yet. '
                       'The chapter search will appear after all 69 chapters have been imported.</p></main>')
        (out / "index.html").write_text(page("Liddon's Life of Pusey", placeholder), "utf-8")
        print("LIDDON BUILD: waiting for the 69 source chapters")
        return {"chapters": 0, "sections": 0}
    chapterdir, sectiondir = out / "chapters", out / "sections"
    shutil.rmtree(chapterdir, ignore_errors=True)
    shutil.rmtree(sectiondir, ignore_errors=True)
    chapterdir.mkdir()
    sectiondir.mkdir()
    navigation = [(d["volume"],d["chapter"]) for d in docs]
    total_words, total_sections = 0, 0
    volume_links = {}
    for i, doc in enumerate(docs):
        v, c = doc["volume"], doc["chapter"]
        name, stem = label(v,c), key(v,c)
        paras = paragraphs(doc["text"])
        groups = sections(paras)
        total_words += doc["words"]
        total_sections += len(groups)
        volume_links.setdefault(v, []).append(
            '<li><a href="chapters/' + stem + '.html">Chapter ' + ROMANS[c] + '</a></li>')
        prev = f'<a href="{key(*navigation[i-1])}.html">← Previous chapter</a>' if i else '<span></span>'
        nex = f'<a href="{key(*navigation[i+1])}.html">Next chapter →</a>' if i < len(docs)-1 else '<span></span>'
        chapters = ('<main class="reader"><div class="kicker">Henry Parry Liddon · 1894</div>'
                    '<h1>' + name + '</h1><p><a href="../index.html">All 69 chapters · Search</a></p>'
                    '<div class="reader-nav">' + prev + nex + '</div>' + prose(paras)
                    + '<div class="reader-nav">' + prev + nex + '</div>'
                    '<p class="source-note small">Transcription: Revd R. D. Hacking (2002), Project Canterbury. '
                    '<a href="' + html.escape(doc["source_url"], quote=True) + '">Original source chapter</a>.</p>'
                    '</main>')
        (chapterdir / (stem + ".html")).write_text(page(name + " | Liddon", chapters), "utf-8")
        for j, group in enumerate(groups, 1):
            section_id = f"{stem}-s{j:03d}"
            sec_title = name + " · Passage " + str(j)
            # One indexed page per ~900 words yields relevant excerpts and multiple hits per chapter.
            head = ('<meta data-pagefind-meta="volume[content]" content="Volume ' + ROMANS[v] + '">'
                    '<meta data-pagefind-meta="chapter[content]" content="Chapter ' + ROMANS[c] + '">'
                    '<meta data-pagefind-meta="passage[content]" content="Passage ' + str(j) + '">')
            contents = ('<main class="reader"><div class="kicker">Henry Parry Liddon · 1894</div>'
                        '<h1>' + name + '</h1><p><a href="../chapters/' + stem +
                        '.html">Read complete chapter</a> · <a href="../index.html">Search biography</a></p>'
                        '<article data-pagefind-body id="liddon-text">' + prose(group) + '</article>'
                        '<p class="small"><a href="' + html.escape(doc["source_url"], quote=True) +
                        '">Source transcription</a></p></main>')
            # The Pagefind metadata must live on the page being indexed.
            document = page(sec_title + " | Liddon", contents)
            document = document.replace('</head>', head + '</head>', 1)
            (sectiondir / (section_id + ".html")).write_text(document, "utf-8")
    catalogue = ''.join(
        '<section class="volume"><h2>Volume ' + ROMANS[v] + '</h2><ol class="chapters">' +
        ''.join(volume_links[v]) + '</ol></section>' for v in VOLUME_CHAPTERS)
    main = ('<main><div class="kicker">Liddon</div>'
            '<h1>The Life of Edward Bouverie Pusey</h1>'
            '<p class="intro">Henry Parry Liddon’s biography (1894), searchable as one continuous '
            'work across all four original volumes. Results identify the original volume, chapter, '
            'and passage, and open the text in context.</p>'
            '<p class="small">Transcription by the Revd R. D. Hacking (2002), '
            '<a href="' + SOURCE + '">Project Canterbury</a>.</p>'
            '<div class="count">' + str(len(docs)) + ' chapters · ' +
            f'{total_words:,}' + ' searchable words</div>'
            '<section class="search-panel"><label for="q"><strong>Search the complete biography</strong></label>'
            '<input type="search" id="q" placeholder="Word or phrase…" autocomplete="off">'
            '<p class="small">Searches all 69 chapters together. Quoted phrases are supported; '
            'possible OCR spelling variations are included.</p></section>'
            '<section id="search-area" hidden><p id="search-count" class="count" role="status"></p>'
            '<ol id="search-hits" class="results"></ol>'
            '<button id="search-more" type="button" hidden>Show more results</button></section>'
            '<div id="chapter-browser"><h2>Browse all chapters</h2>' + catalogue + '</div>'
            '<script type="module" src="search.js"></script></main>')
    (out / "index.html").write_text(page("Search Liddon's Life of Pusey",main), "utf-8")
    shutil.copy2(ROOT / "liddon_search.js", out / "search.js")
    print(f"LIDDON BUILD COMPLETE {len(docs)} chapters / {total_sections} indexed passages / {total_words:,} words")
    return {"chapters": len(docs), "sections": total_sections, "words": total_words}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("fetch", "build"):
        raise SystemExit("Usage: python liddon_library.py [fetch|build]")
    if sys.argv[1] == "fetch":
        harvest()
    else:
        build()
