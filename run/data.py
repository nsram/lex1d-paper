"""Data preparation (standard library only).

Simulation: the 12 files written by data/generate.py (seed 2048) into simulation/input/. The reference
files were generated on N. Sriram's Mac with NumPy 2.3.5; their line counts and SHA-256 are in
data/shasum.txt and every file is checked against it before the run (a mismatch is reported as a
warning: the run continues, but its results will not be bit-identical to results/gold/).
Slices: 7 consecutive, non-overlapping blocks of 2^14 ... 2^20 values (they use the whole file):
    counts = [16384, 32768, 65536, 131072, 262144, 524288, 1048576]; slice i starts after slices 1..i-1.
D (distinct values) is recomputed per slice and checked against data/slice_counts.csv.

Audio: dharini-abhogi (8,168,256 values), read from data/audio/dharini-abhogi.txt.gz; the SHA-256 of
the uncompressed text is pinned.

Every solver reads the same little-endian float64 file, written here from the text with Python float()
(correctly rounded, the same doubles C strtod gives). For each input PREFIX:
    PREFIX.raw.f64     values in file order (the raw-input script)
    PREFIX.sorted.f64  the same values sorted ascending (the presorted script)
Weighted inputs (section `weighted`) also get PREFIX.w.raw.f64 (weights in file order) and the pair
files PREFIX.wx.sorted.f64 / PREFIX.w.sorted.f64 (pairs sorted by value, then weight).
Weights: uniform(0.1, 10) from Python's random.Random(seed), seed = 24000 + 100*dataset_index + slice
(dataset_index = position in DATASETS). Mersenne Twister, identical on every platform.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import random
import sys
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
DATA = os.path.join(PACK, "data")

NROWS = 2_080_768
COUNTS = [16384, 32768, 65536, 131072, 262144, 524288, 1048576]
assert sum(COUNTS) == NROWS
DATASETS = [
    "uniform_continuous", "gaussian_continuous", "exponential_continuous", "weibull_continuous",
    "lognormal_continuous", "gmm_continuous", "wg_mixture_continuous", "bimodal_gaussian_continuous",
    "mixed_continuous", "truncated_continuous", "triangular_discrete", "spike_uniform_discrete",
]
AUDIO_NAME = "dharini-abhogi.txt.gz"
AUDIO_SHA256 = "b19a45a308ba4758d8769b0d71e43ccf7503c0a0182e8d05e3ac5583586b2c3e"
AUDIO_N = 8_168_256
AUDIO_D = 7_295_677  # distinct values in the full audio file


def shasums() -> dict:
    out = {}
    with open(os.path.join(DATA, "shasum.txt")) as f:
        for line in f:
            if line.strip():
                h, p = line.split()
                out[os.path.basename(p)[:-4]] = h
    return out


def d_expected() -> dict:
    out = {}
    with open(os.path.join(DATA, "slice_counts.csv")) as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            out[parts[0]] = [int(v) for v in parts[1:]]
    return out


def find_input(sim: str) -> str | None:
    """simulation/input/, or simulation/ itself, or simulation/input/input (a copied folder nested one level)."""
    for c in (os.path.join(sim, "input"), sim, os.path.join(sim, "input", "input")):
        if os.path.isfile(os.path.join(c, "gaussian_continuous.txt")):
            return os.path.realpath(c)
    return None


def forget_stale(prepared: str, dataset: str, sha: str) -> None:
    """Prepared .f64 inputs are cached in work/*/inputs/ across sessions. Each dataset's cache records the
    SHA-256 of the text file it was cut from; if the text file has changed since (for example generated
    files replaced by the reference files), the cached slices are deleted so they are prepared again."""
    stamp = os.path.join(prepared, dataset + ".source_sha256")
    old = open(stamp).read().strip() if os.path.isfile(stamp) else None
    if old == sha:
        return
    stale = [f for f in os.listdir(prepared) if f.startswith(dataset + "_s")] if os.path.isdir(prepared) else []
    for f in stale:
        os.remove(os.path.join(prepared, f))
    if stale and old is not None:
        print(f"note     {dataset}: input file changed since its slices were prepared; preparing them again", flush=True)
    os.makedirs(prepared, exist_ok=True)
    with open(stamp, "w") as f:
        f.write(sha + "\n")


def verify(inp: str, datasets, prepared: str = "") -> int:
    sums = shasums()
    bad = 0
    for d in datasets:
        p = os.path.join(inp, d + ".txt")
        if not os.path.isfile(p):
            print(f"MISSING {p}")
            bad += 1
            continue
        h = hashlib.sha256()
        n = 0
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
                n += chunk.count(b"\n")
        ok = n == NROWS and h.hexdigest() == sums[d]
        bad += not ok
        if prepared:
            forget_stale(prepared, d, h.hexdigest())
        print(f"{'ok      ' if ok else 'MISMATCH'} {d}: {n} lines, sha256 {h.hexdigest()}"
              + ("" if ok else f"  (expected {NROWS} lines, sha256 {sums[d]})"), flush=True)
    return bad


def _write(path: str, vals) -> None:
    a = array("d", vals)
    if sys.byteorder != "little":
        a.byteswap()
    with open(path + ".tmp", "wb") as f:
        a.tofile(f)
    os.replace(path + ".tmp", path)


def write_input(prefix: str, vals, weights=None) -> None:
    _write(prefix + ".raw.f64", vals)
    _write(prefix + ".sorted.f64", sorted(vals))
    if weights is not None:
        _write(prefix + ".w.raw.f64", weights)
        pairs = sorted(zip(vals, weights))
        _write(prefix + ".wx.sorted.f64", [p[0] for p in pairs])
        _write(prefix + ".w.sorted.f64", [p[1] for p in pairs])


def _read(path: str) -> array:
    a = array("d")
    with open(path, "rb") as f:
        a.frombytes(f.read())
    if sys.byteorder != "little":
        a.byteswap()
    return a


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_input(prefix: str, weighted: bool) -> list:
    """Re-reads the prepared files of one slice and checks that each sorted copy is a permutation of
    its own raw slice (same count, same multiset of exact float64 bit patterns) in ascending order.
    Returns manifest rows (file, n, sha256, check)."""
    raw = _read(prefix + ".raw.f64")
    srt = _read(prefix + ".sorted.f64")
    asc = all(srt[i] <= srt[i + 1] for i in range(len(srt) - 1))
    # multiset of exact bit patterns: sort the raw 64-bit integers of both files and compare
    perm = len(raw) == len(srt) and sorted(array("q", raw.tobytes())) == sorted(array("q", srt.tobytes()))
    ok = asc and perm
    rows = [dict(file=os.path.basename(prefix + ".raw.f64"), n=len(raw), sha256=_sha(prefix + ".raw.f64"), check="raw"),
            dict(file=os.path.basename(prefix + ".sorted.f64"), n=len(srt), sha256=_sha(prefix + ".sorted.f64"),
                 check=f"ascending={int(asc)} permutation_of_raw={int(perm)}")]
    if weighted:
        wr, xs, ws = _read(prefix + ".w.raw.f64"), _read(prefix + ".wx.sorted.f64"), _read(prefix + ".w.sorted.f64")
        bits = lambda a: array("q", a.tobytes())
        pok = (len(wr) == len(raw) == len(xs) == len(ws)
               and sorted(zip(bits(raw), bits(wr))) == sorted(zip(bits(xs), bits(ws)))
               and all((xs[i], ws[i]) <= (xs[i + 1], ws[i + 1]) for i in range(len(xs) - 1)))
        ok = ok and pok
        for suf in (".w.raw.f64", ".wx.sorted.f64", ".w.sorted.f64"):
            rows.append(dict(file=os.path.basename(prefix + suf), n=len(wr), sha256=_sha(prefix + suf),
                             check="weights" if suf == ".w.raw.f64" else f"pairs_sorted_permutation_of_raw={int(pok)}"))
    for r in rows:
        r["ok"] = int(ok)
    return rows


def weights_for(dataset: str, slice_i: int, n: int):
    rng = random.Random(24000 + 100 * DATASETS.index(dataset) + slice_i)
    return [rng.uniform(0.1, 10.0) for _ in range(n)]


def prepare_dataset(inp: str, outdir: str, dataset: str, slices, weighted_slices=(), truncate: int = 0):
    """Writes outdir/{dataset}_s{i}.* for each slice; returns list of meta dicts."""
    with open(os.path.join(inp, dataset + ".txt"), "rb") as f:
        lines = f.read().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    if len(lines) != NROWS:
        raise SystemExit(f"{dataset}: {len(lines)} lines, expected {NROWS}")
    dexp = d_expected().get(dataset, [None] * 7)
    metas = []
    for i in slices:
        start = sum(COUNTS[: i - 1])
        part = lines[start: start + COUNTS[i - 1]]
        if truncate:
            part = part[:truncate]
        vals = [float(x) for x in part]
        sha = hashlib.sha256(b"\n".join(part) + b"\n").hexdigest()
        w = weights_for(dataset, i, len(vals)) if i in weighted_slices else None
        prefix = os.path.join(outdir, f"{dataset}_s{i}")
        write_input(prefix, vals, w)
        d = len(set(vals))
        de = None if truncate else dexp[i - 1]
        meta = dict(dataset=dataset, slice=i, N=len(vals), D=d, D_expected=de if de is not None else "",
                    start=start, sha256=sha, weighted=int(w is not None), prefix=prefix)
        with open(prefix + ".meta", "w") as f:
            f.write(" ".join(f"{k}={v}" for k, v in meta.items()) + "\n")
        if de is not None and d != de:
            raise SystemExit(f"{dataset} slice {i}: D = {d}, expected {de} (data/slice_counts.csv)")
        metas.append(meta)
    return metas


def audio_path() -> str:
    return os.path.join(DATA, "audio", AUDIO_NAME)


def find_audio() -> str:
    p = audio_path()
    return os.path.relpath(p, PACK) if os.path.isfile(p) else ""


def prepare_audio(outdir: str, truncate: int = 0, weighted: bool = False):
    p = audio_path()
    if not os.path.isfile(p):
        raise SystemExit(f"audio not found: {os.path.relpath(p, PACK)} (see data/audio/README.md)")
    with open(p, "rb") as f:
        gz = f.read()
    raw = gzip.decompress(gz)
    h = hashlib.sha256(raw).hexdigest()
    if h != AUDIO_SHA256:
        raise SystemExit(f"audio sha256 {h} != pinned {AUDIO_SHA256}")
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    if len(lines) != AUDIO_N:
        raise SystemExit(f"audio: {len(lines)} lines, expected {AUDIO_N}")
    if truncate:
        lines = lines[:truncate]
    vals = [float(x) for x in lines]
    del lines, raw
    prefix = os.path.join(outdir, "audio_s0")
    write_input(prefix, vals)
    d = len(set(vals))
    if not truncate and d != AUDIO_D:
        raise SystemExit(f"audio: D = {d}, expected {AUDIO_D}")
    meta = dict(dataset="audio", slice=0, N=len(vals), D=d, D_expected="" if truncate else AUDIO_D, start=0,
                sha256=h if not truncate else "", weighted=0, prefix=prefix)
    with open(prefix + ".meta", "w") as f:
        f.write(" ".join(f"{k}={v}" for k, v in meta.items()) + "\n")
    return meta


def read_meta(prefix: str):
    p = prefix + ".meta"
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        kv = dict(t.split("=", 1) for t in f.read().split())
    for k in ("slice", "N", "D", "start", "weighted"):
        kv[k] = int(kv[k])
    return kv


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "find-input":
        r = find_input(sys.argv[2])
        if not r:
            sys.exit(3)
        print(r)
    elif len(sys.argv) >= 3 and sys.argv[1] == "verify":
        ds = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else DATASETS
        sys.exit(1 if verify(sys.argv[2], ds, os.environ.get("LEX_PREPARED_DIR", "")) else 0)
    elif len(sys.argv) >= 2 and sys.argv[1] == "find-audio":
        r = find_audio()
        print(r or "not found")
        sys.exit(0 if r else 3)
    else:
        sys.exit("usage: data.py find-input SIM | verify INPUT_DIR [DATASETS] | find-audio")
