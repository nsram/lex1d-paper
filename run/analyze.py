"""Analysis (standard library; matplotlib optional, only for figures).

    python3 run/analyze.py --out out/raw        (the run scripts call this at the end)

For one out folder: merges cells/ into reps.csv (one row per process) and results.csv (one row per
cell x method: medians and min/max over the timed rounds), writes summary.md, gold_check.md (SSE
identity and time ratios against the GOLD run in results/gold/<mode>/; for run 4, against
results/gold/raw/ lex_hybrid rows) and figures/ (if matplotlib imports).
If both out/raw/ and out/sorted/ exist next to each other (with results.csv), it also writes
raw_vs_sorted.csv / raw_vs_sorted.md into both (sort cost = raw - sorted, per cell and method).
For MODE=refine (GOLD run 4) it also writes refine_ablation.md: per-k/M Refine vs coarse-DP gaps,
with continuous, discrete and audio shown separately.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
CONT = ["uniform_continuous", "gaussian_continuous", "exponential_continuous", "weibull_continuous",
        "lognormal_continuous", "gmm_continuous", "wg_mixture_continuous", "bimodal_gaussian_continuous",
        "mixed_continuous", "truncated_continuous"]
DISC = ["triangular_discrete", "spike_uniform_discrete"]
LOADS = {"load", "R_load", "rb_load", "py_load"}
BASE_OF = {"cpp": "load", "R": "R_load", "py": "py_load"}
STAGES = ["t_prep_s", "t_sort_s", "t_atoms_s", "t_collapse_s", "t_dp_s", "t_starts_s", "t_refine_s", "t_summary_s"]


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def fmt(x, nd=4):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if x == 0:
        return "0"
    a = abs(x)
    return f"{x:.{nd}g}" if a >= 1e-3 else f"{x:.2e}"


def mlabel(r):
    return r["method"] + (f" M={r['M']}" if r["method"] in ("lex_hybrid", "rb_hybrid", "py_hybrid") else "")


def merge(out):
    rows = []
    for p in sorted(glob.glob(os.path.join(out, "cells", "*", "*.csv"))):
        with open(p, newline="") as fh:
            rows += list(csv.DictReader(fh))
    if not rows:
        return [], []
    with open(os.path.join(out, "reps.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # baselines: peak RSS of the load-only process per (section, dataset, slice, weighted, load method)
    base = {}
    for r in rows:
        if r["method"] in LOADS and r["status"] == "ok":
            base[(r["section"], r["dataset"], r["slice"], r["weighted"], r["method"])] = f(r["peak_rss_bytes"])
    groups = defaultdict(list)
    for r in rows:
        if r["method"] in LOADS:
            continue
        groups[(r["section"], r["dataset"], int(r["slice"]), int(r["k"]), r["method"], int(r["M"] or 0), r["weighted"])].append(r)
    res = []
    for key, g in groups.items():
        sec, ds, sl, k, meth, M, wt = key
        ok = [r for r in g if r["status"] == "ok"]
        timed = [r for r in ok if r["warmup"] == "0"]
        warm = [r for r in ok if r["warmup"] == "1"]
        g0 = g[0]
        o = dict(section=sec, dataset=ds, slice=sl, N=g0["N"], D=g0["D"], D_expected=g0["D_expected"], k=k,
                 method=meth, M=M, family=g0["family"], weighted=wt, mode=g0["mode"])
        if not ok:
            o["status"] = g0["status"]
            o["skip_reason"] = g0["skip_reason"]
            o["dp_table_est_bytes"] = g0["dp_table_est_bytes"]
            res.append(o)
            continue
        sses = {r["sse"] for r in ok}
        sizes = {r["sizes"] for r in ok}
        coarses = {r.get("coarse_sse", "") for r in ok}
        o.update(status="ok" if len(ok) == len(g) else "partial", skip_reason="",
                 sse=ok[0]["sse"], coarse_sse=ok[0].get("coarse_sse", ""),
                 coarse_sizes=ok[0].get("coarse_sizes", ""),
                 ltr_sse=ok[0].get("ltr_sse", ""), ltr_sizes=ok[0].get("ltr_sizes", ""),
                 ltr_sweeps=ok[0].get("ltr_sweeps", ""), ltr_moves=ok[0].get("ltr_moves", ""),
                 ltr_same_partition=ok[0].get("ltr_same_partition", ""),
                 sse_identical_all_rounds=int(len(sses) == 1 and len(sizes) == 1
                                              and ("" in coarses or len(coarses) == 1)),
                 n_timed=len(timed), k_eff=ok[0]["k_eff"], atoms=ok[0]["atoms"], sweeps=ok[0]["sweeps"],
                 moves=ok[0]["moves"], start=ok[0]["start"], version=ok[0]["version"],
                 api_match=(warm[0]["api_match"] if warm else ""), api_s=(warm[0]["api_s"] if warm else ""),
                 did_sort=ok[0]["did_sort"], dp_table_est_bytes=ok[0]["dp_table_est_bytes"], sizes=ok[0]["sizes"],
                 first_ts=min(r["timestamp"] for r in g), last_ts=max(r["timestamp"] for r in g),
                 sessions="|".join(sorted({r["session"] for r in g})))
        t = [f(r["fit_s"]) for r in timed] or [f(r["fit_s"]) for r in warm]
        t = [x for x in t if x is not None]
        o.update(fit_s=med(t), fit_min_s=min(t) if t else None, fit_max_s=max(t) if t else None,
                 post_sort_s=med([f(r["post_sort_s"]) for r in timed]))
        for s in STAGES:
            o[s] = med([f(r[s]) for r in timed])
        if any(r.get("t_refine_ltr_s") not in (None, "") for r in (timed or ok)):
            o["t_refine_ltr_s"] = med([f(r.get("t_refine_ltr_s")) for r in (timed or ok)])
        rss = [f(r["peak_rss_bytes"]) for r in ok]
        rss = [x for x in rss if x is not None]
        o.update(peak_rss_bytes=med(rss), peak_rss_min=min(rss) if rss else None, peak_rss_max=max(rss) if rss else None,
                 peak_footprint_bytes=med([f(r["peak_footprint_bytes"]) for r in ok]))
        bm = {"rb_hybrid": "rb_load", "py_hybrid": "py_load"}.get(meth, BASE_OF.get(g0["family"], ""))
        b = base.get((sec, ds, str(sl), wt, bm))
        o.update(baseline_method=bm, baseline_rss_bytes=b,
                 rss_above_baseline_bytes=(o["peak_rss_bytes"] - b) if (b is not None and o["peak_rss_bytes"] is not None) else None)
        res.append(o)
    # gap vs our exact DP in the same cell
    ex = {(o["section"], o["dataset"], o["slice"], o["k"], o["weighted"]): o for o in res
          if o["method"] == "ckmeans_exact" and o.get("status") in ("ok", "partial")}
    gold_exact_src = "same-run"
    # Run 4 does not re-run exact: fall back to GOLD raw ckmeans_exact. Runs 1-3 never take this path
    # (they include exact, or like bindings they have no exact and must not gain new gap_pct values).
    if not ex and res and res[0].get("mode") == "refine":
        gp = os.path.join(PACK, "results", "gold", "raw", "results.csv")
        if os.path.isfile(gp):
            with open(gp, newline="") as fh:
                for g in csv.DictReader(fh):
                    if g["method"] == "ckmeans_exact" and g.get("status") in ("ok", "partial"):
                        ex[(g["section"], g["dataset"], int(g["slice"]), int(g["k"]), g["weighted"])] = g
            gold_exact_src = "results/gold/raw"
    for o in res:
        e = ex.get((o["section"], o["dataset"], o["slice"], o["k"], o["weighted"]))
        if e and o.get("sse") not in (None, ""):
            es, s = float(e["sse"]), float(o["sse"])
            o["gap_pct"] = 100 * (s - es) / es if es > 0 else 0.0
            o["sizes_match_exact"] = int(o["sizes"] == e["sizes"])
            cs = o.get("coarse_sse")
            if cs not in (None, ""):
                o["exact_sse"] = e["sse"]
                ls = o.get("ltr_sse")
                if ls not in (None, ""):
                    o["ltr_gap_pct"] = 100 * (float(ls) - es) / es if es > 0 else 0.0
                c = float(cs)
                o["coarse_gap_pct"] = 100 * (c - es) / es if es > 0 else 0.0
                fg, cg = o["gap_pct"], o["coarse_gap_pct"]
                # M >= atoms makes the coarse DP exact, so both gaps should be 0; we flag only
                # when they actually are, so a mismatch is not hidden.
                already = (cg == 0.0 and fg == 0.0)
                o["already_exact"] = int(already)
                if already:
                    o["reduction_factor"] = ""
                    o["pct_gap_removed"] = ""
                elif fg == 0.0:
                    o["reduction_factor"] = "inf"
                    o["pct_gap_removed"] = 100.0
                elif cg == 0.0:
                    o["reduction_factor"] = ""
                    o["pct_gap_removed"] = ""
                else:
                    o["reduction_factor"] = cg / fg
                    o["pct_gap_removed"] = 100.0 * (cg - fg) / cg
    fields = ["section", "dataset", "slice", "N", "D", "D_expected", "k", "method", "M", "family", "weighted", "mode",
              "status", "skip_reason", "sse", "gap_pct", "sizes_match_exact", "sse_identical_all_rounds", "n_timed",
              "fit_s", "fit_min_s", "fit_max_s", "post_sort_s"] + STAGES + [
              "api_s", "api_match", "did_sort", "peak_rss_bytes", "peak_rss_min", "peak_rss_max", "peak_footprint_bytes",
              "baseline_method", "baseline_rss_bytes", "rss_above_baseline_bytes", "dp_table_est_bytes", "k_eff", "atoms",
              "sweeps", "moves", "start", "version", "first_ts", "last_ts", "sessions", "sizes"]
    if any(o.get("coarse_sse") not in (None, "") for o in res):
        # insert Refine-ablation columns after sse (run 4 only)
        i = fields.index("sse") + 1
        extras = ["coarse_sse", "ltr_sse", "exact_sse", "coarse_gap_pct",
                  "ltr_gap_pct", "ltr_same_partition", "t_refine_ltr_s", "ltr_sweeps", "ltr_moves", "ltr_sizes",
                  "reduction_factor", "pct_gap_removed", "already_exact", "coarse_sizes"]
        fields[i:i] = extras
    res.sort(key=lambda o: (o["section"], o["dataset"], o["slice"], o["k"], o["method"], o["M"]))
    with open(os.path.join(out, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(res)
    return rows, res


def table(head, body):
    s = "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n"
    for b in body:
        s += "| " + " | ".join(fmt(x) if not isinstance(x, str) else x for x in b) + " |\n"
    return s + "\n"


def summary(out, rows, res):
    L = []
    mode = res[0]["mode"] if res else "?"
    L.append(f"# LEX benchmark summary ({os.path.basename(out)}, input: {mode})\n")
    sess = sorted({r["session"] for r in rows})
    L.append(f"Processes: {len(rows)}. Sessions: {len(sess)} ({', '.join(sess)}). "
             f"First row {min(r['timestamp'] for r in rows)}, last {max(r['timestamp'] for r in rows)}.\n")
    if len(sess) > 1:
        L.append("**Note: more than one session (the run was resumed). Each row's session is in reps.csv; "
                 "cells are never split across sessions.**\n")
    ok = [o for o in res if o.get("status") == "ok"]
    bad = [o for o in res if o.get("status") not in ("ok", "skipped_mem")]
    skipped = [o for o in res if o.get("status") == "skipped_mem"]
    am = [o for o in ok if o.get("api_match") not in ("", None)]
    L.append("## Checks\n")
    L.append(f"- cell x method rows: {len(res)}; ok {len(ok)}; skipped by the memory guard {len(skipped)}; failed/partial {len(bad)}")
    L.append(f"- api_match (public API == instrumented copy, warm-up round): {sum(o['api_match'] == '1' for o in am)}/{len(am)}")
    L.append(f"- SSE and sizes identical across all rounds: {sum(o['sse_identical_all_rounds'] == 1 for o in ok)}/{len(ok)}")
    dm = [o for o in ok if o["D_expected"] not in ("", None)]
    L.append(f"- D equals dataset_slice_counts.csv: {sum(str(o['D']) == str(o['D_expected']) for o in dm)}/{len(dm)}")
    rv = [o for o in ok if o["method"] == "Ckmeans.1d.dp" and o.get("gap_pct") is not None]
    if rv:
        mx = max(abs(o["gap_pct"]) for o in rv) / 100
        L.append(f"- Ckmeans.1d.dp vs our exact DP: max |rel SSE diff| {mx:.2e} over {len(rv)} cells; "
                 f"identical sizes in {sum(o.get('sizes_match_exact') == 1 for o in rv)}/{len(rv)}")
    ds = {o["did_sort"] for o in ok if o["family"] == "cpp"}
    L.append(f"- C++ did_sort values seen: {sorted(ds)} (raw input: 1; presorted input: 0)")
    aps = sorted({r.get("api_presorted", "") for r in rows if r.get("family") == "cpp" and r.get("api_presorted") not in ("", "-1", None)})
    L.append(f"- lex1d Result::presorted (public API, warm-up round) values seen: {aps} (raw: 0; presorted: 1)")
    pm = [r for r in rows if r.get("status") == "presort_flag_mismatch"]
    L.append(f"- presort flag mismatches: {len(pm)}")
    for o in skipped:
        L.append(f"- skipped: {o['section']} {o['dataset']} s{o['slice']} k={o['k']} {o['method']}: {o['skip_reason']}")
    for o in bad:
        L.append(f"- FAILED/partial: {o['section']} {o['dataset']} s{o['slice']} k={o['k']} {mlabel(o)} {o.get('skip_reason','')}")
    L.append("")
    sec = defaultdict(list)
    for o in ok:
        sec[o["section"]].append(o)
    if sec.get("main"):
        m = sec["main"]
        Ns = sorted({int(o["N"]) for o in m})
        ks = sorted({o["k"] for o in m})
        meths = sorted({(o["method"], o["M"]) for o in m if o["method"] in ("lex_hybrid", "lex_plain")})
        for grp, names in (("continuous (10 datasets)", CONT), ("discrete (2 datasets)", DISC)):
            sel = [o for o in m if o["dataset"] in names and o.get("gap_pct") is not None]
            if not sel:
                continue
            L.append(f"## Main grid, {grp}: largest gap to exact SSE (%) over datasets\n")
            for (meth, M) in meths:
                body = []
                for N in Ns:
                    line = [str(N)]
                    for k in ks:
                        v = [o["gap_pct"] for o in sel if int(o["N"]) == N and o["k"] == k and o["method"] == meth and o["M"] == M]
                        line.append(max(v) if v else None)
                    body.append(line)
                L.append(f"**{meth}{' M=' + str(M) if M else ''}**\n")
                L.append(table(["N \\ k"] + [str(k) for k in ks], body))
        L.append("## Main grid: median fit time (s) over the 10 continuous datasets\n")
        allm = sorted({(o["method"], o["M"]) for o in m})
        for N in Ns:
            body = []
            for (meth, M) in allm:
                line = [meth + (f" M={M}" if M else "")]
                for k in ks:
                    line.append(med([o["fit_s"] for o in m if o["dataset"] in CONT and int(o["N"]) == N and o["k"] == k
                                     and o["method"] == meth and o["M"] == M]))
                body.append(line)
            L.append(f"**N = {N}**\n")
            L.append(table(["method \\ k"] + [str(k) for k in ks], body))
        if mode == "refine" and not any(o["method"] in ("Ckmeans.1d.dp", "ckmeans_exact") for o in m):
            pass
        else:
            L.append("## Main grid: speedup of lex_hybrid M=4096 (median over continuous datasets of time ratios)\n")
        for ref in ("Ckmeans.1d.dp", "ckmeans_exact"):
            if mode == "refine" and not any(o["method"] == ref for o in m):
                continue
            body = []
            for N in Ns:
                line = [str(N)]
                for k in ks:
                    rs = []
                    for d in CONT:
                        a = [o for o in m if o["dataset"] == d and int(o["N"]) == N and o["k"] == k]
                        h = next((o for o in a if o["method"] == "lex_hybrid" and o["M"] == 4096), None)
                        e = next((o for o in a if o["method"] == ref), None)
                        if h and e and h["fit_s"] and e["fit_s"]:
                            rs.append(e["fit_s"] / h["fit_s"])
                    line.append(med(rs))
                body.append(line)
            L.append(f"**{ref} time / lex_hybrid time**\n")
            L.append(table(["N \\ k"] + [str(k) for k in ks], body))
        top = max(Ns)
        L.append(f"## Stage breakdown at N = {top} (median s over continuous datasets)\n")
        body = []
        for (meth, M) in allm:
            if meth == "Ckmeans.1d.dp":
                continue
            for k in ks:
                sel = [o for o in m if o["dataset"] in CONT and int(o["N"]) == top and o["k"] == k and o["method"] == meth and o["M"] == M]
                if sel:
                    body.append([meth + (f" M={M}" if M else ""), str(k)] + [med([o[s] for o in sel]) for s in STAGES]
                                + [med([o["fit_s"] for o in sel]), med([o["post_sort_s"] for o in sel])])
        L.append(table(["method", "k"] + [s[2:-2] for s in STAGES] + ["total", "post-sort"], body))
        L.append(f"## Peak memory at N = {top} (median MiB over continuous datasets; peak RSS / above load baseline)\n")
        body = []
        for (meth, M) in allm:
            line = [meth + (f" M={M}" if M else "")]
            for k in ks:
                sel = [o for o in m if o["dataset"] in CONT and int(o["N"]) == top and o["k"] == k and o["method"] == meth and o["M"] == M]
                p = med([o["peak_rss_bytes"] for o in sel])
                a = med([o["rss_above_baseline_bytes"] for o in sel])
                line.append(f"{p/2**20:.0f} / {a/2**20:.0f}" if p is not None and a is not None else "")
            body.append(line)
        L.append(table(["method \\ k"] + [str(k) for k in ks], body))
    for s in ("audio", "gpt2", "weighted", "bindings"):
        if not sec.get(s):
            continue
        L.append(f"## Section {s}\n")
        body = []
        for o in sorted(sec[s], key=lambda o: (o["dataset"], o["slice"], o["k"], o["method"], o["M"])):
            body.append([o["dataset"], str(o["slice"]), str(o["k"]), mlabel(o), o["fit_s"], o["fit_min_s"], o["fit_max_s"],
                         o["post_sort_s"], o.get("gap_pct"), (o["peak_rss_bytes"] or 0) / 2**20,
                         (o["rss_above_baseline_bytes"] or 0) / 2**20 if o["rss_above_baseline_bytes"] is not None else None])
        L.append(table(["dataset", "slice", "k", "method", "fit s (median)", "min", "max", "post-sort s", "gap %", "peak MiB",
                        "above baseline MiB"], body))
        if s == "bindings":
            body = []
            for key in sorted({(o["dataset"], o["k"]) for o in sec[s]}):
                c = {o["method"]: o for o in sec[s] if (o["dataset"], o["k"]) == key}
                cp = c.get("lex_hybrid")
                if not cp:
                    continue
                line = [key[0], str(key[1]), cp["fit_s"]]
                for b in ("rb_hybrid", "py_hybrid"):
                    o = c.get(b)
                    line += [o["fit_s"] if o else None, (o["fit_s"] / cp["fit_s"]) if o and cp["fit_s"] else None,
                             ("yes" if o and o["sse"] == cp["sse"] else ("NO" if o else ""))]
                body.append(line)
            L.append("**Binding overhead (median fit time; same SSE as C++?)**\n")
            L.append(table(["dataset", "k", "C++ s", "R binding s", "R/C++", "R same SSE", "Python s", "Py/C++", "Py same SSE"], body))
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write("\n".join(L))


def gold_check(out, res):
    """Compare this run with the GOLD run of the same mode: SSE identity and time ratios."""
    if not res:
        return
    mode = res[0]["mode"]
    gold_mode = "raw" if mode == "refine" else mode
    p = os.path.join(PACK, "results", "gold", gold_mode, "results.csv")
    if not os.path.isfile(p) or os.path.abspath(os.path.dirname(p)) == os.path.abspath(out):
        return
    with open(p, newline="") as fh:
        gold = list(csv.DictReader(fh))
    if mode == "refine":
        gold = [g for g in gold if g["method"] == "lex_hybrid"]
        key = lambda r: (r["section"], r["dataset"], str(r["slice"]), str(r["k"]), r["method"], str(r["M"]),
                         r["family"], str(r["weighted"]))
    else:
        key = lambda r: (r["section"], r["dataset"], r["slice"], r["k"], r["method"], r["M"], r["family"], r["weighted"])
    idx = {key(o): o for o in res if o.get("status") == "ok"}
    out_rows = []
    for g in gold:
        o = idx.get(key(g))
        if not o or g.get("status") != "ok" or str(o["N"]) != g["N"]:  # e.g. --smoke pieces: not comparable
            continue
        same = o["sse"] == g["sse"] or f(o["sse"]) == f(g["sse"])
        out_rows.append(dict(section=g["section"], dataset=g["dataset"], slice=g["slice"], k=g["k"], method=g["method"],
                             M=g["M"], family=g["family"], weighted=g["weighted"], sse=o["sse"], sse_gold=g["sse"],
                             sse_identical=int(same),
                             rel_diff=(abs(f(o["sse"]) - f(g["sse"])) / f(g["sse"]) if f(g["sse"]) else ""),
                             sizes_identical=int(o["sizes"] == g["sizes"]),
                             time=o["fit_s"], time_gold=g["fit_s"],
                             time_ratio=(f(o["fit_s"]) / f(g["fit_s"]) if f(g["fit_s"]) and o["fit_s"] else "")))
    if not out_rows:
        return
    with open(os.path.join(out, "gold_check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    if mode == "refine":
        src = f"results/gold/{gold_mode}/results.csv"
        note = " Final SSE and bin sizes are checked against GOLD raw lex_hybrid rows."
        L = [f"# Identity and timing vs GOLD ({os.path.basename(out)})\n",
             f"GOLD: {src} (Apple M3 Max). SSEs should match on any machine; time ratios "
             f"(this run / GOLD, median fit times) show the speed of this machine relative to GOLD.{note}\n"]
    else:
        L = [f"# Identity and timing vs GOLD ({os.path.basename(out)})\n",
             f"GOLD: results/gold/{mode}/results.csv (Apple M3 Max). SSEs should match on any machine; time ratios "
             "(this run / GOLD, median fit times) show the speed of this machine relative to GOLD.\n"]
    body = []
    for m in sorted({r["method"] for r in out_rows}):
        sel = [r for r in out_rows if r["method"] == m]
        rat = [r["time_ratio"] for r in sel if r["time_ratio"] != ""]
        body.append([m, str(len(sel)), f"{sum(r['sse_identical'] for r in sel)}/{len(sel)}",
                     f"{sum(r['sizes_identical'] for r in sel)}/{len(sel)}", med(rat), min(rat) if rat else None, max(rat) if rat else None])
    L.append(table(["method", "cells", "SSE identical", "sizes identical", "time ratio this run/GOLD (median)", "min", "max"], body))
    with open(os.path.join(out, "gold_check.md"), "w") as fh:
        fh.write("\n".join(L))


def raw_vs_sorted(out):
    parent = os.path.dirname(os.path.abspath(out))
    suf = "_smoke" if out.rstrip("/").endswith("_smoke") else ""
    a, b = os.path.join(parent, "raw" + suf), os.path.join(parent, "sorted" + suf)
    if not (os.path.isfile(os.path.join(a, "results.csv")) and os.path.isfile(os.path.join(b, "results.csv"))):
        return
    def load(p):
        with open(os.path.join(p, "results.csv"), newline="") as fh:
            return {(o["section"], o["dataset"], o["slice"], o["k"], o["method"], o["M"], o["weighted"]): o
                    for o in csv.DictReader(fh) if o["status"] == "ok"}
    A, B = load(a), load(b)
    rows = []
    for key in sorted(set(A) & set(B)):
        x, y = A[key], B[key]
        tr, ts = f(x["fit_s"]), f(y["fit_s"])
        rows.append(dict(section=key[0], dataset=key[1], slice=key[2], N=x["N"], k=key[3], method=key[4], M=key[5], weighted=key[6],
                         fit_raw_s=tr, fit_sorted_s=ts, sort_cost_s=(tr - ts) if tr is not None and ts is not None else "",
                         ratio_raw_over_sorted=(tr / ts) if tr and ts else "",
                         t_sort_raw_s=x["t_sort_s"], post_sort_raw_s=x["post_sort_s"],
                         sse_identical=int(x["sse"] == y["sse"]), sizes_identical=int(x["sizes"] == y["sizes"]),
                         peak_rss_raw=x["peak_rss_bytes"], peak_rss_sorted=y["peak_rss_bytes"]))
    if not rows:
        return
    for d in (a, b):
        with open(os.path.join(d, "raw_vs_sorted.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    L = ["# Raw vs presorted input (same cells, two runs)\n",
         f"Cells compared: {len(rows)}. SSE identical: {sum(r['sse_identical'] for r in rows)}/{len(rows)}; "
         f"sizes identical: {sum(r['sizes_identical'] for r in rows)}/{len(rows)}.\n",
         "Sort cost = median fit time on raw input minus median fit time on presorted input (C++ also times its sort stage "
         "directly: t_sort_raw). Ckmeans.1d.dp 4.3.6 also checks for sorted input (one O(n) scan) and skips its std::sort, "
         "but still copies x and builds an index vector.\n"]
    body = []
    for key in sorted({(r["section"], int(r["N"]), r["method"], r["M"]) for r in rows}):
        sel = [r for r in rows if (r["section"], int(r["N"]), r["method"], r["M"]) == key and r["dataset"] not in DISC]
        if not sel:
            continue
        body.append([key[0], str(key[1]), key[2] + (f" M={key[3]}" if key[3] not in ("0", "") else ""),
                     med([r["fit_raw_s"] for r in sel]), med([r["fit_sorted_s"] for r in sel]),
                     med([r["sort_cost_s"] for r in sel if r["sort_cost_s"] != ""]),
                     med([f(r["t_sort_raw_s"]) for r in sel])])
    L.append("Medians over continuous datasets (and all k) per N:\n")
    L.append(table(["section", "N", "method", "raw s", "sorted s", "raw - sorted s", "C++ t_sort (raw) s"], body))
    for d in (a, b):
        with open(os.path.join(d, "raw_vs_sorted.md"), "w") as fh:
            fh.write("\n".join(L))
    print("raw vs sorted comparison written to", a, "and", b)


def figures(out, res):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available: no figures (pip install matplotlib, then rerun this script)")
        return
    m = [o for o in res if o.get("status") == "ok" and o["section"] == "main" and o["dataset"] in CONT]
    if not m:
        return
    fd = os.path.join(out, "figures")
    os.makedirs(fd, exist_ok=True)
    mode = res[0]["mode"]
    Ns = sorted({int(o["N"]) for o in m})
    ks = sorted({o["k"] for o in m})
    meths = sorted({(o["method"], o["M"]) for o in m})
    def series(meth, M, k, key, agg=med):
        ys = []
        for N in Ns:
            v = [o[key] for o in m if int(o["N"]) == N and o["k"] == k and o["method"] == meth and o["M"] == M and o.get(key) is not None]
            ys.append(agg(v) if v else float("nan"))
        return ys
    for key, fname, ylab, agg in (("fit_s", "fig_time_vs_N", "median fit time (s)", med),
                                  ("gap_pct", "fig_gap_vs_N", "largest gap to exact SSE (%)", max),
                                  ("peak_rss_bytes", "fig_rss_vs_N", "median peak RSS (bytes)", med)):
        sel_k = [k for k in (8, 64, 512) if k in ks] or ks[:3]
        fig, axes = plt.subplots(1, len(sel_k), figsize=(5 * len(sel_k), 4), squeeze=False)
        for ax, k in zip(axes[0], sel_k):
            for meth, M in meths:
                if key == "gap_pct" and meth in ("ckmeans_exact", "Ckmeans.1d.dp"):
                    continue
                ys = series(meth, M, k, key, agg)
                ax.plot(Ns, [max(y, 1e-9) if key == "gap_pct" else y for y in ys], marker="o", ms=3,
                        label=meth + (f" M={M}" if M else ""))
            ax.set_xscale("log", base=2)
            ax.set_yscale("log")
            ax.set_title(f"k = {k} ({mode} input)")
            ax.set_xlabel("N")
            ax.set_ylabel(ylab)
            ax.grid(alpha=0.3)
        axes[0][0].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(fd, fname + ".png"), dpi=150)
        plt.close(fig)
    # speedup vs k at the largest N
    top = max(Ns)
    if any(o["method"] in ("Ckmeans.1d.dp", "ckmeans_exact") for o in m):
        fig, ax = plt.subplots(figsize=(6, 4))
        for ref in ("Ckmeans.1d.dp", "ckmeans_exact"):
            ys = []
            for k in ks:
                rs = []
                for d in CONT:
                    a = [o for o in m if o["dataset"] == d and int(o["N"]) == top and o["k"] == k]
                    h = next((o for o in a if o["method"] == "lex_hybrid" and o["M"] == 4096), None)
                    e = next((o for o in a if o["method"] == ref), None)
                    if h and e and h["fit_s"] and e["fit_s"]:
                        rs.append(e["fit_s"] / h["fit_s"])
                ys.append(med(rs) if rs else float("nan"))
            ax.plot(ks, ys, marker="o", label=f"{ref} / lex_hybrid M=4096")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xlabel("k")
        ax.set_ylabel("time ratio (median over datasets)")
        ax.set_title(f"Speedup at N = {top} ({mode} input)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(fd, "fig_speedup_vs_k.png"), dpi=150)
        plt.close(fig)
    # stage breakdown at the largest N
    hy = [(meth, M) for meth, M in meths if meth in ("lex_hybrid", "lex_plain")]
    fig, ax = plt.subplots(figsize=(max(6, len(hy) * len(ks) * 0.25), 4))
    xlab, bottoms, x = [], None, 0
    import itertools
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, ((meth, M), k) in enumerate(itertools.product(hy, ks)):
        sel = [o for o in m if int(o["N"]) == top and o["k"] == k and o["method"] == meth and o["M"] == M]
        b = 0
        for j, s in enumerate(STAGES):
            v = med([o[s] for o in sel]) or 0
            ax.bar(i, v, bottom=b, color=colors[j % len(colors)], label=s[2:-2] if i == 0 else None)
            b += v
        xlab.append(f"{'plain' if meth == 'lex_plain' else M} k{k}")
    ax.set_xticks(range(len(xlab)))
    ax.set_xticklabels(xlab, rotation=90, fontsize=6)
    ax.set_ylabel("median s")
    ax.set_title(f"LEX stages at N = {top} ({mode} input)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(fd, "fig_stages.png"), dpi=150)
    plt.close(fig)
    print("figures written to", fd)

def _rf(v):
    """Parse a reduction factor that may be "inf" or empty."""
    if v in ("", None):
        return None
    if v == "inf":
        return math.inf
    return f(v)


def refine_ablation(out, res):
    """Per-k/M summary of how much Refine reduces the coarse-DP gap (GOLD run 4)."""
    rows = [o for o in res if o.get("status") == "ok" and o["method"] == "lex_hybrid" and o.get("coarse_sse") not in (None, "")]
    if not rows:
        return
    L = ["# Refine vs coarse-DP gap (GOLD run 4)\n",
         "For each lex_hybrid cell: the coarse-DP SSE is the instrumented partition after Collapse(M)+DP(k) "
         "and before Refine; the final SSE is after Refine. Gaps are 100 × (SSE − exact) / exact, using GOLD "
         "raw `ckmeans_exact` SSEs (this run does not re-run the exact DP). Reduction factor is "
         "coarse_gap / final_gap; percent of gap removed is 100 × (coarse_gap − final_gap) / coarse_gap. "
         "When M is at least the number of atoms the coarse DP is already exact (gap 0); those cells are "
         "counted separately and left out of the reduction statistics.\n"]
    already = [o for o in rows if str(o.get("already_exact")) in ("1", "1.0")]
    rest = [o for o in rows if o not in already]
    L.append(f"Cells: {len(rows)} ok; already exact (M ≥ atoms, gap 0): {len(already)}; "
             f"cells with a coarse gap: {len(rest)}.\n")

    def group_of(o):
        if o["section"] == "audio" or o["dataset"] == "audio":
            return "audio"
        if o["dataset"] in DISC:
            return "discrete"
        return "continuous"

    def trip(xs, kind="gap"):
        xs = [x for x in xs if x is not None]
        if not xs:
            return ""
        def one(x):
            if x is math.inf:
                return "∞"
            if kind == "pct" and abs(x - 100) < 1e-9:
                return "100"
            if kind == "intish":
                return fmt(x, 1) if abs(x - round(x)) > 1e-9 else str(int(round(x)))
            return fmt(x)
        return f"{one(med(xs))} ({one(min(xs))}–{one(max(xs))})"

    for grp, label in (("continuous", "continuous (10 datasets)"),
                       ("discrete", "discrete (2 datasets)"),
                       ("audio", "audio")):
        sub = [o for o in rows if group_of(o) == grp]
        if not sub:
            continue
        Ms = sorted({int(o["M"]) for o in sub})
        ks = sorted({int(o["k"]) for o in sub})
        L.append(f"## {label}\n")
        for M in Ms:
            body = []
            n_alr = n_gap = 0
            for k in ks:
                sel = [o for o in sub if int(o["M"]) == M and int(o["k"]) == k]
                alr = [o for o in sel if str(o.get("already_exact")) in ("1", "1.0")]
                use = [o for o in sel if o not in alr]
                n_alr += len(alr)
                n_gap += len(use)
                if not sel:
                    continue
                cg = [f(o.get("coarse_gap_pct")) for o in sel]
                fg = [f(o.get("gap_pct")) for o in sel]
                rd = [_rf(o.get("reduction_factor")) for o in use]
                rm = [f(o.get("pct_gap_removed")) for o in use]
                sw = [f(o.get("sweeps")) for o in sel]
                mv = [f(o.get("moves")) for o in sel]
                body.append([str(k),
                             trip(cg), trip(fg),
                             trip(rd) if any(x is not None for x in rd) else ("already exact" if alr and not use else ""),
                             trip(rm, "pct") if any(x is not None for x in rm) else "",
                             trip(sw, "intish"), trip(mv, "intish"),
                             f"{len(alr)}/{len(sel)}"])
            L.append(f"**M = {M}** ({n_gap} cells with a coarse gap, {n_alr} already exact). "
                     "Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.\n")
            L.append(table(["k", "coarse gap %", "final gap %", "reduction factor", "% of gap removed",
                            "median sweeps", "median moves", "already exact"], body))


    # Exploratory LTR vs standard RTL Refine, started from the same coarse-DP bounds.
    ltr_rows = [o for o in rows if o.get("ltr_sse") not in (None, "")]
    if ltr_rows:
        SKEW = ["lognormal_continuous", "exponential_continuous", "weibull_continuous"]
        def gap_diff(o):
            a, b = f(o.get("ltr_gap_pct")), f(o.get("gap_pct"))
            if a is None or b is None:
                return None
            return a - b  # LTR minus RTL; negative => LTR closer to exact
        n_diff = sum(str(o.get("ltr_same_partition")) == "0" for o in ltr_rows)
        n_same = sum(str(o.get("ltr_same_partition")) == "1" for o in ltr_rows)
        diffs = [gap_diff(o) for o in ltr_rows]
        diffs = [d for d in diffs if d is not None]
        absd = [abs(d) for d in diffs]
        L.append("## Exploratory variant: left-to-right Refine vs standard right-to-left\n")
        L.append("Each cell starts both Refine directions from the same coarse-DP bounds. Tie rules are "
                 "unchanged (larger bounds win; tie sweeps still push right). This is an exploratory "
                 "variant in the paper-repo harness (`bench/refine_ltr.cpp`); frozen lex1d is the RTL code.\n")
        L.append(f"- cells with both directions: {len(ltr_rows)}")
        L.append(f"- partitions equal (LTR == RTL): {n_same}/{len(ltr_rows)}")
        L.append(f"- partitions differ: {n_diff}/{len(ltr_rows)}")
        if diffs:
            L.append(f"- gap difference (LTR − RTL), percentage points: median {fmt(med(diffs))}, "
                     f"min {fmt(min(diffs))}, max {fmt(max(diffs))}; "
                     f"median |diff| {fmt(med(absd))}, max |diff| {fmt(max(absd))}\n")
        # by k (pool M and datasets)
        ks = sorted({int(o["k"]) for o in ltr_rows})
        body = []
        for k in ks:
            sel = [o for o in ltr_rows if int(o["k"]) == k]
            d = [gap_diff(o) for o in sel]
            d = [x for x in d if x is not None]
            nd = sum(str(o.get("ltr_same_partition")) == "0" for o in sel)
            body.append([str(k), str(len(sel)), f"{nd}/{len(sel)}",
                         fmt(med(d)) if d else "", fmt(max(d, key=abs)) if d else "",
                         fmt(med([abs(x) for x in d])) if d else ""])
        L.append("By k (all datasets and M):\n")
        L.append(table(["k", "cells", "partitions differ", "median LTR−RTL gap pp",
                        "signed max |diff| (signed)", "median |diff|"], body))
        # by dataset
        dss = sorted({o["dataset"] for o in ltr_rows})
        body = []
        for ds in dss:
            sel = [o for o in ltr_rows if o["dataset"] == ds]
            d = [x for x in (gap_diff(o) for o in sel) if x is not None]
            nd = sum(str(o.get("ltr_same_partition")) == "0" for o in sel)
            tag = " (skewed)" if ds in SKEW else ""
            body.append([ds + tag, str(len(sel)), f"{nd}/{len(sel)}",
                         fmt(med(d)) if d else "", fmt(max(d, key=abs)) if d else "",
                         fmt(med([abs(x) for x in d])) if d else ""])
        L.append("By dataset (all k and M; lognormal, exponential and weibull are the skewed continuous families):\n")
        L.append(table(["dataset", "cells", "partitions differ", "median LTR−RTL gap pp",
                        "signed max |diff| (signed)", "median |diff|"], body))
        # skewed subset vs other continuous vs discrete vs audio
        def bucket(o):
            if o["section"] == "audio" or o["dataset"] == "audio":
                return "audio"
            if o["dataset"] in DISC:
                return "discrete"
            if o["dataset"] in SKEW:
                return "skewed continuous (lognormal, exponential, weibull)"
            return "other continuous"
        body = []
        for name in ("skewed continuous (lognormal, exponential, weibull)", "other continuous", "discrete", "audio"):
            sel = [o for o in ltr_rows if bucket(o) == name]
            if not sel:
                continue
            d = [x for x in (gap_diff(o) for o in sel) if x is not None]
            nd = sum(str(o.get("ltr_same_partition")) == "0" for o in sel)
            body.append([name, str(len(sel)), f"{nd}/{len(sel)}",
                         fmt(med(d)) if d else "", fmt(max(d, key=abs)) if d else ""])
        L.append("By family:\n")
        L.append(table(["family", "cells", "partitions differ", "median LTR−RTL gap pp", "signed max |diff| (signed)"], body))

    # GOLD identity reminder if gold_check wrote counts into the same folder
    gcp = os.path.join(out, "gold_check.csv")
    if os.path.isfile(gcp):
        with open(gcp, newline="") as fh:
            gc = list(csv.DictReader(fh))
        if gc:
            L.append("## GOLD identity (final SSE vs results/gold/raw lex_hybrid)\n")
            L.append(f"- cells compared: {len(gc)}")
            L.append(f"- final SSE identical: {sum(int(r['sse_identical']) for r in gc)}/{len(gc)}")
            L.append(f"- sizes identical: {sum(int(r['sizes_identical']) for r in gc)}/{len(gc)}\n")

    path = os.path.join(out, "refine_ablation.md")
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    print("refine ablation summary written to", path)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, res = merge(a.out)
    if not rows:
        print("no cells yet in", a.out)
        return 0
    summary(a.out, rows, res)
    gold_check(a.out, res)
    if res and res[0].get("mode") == "refine":
        refine_ablation(a.out, res)
    raw_vs_sorted(a.out)
    try:
        figures(a.out, res)
    except Exception as e:
        print(f"WARNING: figures failed ({e}); results.csv and summaries were still written")
    print(f"analysis: {len(rows)} processes, {len(res)} cell x method rows -> {a.out}/results.csv, summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
