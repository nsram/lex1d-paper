"""Prepare the three paper slices used by run/ablation.sh.

Uses run/data.py (standard library only). Slice numbers are 1-based as in data.py:
slice 3 is N = 65,536 and slice 7 is N = 1,048,576.

Usage, from the repo (the run script calls this):
    python3 run/ablation_prep.py --input simulation/input --prepared work/full/inputs \
        --manifest out/ablation/inputs_manifest.csv
Prints one `dataset,N,path` line per slice, for the driver's --slice flag.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data as D  # noqa: E402

DATASETS = ["uniform_continuous", "gaussian_continuous", "lognormal_continuous"]
# 1-based slice indices: 3 -> 2^16, 7 -> 2^20
SLICES = [3, 7]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="folder holding the 12 simulation .txt files")
    p.add_argument("--prepared", required=True, help="folder for the little-endian .raw.f64 slices")
    p.add_argument("--manifest", required=True, help="path to write inputs_manifest.csv")
    args = p.parse_args()
    os.makedirs(args.prepared, exist_ok=True)

    rows = []
    printed = []
    for dataset in DATASETS:
        metas = D.prepare_dataset(args.input, args.prepared, dataset, SLICES)
        for meta in metas:
            prefix = meta["prefix"]
            checks = D.check_input(prefix, weighted=False)
            for c in checks:
                rows.append({
                    "dataset": dataset,
                    "slice": meta["slice"],
                    "N": meta["N"],
                    "file": c["file"],
                    "n": c["n"],
                    "sha256": c["sha256"],
                    "check": c["check"],
                    "ok": c["ok"],
                    "source_start": meta["start"],
                    "source_sha256": meta["sha256"],
                    "D": meta["D"],
                })
            raw = prefix + ".raw.f64"
            printed.append(f"{dataset},{meta['N']},{raw}")
    os.makedirs(os.path.dirname(os.path.abspath(args.manifest)) or ".", exist_ok=True)
    with open(args.manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for line in printed:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
