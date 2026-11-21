"""Check the transfer formula and move-sign rule (technical paper Lemma 1) and the two-copy
case of Proposition 1, in exact rational arithmetic.

1. Lemma 1, identity (7): the change in SSE when s = 1 to 3 copies of g move from bin 1 to
   bin 2 equals the closed-form formula, against brute-force SSE, in 20,000 random cases.
2. Lemma 1(b): whenever g is farther from its own bin's mean than from the neighbor's
   (d2 < d1, single value), the move lowers SSE; a post-move-means variant of the rule is
   checked on the same draws.
3. Lemma 1(c): the counterexample {0, 1} -> {1.6} (SSE 0.5 -> 0.18) and a second example.
4. Proposition 1 for r = 2: sympy shows the sum of the two "keep together" gains equals a
   quadratic with non-positive discriminant, so splitting two copies never beats both ways
   of keeping them together; 6,000 cases with an empty side (p = 0 or q = 0) by brute force.

Needs sympy. Runtime: about 2 s. Exits nonzero on any failure.
Run with the other checks, from the repo root:  bash run/checks.sh
"""
import random
import sys
from fractions import Fraction as F

import sympy as sp

fails = []


def check(ok, msg):
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)


def sse(v):
    if not v:
        return F(0)
    m = sum(v) / len(v)
    return sum((x - m) ** 2 for x in v)


def mean(v):
    return sum(v) / len(v)


# 1-2. Identity (7) and the move-sign rule on random cases.
random.seed(1)
mismatch = 0
rule_b = [0, 0]      # [cases with d2 < d1, of which the move lowered SSE]
post = [0, 0]        # [cases closer to own post-move mean, of which the move did not pay]
for _ in range(20000):
    n1 = random.randint(2, 6); n2 = random.randint(1, 6)
    A = sorted(F(random.randint(0, 50)) for _ in range(n1 - 1)); g = F(random.randint(int(A[-1]), 60))
    s = random.randint(1, 3); A = A + [g] * s; n1 = len(A)
    B = sorted(F(random.randint(int(g), 90)) for _ in range(n2))
    m1, m2 = mean(A), mean(B)
    d = sse(A[:-s]) + sse([g] * s + B) - sse(A) - sse(B)
    f = F(s * n2, n2 + s) * (g - m2) ** 2 - F(s * n1, n1 - s) * (g - m1) ** 2
    mismatch += d != f
    if s == 1:
        if abs(g - m1) > abs(m2 - g):
            rule_b[0] += 1; rule_b[1] += d < 0
        mA = mean(A[:-1]); mB = mean([g] + B)
        if abs(mB - g) > abs(g - mA):
            post[0] += 1; post[1] += d >= 0
check(mismatch == 0, f"identity (7) vs brute force: 20,000 cases, {mismatch} mismatches")
check(rule_b[0] == rule_b[1] > 0, f"Lemma 1(b): {rule_b[1]} of {rule_b[0]} moves with d2 < d1 lowered SSE")
check(post[0] == post[1] > 0, f"post-move-means rule: {post[1]} of {post[0]} moves did not pay")

# 3. Lemma 1(c) counterexample, and a case closer to the neighbor's post-move mean that does not pay.
A, B, g = [F(0), F(1)], [F(8, 5)], F(1)
old, new = sse(A) + sse(B), sse([F(0)]) + sse([g] + B)
check(abs(g - mean(A)) < abs(g - mean(B)) and old == F(1, 2) and new == F(9, 50),
      "Lemma 1(c): d1 = 1/2 < d2 = 3/5, yet SSE 1/2 -> 9/50")
A, B = [F(0), F(1)], [F(5, 2)]
old, new = sse(A) + sse(B), sse([F(0)]) + sse([g] + B)
check(abs(g - mean([F(0)])) > abs(g - mean([g] + B)) and new > old,
      "closer to neighbor's post-move mean (3/4 < 1) does not imply a gain: SSE 1/2 -> 9/8")

# 4. Proposition 1, r = 2: two copies of x between a left group (size p, mean a) and a right group (size q, mean b).
x, a, b, p, q = sp.symbols("x a b p q", real=True); c, dd = a * p, b * q
p1 = (c + 2 * x) ** 2 / (p + 2) + dd ** 2 / q - (c + x) ** 2 / (p + 1) - (dd + x) ** 2 / (q + 1)
p2 = (dd + 2 * x) ** 2 / (q + 2) + c ** 2 / p - (c + x) ** 2 / (p + 1) - (dd + x) ** 2 / (q + 1)
al, be = p ** 2 + 3 * p + 2, q ** 2 + 3 * q + 2
fq = p * q * x ** 2 * (p * be + q * al) - 2 * p * q * x * (c * be + dd * al) + c ** 2 * q * be + dd ** 2 * p * al
check(sp.simplify(p1 + p2 - 2 * fq / (p * q * al * be)) == 0, "Prop. 1 (r = 2): gain sum equals 2f/(pq(p+1)(p+2)(q+1)(q+2))")
disc = sp.factor(sp.discriminant(fq, x))
check(disc == sp.factor(-4 * p**3 * q**3 * (a - b)**2 * (p + 1) * (p + 2) * (q + 1) * (q + 2)),
      f"Prop. 1 (r = 2): discriminant of f is {disc} <= 0, so f >= 0")
bad = 0
for P, Q in [(0, 3), (3, 0), (0, 0)]:
    for _ in range(2000):
        L = [F(random.randint(0, 30)) for _ in range(P)]; R = [F(random.randint(60, 90)) for _ in range(Q)]
        xx = F(random.randint(20, 70))
        LL = sse(L + [xx, xx]) + sse(R); RR = sse(L) + sse([xx, xx] + R); SP = sse(L + [xx]) + sse([xx] + R)
        bad += min(LL, RR) > SP
check(bad == 0, f"Prop. 1 (r = 2), empty side: 6,000 cases, split better in {bad}")

print("all checks passed" if not fails else f"{len(fails)} check(s) failed")
sys.exit(1 if fails else 0)
