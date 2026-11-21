"""Checks of the worked examples and numbers in the expository paper (its Appendix A, Table 10).

Each row of Table 10 is one section below. Every number the paper quotes for that row is
recomputed here and compared with the value as printed. Exact fractions are used for the
small hand examples; random cases use fixed seeds.

Dependencies: numpy and the lex1d Python binding (from bash run/setup.sh).

From the repo root:  bash run/expo_checks.sh
Writes out/expo_checks/results.json and out/expo_checks/summary.md. Exits 1 if any check fails.
"""
import itertools, json, math, os, sys, time
from collections import Counter
from fractions import Fraction as Fr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "expo_checks")
BIG = 1 - 1e-12  # largest allowed tolerance: Refine applies (almost) no gain moves

try:
    import numpy as np
    import lex
except ImportError as e:
    sys.exit(f"{e}. Run from the repo root: bash run/expo_checks.sh (needs bash run/setup.sh first)")

T0 = time.time()
ROWS = []      # (row number, title)
CHECKS = []    # dicts: row, what, got, paper, ok


def row(title):
    ROWS.append(title)


def check(what, got, paper, ok=None):
    """Record one check. By default the value must equal the paper's value (as printed, or as a number)."""
    if ok is None:
        ok = got == paper or str(got) == str(paper)
    CHECKS.append(dict(row=len(ROWS), what=what, got=str(got), paper=str(paper), ok=bool(ok)))


def f2(v):
    return f"{float(v):.2f}"


def sse(vals):
    v = [Fr(x) for x in vals]
    m = sum(v) / len(v)
    return sum((x - m) ** 2 for x in v)


def sse_cuts(vals, cuts):
    b = [0] + list(cuts) + [len(vals)]
    return sum(sse(vals[b[j]:b[j + 1]]) for j in range(len(b) - 1))


def all_cuts(vals, k):
    """Every contiguous k-partition: list of (SSE, cuts), sorted by SSE."""
    return sorted((sse_cuts(vals, c), c) for c in itertools.combinations(range(1, len(vals)), k - 1))


def ward(a, b):
    na, nb = len(a), len(b)
    return Fr(na * nb, na + nb) * (Fr(sum(a), na) - Fr(sum(b), nb)) ** 2


def collapse(vals, G):
    """Adjacent Ward merging down to G groups; exact ties go to the leftmost pair. Returns groups, merge log."""
    groups = [[v] for v in vals]
    log = []
    while len(groups) > G:
        costs = [ward(groups[i], groups[i + 1]) for i in range(len(groups) - 1)]
        i = costs.index(min(costs))
        log.append((groups[i][:], groups[i + 1][:], costs[i]))
        groups[i:i + 2] = [groups[i] + groups[i + 1]]
    return groups, log


def coarse_dp(groups, k):
    """Best k-partition that keeps the groups whole (brute force over group bounds): (true SSE, bins)."""
    best = None
    for c in itertools.combinations(range(1, len(groups)), k - 1):
        b = (0,) + c + (len(groups),)
        bins = [sum(groups[b[j]:b[j + 1]], []) for j in range(k)]
        t = sum(sse(p) for p in bins)
        if best is None or t < best[0]:
            best = (t, bins)
    return best


def bounds_of(groups):
    out, s = [], 0
    for g in groups[:-1]:
        s += len(g)
        out.append(s)
    return out


def eight_moves(units, b):
    """The eight Refine moves on the single window of a 3-bin partition of 'units' (lists of pieces).
    b = [0, b1, b2, n] in piece indices. Returns {(left op, right op): (delta, new b)}."""
    def tot(bb):
        return sum(sse(sum(units[bb[j]:bb[j + 1]], [])) for j in range(3))
    cur = tot(b)
    res = {}
    for lo, ro in itertools.product(["stay", "give", "take"], repeat=2):
        if lo == ro == "stay":
            continue
        nb = b[:]
        nb[1] += {"stay": 0, "give": 1, "take": -1}[lo]
        nb[2] += {"stay": 0, "give": -1, "take": 1}[ro]
        if all(nb[j] < nb[j + 1] for j in range(3)):
            res[(lo, ro)] = (tot(nb) - cur, nb)
    return res


