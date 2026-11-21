"""Check numbers in the expository paper that can be recomputed from scratch (exact arithmetic,
no data files): the Refine move count for windows of w = 3 to 7 bins (8, 20, 40, 70, 112 moves;
w(w-1) single plus 2*C(w,3) twin moves, total (w-1)w(w+1)/3), the Lemma 1(c) example
(SSE 0.5 -> 0.18), and Exercises 4, 5 and 7 (transfer deltas -49.5 and -1.5; memory 68 MB vs 4.1 GB).

Runtime: under 1 s. Exits nonzero on any failure (failed assert).
Run with the other checks, from the repo root:  bash run/checks.sh
"""
from fractions import Fraction as F
from itertools import product
from math import comb
def sse(xs):
    xs=[F(x) for x in xs]; m=sum(xs)/len(xs); return sum((x-m)**2 for x in xs)
def delta10(s,n1,m1,n2,m2,g):
    return F(s*n2,n2+s)*(g-m2)**2-F(s*n1,n1-s)*(g-m1)**2
# Move count: brute force over boundary-shift patterns of a w-bin window.
def brute(w):
    single=twin=0
    for v in product((-1,0,1),repeat=w-1):
        nz=[i for i,x in enumerate(v) if x]
        if not nz or nz[-1]-nz[0]+1!=len(nz): continue  # must be one contiguous run
        seg=[v[i] for i in nz]; ch=sum(seg[i]!=seg[i+1] for i in range(len(seg)-1))
        if ch==0: single+=1
        elif ch==1: twin+=1
    return single,twin
for w,exp in [(3,8),(4,20),(5,40),(6,70),(7,112)]:
    s,t=brute(w); assert (s,t)==(w*(w-1),2*comb(w,3)) and s+t==exp==(w-1)*w*(w+1)//3,(w,s,t)
    print(f'w={w}: singles {s}, twins {t}, total {s+t}')
assert F(112,8)==14; print('112/8 = 14')
# Lemma 1(c) example
a,b=[0,1],[F(16,10)]
before=sse(a)+sse(b); after=sse([0])+sse([1,F(16,10)])
d=delta10(1,2,F(1,2),1,F(16,10),1)
assert before==F(1,2) and after==F(18,100) and d==after-before
assert 2*F(1,4)==F(1,2) and F(1,2)*F(36,100)==F(18,100)
print('Lemma 1(c): SSE',float(before),'->',float(after),'delta',float(d))
# Exercise 4
assert sse([0,10])+sse([11])==50 and sse([0])+sse([10,11])==F(1,2) and delta10(1,2,5,1,11,10)==F(-99,2); print('Ex4 delta -49.5')
# Exercise 5 (memory, decimal MB/GB)
lex=40e6+max(28e6,4*255*4097+60*4096); ck=16*256*1e6
print('Ex5: LEX %.1f MB, Ckmeans %.3f GB'%(lex/1e6,ck/1e9)); assert round(lex/1e6)==68 and round(ck/1e9,1)==4.1
# Exercise 7
d7=delta10(1,2,1,1,3,2); assert d7==F(-3,2) and sse([0,2])+sse([3])==2 and sse([0])+sse([2,3])==F(1,2); print('Ex7 delta -1.5, SSE 2 -> 0.5')
print('all checks passed')
