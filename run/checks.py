"""Numerical checks of the technical paper's propositions.

Uses the lex1d Python binding, sympy for the algebraic identities, and brute force on
tiny inputs. Random cases use seed 20261116. The DP-table memory formulas are checked
against results/gold/raw/results.csv.

Dependencies: numpy, sympy, pandas, and the lex1d Python binding (from bash run/setup.sh).

From the repo root:  bash run/checks.sh
Writes out/checks/results.json and out/checks/summary.md.
"""
import itertools, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "results", "gold", "raw", "results.csv")
OUT = os.path.join(ROOT, "out", "checks")
SEED = 20261116
BIG = 1 - 1e-12  # largest allowed tolerance: Refine applies (almost) no gain moves


def _venv_python():
    return os.path.join(ROOT, ".venv", "bin", "python")


def _import_deps():
    """Import numpy, sympy, pandas and lex, re-execing .venv/bin/python if needed."""
    vpy = _venv_python()
    here = os.path.abspath(sys.executable)

    def missing():
        need = []
        for name in ("numpy", "sympy", "pandas", "lex"):
            try:
                __import__(name)
            except ImportError:
                need.append(name)
        return need

    need = missing()
    if need and os.path.isfile(vpy) and os.path.abspath(vpy) != here:
        os.execv(vpy, [vpy, os.path.abspath(__file__)] + sys.argv[1:])
    if need:
        hint = "bash run/setup.sh" if "lex" in need else f"{vpy or 'python3'} -m pip install sympy pandas"
        sys.exit(f"Missing {', '.join(need)}. From the repo root run: {hint}")
    import numpy as np, sympy as sp, pandas as pd, lex
    return np, sp, pd, lex


np, sp, pd, lex = _import_deps()


def sse(x, b):
    return float(sum(((x[b[i]:b[i + 1]] - x[b[i]:b[i + 1]].mean()) ** 2).sum() for i in range(len(b) - 1)))


def identities():
    """Ward merge cost, transfer formula, and concavity of the split-run objective."""
    out = {}
    na, nb, ma, mb, c, n1, n2, m1, m2, g, p, t, q, r, a, b = sp.symbols(
        "n_a n_b m_a m_b c n1 n2 m1 m2 g p t q r a b", positive=True)
    mu = (na * ma + nb * mb) / (na + nb)
    out["ward_identity"] = sp.simplify(na * ma ** 2 + nb * mb ** 2 - (na + nb) * mu ** 2 - na * nb / (na + nb) * (ma - mb) ** 2) == 0
    # transfer: SSE change moving c copies of g from bin1 (n1, m1, includes the piece) to bin2 (n2, m2)
    s1 = n1 * m1
    m1n = (s1 - c * g) / (n1 - c)
    m2n = (n2 * m2 + c * g) / (n2 + c)
    # SSE = sum x^2 - n m^2; sum x^2 unchanged
    dS = (n1 * m1 ** 2 + n2 * m2 ** 2) - ((n1 - c) * m1n ** 2 + (n2 + c) * m2n ** 2)
    out["transfer_identity"] = sp.simplify(dS - (c * n2 / (n2 + c) * (g - m2) ** 2 - c * n1 / (n1 - c) * (g - m1) ** 2)) == 0
    F = p * t / (p + t) * (g - a) ** 2 + q * (r - t) / (q + r - t) * (b - g) ** 2
    out["split_run_second_derivative"] = str(sp.simplify(sp.diff(F, t, 2)))
    return out


def dp_vs_bruteforce(rng):
    """Exact DP == brute force over all cut sets (cuts allowed inside runs of ties)."""
    bad = 0
    n_cases = 0
    for it in range(400):
        n = int(rng.integers(3, 10))
        k = int(rng.integers(2, min(n, 5) + 1))
        x = np.sort(rng.integers(0, 6, n).astype(float)) if it % 2 else np.sort(rng.normal(size=n))
        d = len(np.unique(x))
        kk = min(k, d)
        best = min(sse(x, (0,) + cc + (n,)) for cc in itertools.combinations(range(1, n), kk - 1))
        e = lex.ckmeans_exact(x, kk).sse
        n_cases += 1
        if abs(e - best) > 1e-9 * max(1, best):
            bad += 1
    return dict(cases=n_cases, mismatches=bad)


