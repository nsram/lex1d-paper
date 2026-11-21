"""Run 5 (exploratory): precision grouping before LEX on the audio. Called by run/run5.sh; standard library only.

Prepares the audio inputs as runs 1-4 do (data.prepare_audio into work/full/inputs/, reused if already there,
then data.check_input), runs bench/precgroup_fit once per (round, k, variant), and writes out/precgroup/:
    runs.csv      one row per process (warm-up round 0 included, timed=0)
    summary.md    medians over the timed rounds, speedups, gaps to the GOLD exact SSE, and the checks
Checks (any failure: FAIL in summary.md, exit 1):
    raw variant SSE identical to GOLD lex_hybrid M=4096 (results/gold/raw/results.csv, audio, weighted 0)
    every run: |SSE (weighted + within-atom) - SSE recomputed on raw values| / SSE <= 1e-12
    warm-up: public API = instrumented copy (api_match), fast grouping = reference grouping (group_match)
    D = 7,295,677 (raw) and 552,603 (5 significant digits)
Usage: precgroup.py --fit DRIVER --workdir WORK --out OUT --session ID [--reps 3] | --analyze-only --out OUT
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import data  # noqa: E402

KS = [64, 256, 512]
M = 4096
VARIANTS = [("raw", 0), ("sig5", 5)]
EXPECT_D = {"raw": 7_295_677, "sig5": 552_603}
REL_TOL = 1e-12
FIELDS = ["session", "round", "timed", "variant", "sig", "k", "M", "n", "D", "k_eff", "group_s", "fit_s", "total_s",
          "sort_s", "t_prep_s", "t_sort_s", "t_atoms_s", "t_collapse_s", "t_dp_s", "t_refine_s", "t_summary_s",
          "sweeps", "moves", "start", "sse_lib", "within_ss", "sse", "sse_raw", "rel_diff", "api_match", "group_match",
          "rss_self", "sizes", "ts"]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def gold():
    p = os.path.join(PACK, "results", "gold", "raw", "results.csv")
    ex, hy = {}, {}
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["dataset"] != "audio" or r["weighted"] != "0" or r["status"] != "ok":
                continue
            if r["method"] == "ckmeans_exact":
                ex[int(r["k"])] = r["sse"]
            elif r["method"] == "lex_hybrid" and r["M"] == str(M):
                hy[int(r["k"])] = r["sse"]
    return ex, hy


def run(a):
    idir = os.path.join(a.workdir, "inputs")
    os.makedirs(idir, exist_ok=True)
    m = data.read_meta(os.path.join(idir, "audio_s0"))
    if not (m and os.path.exists(m["prefix"] + ".sorted.f64") and m["N"] == data.AUDIO_N):
        t = time.time()
        m = data.prepare_audio(idir)
        print(f"{now_iso()} prepared audio ({time.time()-t:.1f}s)", flush=True)
    else:
        print(f"{now_iso()} audio inputs already prepared: {m['prefix']}", flush=True)
    rows = data.check_input(m["prefix"], False)
    for r in rows:
        print(f"input    {r['file']} n={r['n']} sha256={r['sha256']} {r['check']} ok={r['ok']}", flush=True)
    if not all(r["ok"] for r in rows):
        sys.exit("FAIL: prepared audio inputs did not pass data.check_input")
    raw_f, sorted_f = m["prefix"] + ".raw.f64", m["prefix"] + ".sorted.f64"
    out_csv = os.path.join(a.out, "runs.csv")
    new = not os.path.exists(out_csv)
    with open(out_csv, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        # round 0 = warm-up (verify mode, not timed); rounds 1..reps timed; variant order alternates per round
        for rnd in range(a.reps + 1):
            order = VARIANTS if rnd % 2 == 0 else VARIANTS[::-1]
            for k in KS:
                for name, sig in order:
                    mode = "verify" if rnd == 0 else "timed"
                    cmd = [a.fit, raw_f, sorted_f, str(k), str(M), str(sig), mode]
                    p = subprocess.run(cmd, capture_output=True, text=True)
                    line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT")), "")
                    kv = dict(t.split("=", 1) for t in line.split()[1:] if "=" in t)
                    if p.returncode != 0 or "error" in kv:
                        sys.stderr.write(p.stderr)
                        sys.exit(f"FAIL: {' '.join(cmd)} exited {p.returncode}: {line[:300]} {p.stderr.strip()[:300]}")
                    kv.update(session=a.session, round=rnd, timed=int(rnd > 0), ts=now_iso())
                    w.writerow(kv)
                    fh.flush()
                    print(f"{kv['ts']} round {rnd} {name:4s} k={k:3d} D={kv['D']} group={float(kv['group_s']):.3f}s "
                          f"fit={float(kv['fit_s']):.3f}s total={float(kv['total_s']):.3f}s sse={kv['sse']} "
                          f"rel_diff={kv['rel_diff']}", flush=True)


def fmt(x, d=3):
    return "" if x is None else f"{x:.{d}f}"


def analyze(out):
    with open(os.path.join(out, "runs.csv"), newline="") as fh:
        rows = list(csv.DictReader(fh))
    sess = rows[-1]["session"]
    rows = [r for r in rows if r["session"] == sess]  # the latest session only
    ex, hy = gold()
    fails = []
    for r in rows:
        if float(r["rel_diff"]) > REL_TOL:
            fails.append(f"rel_diff {r['rel_diff']} > {REL_TOL} ({r['variant']} k={r['k']} round {r['round']})")
        if int(r["D"]) != EXPECT_D[r["variant"]]:
            fails.append(f"D = {r['D']}, expected {EXPECT_D[r['variant']]} ({r['variant']} k={r['k']})")
        if r["timed"] == "0" and (r["api_match"] != "1" or (r["variant"] != "raw" and r["group_match"] != "1")):
            fails.append(f"warm-up check failed: api_match={r['api_match']} group_match={r['group_match']} ({r['variant']} k={r['k']})")
        if r["variant"] == "raw" and float(r["sse_lib"]) != float(hy[int(r["k"])]):
            fails.append(f"raw SSE {r['sse_lib']} != GOLD lex_hybrid M={M} SSE {hy[int(r['k'])]} (k={r['k']}, round {r['round']})")
    timed = [r for r in rows if r["timed"] == "1"]
    reps = len({r["round"] for r in timed})
    med = lambda sel, f: statistics.median(float(r[f]) for r in sel) if sel else None
    cell = {(v, k): [r for r in timed if r["variant"] == v and int(r["k"]) == k] for v, _ in VARIANTS for k in KS}
    L = ["# Run 5: precision grouping before LEX, audio (exploratory)\n",
         f"Session {sess}; {reps} timed rounds after one warm-up round, medians shown; M = {M}. "
         "Times are from the sorted array (the sort is the same for both variants and is shown separately). "
         "sig5: values rounded to 5 significant digits are grouped into atoms (count and mean of their true values); "
         "LEX runs on the atoms with weights. SSE = weighted SSE + within-atom sum of squares, checked against the "
         "SSE recomputed on the raw values from the mapped cuts. Gap = 100 (SSE - exact) / exact, exact SSE from "
         "results/gold/raw/results.csv (ckmeans_exact).\n",
         f"**Checks: {'PASS' if not fails else 'FAIL'}**" + ("" if not fails else "\n\n" + "\n".join("- " + x for x in fails)) + "\n",
         "| variant | k | D | group s | collapse s | DP s | refine s | LEX fit s | total s | speedup | SSE | gap % | max rel diff |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in KS:
        base = med(cell[("raw", k)], "total_s")
        for v, _ in VARIANTS:
            sel = cell[(v, k)]
            if not sel:
                continue
            tot = med(sel, "total_s")
            sse = float(sel[0]["sse"])
            gap = 100 * (sse - float(ex[k])) / float(ex[k])
            L.append(f"| {v} | {k} | {sel[0]['D']} | {fmt(med(sel, 'group_s'))} | {fmt(med(sel, 't_collapse_s'))} | "
                     f"{fmt(med(sel, 't_dp_s'))} | {fmt(med(sel, 't_refine_s'))} | {fmt(med(sel, 'fit_s'))} | {fmt(tot)} | "
                     f"{fmt(base / tot, 1) if base and tot else ''}x | {sse:.10g} | {gap:.5f} | "
                     f"{max(float(r['rel_diff']) for r in sel):.1e} |")
    srt = med(timed, "sort_s")
    L.append(f"\nSort of the raw audio (library sort, median over all runs): {fmt(srt)} s. "
             "Add it to both totals for a from-raw comparison.\n")
    L.append("GOLD reference (Apple M3 Max, results/gold/raw, lex_hybrid M=4096, from raw): k=512 total 3.07 s "
             "(sort 0.50, collapse 2.33, DP 0.035, refine 0.127).\n")
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit")
    ap.add_argument("--workdir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--session", default="")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--analyze-only", action="store_true")
    a = ap.parse_args()
    if not a.analyze_only:
        run(a)
    sys.exit(analyze(a.out))
