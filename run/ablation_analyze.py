#!/usr/bin/env python3
"""Summarize a paired-move ablation results.csv.

Usage: analyze.py results.csv

Writes, next to results.csv:
  summary is printed to stdout (the run script tees it to summary.txt)
  moves_8way.csv  accepted moves and SSE drop for each of the 8 window moves
  moves_3way.csv  the same numbers rolled up to single / shrink_grow / translate
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# Move numbers from lex1d/cpp/src/refine.cpp (kLeftOp / kRightOp).
# 0 stay, 1 give, 2 take on each of the middle bin's two cuts.
OPS = ("stay", "give", "take")
# move: left op, right op, 3-type, short description
MOVES = (
    (0, 1, 1, "shrink_grow", "paired shrink of the middle bin"),
    (1, 1, 0, "single", "single move of the left cut (give)"),
    (2, 0, 1, "single", "single move of the right cut (give)"),
    (3, 2, 0, "single", "single move of the left cut (take)"),
    (4, 0, 2, "single", "single move of the right cut (take)"),
    (5, 2, 1, "translate", "paired translate of the middle bin one piece left"),
    (6, 1, 2, "translate", "paired translate of the middle bin one piece right"),
    (7, 2, 2, "shrink_grow", "paired grow of the middle bin"),
)
SINGLE = (1, 2, 3, 4)
SHRINK_GROW = (0, 7)
TRANSLATE = (5, 6)
PAIRED = SHRINK_GROW + TRANSLATE
TYPES = (
    ("single", SINGLE),
    ("shrink_grow", SHRINK_GROW),
    ("translate", TRANSLATE),
)
TYPE_OF = {i: name for name, idxs in TYPES for i in idxs}


def fnum(x):
    return float(x) if x not in ("", None) else 0.0


def inum(x):
    return int(x) if x not in ("", None) else 0


def median(xs):
    return statistics.median(xs) if xs else float("nan")


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def type_counts(row):
    out = {}
    for name, idxs in TYPES:
        out[name] = sum(inum(row[f"m{i}"]) for i in idxs)
        out[name + "_gain"] = sum(fnum(row[f"g{i}"]) for i in idxs)
    out["moves"] = inum(row["moves"])
    out["gain"] = sum(fnum(row[f"g{i}"]) for i in range(8))
    out["paired"] = sum(inum(row[f"m{i}"]) for i in PAIRED)
    return out


def fmt_pct(x, digits=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NA"
    return f"{100 * x:.{digits}f}%"


def pool_moves(rows, start=None, variant=None):
    """Sum m0..m7 and g0..g7 over rows, optionally filtered."""
    hist = [0] * 8
    gains = [0.0] * 8
    n = 0
    for r in rows:
        if start is not None and r["start"] != start:
            continue
        if variant is not None and r["variant"] != variant:
            continue
        n += 1
        for i in range(8):
            hist[i] += inum(r[f"m{i}"])
            gains[i] += fnum(r[f"g{i}"])
    return hist, gains, n


def share(part, total):
    if not total:
        return ""
    return f"{part / total:.10g}"


def write_tables(out_dir: Path, rows):
    starts = []
    for s in ("collapse", "coarse4096"):
        if any(r["start"] == s for r in rows):
            starts.append(s)
    variants = []
    for v in ("all8", "single"):
        if any(r["variant"] == v for r in rows):
            variants.append(v)
    scopes = [(s, v) for s in starts for v in variants]
    if len(starts) > 1:
        scopes.extend([("all", v) for v in variants])

    eight_path = out_dir / "moves_8way.csv"
    three_path = out_dir / "moves_3way.csv"
    eight_fields = [
        "start", "variant", "cells", "move", "left", "right", "type3",
        "description", "accepted_moves", "sse_drop", "move_share", "drop_share",
    ]
    three_fields = [
        "start", "variant", "cells", "type", "moves", "sse_drop",
        "move_share", "drop_share",
    ]

    with eight_path.open("w", newline="") as f8, three_path.open("w", newline="") as f3:
        w8 = csv.DictWriter(f8, fieldnames=eight_fields)
        w3 = csv.DictWriter(f3, fieldnames=three_fields)
        w8.writeheader()
        w3.writeheader()
        for start, variant in scopes:
            hist, gains, ncells = pool_moves(
                rows,
                start=None if start == "all" else start,
                variant=variant,
            )
            total_m = sum(hist)
            total_g = sum(gains)
            for move, lo, ro, typ, desc in MOVES:
                w8.writerow({
                    "start": start,
                    "variant": variant,
                    "cells": ncells,
                    "move": move,
                    "left": OPS[lo],
                    "right": OPS[ro],
                    "type3": typ,
                    "description": desc,
                    "accepted_moves": hist[move],
                    "sse_drop": f"{gains[move]:.17g}",
                    "move_share": share(hist[move], total_m),
                    "drop_share": share(gains[move], total_g),
                })
            for typ, idxs in TYPES:
                nm = sum(hist[i] for i in idxs)
                gg = sum(gains[i] for i in idxs)
                w3.writerow({
                    "start": start,
                    "variant": variant,
                    "cells": ncells,
                    "type": typ,
                    "moves": nm,
                    "sse_drop": f"{gg:.17g}",
                    "move_share": share(nm, total_m),
                    "drop_share": share(gg, total_g),
                })
    return eight_path, three_path


def print_move_tables(rows):
    starts = []
    for s in ("collapse", "coarse4096"):
        if any(r["start"] == s for r in rows):
            starts.append(s)
    variants = []
    for v in ("all8", "single"):
        if any(r["variant"] == v for r in rows):
            variants.append(v)

    print("=== 8-way accepted moves and SSE drop (pooled) ===")
    print("move  left  right  type3        count   move share   SSE-drop share")
    for start in starts:
        for variant in variants:
            hist, gains, _ = pool_moves(rows, start=start, variant=variant)
            total_m = sum(hist)
            total_g = sum(gains)
            print(f"  -- start={start}  variant={variant}  moves={total_m}  drop={total_g:.6g}")
            for move, lo, ro, typ, _desc in MOVES:
                ms = hist[move] / total_m if total_m else float("nan")
                gs = gains[move] / total_g if total_g else float("nan")
                print(
                    f"    {move}   {OPS[lo]:<4}  {OPS[ro]:<4}  {typ:<12} "
                    f"{hist[move]:8d}   {fmt_pct(ms, 1):>8}    {fmt_pct(gs, 1):>8}"
                )
    print()

    print("=== 3-way accepted moves and SSE drop (pooled) ===")
    print("type         count   move share   SSE-drop share")
    for start in starts:
        for variant in variants:
            hist, gains, _ = pool_moves(rows, start=start, variant=variant)
            total_m = sum(hist)
            total_g = sum(gains)
            print(f"  -- start={start}  variant={variant}")
            for typ, idxs in TYPES:
                nm = sum(hist[i] for i in idxs)
                gg = sum(gains[i] for i in idxs)
                ms = nm / total_m if total_m else float("nan")
                gs = gg / total_g if total_g else float("nan")
                print(
                    f"    {typ:<12} {nm:8d}   {fmt_pct(ms, 1):>8}    {fmt_pct(gs, 1):>8}"
                )
    print()


def main():
    if len(sys.argv) != 2:
        print("usage: analyze.py results.csv", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    rows = load(path)
    if not rows:
        print("no rows")
        return 1
    out_dir = path.parent

    print("Paired-move ablation summary")
    print("8-way moves are the kLeftOp/kRightOp combinations in refine.cpp.")
    print("3-way types: single = moves 1-4; shrink_grow = 0,7; translate = 5,6.")
    print()

    n_rows = len(rows)
    checks = defaultdict(int)
    for r in rows:
        checks[r["check"]] += 1
    print(f"rows: {n_rows}")
    print("checks:", ", ".join(f"{k}={v}" for k, v in sorted(checks.items())))
    bad = n_rows - checks.get("ok", 0)
    if bad:
        print(f"WARNING: {bad} row(s) failed a correctness check.")
    else:
        print("All identity and below-exact checks passed.")
    print()

    eight_path, three_path = write_tables(out_dir, rows)

    # Pair all8 vs single on (dataset, N, k, start)
    by_key = defaultdict(dict)
    for r in rows:
        key = (r["dataset"], r["N"], r["k"], r["start"])
        by_key[key][r["variant"]] = r

    paired = []
    missing = 0
    for key, variants in sorted(by_key.items(), key=lambda kv: (kv[0][3], int(kv[0][1]), int(kv[0][2]), kv[0][0])):
        if "all8" not in variants or "single" not in variants:
            missing += 1
            continue
        a, s = variants["all8"], variants["single"]
        ta, ts = type_counts(a), type_counts(s)
        d = {
            "dataset": key[0],
            "N": int(key[1]),
            "k": int(key[2]),
            "start": key[3],
            "ree_all8": fnum(a["gap_pct"]),
            "ree_single": fnum(s["gap_pct"]),
            "t_all8": fnum(a["refine_s"]),
            "t_single": fnum(s["refine_s"]),
            "sweeps_all8": inum(a["sweeps"]),
            "sweeps_single": inum(s["sweeps"]),
            "moves_all8": ta["moves"],
            "moves_single": ts["moves"],
            "paired_all8": ta["paired"],
            "gain_all8": ta["gain"],
            "gain_single": ts["gain"],
            "vs": s.get("single_vs_all8", ""),
        }
        for name, _ in TYPES:
            d[f"n_{name}_all8"] = ta[name]
            d[f"n_{name}_single"] = ts[name]
            d[f"g_{name}_all8"] = ta[name + "_gain"]
            d[f"g_{name}_single"] = ts[name + "_gain"]
        d["delta_pp"] = d["ree_single"] - d["ree_all8"]
        paired.append(d)
    if missing:
        print(f"WARNING: {missing} cell(s) missing a variant pair.")
        print()

    def classify(g):
        w = l = t = 0
        for row in g:
            if row["delta_pp"] > 1e-9:
                w += 1  # all8 better (single has higher REE)
            elif row["delta_pp"] < -1e-9:
                l += 1
            else:
                t += 1
        return w, l, t

    starts = []
    for s in ("collapse", "coarse4096"):
        if any(r["start"] == s for r in paired):
            starts.append(s)

    for start in starts:
        g = [r for r in paired if r["start"] == start]
        print(f"=== start {start}  ({len(g)} cells) ===")
        ree_a = [r["ree_all8"] for r in g]
        ree_s = [r["ree_single"] for r in g]
        print(
            "REE %  all8 median / max:   "
            f"{median(ree_a):.6g} / {max(ree_a):.6g}"
        )
        print(
            "REE %  single median / max: "
            f"{median(ree_s):.6g} / {max(ree_s):.6g}"
        )
        w, l, t = classify(g)
        print(f"all8 better / single better / tie: {w} / {l} / {t}")
        deltas = [r["delta_pp"] for r in g]
        print(
            "paired delta (single - all8, pp): "
            f"median {median(deltas):.6g}, mean {sum(deltas)/len(deltas):.6g}, "
            f"max |delta| {max(abs(x) for x in deltas):.6g}"
        )

        timed = [r for r in g if r["moves_all8"] > 0 and r["t_all8"] > 0]
        if timed:
            ratios = [r["t_single"] / r["t_all8"] for r in timed]
            print(
                "refine time single / all8: "
                f"median {median(ratios):.3f}  "
                f"(n={len(timed)} cells with all8 moves)"
            )
        else:
            print("refine time single / all8: NA (no all8 moves)")

        def pool(variant_suffix):
            totals_n = {name: 0 for name, _ in TYPES}
            totals_g = {name: 0.0 for name, _ in TYPES}
            nsum = gsum = 0.0
            for r in g:
                for name, _ in TYPES:
                    totals_n[name] += r[f"n_{name}_{variant_suffix}"]
                    totals_g[name] += r[f"g_{name}_{variant_suffix}"]
                nsum += r[f"moves_{variant_suffix}"]
                gsum += r[f"gain_{variant_suffix}"]
            return totals_n, totals_g, nsum, gsum

        for label, suffix in (("all8", "all8"), ("single", "single")):
            totals_n, totals_g, nsum, gsum = pool(suffix)
            print(f"  {label} accepted-move share (pooled):")
            parts = []
            for name, _ in TYPES:
                sh = (totals_n[name] / nsum) if nsum else float("nan")
                parts.append(f"{name} {fmt_pct(sh)} (n={totals_n[name]})")
            print("    " + ", ".join(parts) + f"  total moves={int(nsum)}")
            print(f"  {label} SSE-reduction share (pooled, sum of computed move gains):")
            parts = []
            for name, _ in TYPES:
                sh = (totals_g[name] / gsum) if gsum else float("nan")
                parts.append(f"{name} {fmt_pct(sh)} (gain={totals_g[name]:.6g})")
            print("    " + ", ".join(parts) + f"  total gain={gsum:.6g}")

        psum = sum(r["paired_all8"] for r in g)
        msum = sum(r["moves_all8"] for r in g)
        shares = []
        for r in g:
            if r["moves_all8"] > 0:
                shares.append(r["paired_all8"] / r["moves_all8"])
        print(
            "  all8 paired share of accepted moves: "
            f"pooled {fmt_pct(psum / msum if msum else float('nan'))}, "
            f"median across cells {fmt_pct(median(shares) if shares else float('nan'))}"
        )
        print()

        for N in sorted({r["N"] for r in g}):
            gg = [r for r in g if r["N"] == N]
            w, l, t = classify(gg)
            ree_a = [r["ree_all8"] for r in gg]
            ree_s = [r["ree_single"] for r in gg]
            print(
                f"  N={N}: cells={len(gg)}  "
                f"all8 REE med/max {median(ree_a):.5g}/{max(ree_a):.5g}  "
                f"single {median(ree_s):.5g}/{max(ree_s):.5g}  "
                f"all8 better/single better/tie {w}/{l}/{t}"
            )
        print()

    print_move_tables(rows)
    print(f"Wrote {eight_path.name} and {three_path.name} next to results.csv.")
    print()

    if paired:
        print("=== largest REE differences (single - all8, percentage points) ===")
        ranked = sorted(paired, key=lambda r: r["delta_pp"])
        print("all8 better most (single REE higher):")
        for r in ranked[-5:][::-1]:
            print(
                f"  {r['dataset']} N={r['N']} k={r['k']} {r['start']}: "
                f"all8 {r['ree_all8']:.6g}  single {r['ree_single']:.6g}  "
                f"delta {r['delta_pp']:.6g}"
            )
        print("single better most (all8 REE higher):")
        for r in ranked[:5]:
            print(
                f"  {r['dataset']} N={r['N']} k={r['k']} {r['start']}: "
                f"all8 {r['ree_all8']:.6g}  single {r['ree_single']:.6g}  "
                f"delta {r['delta_pp']:.6g}"
            )

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
