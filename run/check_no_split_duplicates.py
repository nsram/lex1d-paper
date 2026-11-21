"""Check Corollary 1 of the technical paper (no optimum splits an atom), in exact rational
arithmetic.

On 4,000 small random multisets (4 to 10 integers from 0 to 6, k = 2 to 4 bins), every
contiguous partition is enumerated and kept if no transfer of a single value between
neighboring bins lowers SSE (8,591 such partitions with this seed). None may have two
neighboring bins sharing a value unless both bins hold only that value.

Runtime: about 7 s. Exits nonzero on any failure.
Run with the other checks, from the repo root:  bash run/checks.sh
"""
import itertools
import random
import sys
from fractions import Fraction as F


def sse(v):
    m = sum(v) / len(v)
    return sum((x - m) ** 2 for x in v)


random.seed(3)
stable_count = 0
split = []
for _ in range(4000):
    n = random.randint(4, 10); x = sorted(F(random.randint(0, 6)) for _ in range(n)); k = random.randint(2, 4)
    if len(set(x)) < k:
        continue
    for cuts in itertools.combinations(range(1, n), k - 1):
        b = [0, *cuts, n]; bins = [x[b[i]:b[i + 1]] for i in range(k)]
        tot = sum(map(sse, bins)); stable = True
        for i in range(k - 1):
            base = tot - sse(bins[i]) - sse(bins[i + 1])
            if len(bins[i]) >= 2 and base + sse(bins[i][:-1]) + sse([bins[i][-1]] + bins[i + 1]) < tot:
                stable = False
            if len(bins[i + 1]) >= 2 and base + sse(bins[i] + [bins[i + 1][0]]) + sse(bins[i + 1][1:]) < tot:
                stable = False
        if stable:
            stable_count += 1
            if any(bins[i][-1] == bins[i + 1][0] and not (len(set(bins[i])) == 1 and len(set(bins[i + 1])) == 1)
                   for i in range(k - 1)):
                split.append(bins)

print(f"stable partitions: {stable_count}; with a split atom (outside the all-copies case): {len(split)}")
for s in split[:5]:
    print("  counterexample:", s)
ok = stable_count > 0 and not split
print("all checks passed" if ok else "FAIL")
sys.exit(0 if ok else 1)