# ---------------------------------------------------------------- 1
row("Hand DP example (Section 3.2; also Sections 1.2, 2.4, Exercise 3)")
x6 = [1, 2, 4, 7, 8, 15]
N = 6
check("pairing SSE (Section 1.2)", float(sse([1, 2]) + sse([4, 7]) + sse([8, 15])), 29.5)
check("grouping SSE = 31/6", sse([1, 2, 4]) + sse([7, 8]) + sse([15]), "31/6")
check("31/6 is less than a fifth of 29.5", Fr(31, 6) < Fr(59, 2) / 5, True)
bf = all_cuts(x6, 3)
check("number of 3-partitions", len(bf), 10)
check("brute-force optimum", bf[0][0], "31/6")
check("brute-force optimal cuts", bf[0][1], (3, 5))
check("worst partition SSE", bf[-1][0], 65)
S = [sum(x6[:j]) for j in range(N + 1)]
Q = [sum(v * v for v in x6[:j]) for j in range(N + 1)]
check("prefix sums S", tuple(S), (0, 1, 3, 7, 14, 22, 37))
check("prefix sums Q", tuple(Q), (0, 1, 5, 21, 70, 134, 359))
c = lambda i, j: Fr(Q[j] - Q[i]) - Fr((S[j] - S[i]) ** 2, j - i)
check("c(3, 6) from (9)", c(3, 6), 38)
table3 = {0: "0 0.50 4.67 21.00 37.20 130.83", 1: "0 2.00 12.67 22.75 98.80", 2: "0 4.50 8.67 65.00",
          3: "0 0.50 38.00", 4: "0 24.50", 5: "0"}
for i, want in table3.items():
    got = " ".join("0" if c(i, j) == 0 else f2(c(i, j)) for j in range(i + 1, N + 1))
    check(f"Table 3 row i = {i}", got, want)
F = {(1, j): c(0, j) for j in range(1, N + 1)}
T = {}
for b in (2, 3):
    for j in range(b, N + 1):
        cand = [(F[(b - 1, i)] + c(i, j), i) for i in range(b - 1, j)]
        m = min(v for v, i in cand)
        F[(b, j)] = m
        T[(b, j)] = max(i for v, i in cand if v == m)  # largest i on ties
table4 = {1: "0 0.50 4.67 21.00 37.20 130.83", 2: "0 [1] | 0.50 [2] | 4.67 [3] | 5.17 [3] | 37.20 [5]",
          3: "0 [2] | 0.50 [3] | 1.00 [3] | 5.17 [5]"}
check("Table 4 row 1", " ".join("0" if F[(1, j)] == 0 else f2(F[(1, j)]) for j in range(1, N + 1)), table4[1])
for b in (2, 3):
    got = " | ".join(("0" if F[(b, j)] == 0 else f2(F[(b, j)])) + f" [{T[(b, j)]}]" for j in range(b, N + 1))
    check(f"Table 4 row {b}", got, table4[b])
check("F(2, 5) candidates", " ".join(f2(F[(1, i)] + c(i, 5)) for i in range(1, 5)), "22.75 9.17 5.17 21.00")
check("F(2, 5) = 31/6, T = 3", (F[(2, 5)], T[(2, 5)]), (Fr(31, 6), 3))
check("F(3, 6) candidates", " ".join(f2(F[(2, i)] + c(i, 6)).rstrip("0").rstrip(".") for i in range(2, 6)), "65 38.5 29.17 5.17")
check("F(3, 6) = 31/6, T = 5", (F[(3, 6)], T[(3, 6)]), (Fr(31, 6), 5))
check("backtracking cuts", (T[(2, T[(3, 6)])], T[(3, 6)]), (3, 5))
check("Exercise 3 candidates", " ".join(f2(F[(1, i)] + c(i, 6)) for i in range(1, 6)), "98.80 65.50 42.67 45.50 37.20")
check("F(2, 6) = 37.20 with T(2, 6) = 5 (two-bin optimum)", (f2(F[(2, 6)]), T[(2, 6)]), ("37.20", 5))
check("two-bin brute force agrees", (f2(all_cuts(x6, 2)[0][0]), all_cuts(x6, 2)[0][1]), ("37.20", (5,)))
e = lex.ckmeans_exact(np.array(x6, float), 3)
check("ckmeans_exact bounds", list(map(int, e.bounds)), [0, 3, 5, 6])
check("ckmeans_exact SSE = 31/6", abs(e.sse - 31 / 6) < 1e-12, True)