def random_cases(rng):
    """P2 exactness when D <= M; P3 never worse than Collapse; Refine never raises SSE; Collapse hierarchy."""
    ex_bad = ex_n = p3_bad = ref_bad = hier_bad = below = 0
    n_cases = 0
    out = dict(nomove_moves=0, hier_checked=0, hier_skipped_refined=0)
    for it in range(300):
        n = int(rng.integers(200, 5000))
        k = int(rng.choice([2, 3, 5, 8, 16, 32, 64]))
        if it % 3 == 0:
            x = rng.integers(0, int(rng.integers(5, 400)), n).astype(float)
        elif it % 3 == 1:
            x = rng.lognormal(size=n)
        else:
            x = np.round(rng.normal(size=n), 2)
        M = int(rng.choice([k + 1, 2 * k, 64, 256, 1024]))
        d = len(np.unique(x))
        if k >= d:
            continue
        n_cases += 1
        E = lex.ckmeans_exact(x, k).sse
        hyb = lex.lex_hybrid(x, k, coarse_groups=M)
        hyb0 = lex.lex_hybrid(x, k, coarse_groups=M, tolerance=BIG)
        out["nomove_moves"] += int(hyb0.moves)
        col = lex.lex_plain(x, k, tolerance=BIG)
        out["nomove_moves"] += int(col.moves)
        pl = lex.lex_plain(x, k)
        if hyb.sse < E * (1 - 1e-12):
            below += 1
        if d <= M:
            ex_n += 1
            if not (np.array_equal(hyb.bounds, lex.ckmeans_exact(x, k).bounds) and hyb.sse == E and hyb.moves == 0):
                ex_bad += 1
        if hyb.sse > col.sse * (1 + 1e-12):
            p3_bad += 1
        if hyb.sse > hyb0.sse * (1 + 1e-12) or pl.sse > col.sse * (1 + 1e-12):
            ref_bad += 1
        G = min(M, d)
        if G > k:
            cg = lex.lex_hybrid(x, G, coarse_groups=0, tolerance=BIG)  # Collapse to G groups
            if col.moves or cg.moves:
                out["hier_skipped_refined"] += 1
                continue
            out["hier_checked"] += 1
            if not set(col.bounds.tolist()) <= set(cg.bounds.tolist()):
                hier_bad += 1
                out.setdefault("hier_fail_detail", []).append(
                    dict(it=it, col_moves=int(col.moves), cg_moves=int(cg.moves), k=k, G=G, d=d))
    out["random_cases"] = n_cases
    out["exact_when_D_le_M"] = dict(cases=ex_n, failures=ex_bad)
    out["never_worse_than_collapse_failures"] = p3_bad
    out["refine_raised_sse"] = ref_bad
    out["collapse_hierarchy_failures"] = hier_bad
    out["below_optimum"] = below
    return out


def memory_formulas():
    """Table formulas vs the GOLD harness estimates in results/gold/raw/results.csv."""
    if not os.path.isfile(GOLD):
        sys.exit(f"Missing {os.path.relpath(GOLD, ROOT)}. This file ships in the repo.")
    m = pd.read_csv(GOLD)
    h = m[(m.method == "lex_hybrid") & (m.status == "ok")]
    f = 4 * (h.k - 1) * (np.minimum(h.M, h.D) + 1)
    e = m[(m.method == "ckmeans_exact") & (m.status == "ok")]
    rr = m[(m.method == "Ckmeans.1d.dp") & (m.status == "ok")]
    return {
        "table_formula_matches_harness": dict(rows=len(h), mismatches=int((f != h.dp_table_est_bytes).sum())),
        "exact_table_formula_matches": dict(rows=len(e), mismatches=int((4 * (e.k - 1) * (e.D + 1) != e.dp_table_est_bytes).sum())),
        "R_table_formula_matches": dict(rows=len(rr), mismatches=int((16 * rr.k * rr.N != rr.dp_table_est_bytes).sum())),
    }


