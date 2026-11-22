#!/usr/bin/env python3
"""Regenerate Figures 1-5 of the technical paper.

From the repository root:

    python3 paper/technical/figs/make_figs.py

Reads results/gold/raw/results.csv (main grid) and results/gold/refine/results.csv
(coarse-DP REE medians). Writes the PNGs next to this script, with the filenames
the technical paper's LaTeX includes.
"""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = ROOT / "results" / "gold" / "raw" / "results.csv"
REFINE = ROOT / "results" / "gold" / "refine" / "results.csv"

C = {"lex": "#1f5fbf", "exact": "#000000", "plain": "#e07b00", "coarse": "#2e8b3a"}


def fig1_example():
    """Figure 1: LEX on ten values (k = 3, M = 5). SSEs are exact fractions."""
    x = [9, 12, 14, 17, 19, 22, 26, 27, 32, 36]

    def sseF(parts):
        t = F(0)
        for b in parts:
            m = F(sum(b), len(b))
            t += sum((v - m) ** 2 for v in b)
        return t

    def split(cuts):
        c = [0] + cuts + [len(x)]
        return [x[c[i]:c[i + 1]] for i in range(len(c) - 1)]

    best = min(sseF(split([a, b])) for a, b in combinations(range(1, 10), 2))
    rows = [
        ("Collapse to M = 5 groups", split([3, 5, 6, 8]), "groups"),
        ("Exact DP on the groups", split([5, 8]), "bins"),
        ("Refine: 19 moves to the middle bin", split([4, 8]), "bins"),
        ("Without the DP: Collapse to 3 bins, then Refine", split([3, 6]), "bins"),
    ]
    S = [sseF(r[1]) for r in rows]
    assert best == 83 and S[2] == 83 and S[1] == F(424, 5) and S[3] == F(1081, 12) and S[0] == F(139, 6)
    labels = [
        "",
        f"3-bin SSE {float(S[1]):.2f}",
        f"3-bin SSE {float(S[2]):.2f} (optimal)",
        f"3-bin SSE {float(S[3]):.2f}\n(8.5% above the optimum)",
    ]
    rowcol = ["#888888", "#2e8b3a", "#1f5fbf", "#e07b00"]
    plt.rcParams.update({"font.size": 10})
    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    for r, (name, parts, kind) in enumerate(rows):
        y = -r * 1.0
        for j, b in enumerate(parts):
            c = rowcol[r]
            ax.add_patch(plt.Rectangle(
                (b[0] - 0.9, y - 0.22), b[-1] - b[0] + 1.8, 0.44,
                facecolor=c, alpha=0.10 + 0.12 * (j % 2), edgecolor=c, lw=1.2,
            ))
            ax.scatter(b, [y] * len(b), s=28, color=c, zorder=3)
        ax.text(7.2, y + 0.30, name, fontsize=10, ha="left", color="k")
        ax.text(38.2, y, labels[r], fontsize=9, va="center", color=rowcol[r])
    ax.plot([18, 18], [0.24, -0.26], color="k", ls=":", lw=1.6, zorder=4)
    ax.text(18, -0.40, "optimal cut 17 | 19, lost inside a group", color="k", fontsize=8.5, ha="center", va="center")
    ax.annotate("", xy=(19, -1.50), xytext=(19, -1.18), arrowprops=dict(arrowstyle="->", color="k", lw=1.2))
    ax.text(19.6, -1.34, "net SSE change: $-1.8$", fontsize=8.5, va="center")
    for v in x:
        ax.text(v, -3.62, str(v), ha="center", fontsize=9)
    ax.set_xlim(7, 48)
    ax.set_ylim(-3.85, 0.65)
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(HERE / "bot_v23_fig1_example.png", dpi=200)
    plt.close(fig)


