"""Benchmark orchestrator (standard library only). Called by the run scripts; not meant to be run by hand.

One process per fit, under /usr/bin/time (-l on macOS, -v on Linux), so every fit has its own peak RSS.
Cells are (section, dataset, slice, k). Inside a cell, the methods are INTERLEAVED: round 0 is a warm-up
and verification round (C++: one public-API call then one instrumented call, api_match checked; R: one
call), then REPS timed rounds. The method order is rotated by one position every round (and the starting
position by cell), so slow drift in machine speed hits every method equally. A cell's rows are written
to out/cells/<section>/<cell>.csv only when all its rounds finish (atomic rename), so a rerun resumes at
the first unfinished cell. Every row carries the session id and a timestamp.

--mode raw     every fit gets the values in file order
--mode sorted  every fit gets the same slice's values presorted (each slice sorted on its own after cutting).
               lex1d detects sorted input (std::is_sorted) and skips its sort; Ckmeans.1d.dp 4.3.6 also
               checks (one O(n) scan, src/Ckmeans.1d.dp.cpp) and skips its std::sort
--mode bindings  binding-overhead subset (C++ driver vs lex1d R binding vs lex1d Python binding)
--mode refine  GOLD run 4: lex_hybrid only, raw input order, M in {4096, 8192, 16384}. The driver
               (bench/refine_fit.cpp) also records the coarse-DP SSE before Refine.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data  # noqa: E402

K_FULL = [4, 8, 16, 32, 64, 128, 256, 512]
K_WEIGHTED = [8, 64, 256, 512]
WEIGHTED_DATASETS = ["uniform_continuous", "gaussian_continuous", "lognormal_continuous"]
M_MAIN = [4096, 8192, 16384]
M_SWEEP = [1024, 2048]
K_BIND = [8, 64, 512]

# method key -> (family, method label, M)
def method_table(weighted: bool):
    return {
        "exact": ("cpp", "ckmeans_exact", 0),
        "ckmeans": ("R", "Ckmeans.1d.dp", 0),
        "plain": ("cpp", "lex_plain", 0),
        **{f"hybrid{m}": ("cpp", "lex_hybrid", m) for m in M_SWEEP + M_MAIN},
    }


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ram_bytes() -> int:
    try:
        if platform.system() == "Darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


def ram_available() -> int:
    """Memory the OS can hand out now without swapping (bytes; 0 if unknown).
    macOS: free + inactive + speculative + purgeable pages (vm_stat). Linux: MemAvailable."""
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["vm_stat"], text=True)
            page = int(re.search(r"page size of (\d+) bytes", out).group(1))
            pages = 0
            for name in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"):
                m = re.search(name + r":\s+(\d+)", out)
                pages += int(m.group(1)) if m else 0
            return pages * page
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


def time_prefix():
    return ["/usr/bin/time", "-l"] if platform.system() == "Darwin" else ["/usr/bin/time", "-v"]


def parse_time(err: str):
    rss = wall = foot = None
    if m := re.search(r"^\s*(\d+)\s+maximum resident set size", err, re.M):
        rss = int(m.group(1))
    elif m := re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", err):
        rss = int(m.group(1)) * 1024
    if m := re.search(r"^\s*(\d+)\s+peak memory footprint", err, re.M):
        foot = int(m.group(1))
    if m := re.search(r"^\s*([\d.]+)\s+real\s", err, re.M):
        wall = float(m.group(1))
    elif m := re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(?:(\d+):)?(\d+):([\d.]+)", err):
        wall = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return rss, wall, foot


def parse_result(out: str) -> dict:
    for line in out.splitlines():
        if line.startswith("RESULT "):
            return dict(kv.split("=", 1) for kv in line.split()[1:] if "=" in kv)
    return {}


def dp_table_est(label: str, k: int, n: int, d: int, M: int) -> int:
    """Predicted DP-table bytes (formulae from the earlier memory study) used for the memory guard."""
    if label == "Ckmeans.1d.dp":
        return 16 * k * n
    if label == "ckmeans_exact":
        return 4 * max(k - 1, 0) * (d + 1)
    if label == "lex_hybrid":
        return 4 * max(k - 1, 0) * (max(k, min(M, d)) + 1)
    return 0


ROW_FIELDS = [
    "session", "timestamp", "mode", "section", "cell", "dataset", "slice", "N", "D", "D_expected", "k", "method",
    "M", "family", "weighted", "rep", "warmup", "order_pos", "status", "skip_reason", "exit_code", "sse", "k_eff",
    "atoms", "fit_s", "post_sort_s", "api_s", "api_match", "did_sort", "t_prep_s", "t_sort_s", "t_atoms_s",
    "t_collapse_s", "t_dp_s", "t_starts_s", "t_refine_s", "t_summary_s", "sweeps", "moves", "start", "load_s",
    "api_presorted",
    "wall_s", "peak_rss_bytes", "peak_footprint_bytes", "rss_self_bytes", "dp_table_est_bytes", "version",
    "input_file", "sizes",
]
# Appended only when --mode refine so runs 1-3 keep the original cell-CSV columns.
REFINE_ROW_FIELDS = [
    "session", "timestamp", "mode", "section", "cell", "dataset", "slice", "N", "D", "D_expected", "k", "method",
    "M", "family", "weighted", "rep", "warmup", "order_pos", "status", "skip_reason", "exit_code", "sse", "coarse_sse", "ltr_sse", "k_eff",
    "atoms", "fit_s", "post_sort_s", "api_s", "api_match", "did_sort", "t_prep_s", "t_sort_s", "t_atoms_s",
    "t_collapse_s", "t_dp_s", "t_starts_s", "t_refine_s", "t_refine_ltr_s", "t_summary_s", "sweeps", "moves", "ltr_sweeps", "ltr_moves", "ltr_same_partition", "start", "load_s",
    "api_presorted",
    "wall_s", "peak_rss_bytes", "peak_footprint_bytes", "rss_self_bytes", "dp_table_est_bytes", "version",
    "input_file", "sizes", "coarse_sizes", "ltr_sizes",
]


class Runner:
    def __init__(self, a):
        self.a = a
        self.ram = ram_bytes()
        self.limit = int(a.mem_limit_gb * 1e9)
        self.cells_done = 0
        self.t0 = time.time()

    # ---------- one process ----------
    def run_proc(self, family, cmd):
        full = time_prefix() + cmd
        env = dict(os.environ)
        p = subprocess.run(full, capture_output=True, text=True, env=env)
        res = parse_result(p.stdout)
        rss, wall, foot = parse_time(p.stderr)
        return p.returncode, res, rss, wall, foot, p.stderr

    def cmd_for(self, key, info, k, mode_flag, inp):
        fam, label, M = info
        x, w = inp
        if fam == "cpp":
            kind = {"ckmeans_exact": "exact", "lex_plain": "plain", "lex_hybrid": "hybrid", "load": "load"}[label]
            c = [self.a.fit, x, kind, str(k), str(M), mode_flag]
            return c + ([w] if w else [])
        if fam == "R":
            meth = {"Ckmeans.1d.dp": "ckmeans", "R_load": "R_load", "rb_hybrid": "rb_hybrid", "rb_load": "rb_load"}[label]
            return [self.a.rscript, os.path.join(HERE, "fit_r.R"), x, meth, str(k), str(M)] + ([w] if w else [])
        if fam == "py":
            return [self.a.pyb, os.path.join(HERE, "fit_py.py"), x, label, str(k), str(M)]
        raise ValueError(fam)

    # ---------- inputs ----------
    def inp(self, meta, weighted):
        p = meta["prefix"]
        if self.a.mode == "sorted":
            return (p + ".wx.sorted.f64", p + ".w.sorted.f64") if weighted else (p + ".sorted.f64", None)
        return (p + ".raw.f64", p + ".w.raw.f64") if weighted else (p + ".raw.f64", None)

    # ---------- one cell ----------
    def cell(self, section, meta, k, methods, weighted, cell_index, baseline=False):
        name = f"{meta['dataset']}_s{meta['slice']}_" + ("load" + ("_w" if weighted else "") if baseline else f"k{k}")
        cdir = os.path.join(self.a.out, "cells", section)
        os.makedirs(cdir, exist_ok=True)
        path = os.path.join(cdir, name + ".csv")
        if os.path.exists(path):
            self.cells_done += 1
            return
        inp = self.inp(meta, weighted)
        base = dict(session=self.a.session, mode=self.a.mode, section=section, cell=name, dataset=meta["dataset"],
                    slice=meta["slice"], N=meta["N"], D=meta["D"], D_expected=meta.get("D_expected", ""), k=k if not baseline else 0,
                    weighted=int(weighted), input_file=os.path.basename(inp[0]))
        rows, run, skipped = [], [], []
        for key, info in methods:
            fam, label, M = info
            est = dp_table_est(label, k, meta["N"], meta["D"], M) if not baseline else 0
            reason = ""
            if est > self.limit:
                reason = f"dp_table_est {est} B > mem limit {self.limit} B"
            elif self.ram and est > 0.85 * self.ram:
                reason = f"dp_table_est {est} B > 85% of RAM {self.ram} B"
            elif self.a.free_mem_guard and est > 2**30:
                avail = ram_available()
                if avail and est + 2 * 2**30 > avail:  # table plus ~2 GB for R, the data and the OS
                    reason = (f"dp_table_est {est} B > memory available now {avail} B "
                              f"minus a 2 GB margin (skipped instead of swapping; to retry, free memory, delete this cell's CSV "
                              f"under out/.../cells/ and re-run)")
            if reason:
                skipped.append(dict(base, method=label, M=M, family=fam, rep="", warmup="", order_pos="",
                                    status="skipped_mem", skip_reason=reason, dp_table_est_bytes=est,
                                    timestamp=now_iso()))
            else:
                run.append((key, info, est))
        reps = 1 if baseline else self.a.reps + 1  # baseline: one load process per family
        for rep in range(reps):
            n = len(run)
            if n == 0:
                break
            rot = (cell_index + rep) % n
            order = run[rot:] + run[:rot]
            for pos, (key, info, est) in enumerate(order):
                fam, label, M = info
                warm = rep == 0 and not baseline
                mode_flag = "verify" if warm else "timed"
                ts = now_iso()
                rc, res, rss, wall, foot, err = self.run_proc(fam, self.cmd_for(key, info, k, mode_flag, inp))
                ok = rc == 0 and res and "error" not in res
                row = dict(base, timestamp=ts, method=label, M=M, family=fam, rep=rep, warmup=int(warm),
                           order_pos=pos, status="ok" if ok else "failed", exit_code=rc,
                           skip_reason="" if ok else (err.strip().splitlines() or [""])[-1][:300].replace(",", ";"),
                           wall_s=wall, peak_rss_bytes=rss, peak_footprint_bytes=foot, dp_table_est_bytes=est)
                for f in ("sse", "coarse_sse", "ltr_sse", "k_eff", "atoms", "fit_s", "post_sort_s", "api_s", "api_match", "did_sort", "t_prep_s",
                          "t_sort_s", "t_atoms_s", "t_collapse_s", "t_dp_s", "t_starts_s", "t_refine_s", "t_refine_ltr_s", "t_summary_s",
                          "sweeps", "moves", "ltr_sweeps", "ltr_moves", "ltr_same_partition",
                          "start", "load_s", "version", "sizes", "coarse_sizes", "ltr_sizes"):
                    if f in res:
                        row[f] = res[f]
                if "rss_self" in res:
                    row["rss_self_bytes"] = res["rss_self"]
                if res.get("api_s") == "nan":
                    row["api_s"] = ""
                if res.get("api_match") == "-1":
                    row["api_match"] = ""
                if ok and fam == "cpp" and label != "load":
                    want = "0" if self.a.mode == "sorted" else "1"
                    row["api_presorted"] = res.get("api_presorted", "")
                    good = row.get("did_sort") == want and (row["api_presorted"] in ("", "-1") or row["api_presorted"] == ("1" if want == "0" else "0"))
                    if not good:
                        row["status"] = "presort_flag_mismatch"
                        row["skip_reason"] = f"mode={self.a.mode} did_sort={row.get('did_sort')} api_presorted={row['api_presorted']}"
                        print(f"  ERROR presort flag: {name} {label} M={M} {row['skip_reason']}", flush=True)
                rows.append(row)
                if not ok:
                    print(f"  FAILED {name} {label} M={M} rep={rep} rc={rc}: {row['skip_reason']}", flush=True)
        rows += skipped
        tmp = path + ".tmp"
        with open(tmp, "w", newline="") as f:
            fields = REFINE_ROW_FIELDS if self.a.mode == "refine" else ROW_FIELDS
            wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)
        os.replace(tmp, path)
        self.cells_done += 1
        el = time.time() - self.t0
        fits = [r for r in rows if r.get("rep") not in ("", 0) and r.get("status") == "ok"]
        med = {}
        for r in fits:
            med.setdefault((r["method"], r["M"]), []).append(float(r["fit_s"]) if r.get("fit_s") not in (None, "") else 0.0)
        msg = " ".join(f"{m}{'' if not M else M}={statistics.median(v):.4g}s" for (m, M), v in sorted(med.items(), key=str))
        print(f"{now_iso()} [{self.cells_done}/{self.total}] {section} {name} done ({el/60:.1f} min elapsed) {msg}"
              + (f"  skipped: {len(skipped)}" if skipped else ""), flush=True)


def build_plan(a, r: Runner):
    """Returns list of (section, meta_key, k, methods, weighted, baseline)."""
    plan = []
    if a.mode == "bindings":
        cpp = ("cpp", "lex_hybrid", 4096)
        fams = [("cpp", cpp)]
        if a.rscript and a.rb:
            fams.append(("rb", ("R", "rb_hybrid", 4096)))
        if a.pyb:
            fams.append(("py", ("py", "py_hybrid", 4096)))
        loads = [("cpp_load", ("cpp", "load", 0))]
        if a.rscript and a.rb:
            loads.append(("rb_load", ("R", "rb_load", 0)))
        if a.pyb:
            loads.append(("py_load", ("py", "py_load", 0)))
        for key in a.bind_inputs:
            plan.append(("bindings", key, 0, loads, False, True))
            for k in a.k_bind:
                plan.append(("bindings", key, k, fams, False, False))
        return plan
    if a.mode == "refine":
        # lex_hybrid only, main M values, no load baselines, no weighted section, no extra M-sweep.
        hy = [(f"hybrid{m}", ("cpp", "lex_hybrid", m)) for m in M_MAIN]
        if "main" in a.sections:
            for s in a.slices:
                for d in a.datasets:
                    for k in a.k:
                        plan.append(("main", (d, s), k, hy, False, False))
        if "audio" in a.sections:
            for k in a.k:
                plan.append(("audio", ("audio", 0), k, hy, False, False))
        return plan
    mt = method_table(False)
    def meths(msweep, weighted=False):
        keys = ["exact"] + (["ckmeans"] if a.rscript else []) + ["plain"]
        Ms = (M_SWEEP if msweep else []) + M_MAIN if not weighted else [4096]
        keys += [f"hybrid{m}" for m in Ms]
        return [(kk, mt[kk]) for kk in keys]
    def loads():
        return [("cpp_load", ("cpp", "load", 0))] + ([("R_load", ("R", "R_load", 0))] if a.rscript else [])
    if "main" in a.sections:
        for s in a.slices:
            for d in a.datasets:
                key = (d, s)
                plan.append(("main", key, 0, loads(), False, True))
                for k in a.k:
                    plan.append(("main", key, k, meths("msweep" in a.sections and s == max(a.slices)), False, False))
    if "audio" in a.sections:
        plan.append(("audio", ("audio", 0), 0, loads(), False, True))
        for k in a.k:
            plan.append(("audio", ("audio", 0), k, meths("msweep" in a.sections), False, False))
    if "gpt2" in a.sections:  # second real dataset: the same protocol as the audio section
        plan.append(("gpt2", ("gpt2", 0), 0, loads(), False, True))
        for k in a.k:
            plan.append(("gpt2", ("gpt2", 0), k, meths("msweep" in a.sections), False, False))
    if "weighted" in a.sections:
        for s in a.w_slices:
            for d in a.w_datasets:
                plan.append(("weighted", (d, s), 0, loads(), True, True))
                for k in a.k_weighted:
                    plan.append(("weighted", (d, s), k, meths(False, True), True, False))
    return plan


def prepare_inputs(a, plan):
    """Prepare every input the plan needs (skips ones already prepared by an earlier session)."""
    idir = os.path.join(a.workdir, "inputs")
    os.makedirs(idir, exist_ok=True)
    need = {}
    for sec, key, k, m, w, b in plan:
        need.setdefault(key, set()).add(w)
    metas = {}
    by_ds = {}
    for (d, s), ws in need.items():
        by_ds.setdefault(d, []).append((s, any(ws)))
    for d, lst in sorted(by_ds.items()):
        ready = {}
        for s, w in lst:
            m = data.read_meta(os.path.join(idir, f"{d}_s{s}"))
            if m and (not w or m["weighted"]) and os.path.exists(m["prefix"] + ".sorted.f64"):
                ready[s] = m
        todo = [(s, w) for s, w in lst if s not in ready]
        if todo:
            t = time.time()
            if d == "audio":
                ready[0] = data.prepare_audio(idir, truncate=a.audio_truncate)
            elif d == "gpt2":
                ready[0] = data.prepare_gpt2(idir, truncate=a.gpt2_truncate)
            else:
                ms = data.prepare_dataset(a.input_dir, idir, d, [s for s, _ in todo],
                                          weighted_slices=[s for s, w in todo if w], truncate=a.truncate)
                for m in ms:
                    ready[m["slice"]] = m
            print(f"{now_iso()} prepared {d} slices {[s for s, _ in todo]} ({time.time()-t:.1f}s)", flush=True)
        for s, _ in lst:
            metas[(d, s)] = ready[s]
    # per-slice check of every prepared input (each sorted copy is a permutation of its own raw slice,
    # ascending), plus a SHA-256 manifest; also re-run on resume, so a damaged file is caught
    rows, bad = [], 0
    for (d, s), m in sorted(metas.items(), key=str):
        for r in data.check_input(m["prefix"], bool(m["weighted"])):
            r = dict(dataset=d, slice=s, **r)
            rows.append(r)
            bad += r["ok"] == 0
    man = os.path.join(a.out, "inputs_manifest.csv")
    with open(man, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["dataset", "slice", "file", "n", "sha256", "check", "ok"])
        w.writeheader()
        w.writerows(rows)
    nslices = len(metas)
    print(f"{now_iso()} inputs checked: {nslices} slices, {len(rows)} files; "
          f"{'all sorted copies are ascending permutations of their own raw slice' if not bad else str(bad) + ' FAILED'} "
          f"(inputs_manifest.csv)", flush=True)
    if bad:
        raise SystemExit("input check failed; see inputs_manifest.csv")
    return metas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["raw", "sorted", "bindings", "refine"])
    ap.add_argument("--input-dir", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--fit", required=True)
    ap.add_argument("--rscript", default="")
    ap.add_argument("--rb", type=int, default=0)
    ap.add_argument("--pyb", default="")
    ap.add_argument("--session", required=True)
    ap.add_argument("--sections", default="main,msweep,audio,weighted")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mem-limit-gb", type=float, default=100)
    ap.add_argument("--datasets", default=",".join(data.DATASETS))
    ap.add_argument("--slices", default="1,2,3,4,5,6,7")
    ap.add_argument("--k", default=",".join(map(str, K_FULL)))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--free-mem-guard", type=int, default=0)
    a = ap.parse_args()
    a.sections = [s for s in a.sections.split(",") if s]
    a.datasets = [d for d in a.datasets.split(",") if d]
    a.slices = [int(s) for s in a.slices.split(",") if s]
    a.k = [int(v) for v in a.k.split(",") if v]
    a.k_weighted, a.w_datasets, a.w_slices = K_WEIGHTED, WEIGHTED_DATASETS, list(a.slices)
    a.k_bind = K_BIND
    a.bind_inputs = [("gaussian_continuous", 7), ("audio", 0)]
    a.truncate = a.audio_truncate = a.gpt2_truncate = 0
    if a.smoke:  # light check: tiny pieces of the real files, two k, one timed round
        a.truncate, a.audio_truncate, a.gpt2_truncate = 2048, 20000, 65536
        a.slices = [1, 2]
        a.datasets = ["gaussian_continuous", "lognormal_continuous", "triangular_discrete", "spike_uniform_discrete"]
        a.k = [4, 64]
        a.k_weighted, a.w_datasets, a.w_slices = [8], ["gaussian_continuous"], [1]
        a.k_bind = [8, 64]
    r = Runner(a)
    plan = build_plan(a, r)
    r.total = len(plan)
    print(f"{now_iso()} plan: {len(plan)} cells, mode={a.mode}, sections={a.sections}, reps={a.reps} (+1 warm-up), "
          f"RAM={r.ram/1e9:.1f} GB, available now={ram_available()/1e9:.1f} GB, mem limit={a.mem_limit_gb} GB", flush=True)
    if a.plan_only:
        for p in plan:
            print(p[0], p[1], p[2], [m[0] for m in p[3]], "weighted" if p[4] else "", "baseline" if p[5] else "")
        return 0
    metas = prepare_inputs(a, plan)
    for i, (sec, key, k, methods, w, b) in enumerate(plan):
        r.cell(sec, metas[key], k, methods, w, i, baseline=b)
    print(f"{now_iso()} all {len(plan)} cells done ({(time.time()-r.t0)/60:.1f} min this session)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
