"""Fetch the GPT-2 Large weight tensor used as the second real dataset (standard library only).

From the repo root:  bash run/gpt2.sh   (calls this when data/gpt2/ has no tensor yet)
By hand:             python3 run/gpt2_fetch.py [--full]

Source: Hugging Face openai-community/gpt2-large (MIT license), file model.safetensors at the pinned
commit below, tensor h.0.mlp.c_fc.weight (named transformer.h.0.mlp.c_fc.weight in the PyTorch module):
float32, shape 1280 x 5120 = 6,553,600 values.

Default: HTTPS range reads only. It reads the 8-byte header length and the JSON header, checks the
tensor's dtype (F32), shape and byte offsets, then reads only the tensor's 26,214,400 bytes and checks
their SHA-256 against the pinned value. --full instead downloads the whole model.safetensors
(3,247,159,078 bytes), checks its SHA-256 against the Hugging Face LFS hash pinned below, and extracts
the tensor from it.

Writes data/gpt2/gpt2-large_h0_mlp_c_fc_weight.f32le (the tensor bytes as stored: little-endian
float32, row-major) and data/gpt2/gpt2_stats.json (hashes, N, D, min, max, mean, sd, kurtosis).
Stops with an error if D <= 4,096 (the data would not exercise Collapse and Refine at M = 4,096).
"""
import hashlib
import json
import math
import os
import struct
import sys
import urllib.request
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(os.path.dirname(HERE), "data", "gpt2")
REPO = "openai-community/gpt2-large"
REVISION = "32b71b12589c2f8d625668d2335a01cac3249519"
URL = f"https://huggingface.co/{REPO}/resolve/{REVISION}/model.safetensors"
FILE_SIZE = 3_247_159_078
FILE_SHA256 = "5f47f3e12f91cd33b662ce7e433b6150ad5512b5884a2cee961b50e9c3bbebce"  # Hugging Face LFS hash
TENSOR = "h.0.mlp.c_fc.weight"
SHAPE = [1280, 5120]
TENSOR_SHA256 = "3b5cac6f1a695c6d6493aa65cdabec45b3a6dd541fee24604e03d208a5d28557"  # SHA-256 of the tensor's raw bytes
OUT_NAME = "gpt2-large_h0_mlp_c_fc_weight.f32le"
M_DEFAULT = 4096


def get(url, start=None, end=None):
    req = urllib.request.Request(url, headers={"User-Agent": "lex1d-paper/gpt2_fetch"})
    if start is not None:
        req.add_header("Range", f"bytes={start}-{end}")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def header(read):
    n = struct.unpack("<Q", read(0, 7))[0]
    h = json.loads(read(8, 8 + n - 1))
    return n, h


def stats(vals):
    n = len(vals)
    mean = math.fsum(vals) / n
    m2 = math.fsum((x - mean) ** 2 for x in vals) / n
    m4 = math.fsum((x - mean) ** 4 for x in vals) / n
    return dict(min=min(vals), max=max(vals), mean=mean, sd=math.sqrt(m2 * n / (n - 1)),
                kurtosis_excess=m4 / m2 ** 2 - 3.0)


def main():
    full = "--full" in sys.argv[1:]
    os.makedirs(OUTDIR, exist_ok=True)
    if full:
        path = os.path.join(OUTDIR, "model.safetensors")
        if not (os.path.isfile(path) and os.path.getsize(path) == FILE_SIZE):
            print(f"downloading {URL} ({FILE_SIZE/1e9:.2f} GB) to {os.path.relpath(path)}", flush=True)
            req = urllib.request.Request(URL, headers={"User-Agent": "lex1d-paper/gpt2_fetch"})
            with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
                while chunk := r.read(1 << 24):
                    f.write(chunk)
            os.replace(path + ".part", path)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 24), b""):
                h.update(chunk)
        if h.hexdigest() != FILE_SHA256:
            sys.exit(f"model.safetensors SHA-256 {h.hexdigest()} != pinned {FILE_SHA256}")
        print("model.safetensors SHA-256 matches the Hugging Face LFS hash", flush=True)
        def read(a, b):
            with open(path, "rb") as f:
                f.seek(a)
                return f.read(b - a + 1)
        file_sha_verified = True
    else:
        read = lambda a, b: get(URL, a, b)
        file_sha_verified = False
    n, h = header(read)
    t = h.get(TENSOR)
    if not t:
        sys.exit(f"tensor {TENSOR} not in the safetensors header")
    if t["dtype"] != "F32" or t["shape"] != SHAPE:
        sys.exit(f"{TENSOR}: dtype {t['dtype']} shape {t['shape']}, expected F32 {SHAPE}")
    a, b = t["data_offsets"]
    N = SHAPE[0] * SHAPE[1]
    if b - a != 4 * N:
        sys.exit(f"{TENSOR}: {b - a} bytes, expected {4 * N}")
    raw = read(8 + n + a, 8 + n + b - 1)
    tsha = hashlib.sha256(raw).hexdigest()
    if tsha != TENSOR_SHA256:
        sys.exit(f"tensor SHA-256 {tsha} != pinned {TENSOR_SHA256}")
    vals32 = array("f")
    vals32.frombytes(raw)
    if sys.byteorder != "little":
        vals32.byteswap()
    vals = array("d", vals32)  # exact float32 -> float64 conversion, row-major order kept
    if any(math.isnan(x) or math.isinf(x) for x in vals):
        sys.exit("tensor has NaN or Inf values")
    D = len(set(vals))
    if D <= M_DEFAULT:
        sys.exit(f"D = {D} <= {M_DEFAULT}: LEX would be exact here and the benchmark would not test Collapse/Refine")
    v = array("d", vals)
    if sys.byteorder != "little":
        v.byteswap()
    v64 = v.tobytes()
    s = dict(source=f"https://huggingface.co/{REPO}", revision=REVISION, file="model.safetensors", file_size=FILE_SIZE,
             file_sha256=FILE_SHA256, file_sha256_verified_here=file_sha_verified, header_bytes=n,
             tensor=TENSOR, dtype=t["dtype"], shape=SHAPE, data_offsets=[a, b], order="row-major (as stored)",
             tensor_bytes_sha256=tsha, float64_le_sha256=hashlib.sha256(v64).hexdigest(),
             N=N, D=D, **stats(vals))
    with open(os.path.join(OUTDIR, OUT_NAME), "wb") as f:
        f.write(raw)
    with open(os.path.join(OUTDIR, "gpt2_stats.json"), "w") as f:
        json.dump(s, f, indent=1)
    print(json.dumps(s, indent=1))
    print(f"wrote data/gpt2/{OUT_NAME} and data/gpt2/gpt2_stats.json")


if __name__ == "__main__":
    main()
