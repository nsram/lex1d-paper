#!/usr/bin/env python3
"""Numbers from run 4 (the diagnostic Refine run) quoted in the papers.

From the repo root:   bash run/run4_numbers.sh

Reads results/gold/refine/results.csv (run 4, GOLD-checked: final SSE and bin sizes identical to
results/gold/raw lex_hybrid in 2,040 of 2,040 cells) and, for one cross-check, the lex_hybrid rows of
results/gold/raw/results.csv. Never uses run 4's timing columns (t_refine_s, fit_s, t_summary_s,
t_refine_ltr_s, ...): the papers do not use them.

Writes out/run4_numbers/results.json and out/run4_numbers/summary.md, and prints the summary.
"""
import json
import os

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN4 = os.path.join(ROOT, "results", "gold", "refine", "results.csv")
RAW = os.path.join(ROOT, "results", "gold", "raw", "results.csv")
OUT = os.path.join(ROOT, "out", "run4_numbers")
TWO20 = 1048576

r = pd.read_csv(RUN4)
assert len(r) == 2040 and (r.status == "ok").all(), "unexpected results/gold/refine/results.csv"
cont = r.dataset.str.endswith("continuous")
disc = r.dataset.str.endswith("discrete")
out = {}


def summ(d):
    """Medians over the cells where the coarse DP was not exact (as in Table 3 of the technical paper)."""
    g = d[d.coarse_gap_pct > 0]
    return dict(cells=int(len(d)), coarse_not_exact=int(len(g)),
                coarse_median_pct=float(g.coarse_gap_pct.median()),
                final_median_pct=float(g.gap_pct.median()),
                removed_median_pct=float(g.pct_gap_removed.median()),
                removed_min_pct=float(g.pct_gap_removed.min()),
                moves_median=float(d.moves.median()))


# Table 3: continuous datasets, M = 4,096, all N (70 cells per k)
out["table3_M4096"] = {int(k): summ(d) for k, d in r[cont & (r.M == 4096)].groupby("k")}

# final error agrees with the main runs (median at k = 512, M = 4,096, continuous)
raw = pd.read_csv(RAW)
main = raw[(raw.section == "main") & (raw.weighted == 0) & (raw.method == "lex_hybrid")
           & raw.dataset.str.endswith("continuous") & (raw.M == 4096) & (raw.k == 512)]
out["final_median_k512_M4096"] = dict(run4=float(r[cont & (r.M == 4096) & (r.k == 512)].gap_pct.median()),
                                      main_runs=float(main.gap_pct.median()), main_cells=int(len(main)))

# left-to-right sweeps (exploratory variant) against the released right-to-left sweeps
diff = r[r.ltr_same_partition == 0]
dpp = diff.ltr_gap_pct - diff.gap_pct
out["ltr"] = dict(cells=int(len(r)), different_sse=int((dpp != 0).sum()), different_partition=int(len(diff)),
                  different_discrete=int(diff.dataset.str.endswith("discrete").sum()),
                  ltr_lower=int((dpp < 0).sum()), ltr_higher=int((dpp > 0).sum()),
                  max_abs_pp=float(dpp.abs().max()))


def reg(d, col):
    """log2(error) ~ log2 k + log2 M + dataset, cluster-robust by dataset; normal 95% intervals."""
    d = d[d[col] > 0].copy()
    d["le"], d["lk"], d["lM"] = np.log2(d[col]), np.log2(d.k), np.log2(d.M)
    f = smf.ols("le ~ lk + lM + C(dataset)", d).fit(cov_type="cluster", cov_kwds={"groups": d.dataset})
    V, ci = f.cov_params(), f.conf_int()
    a, b = f.params.lk, f.params.lM
    se = np.sqrt(V.loc["lk", "lk"] + V.loc["lM", "lM"] + 2 * V.loc["lk", "lM"])
    return dict(cells=int(f.nobs), alpha=float(a), alpha_ci=[float(x) for x in ci.loc["lk"]],
                beta=float(b), beta_ci=[float(x) for x in ci.loc["lM"]], sum=float(a + b),
                sum_ci=[float(a + b - 1.96 * se), float(a + b + 1.96 * se)], R2=float(f.rsquared))


big = cont & (r.k >= 64)
out["coarse_reg_N2^20"] = reg(r[big & (r.N == TWO20)], "coarse_gap_pct")
out["coarse_reg_N>=131072"] = reg(r[big & (r.N >= 131072)], "coarse_gap_pct")
# final error over the same cells (identical to the main runs, whose final SSEs these equal)
out["final_reg_N>=131072"] = reg(r[big & (r.N >= 131072)], "gap_pct")
out["final_reg_beta_by_N"] = {int(N): reg(r[big & (r.N == N)], "gap_pct")["beta"] for N in sorted(r[big & (r.N >= 131072)].N.unique())}

# coarse error per doubling, N = 2^20, median over the 10 datasets of the ratio
x = r[cont & (r.N == TWO20) & (r.k == 512)].pivot(index="dataset", columns="M", values="coarse_gap_pct")
out["coarse_per_doubling_M_k512"] = {"4096->8192": float((x[4096] / x[8192]).median()),
                                     "8192->16384": float((x[8192] / x[16384]).median())}