# ---------------------------------------------------------------- 2
row("Contiguity and non-nesting (Sections 2.2, 2.6)")
check("interleaved bins {1,2,8}, {4,9,10}", f2(sse([1, 2, 8]) + sse([4, 9, 10])), "49.33")
check("contiguous runs {1,2,4}, {8,9,10}", f2(sse([1, 2, 4]) + sse([8, 9, 10])), "6.67")
check("partitions at N = 1,000, k = 10 exceed 10^21", math.comb(999, 9) > 10 ** 21, True)
z = [0, 2, 3, 5]
p2, p3 = all_cuts(z, 2), all_cuts(z, 3)
check("2-bin optimum {0,2}|{3,5}, SSE 4, unique", (p2[0][1], p2[0][0], p2[1][0] > p2[0][0]), ((2,), 4, True))
check("3-bin optimum {0}|{2,3}|{5}, SSE 0.5, unique", (p3[0][1], str(p3[0][0]), p3[1][0] > p3[0][0]), ((1, 3), "1/2", True))
best_add = min(s for s, cc in p3 if 2 in cc)
check("adding a cut to the 2-bin optimum gives at best SSE 2", best_add, 2)
check("which is four times the optimum", best_add / p3[0][0], 4)

# ---------------------------------------------------------------- 3 and 4 share one random stream
rng = np.random.default_rng(20261117)
row("Quadrangle inequality (Section 5.1)")
worst, count = 0.0, 0
for it in range(4000):
    n = int(rng.integers(4, 40))
    v = np.sort(rng.choice([rng.normal(size=n), rng.lognormal(size=n), rng.integers(0, 5, n).astype(float)]))
    P = np.concatenate([[0], np.cumsum(v)])
    P2 = np.concatenate([[0], np.cumsum(v * v)])
    cc = lambda i, j: 0.0 if j <= i else P2[j] - P2[i] - (P[j] - P[i]) ** 2 / (j - i)
    for _ in range(20):
        a, b, cq, d = sorted(rng.integers(0, n + 1, 4))
        slack = cc(a, d) + cc(b, cq) - cc(a, cq) - cc(b, d)
        count += 1
        worst = min(worst, slack / (1 + abs(cc(a, d))))
check("random quadruples (normal, lognormal, integer)", f"{count:,}", "80,000")
check("min relative slack (rounding only)", f"{worst:.0e}", "-2e-16")

row("Monotone split (Section 5.2)")
mono_rows, mono_bad = 0, 0
for it in range(300):
    n = int(rng.integers(5, 60))
    v = np.sort(rng.normal(size=n))
    P = np.concatenate([[0], np.cumsum(v)])
    P2 = np.concatenate([[0], np.cumsum(v * v)])
    cc = lambda i, j: P2[j] - P2[i] - (P[j] - P[i]) ** 2 / (j - i)
    prev = [cc(0, j) if j > 0 else 0 for j in range(n + 1)]
    for b in range(2, min(6, n)):
        opts = []
        for j in range(b, n + 1):
            vals = [prev[i] + cc(i, j) for i in range(b - 1, j)]
            m = min(vals)
            opts.append(max(i for i, vv in zip(range(b - 1, j), vals) if vv <= m + 1e-12 * (1 + abs(m))))
        mono_rows += 1
        mono_bad += int(any(opts[t + 1] < opts[t] for t in range(len(opts) - 1)))
        prev = [0] * b + [min(prev[i] + cc(i, j) for i in range(b - 1, j)) for j in range(b, n + 1)]
check("DP rows of random normal data", f"{mono_rows:,}", "1,197")
check("violations", mono_bad, 0)

# ---------------------------------------------------------------- 5
row("SMAWK overview (Section 5.4)")
INF = float("inf")