def write_summary(out):
    dp, ex = out["dp_vs_bruteforce"], out["exact_when_D_le_M"]
    hy, ck, rr = out["table_formula_matches_harness"], out["exact_table_formula_matches"], out["R_table_formula_matches"]
    rows = [
        ("Prop. 1 (atoms never split)",
         "second derivative of Φ (symbolic); exact DP over atoms vs brute force over all cut sets",
         f"{dp['cases']} cases, {dp['mismatches']} mismatches"),
        ("Lemma 1, Prop. 2 (DP correctness)",
         "exact DP vs brute force",
         f"{dp['cases']} cases, {dp['mismatches']} mismatches"),
        ("Ward cost, transfer formula",
         "symbolic identities",
         "both hold" if out["ward_identity"] and out["transfer_identity"] else "FAILED"),
        ("Prop. 3 (Collapse hierarchical)",
         "bounds of Collapse to k contained in bounds of Collapse to G",
         f"{out['hier_checked']} cases, {out['collapse_hierarchy_failures']} failures"),
        ("Prop. 4 (never worse than Collapse)",
         "SSE of LEX ≤ SSE of Collapse to k",
         f"{out['random_cases']} cases, {out['never_worse_than_collapse_failures']} failures"),
        ("Prop. 5 (exact when D ≤ M)",
         "bounds, SSE and moves vs ckmeans_exact",
         f"{ex['cases']} cases, {ex['failures']} failures"),
        ("Prop. 6 (Refine monotone, terminates)",
         "SSE after Refine ≤ SSE before",
         f"{out['random_cases']} cases, {out['refine_raised_sse']} increases"),
        ("Prop. 9 (memory formulas)",
         "table formulas vs GOLD results/gold/raw/results.csv estimates",
         f"{hy['rows']:,} + {ck['rows']:,} + {rr['rows']:,} configurations, {hy['mismatches'] + ck['mismatches'] + rr['mismatches']} mismatches"),
        ("No result below the optimum",
         "SSE of LEX < exact SSE",
         f"0 of {out['random_cases']} random cases" if out["below_optimum"] == 0 else f"{out['below_optimum']} of {out['random_cases']} random cases"),
    ]
    lines = [
        "# Numerical checks of the propositions",
        "",
        "Script `run/checks.py`, lex1d Python binding, seed 20261116. Random cases: N = 200 to 5,000, "
        "k = 2 to 64, integer, lognormal and rounded-normal data, M from k + 1 to 1,024; brute-force "
        "cases: N = 3 to 9. The memory-formula check uses GOLD `results/gold/raw/results.csv` "
        "(the paper's earlier 32 + 32 + 31 count was from a smaller pre-GOLD harness; the formulas are the same).",
        "",
        "Table 11 also reports 112 of 112 discrete synthetic cells exact, 3,096 of 3,096 LEX fits of "
        "Section 6 finished with no SSE increase and none below the optimum, and Lemma 2 on 30 GOLD "
        "cells. Those figures come from the GOLD benchmark, not from this script.",
        "",
        "| Statement | Check | Result |",
        "|---|---|---|",
    ]
    for a, b, c in rows:
        lines.append(f"| {a} | {b} | {c} |")
    lines += ["", "Every statement checked by this script passed." if all([
        out["ward_identity"], out["transfer_identity"], dp["mismatches"] == 0,
        out["collapse_hierarchy_failures"] == 0, out["never_worse_than_collapse_failures"] == 0,
        ex["failures"] == 0, out["refine_raised_sse"] == 0, out["below_optimum"] == 0,
        hy["mismatches"] == 0, ck["mismatches"] == 0, rr["mismatches"] == 0,
    ]) else "", ""]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "summary.md")
    open(path, "w").write("\n".join(lines))
    return path


def main():
    rng = np.random.default_rng(SEED)
    out = identities()
    out["dp_vs_bruteforce"] = dp_vs_bruteforce(rng)
    out.update(random_cases(rng))
    out.update(memory_formulas())
    os.makedirs(OUT, exist_ok=True)
    json_path = os.path.join(OUT, "results.json")
    json.dump(out, open(json_path, "w"), indent=1, default=str)
    write_summary(out)
    rel = os.path.relpath(OUT, ROOT)
    print(json.dumps(out, indent=1, default=str))
    print(f"wrote {rel}/results.json and {rel}/summary.md")


if __name__ == "__main__":
    main()