y = r[cont & (r.N == TWO20) & (r.M == 4096)].pivot(index="dataset", columns="k", values="coarse_gap_pct")
out["coarse_per_doubling_k_M4096"] = {f"{a}->{b}": float((y[b] / y[a]).median()) for a, b in [(64, 128), (128, 256), (256, 512)]}

# discrete datasets, all three M
dd = r[disc]
out["discrete"] = dict(cells=int(len(dd)), coarse_exact=int((dd.coarse_gap_pct == 0).sum()),
                       final_exact=int((dd.gap_pct <= 0).sum()), max_sweeps=int(dd.sweeps.max()), max_moves=int(dd.moves.max()))

# audio, k = 512, M = 4,096
au = r[(r.dataset == "audio") & (r.k == 512) & (r.M == 4096)].iloc[0]
out["audio_k512_M4096"] = dict(coarse_pct=float(au.coarse_gap_pct), final_pct=float(au.gap_pct), removed_pct=float(au.pct_gap_removed))

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(out, f, indent=1)

g = lambda v, d=3: "0" if v == 0 else f"{v:#.{d}g}"  # keeps trailing zeros (0.40, not 0.4)
L = ["# Run 4 numbers (diagnostic Refine run)", "",
     "Source: results/gold/refine/results.csv (run 4); one cross-check uses results/gold/raw/results.csv. "
     "Timing columns are not used.", "",
     "## Table 3: continuous, M = 4,096, all N (medians over cells where the coarse DP was not exact)", "",
     "| k | cells | coarse not exact | coarse DP median % | after Refine median % | removed median % | removed min % | moves median |",
     "|---:|---:|---:|---:|---:|---:|---:|---:|"]
for k, s in out["table3_M4096"].items():
    L.append(f"| {k} | {s['cells']} | {s['coarse_not_exact']} | {g(s['coarse_median_pct'],2)} | {g(s['final_median_pct'],2)} | "
             f"{s['removed_median_pct']:.1f} | {s['removed_min_pct']:.1f} | {s['moves_median']:.0f} |")
fm = out["final_median_k512_M4096"]
L += ["", f"Final median at k = 512, M = 4,096: run 4 {fm['run4']:.3f}%, main runs {fm['main_runs']:.3f}% ({fm['main_cells']} cells).", ""]
lt = out["ltr"]
L += [f"Left-to-right sweeps: different SSE in {lt['different_sse']} of {lt['cells']} cells "
      f"({lt['different_discrete']} discrete), lower in {lt['ltr_lower']}, higher in {lt['ltr_higher']}, "
      f"at most {lt['max_abs_pp']:.4f} percentage points.", ""]
def regline(name, q):
    return (f"{name}: {q['cells']} cells, alpha = {q['alpha']:.2f} [{q['alpha_ci'][0]:.2f}, {q['alpha_ci'][1]:.2f}], "
            f"beta = {q['beta']:.2f} [{q['beta_ci'][0]:.2f}, {q['beta_ci'][1]:.2f}], "
            f"alpha + beta = {q['sum']:.2f} [{q['sum_ci'][0]:.2f}, {q['sum_ci'][1]:.2f}], R^2 = {q['R2']:.3f}")
L += ["## Regressions (k >= 64, M = 4,096 to 16,384, continuous; log2 error on log2 k, log2 M, dataset)", "",
      "- " + regline("Coarse DP, N = 2^20", out["coarse_reg_N2^20"]),
      "- " + regline("Coarse DP, N >= 131,072", out["coarse_reg_N>=131072"]),
      "- " + regline("Final error, N >= 131,072", out["final_reg_N>=131072"]),
      "- Final error, beta by N: " + ", ".join(f"{N}: {b:.2f}" for N, b in out["final_reg_beta_by_N"].items()), "",
      "Coarse error per doubling at N = 2^20 (median ratio over datasets): M at k = 512: "
      + ", ".join(f"{a} {v:.2f}" for a, v in out["coarse_per_doubling_M_k512"].items())
      + "; k at M = 4,096: " + ", ".join(f"{a} {v:.2f}" for a, v in out["coarse_per_doubling_k_M4096"].items()), ""]
d = out["discrete"]
L += [f"Discrete (all M): {d['cells']} cells, coarse DP exact in {d['coarse_exact']}, final exact in {d['final_exact']}, "
      f"at most {d['max_sweeps']} sweep(s) and {d['max_moves']} moves.", ""]
a = out["audio_k512_M4096"]
L += [f"Audio, k = 512, M = 4,096: coarse DP {a['coarse_pct']:.3f}%, after Refine {a['final_pct']:.4f}%, Refine removed {a['removed_pct']:.1f}%.", ""]
txt = "\n".join(L)
with open(os.path.join(OUT, "summary.md"), "w") as f:
    f.write(txt)
print(txt)
print(f"wrote {os.path.relpath(OUT, ROOT)}/results.json and summary.md")
