"""One fit through the lex1d Python binding (nanobind, frozen 8a691ee) per process.
Run with the repo's private venv python (.venv/). Peak RSS comes from /usr/bin/time outside.
Usage: python fit_py.py INPUT_F64 METHOD K M
  METHOD  py_load    import numpy + lex, read the data (baseline)
          py_hybrid  lex.lex_hybrid(x, k, coarse_groups=M)
Prints: RESULT key=value ...
"""
import sys
import time

path, method, k, M = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
t0 = time.perf_counter()
import numpy as np  # noqa: E402
import lex  # noqa: E402
x = np.fromfile(path, dtype="<f8")
t1 = time.perf_counter()
try:
    from importlib.metadata import version
    ver = version("lex1d")
except Exception:
    ver = "?"
if method == "py_load":
    print(f"RESULT method=py_load n={x.size} weighted=0 load_s={t1 - t0:.9f} checksum={float(x.sum()):.17g} "
          f"version={ver} numpy={np.__version__}")
elif method == "py_hybrid":
    t2 = time.perf_counter()
    r = lex.lex_hybrid(x, k, coarse_groups=M)
    t3 = time.perf_counter()
    sizes = "|".join(str(int(s)) for s in r.sizes)
    print(f"RESULT method=py_hybrid k={k} M={M} n={x.size} weighted=0 atoms={int(r.atoms)} k_eff={int(r.k)} "
          f"sse={float(r.sse):.17g} fit_s={t3 - t2:.9f} load_s={t1 - t0:.9f} sweeps={int(r.sweeps)} "
          f"moves={int(r.moves)} version={ver} numpy={np.__version__} sizes={sizes}")
else:
    sys.exit("unknown method " + method)