def smawk(rows, cols, A):
    """Row minima of a totally monotone matrix: {row: column}, leftmost column on ties."""
    if not rows:
        return {}
    S_ = []
    for col in cols:  # REDUCE
        while S_ and A(rows[len(S_) - 1], S_[-1]) > A(rows[len(S_) - 1], col):
            S_.pop()
        if len(S_) < len(rows):
            S_.append(col)
    ans = smawk(rows[1::2], S_, A)  # every other row
    pos = {col: i for i, col in enumerate(S_)}
    start = 0
    for t in range(0, len(rows), 2):  # INTERPOLATE
        r = rows[t]
        stop = pos[ans[rows[t + 1]]] if t + 1 < len(rows) else len(S_) - 1
        best = None
        for i in range(start, stop + 1):
            if best is None or A(r, S_[i]) < A(r, best):
                best = S_[i]
        ans[r] = best
        start = stop
    return ans


rng5 = np.random.default_rng(1)
sm_rows, sm_bad = 0, 0
for it in range(400):
    n = int(rng5.integers(3, 80))
    v = np.sort(rng5.choice([rng5.normal(size=n), rng5.lognormal(size=n), rng5.integers(0, 6, n).astype(float)]))
    P = np.concatenate([[0], np.cumsum(v)])
    P2 = np.concatenate([[0], np.cumsum(v * v)])
    cc = lambda i, j: P2[j] - P2[i] - (P[j] - P[i]) ** 2 / (j - i)
    prev = [cc(0, j) if j > 0 else 0.0 for j in range(n + 1)]
    for b in range(2, min(8, n) + 1):
        A = lambda j, i: prev[i] + cc(i, j) if b - 1 <= i < j else INF
        rows_, cols_ = list(range(b, n + 1)), list(range(b - 1, n))
        ans = smawk(rows_, cols_, A)
        for j in rows_:
            m = min(A(j, i) for i in cols_)
            sm_rows += 1
            sm_bad += int(A(j, ans[j]) > m + 1e-9 * (1 + abs(m)))
        prev = [INF] * b + [A(j, ans[j]) for j in rows_]
check("DP rows checked against brute-force row minima", f"{sm_rows:,}", "102,171")
check("errors", sm_bad, 0)

# ---------------------------------------------------------------- 6
row("Ten-value LEX trace (Section 4, Figure 1)")
x10 = [9, 12, 14, 17, 19, 22, 26, 27, 32, 36]
X10 = np.array(x10, float)
opt10 = all_cuts(x10, 3)
check("cut pairs searched", len(opt10), 36)
check("optimum {9..17}|{19..27}|{32,36}, SSE 83", (opt10[0][1], opt10[0][0]), ((4, 8), 83))
check("initial pair costs", " ".join(str(float(sse(p))).rstrip("0").rstrip(".") for p in zip(x10, x10[1:])),
      "4.5 2 4.5 2 4.5 8 0.5 12.5 8")
g5, log = collapse(x10, 5)
check("five merges and costs",
      "; ".join(f"{a}+{b} {f2(cst)}" for a, b, cst in log),
      "[26]+[27] 0.50; [12]+[14] 2.00; [17]+[19] 2.00; [32]+[36] 8.00; [9]+[12, 14] 10.67")
check("tie 12+14 vs 17+19 (both 2)", ward([12], [14]) == ward([17], [19]) == 2, True)
check("tie 9+{12,14} vs {17,19}+22 (both 32/3)", ward([9], [12, 14]) == ward([17, 19], [22]) == Fr(32, 3), True)
check("five groups", g5, [[9, 12, 14], [17, 19], [22], [26, 27], [32, 36]])
check("lex1d Collapse to 5 groups: same bounds", list(map(int, lex.lex_hybrid(X10, 5, coarse_groups=0, tolerance=BIG).bounds)),
      [0] + bounds_of(g5) + [10])
W = sum(sse(g) for g in g5)
check("within-group sums", " ".join(f2(sse(g)) for g in g5), "12.67 2.00 0.00 0.50 8.00")
check("W = 139/6", W, "139/6")
table5 = {(1, 2): ("110.70", "133.87"), (1, 3): ("66.92", "90.08"), (1, 4): ("72.30", "95.47"),
          (2, 3): ("104.38", "127.55"), (2, 4): ("61.63", "84.80"), (3, 4): ("98.83", "122.00")}
for cuts, (dpc, tru) in table5.items():
    b = (0,) + cuts + (5,)
    t = sum(sse(sum(g5[b[j]:b[j + 1]], [])) for j in range(3))
    check(f"Table 5 cuts after groups {cuts}", (f2(t - W), f2(t)), (dpc, tru))