def figs_2_to_5():
    """Figures 2-5 from the GOLD raw grid and run-4 coarse-DP medians."""
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 10,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 220,
    })
    r = pd.read_csv(RAW)
    assert (r.status == "ok").all(), f"unexpected statuses in {RAW}"
    refine = pd.read_csv(REFINE)
    assert (refine.status == "ok").all(), f"unexpected statuses in {REFINE}"

    key = ["dataset", "slice", "N", "k"]
    m = r[(r.section == "main") & (r.D == r.N)]
    ex = m[m.method == "ckmeans_exact"].set_index(key)
    R = m[m.method == "Ckmeans.1d.dp"].set_index(key)
    x = m[m.method.isin(["lex_hybrid", "lex_plain"])].set_index(key).copy()
    x["e"] = (x.sse - ex.sse.reindex(x.index)) / ex.sse.reindex(x.index) * 100
    x["tR"] = R.fit_s.reindex(x.index)
    x["su"] = x.tR / x.fit_s
    x = x.reset_index()
    H = x[(x.method == "lex_hybrid") & (x.M == 4096)]
    P = x[x.method == "lex_plain"]
    ks = sorted(H.k.unique())
    assert len(H) == 560 and len(P) == 560

    # Median coarse-DP REE (%) over continuous cells with a positive coarse gap,
    # M = 4,096, all N. Same definition as run/run4_numbers.py Table 3.
    cont = refine[refine.dataset.str.endswith("continuous") & (refine.M == 4096)]
    cm = pd.Series(
        {k: float(cont[(cont.k == k) & (cont.coarse_gap_pct > 0)].coarse_gap_pct.median()) for k in ks},
    )

    def label(ax, xv, yv, txt, col, dy=1.0, ha="left"):
        ax.text(xv, yv * dy, txt, color=col, fontsize=9, ha=ha, va="center")

    def logx2(ax, ticks, lab=None):
        ax.set_xscale("log", base=2)
        ax.set_xticks(ticks)
        ax.set_xticklabels(lab or [str(t) for t in ticks])
        ax.minorticks_off()

    # Figure 2: accuracy and what each stage contributes
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    hm = H.groupby("k").e.median()
    hx = H.groupby("k").e.max()
    pm = P.groupby("k").e.median()
    px = P.groupby("k").e.max()
    ax.plot(ks, px.values, "--", color=C["plain"], lw=1.3)
    ax.plot(ks, pm.replace(0, np.nan).values, "-", color=C["plain"], lw=1.8)
    ax.plot(ks, cm.values, "-", color=C["coarse"], lw=1.8)
    ax.plot(ks, hx.values, "--", color=C["lex"], lw=1.3)
    ax.plot(ks, hm.replace(0, np.nan).values, "-", color=C["lex"], lw=1.8)
    ax.set_yscale("log")
    logx2(ax, ks)
    ax.set_xlim(3.3, 1500)
    ax.set_ylim(1e-7, 60)
    label(ax, 560, pm[512], "no DP", C["plain"])
    label(ax, 560, cm[512], "coarse DP,\nbefore Refine", C["coarse"], dy=0.9)
    label(ax, 560, hm[512], "LEX", C["lex"])
    ax.set_xlabel("k (bins)")
    ax.set_ylabel("REE (%)")
    ax.grid(alpha=.25, which="major")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "bot_v23_fig2_accuracy.png")
    plt.close(fig)

    # Figure 3: time and memory, one column per k
    gg = r[(r.section == "main") & (r.dataset == "gaussian_continuous")]
    K3 = [8, 64, 512]
    fig, axs = plt.subplots(2, 3, figsize=(7.4, 4.9), sharex=True)
    NT = [2 ** 14, 2 ** 16, 2 ** 18, 2 ** 20]
    NL = ["$2^{14}$", "$2^{16}$", "$2^{18}$", "$2^{20}$"]
    for j, k_ in enumerate(K3):
        a = H[H.k == k_].groupby("N").fit_s.median()
        b = H[H.k == k_].groupby("N").tR.median()
        L_ = gg[(gg.method == "lex_hybrid") & (gg.M == 4096) & (gg.k == k_)].sort_values("N")
        C_ = gg[(gg.method == "Ckmeans.1d.dp") & (gg.k == k_)].sort_values("N")
        t, mm = axs[0, j], axs[1, j]
        t.plot(a.index, a.values, "-o", ms=2.5, color=C["lex"], lw=1.6)
        t.plot(b.index, b.values, "-s", ms=2.5, color=C["exact"], lw=1.4)
        mm.plot(L_.N, L_.peak_rss_bytes / 1e9, "-o", ms=2.5, color=C["lex"], lw=1.6)
        mm.plot(C_.N, C_.peak_rss_bytes / 1e9, "-s", ms=2.5, color=C["exact"], lw=1.4)
        t.set_title(f"k = {k_}")
        for ax_ in (t, mm):
            ax_.set_yscale("log")
            logx2(ax_, NT, NL)
            ax_.grid(alpha=.25)
            for sp in ["top", "right"]:
                ax_.spines[sp].set_visible(False)
        t.set_ylim(1e-3, 60)
        mm.set_ylim(2e-3, 20)
        if j == 2:
            label(t, 2 ** 20 * 1.15, b.values[-1], "Ckmeans\n.1d.dp", C["exact"])
            label(t, 2 ** 20 * 1.15, a.values[-1], "LEX", C["lex"], dy=0.6)
            label(mm, 2 ** 20 * 1.15, C_.peak_rss_bytes.values[-1] / 1e9, "Ckmeans\n.1d.dp", C["exact"])
            label(mm, 2 ** 20 * 1.15, L_.peak_rss_bytes.values[-1] / 1e9, "LEX", C["lex"])
        mm.set_xlabel("N")
        t.set_xlim(2 ** 13.5, 2 ** 22.3)
    axs[0, 0].set_ylabel("fit time (s)")
    axs[1, 0].set_ylabel("peak memory (GB)")
    fig.tight_layout()
    fig.savefig(HERE / "bot_v23_fig3_time_memory.png")
    plt.close(fig)

    # Figure 4: the M tradeoff at N = 2^20, one panel per k, plus time at k = 512
    b3 = r[(r.section == "main") & (r.D == r.N) & (r.method == "lex_hybrid") & (r.N == 1048576)].copy()
    e3 = ex.sse.reset_index()
    b3 = b3.merge(e3, on=key, suffixes=("", "_ex"))
    b3["e"] = (b3.sse - b3.sse_ex) / b3.sse_ex * 100
    Ms = sorted(b3.M.unique())
    ML = ["1K", "2K", "4K", "8K", "16K"]
    fig, axs = plt.subplots(1, 4, figsize=(8.6, 2.9))
    for i, k_ in enumerate([64, 256, 512]):
        d = b3[b3.k == k_]
        ax = axs[i]
        ax.plot(Ms, d.groupby("M").e.median().values, "-o", ms=3, color=C["lex"], lw=1.6)
        ax.plot(Ms, d.groupby("M").e.max().values, "--", color=C["lex"], lw=1.2)
        ax.set_yscale("log")
        ax.set_title(f"REE (%), k = {k_}")
        ax.set_ylim(2e-5, 2)
    for ax in axs[1:3]:
        ax.set_yticklabels([])
    d = b3[b3.k == 512]
    axs[3].plot(Ms, d.groupby("M").fit_s.median().values, "-o", ms=3, color=C["lex"], lw=1.6)
    axs[3].set_ylim(0, 0.5)
    axs[3].set_title("fit time (s), k = 512")
    label(axs[0], Ms[0] * 1.1, d[d.M == Ms[0]].e.median() * 0 + b3[(b3.k == 64) & (b3.M == Ms[0])].e.max() * 1.8, "maximum", C["lex"])
    label(axs[0], Ms[1] * 0.9, b3[(b3.k == 64) & (b3.M == Ms[1])].e.median() * 0.22, "median", C["lex"])
    for ax in axs:
        logx2(ax, Ms, ML)
        ax.set_xlabel("M")
        ax.grid(alpha=.25)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "bot_v23_fig4_msweep.png")
    plt.close(fig)

    # Figure 5 (appendix): speedup by k
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    cmap = plt.get_cmap("Blues")
    for i, k_ in enumerate(ks):
        s = H[H.k == k_].groupby("N").su.median()
        col = cmap(0.45 + 0.55 * i / (len(ks) - 1))
        ax.plot(s.index, s.values, "-o", ms=2.5, lw=1.5, color=col)
        label(ax, 2 ** 20 * 1.12, s.values[-1], f"k = {k_}", col)
    ax.axhline(1, color="k", lw=.8, ls=":")
    ax.set_yscale("log")
    logx2(ax, NT, NL)
    ax.set_xlim(2 ** 13.7, 2 ** 21.4)
    ax.set_xlabel("N")
    ax.set_ylabel("speedup over Ckmeans.1d.dp")
    ax.grid(alpha=.25)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "bot_v23_fig5_speedup_all.png")
    plt.close(fig)


def main():
    if not RAW.is_file():
        raise SystemExit(f"missing {RAW} (run this from a checkout of lex1d-paper)")
    if not REFINE.is_file():
        raise SystemExit(f"missing {REFINE} (run this from a checkout of lex1d-paper)")
    fig1_example()
    figs_2_to_5()
    names = [
        "bot_v23_fig1_example.png",
        "bot_v23_fig2_accuracy.png",
        "bot_v23_fig3_time_memory.png",
        "bot_v23_fig4_msweep.png",
        "bot_v23_fig5_speedup_all.png",
    ]
    for name in names:
        print(HERE.joinpath(name).relative_to(ROOT))


if __name__ == "__main__":
    main()
