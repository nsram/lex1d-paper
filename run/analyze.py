"""Analysis (standard library; matplotlib optional, only for figures).

    python3 run/analyze.py --out out/raw        (the run scripts call this at the end)

For one out folder: merges cells/ into reps.csv (one row per process) and results.csv (one row per
cell x method: medians and min/max over the timed rounds), writes summary.md, prior_check.md (SSE
identity and time ratios against the earlier Mac runs in results/prior/) and figures/ (if matplotlib imports).
If both out/raw/ and out/sorted/ exist next to each other (with results.csv), it also writes
raw_vs_sorted.csv / raw_vs_sorted.md into both (sort cost = raw - sorted, per cell and method).
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
        o.update(status="ok" if len(ok) == len(g) else "partial", skip_reason="",
                 sse=ok[0]["sse"], sse_identical_all_rounds=int(len(sses) == 1 and len(sizes) == 1),
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
    for o in res:
        e = ex.get((o["section"], o["dataset"], o["slice"], o["k"], o["weighted"]))
        if e and o.get("sse") not in (None, ""):
            es, s = float(e["sse"]), float(o["sse"])
            o["gap_pct"] = 100 * (s - es) / es if es > 0 else 0.0
            o["sizes_match_exact"] = int(o["sizes"] == e["sizes"])
    fields = ["section", "dataset", "slice", "N", "D", "D_expected", "k", "method", "M", "family", "weighted", "mode",
              "status", "skip_reason", "sse", "gap_pct", "sizes_match_exact", "sse_identical_all_rounds", "n_timed",
              "fit_s", "fit_min_s", "fit_max_s", "post_sort_s"] + STAGES + [
              "api_s", "api_match", "did_sort", "peak_rss_bytes", "peak_rss_min", "peak_rss_max", "peak_footprint_bytes",
              "baseline_method", "baseline_rss_bytes", "rss_above_baseline_bytes", "dp_table_est_bytes", "k_eff", "atoms",
              "sweeps", "moves", "start", "version", "first_ts", "last_ts", "sessions", "sizes"]
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
        L.append("## Main grid: speedup of lex_hybrid M=4096 (median over continuous datasets of time ratios)\n")
        for ref in ("Ckmeans.1d.dp", "ckmeans_exact"):
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
    for s in ("audio", "weighted", "bindings"):
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


def prior_check(out, res):
    p = os.path.join(PACK, "results", "prior", "prior_mac.csv")
    if not os.path.isfile(p) or not res:
        return
    with open(p, newline="") as fh:
        prior = list(csv.DictReader(fh))
    mode = res[0]["mode"]
    idx = {}
    for o in res:
        if o.get("status") != "ok":
            continue
        meth = {"rb_hybrid": "lex_hybrid"}.get(o["method"], o["method"]) if o["section"] == "bindings" else o["method"]
        idx[(o["section"], o["dataset"], int(o["slice"]), int(o["k"]), meth, int(o["M"] or 0), o["family"] if o["section"] == "bindings" else "")] = o
    out_rows = []
    for r in prior:
        fam = "R" if r["source"] == "v23_rbind" else ""
        if r["source"] == "v23_rbind" and r["method"] == "Ckmeans.1d.dp":
            continue  # v23's k=16 drift cells are covered by the main grid
        sec = r["section"]
        key = (sec, r["dataset"], int(r["slice"]), int(r["k"]), r["method"], int(float(r["M"] or 0)), fam)
        o = idx.get(key)
        if not o:
            continue
        full_n = 8_168_256 if int(r["slice"]) == 0 else 2 ** (13 + int(r["slice"]))
        if int(o["N"]) != full_n:  # e.g. --smoke pieces: not comparable
            continue
        t_prior = f(r["time_presorted_s"]) if mode == "sorted" else f(r["time_raw_s"])
        same = o["sse"] == r["sse"] or (f(o["sse"]) == f(r["sse"]))
        out_rows.append(dict(source=r["source"], section=sec, dataset=r["dataset"], slice=r["slice"], k=r["k"], method=r["method"],
                             M=r["M"], sse_v24=o["sse"], sse_prior=r["sse"], sse_identical=int(same),
                             rel_diff=(abs(f(o["sse"]) - f(r["sse"])) / f(r["sse"]) if f(r["sse"]) else ""),
                             sizes_identical=(int(o["sizes"] == r["sizes"]) if r["sizes"] else ""),
                             time_v24=o["fit_s"], time_prior=t_prior,
                             time_ratio_v24_over_prior=(o["fit_s"] / t_prior if t_prior and o["fit_s"] else "")))
    if not out_rows:
        return
    with open(os.path.join(out, "prior_check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    L = [f"# Identity and drift vs earlier Mac runs ({os.path.basename(out)})\n",
         "This run's time is the median of the timed rounds (one fit per process). Earlier times: v15 = median of in-process repeats "
         f"({'presorted_s' if mode == 'sorted' else 'time_s, unsorted'}); v19/v21/v23 = single fits. Same Mac, different day.\n"]
    body = []
    for key in sorted({(r["source"], r["method"]) for r in out_rows}):
        sel = [r for r in out_rows if (r["source"], r["method"]) == key]
        rat = [r["time_ratio_v24_over_prior"] for r in sel if r["time_ratio_v24_over_prior"] != ""]
        szs = [r["sizes_identical"] for r in sel if r["sizes_identical"] != ""]
        body.append([key[0], key[1], str(len(sel)), f"{sum(r['sse_identical'] for r in sel)}/{len(sel)}",
                     f"{sum(szs)}/{len(szs)}" if szs else "", med(rat), min(rat) if rat else None, max(rat) if rat else None])
    L.append(table(["earlier run", "method", "cells", "SSE identical", "sizes identical", "time ratio this run/earlier (median)", "min", "max"], body))
    with open(os.path.join(out, "prior_check.md"), "w") as fh:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, res = merge(a.out)
    if not rows:
        print("no cells yet in", a.out)
        return 0
    summary(a.out, rows, res)
    prior_check(a.out, res)
    raw_vs_sorted(a.out)
    figures(a.out, res)
    print(f"analysis: {len(rows)} processes, {len(res)} cell x method rows -> {a.out}/results.csv, summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