cm, dpbins = coarse_dp(g5, 3)
check("DP picks cuts after groups 2 and 4", dpbins, [[9, 12, 14, 17, 19], [22, 26, 27], [32, 36]])
check("B* = 1849/30", cm - W, "1849/30")
check("C_M = 84.80, 2.2% above optimal", (f2(cm), f"{100 * float(cm / 83 - 1):.1f}"), ("84.80", "2.2"))
check("Step 3: removing 19 saves 28.8", float(Fr(4, 5) * (19 - 13) ** 2), 28.8)
check("Step 3: adding 19 costs 27.0", f"{float(Fr(3, 4) * (19 - 25) ** 2):.1f}", "27.0")
check("Step 3: removal saving equals Ward reversal", sse([9, 12, 14, 17, 19]) - sse([9, 12, 14, 17]), Fr(144, 5))
units = [[v] for v in x10]
mv = eight_moves(units, [0, 5, 8, 10])
improving = {m: d for m, (d, nb) in mv.items() if d < 0}
check("eight moves from the DP partition", len(mv), 8)
check("only improving move: (take, stay), delta = -1.8", (list(improving), float(list(improving.values())[0])),
      ([("take", "stay")], -1.8))
mv2 = eight_moves(units, [0, 4, 8, 10])
check("second sweep: no improving move", min(d for d, nb in mv2.values()) >= 0, True)
mv3 = eight_moves(units, [0, 3, 6, 10])
ds = sorted(float(d) for d, nb in mv3.values())
check("from Collapse-to-3: all 8 moves raise SSE, +9.25 to +63.12", (len(ds), f"{ds[0]:+.2f}", f"{ds[-1]:+.2f}"),
      (8, "+9.25", "+63.12"))
g3, log3 = collapse(x10, 3)
check("Collapse-to-3 SSE 90.08, 8.5% above", (f2(sum(sse(g) for g in g3)), f"{100 * float(sum(sse(g) for g in g3) / 83 - 1):.1f}"),
      ("90.08", "8.5"))
h = lex.lex_hybrid(X10, 3, coarse_groups=5)
h0 = lex.lex_hybrid(X10, 3, coarse_groups=5, tolerance=BIG)
pl = lex.lex_plain(X10, 3)
ex = lex.ckmeans_exact(X10, 3)
check("lex_hybrid before Refine: 84.80 at bounds 0,5,8,10", (f2(h0.sse), list(map(int, h0.bounds))), ("84.80", [0, 5, 8, 10]))
check("lex_hybrid: 83.00, one move, two sweeps", (f2(h.sse), list(map(int, h.bounds)), int(h.moves), int(h.sweeps)),
      ("83.00", [0, 4, 8, 10], 1, 2))
check("lex_plain: 90.08, no move", (f2(pl.sse), list(map(int, pl.bounds)), int(pl.moves)), ("90.08", [0, 3, 6, 10], 0))
check("ckmeans_exact: 83.00", (f2(ex.sse), list(map(int, ex.bounds))), ("83.00", [0, 4, 8, 10]))

# ---------------------------------------------------------------- 7
row("Coarse DP for every M (Section 4)")
got = []
for M in range(3, 9):
    gm, _ = collapse(x10, M)
    t, _ = coarse_dp(gm, 3)
    got.append(f"M={M}:{f2(t)}")
    lx = lex.lex_hybrid(X10, 3, coarse_groups=M, tolerance=BIG)
    check(f"lex1d coarse DP agrees at M = {M}", f2(lx.sse), f2(t))
check("coarse SSE by M", " ".join(got), "M=3:90.08 M=4:90.08 M=5:84.80 M=6:84.80 M=7:84.80 M=8:83.00")
six = []
for M in (3, 4, 5):
    gm, _ = collapse(x6, M)
    six.append(coarse_dp(gm, 3)[0] == Fr(31, 6))
check("six values: coarse DP exact for M in {3, 4, 5}", six, [True, True, True])

# ---------------------------------------------------------------- 8
row("Pipeline toy example (Figure 2)")
vals = [9, 9, 12, 14, 14, 14, 17, 19, 22, 22, 26, 27, 32, 36, 36]
cnt = Counter(vals)
atoms = [[v] * cnt[v] for v in sorted(cnt)]  # one piece per atom
check("N = 15, D = 10", (len(vals), len(atoms)), (15, 10))
groups = [a[:] for a in atoms]
while len(groups) > 5:
    costs = [ward(groups[i], groups[i + 1]) for i in range(len(groups) - 1)]
    i = costs.index(min(costs))
    groups[i:i + 2] = [groups[i] + groups[i + 1]]
