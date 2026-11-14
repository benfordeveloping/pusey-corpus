#!/usr/bin/env python3
"""Verify the exact owner sources and safe Pusey-only indexing boundaries."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
def read(p):return (root/p).read_text(encoding="utf-8")
records="data/records/"
t=json.loads(read(records+"1842-introduction-and-notes-to-tertullian.json"))
u=json.loads(read(records+"1859-university-sermons-vol-i-nine-sermons.json"))
p=json.loads(read(records+"1860-the-minor-prophets-with-commentary.json"))
assert t["status"]=="downloaded" and t["scope_verified"] is True
assert t["content_scope"]=="pusey_preface_or_introduction_only"
ts=read("data/clean/1842-introduction-and-notes-to-tertullian.txt")
for name in "ABCDEFGHIKLMNOPQR":
    assert "[EDITORIAL NOTE "+name+"]" in ts,name
assert "[SIGNED PREFACE" in ts
assert not any(x in ts for x in (
    "[ADDITIONAL NOTES]","THE FIRST BOOK TO HIS WIFE",
    "THE SECOND BOOK TO HIS WIFE","ON PRESCRIPTION AGAINST HERETICS"))
assert len(t["extraction_boundaries"]["included_sections"])==18
assert 70_000<len(ts.split())<90_000
assert len(read("data/raw/1842-introduction-and-notes-to-tertullian.txt"))>1_900_000
us=read("data/clean/1859-university-sermons-vol-i-nine-sermons.txt")
assert len(us)>1_200_000
assert "a605354300puseuoft" in u["text_url"]
assert u["word_count"]>=200_000
ps=read("data/clean/1860-the-minor-prophets-with-commentary.txt")
assert len(ps)>4_000_000
assert "[VOLUME I" in ps and "[END VOLUME I]" in ps and "[VOLUME II" in ps
assert ps.index("[END VOLUME I]")<ps.index("[VOLUME II")
assert "Hosea" in ps and "Malachi" in ps
assert len(p["source_volumes"])==2 and all(x["sha256"] for x in p["source_volumes"])
ledger=json.loads(read("data/owner_source_ledger_20261113.json"))["entries"]
for ident in (t["id"],u["id"],p["id"]):
    assert sum(x["bibliography_id"]==ident for x in ledger)==1,ident
works=json.loads(read("bibliography.json"))["works"]
assert sum(x["id"]==p["id"] for x in works)==1
print("OWNER SOURCE TEST: University I replacement; both Minor Prophets volumes; 17 attributed Tertullian notes; exclusions and provenance OK")
