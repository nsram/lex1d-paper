"""Checks that the repo's lex1d/ folder is byte-identical to commit 8a691ee: every file listed in
run/lex1d_8a691ee.sha256 (computed from the commit's zip) must exist with the
same SHA-256, and lex1d/ must hold no other files (macOS .DS_Store files are ignored and reported).
Exit 0 = identical, 1 = differs. Standard library only."""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
root = os.path.join(PACK, "lex1d")
man = {}
with open(os.path.join(HERE, "lex1d_8a691ee.sha256")) as f:
    for line in f:
        if line.startswith("#") or not line.strip():
            continue
        h, rel = line.rstrip("\n").split("  ", 1)
        man[rel] = h
bad, ok, ignored = [], 0, []
for rel, h in man.items():
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        bad.append(f"missing: lex1d/{rel}")
        continue
    with open(p, "rb") as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    if got != h:
        bad.append(f"differs: lex1d/{rel} (sha256 {got}, expected {h})")
    else:
        ok += 1
for d, _, files in os.walk(root):
    for fn in files:
        rel = os.path.relpath(os.path.join(d, fn), root).replace(os.sep, "/")
        if rel in man:
            continue
        if fn == ".DS_Store":
            ignored.append(rel)
        else:
            bad.append(f"extra file not in commit 8a691ee: lex1d/{rel}")
print(f"lex1d check: {ok}/{len(man)} files identical to commit 8a691ee"
      + (f"; ignored {len(ignored)} .DS_Store" if ignored else ""))
for b in bad:
    print("  " + b)
sys.exit(1 if bad else 0)