check("G = max(k, min(M, D)) = 5", max(3, min(5, len(atoms))), len(groups))
check("Collapse groups include {17, 19, 22}", [sorted(set(g)) for g in groups].count([17, 19, 22]), 1)
t, dpb = coarse_dp(groups, 3)
units_b = [0]
for p in dpb:
    units_b.append(units_b[-1] + len(set(p)))
mvs = eight_moves(atoms, units_b)
best = min(mvs.items(), key=lambda kv: (kv[1][0], [-u for u in kv[1][1]]))
(lo_ro, (d, nb)) = best
moved = [a[0] for a in atoms[min(units_b[1], nb[1]):max(units_b[1], nb[1])]]
check("Refine's move (give, stay) gives atom 17 to the left bin", (lo_ro, moved, d < 0), (("give", "stay"), [17], True))
after = eight_moves(atoms, nb)
check("no further improving move", min(dd for dd, _ in after.values()) >= 0, True)
fin = sum(sse(sum(atoms[nb[j]:nb[j + 1]], [])) for j in range(3))
opt = min(sum(sse(sum(atoms[b[j]:b[j + 1]], [])) for j in range(3))
          for cc in itertools.combinations(range(1, 10), 2) for b in [(0,) + cc + (10,)])
check("final partition is the brute-force optimum", fin == opt, True)
fx = lex.lex_hybrid(np.array(vals, float), 3, coarse_groups=5)
check("lex1d lex_hybrid reaches the same SSE", abs(fx.sse - float(opt)) < 1e-9 * float(opt), True)

# ---------------------------------------------------------------- 9
row("Atom endpoint property (Section 2.5)")
rng9 = np.random.default_rng(20261120)
viol = 0
for it in range(2000):
    p_, q_, r = int(rng9.integers(1, 8)), int(rng9.integers(1, 8)), int(rng9.integers(2, 7))
    Av = rng9.normal(size=p_)
    Bv = rng9.normal(size=q_) + rng9.uniform(0, 3)
    g = float(rng9.uniform(Av.max(), max(Av.max(), Bv.min()) + 1))
    def s_(v):
        v = np.array(v, float)
        return float(((v - v.mean()) ** 2).sum())
    phi = [s_(list(Av) + [g] * t) + s_(list(Bv) + [g] * (r - t)) for t in range(r + 1)]
    viol += int(min(phi[0], phi[-1]) > min(phi) + 1e-9)
check("random multi-copy cases", f"{2000:,}", "2,000")
check("violations (minimum not at t = 0 or t = r)", viol, 0)

# ---------------------------------------------------------------- 10
row("Transfer threshold (Section 11.1; Exercise 4)")
check("A = {0, 1.6}, B = {2.6}: 1.6 is nearer m_A (0.8 vs 1.0)", (f"{1.6 - 0.8:.1f}", f"{2.6 - 1.6:.1f}"), ("0.8", "1.0"))
before = sse([0, Fr(16, 10)]) + sse([Fr(26, 10)])
after_ = sse([0]) + sse([Fr(16, 10), Fr(26, 10)])
check("moving 1.6 to B: SSE 1.28 -> 0.50", (f2(before), f2(after_)), ("1.28", "0.50"))
d20 = lambda s, n1, m1, n2, m2, g: Fr(s * n2, n2 + s) * (g - m2) ** 2 - Fr(s * n1, n1 - s) * (g - m1) ** 2
check("(20) gives the same change", d20(1, 2, Fr(8, 10), 1, Fr(26, 10), Fr(16, 10)), after_ - before)
check("Exercise 4 directly: 50 -> 0.5, delta = -49.5", (sse([0, 10]), sse([10, 11]), float(sse([10, 11]) - sse([0, 10]))), (50, Fr(1, 2), -49.5))
check("Exercise 4 by (20)", float(d20(1, 2, 5, 1, 11, 10)), -49.5)

# ---------------------------------------------------------------- 11
row("Memory budgets and Exercise 2 (Sections 13.2, 15, 18)")


