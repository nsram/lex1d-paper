"""Partition similarity of LEX vs the exact optimum, from GOLD bin sizes.

Reads results/gold/raw/results.csv (no rerun needed). Bins are contiguous in sorted order, so each
partition is fully described by its bin sizes. For every unweighted LEX cell with a matching
ckmeans_exact cell it computes the adjusted Rand index (ARI) and the pair Jaccard index. Writes out/partsim/partition_similarity.csv (one row
per cell) and out/partsim/summary.md (medians over the continuous datasets, plus the audio).
Standard library only. Run from the repo root: python3 run/partsim.py
"""
import collections, csv, itertools, os, statistics as st
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "results", "gold", "raw", "results.csv")
OUT = os.path.join(ROOT, "out", "partsim")


def similarity(a, b):
    """ARI and pair Jaccard index for two contiguous partitions given by their bin sizes."""
    n = sum(a)
    assert n == sum(b) and len(a) == len(b)
    ca, cb = list(itertools.accumulate(a)), list(itertools.accumulate(b))
    cell = collections.Counter()  # contingency table: (bin in a, bin in b) -> count
    i = j = prev = 0
    for c in sorted(set(ca) | set(cb)):
        cell[(i, j)] += c - prev
        prev = c
        i += c == ca[i]
        j += c == cb[j]
    s = sum(comb(v, 2) for v in cell.values())
    sa, sb, t = sum(comb(v, 2) for v in a), sum(comb(v, 2) for v in b), comb(n, 2)
    e = sa * sb / t
    ari = (s - e) / ((sa + sb) / 2 - e) if (sa + sb) / 2 != e else 1.0
    return ari, s / (sa + sb - s)


def main():
    rows = list(csv.DictReader(open(GOLD)))
    key = lambda r: (r["dataset"], r["slice"], r["N"], r["k"])
    exact = {key(r): r for r in rows
             if r["method"] == "ckmeans_exact" and r["status"] == "ok" and r["weighted"] == "0" and r["sizes"]}
    out = []
    for r in rows:
        if not r["method"].startswith("lex") or r["status"] != "ok" or r["weighted"] != "0":
            continue
        e = exact.get(key(r))
        if not e:
            continue
        a, b = [list(map(int, x["sizes"].split("|"))) for x in (r, e)]
        if len(a) != len(b):
            continue
        ari, jac = similarity(a, b)
        gap = 100 * (float(r["sse"]) - float(e["sse"])) / float(e["sse"])
        out.append(dict(dataset=r["dataset"], slice=r["slice"], N=r["N"], k=int(r["k"]), method=r["method"],
                        M=r["M"], gap_pct=gap, ari=ari, pair_jaccard=jac))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "partition_similarity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    L = ["# Partition similarity, LEX vs exact (GOLD raw)", "",
         "Continuous: medians over the 10 continuous datasets (70 cells per k: 7 slices; M values outside 4096-16384 come from the M sweep, 10 cells). Audio: one cell per k.", ""]
    groups = collections.defaultdict(list)
    for o in out:
        fam = "audio" if o["dataset"] == "audio" else "continuous" if o["dataset"].endswith("_continuous") else None
        if fam:
            groups[(fam, o["method"], o["M"])].append(o)
    for (fam, m, M), g in sorted(groups.items()):
        L += [f"## {fam}: {m}" + (f", M = {M}" if M not in ("", "0") else ""), "",
              "| k | cells | median ARI | min ARI | median pair Jaccard |",
              "|---|---|---|---|---|"]
        byk = collections.defaultdict(list)
        for o in g:
            byk[o["k"]].append(o)
        for k in sorted(byk):
            c = byk[k]
            L.append(f"| {k} | {len(c)} | {st.median(x['ari'] for x in c):.4g} | {min(x['ari'] for x in c):.4g} | "
                     f"{st.median(x['pair_jaccard'] for x in c):.4g} |")
        L.append("")
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(L))
    print(f"{len(out)} cells; wrote {os.path.relpath(OUT, ROOT)}/partition_similarity.csv and summary.md")


if __name__ == "__main__":
    main()