def mem(N, D, k, M):
    G = max(k, min(M, D))
    return 40 * N + max(28 * D, 4 * (k - 1) * (G + 1) + 60 * G), 4 * (k - 1) * (G + 1), 16 * k * N + 40 * N


def unit(b):
    if b >= 1e9:
        return f"{b / 1e9:.3g} GB"
    if b >= 1e6:
        return f"{b / 1e6:.2g} MB" if b < 1e7 else f"{b / 1e6:.0f} MB"
    return f"{b / 1e3:.3g} kB"


table9 = [((1000, 16, 256), ("70.8 kB", "15.4 kB", "296 kB")),
          ((10000, 16, 256), ("680 kB", "15.4 kB", "2.96 MB")),
          ((10000, 16, 1024), ("680 kB", "61.5 kB", "2.96 MB")),
          ((100000, 64, 1024), ("6.8 MB", "0.26 MB", "106 MB")),
          ((1000000, 256, 4096), ("68 MB", "4.2 MB", "4.14 GB"))]
for (N_, k_, M_), want in table9:
    w, tb, ck = mem(N_, N_, k_, M_)
    tb_s = f"{tb / 1e6:.2f} MB" if (tb >= 1e5 and tb < 1e6) else unit(tb)
    ck_s = f"{ck / 1e6:.2f} MB" if ck < 1e7 and ck >= 1e6 else unit(ck)
    check(f"Table 9 N = {N_:,}, k = {k_}, M = {M_:,}", (unit(w), tb_s, ck_s), want)
w, tb, ck = mem(10 ** 6, 10 ** 6, 256, 4096)
check("Exercise 5: 40 MB + max(28 MB, 4.4 MB) = 68 MB vs 16kN = 4.1 GB",
      (f"{40e6 / 1e6:.0f}", f"{28e6 / 1e6:.0f}", f"{(4 * 255 * 4097 + 60 * 4096) / 1e6:.1f}", f"{w / 1e6:.0f}", f"{16 * 256 * 1e6 / 1e9:.1f}"),
      ("40", "28", "4.4", "68", "4.1"))
check("DP table at M = 4,096, k = 512: 8,374,268 bytes", f"{4 * 511 * 4097:,}", "8,374,268")
check("at most 8.4 MB", f"{4 * 511 * 4097 / 1e6:.1f}", "8.4")
z = [0, 3, 5, 8]
p2, p3 = all_cuts(z, 2), all_cuts(z, 3)
check("Exercise 2: k = 2 optimum {0,3}|{5,8}, SSE 9, unique", (p2[0][1], p2[0][0], p2[1][0] > p2[0][0]), ((2,), 9, True))
check("Exercise 2: k = 3 optimum {0}|{3,5}|{8}, SSE 2, unique", (p3[0][1], p3[0][0], p3[1][0] > p3[0][0]), ((1, 3), 2, True))

# ---------------------------------------------------------------- 12
row("Additional hand illustrations (Sections 3.3, 5.1, 5.3, 9, 10.5, 11.1, 15; Exercise 6)")
check("k N^2 / 2 at N = 10^6, k = 256: about 1.3 x 10^14", f"{256 * 10 ** 12 / 2:.2e}", "1.28e+14")
check("QI at (0, 1, 4, 5): 21.00 + 22.75 = 43.75", (f2(c(0, 4)), f2(c(1, 5)), f2(c(0, 4) + c(1, 5))), ("21.00", "22.75", "43.75"))
check("QI at (0, 1, 4, 5): 37.20 + 12.67 = 49.87", (f2(c(0, 5)), f2(c(1, 4)), f2(c(0, 5) + c(1, 4))), ("37.20", "12.67", "49.87"))
evals = []
cur, arg_ = {}, {}


def fill(lo, hi, optlo, opthi):
    if lo > hi:
        return
    mid = (lo + hi) // 2
    best, a_ = None, None
    for i in range(min(opthi, mid - 1), optlo - 1, -1):
        v = F[(2, i)] + c(i, mid)
        evals.append((mid, i, f2(v)))
        if best is None or v < best:
            best, a_ = v, i
    cur[mid], arg_[mid] = best, a_
    fill(lo, mid - 1, optlo, a_)
    fill(mid + 1, hi, a_, opthi)


fill(3, 6, 2, 5)
check("FILL(3, 6, 2, 5): j = 4 scans i = 3, 2 (0.50, 4.50), arg 3", evals[:2], [(4, 3, "0.50"), (4, 2, "4.50")])
check("then j = 3 with i = 2; j = 5 with i = 4, 3; j = 6 with i = 5, 4, 3", [(j, i) for j, i, _ in evals[2:]],
      [(3, 2), (5, 4), (5, 3), (6, 5), (6, 4), (6, 3)])
check("8 evaluations instead of 10", (len(evals), sum(j - 2 for j in range(3, 7))), (8, 10))
check("FILL gives row 3 of Table 4", [(cur[j], arg_[j]) for j in range(3, 7)], [(F[(3, j)], T[(3, j)]) for j in range(3, 7)])
g3b = bounds_of(collapse(x10, 3)[0])
check("Collapse bounds {3, 6} within {3, 5, 6, 8}", (g3b, bounds_of(g5), set(g3b) <= set(bounds_of(g5))), ([3, 6], [3, 5, 6, 8], True))
L = (math.sqrt(1849 / 30) - math.sqrt(139 / 6)) ** 2
check("Lemma 2 on the ten values: L = 9.23", f2(L), "9.23")
check("at most about 800% above the optimum", f"{100 * (83 / L - 1):.0f}", "800")
check("cross term 2 sqrt(B* W) = 75.57", f2(2 * math.sqrt(1849 / 30 * 139 / 6)), "75.57")
check("gap C_M - OPT = 1.80", f2(cm - 83), "1.80")
dd = d20(2, 3, Fr(8, 3), 1, 6, 4)
check("two copies of 4 from {0,4,4} to {6}: 8/3 - 32/3 = -8",
      (Fr(2, 3) * (4 - 6) ** 2, 6 * (4 - Fr(8, 3)) ** 2, dd), (Fr(8, 3), Fr(32, 3), -8))
check("direct SSEs 32/3 before, 8/3 after", (sse([0, 4, 4]) + sse([6]), sse([0]) + sse([4, 4, 6])), (Fr(32, 3), Fr(8, 3)))
check("Table 9: 40 + 28 = 68 bytes per value", 40 + 28, 68)
r = [mem(1000, 1000, 16, 256), mem(10000, 10000, 16, 256), mem(10 ** 6, 10 ** 6, 256, 4096)]
check("Table 9: about 4 times less memory at k = 16", [round(ck / w) for w, tb, ck in r[:2]], [4, 4])
check("Table 9: about 60 times less at k = 256, N = 10^6", round(r[2][2] / r[2][0], -1), 60)
check("Exercise 6: 2^(2.29 - 1.98) = 1.24", f"{2 ** (2.29 - 1.98):.2f}", "1.24")

# ---------------------------------------------------------------- report
os.makedirs(OUT, exist_ok=True)
secs = time.time() - T0
summary = []
for n, title in enumerate(ROWS, 1):
    cs = [ch for ch in CHECKS if ch["row"] == n]
    summary.append(dict(row=n, title=title, checks=len(cs), failed=sum(not ch["ok"] for ch in cs)))
res = dict(seconds=round(secs, 2), numpy=np.__version__, rows=summary, checks=CHECKS)
with open(os.path.join(OUT, "results.json"), "w") as fh:
    json.dump(res, fh, indent=1)
lines = ["# Expository checks (run/expo_checks.py)", "",
         f"{len(CHECKS)} checks in {len(ROWS)} rows, {sum(not ch['ok'] for ch in CHECKS)} failed, {secs:.1f} s.", "",
         "| Row | Item (Table 10 of the expository paper) | Checks | Result |", "|---:|---|---:|---|"]
for s_ in summary:
    lines.append(f"| {s_['row']} | {s_['title']} | {s_['checks']} | {'PASS' if s_['failed'] == 0 else 'FAIL (%d)' % s_['failed']} |")
bad = [ch for ch in CHECKS if not ch["ok"]]
if bad:
    lines += ["", "## Failed checks", ""] + [f"- row {ch['row']}: {ch['what']}: got `{ch['got']}`, paper `{ch['paper']}`" for ch in bad]
with open(os.path.join(OUT, "summary.md"), "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if bad else 0)
