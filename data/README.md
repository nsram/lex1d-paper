# Data

| File | What it is |
|---|---|
| `generate.py` | The generator for the 12 simulated datasets (seed 2048). Unchanged from the version used for the papers (SHA-256 `bd017034d0e79411f4eadac264643a16342d49822e36410debcd371206925e8b`). |
| `shasum.txt` | SHA-256 of each of the 12 files as generated on the reference Mac with NumPy 2.3.5 (each file has 2,080,768 lines). |
| `slice_counts.csv` | Distinct values D in each of the 7 slices, per dataset. The run recomputes D for every slice and stops on a mismatch. |
| `audio/` | Where the real audio file goes (see `audio/README.md`). |

## Simulated data

`generate.py` writes 12 files of 2,080,768 values each to `input/` in its working directory, with
`np.savetxt(fmt="%.18f")`. Ten datasets are continuous (uniform, Gaussian, exponential, Weibull,
lognormal, and five mixtures) and two are discrete (a triangular distribution on -2,047..2,047 and a
zero-spike mixture). Each dataset uses its own PCG64 stream derived from seed 2048.

Each file is cut into 7 consecutive, non-overlapping slices of 2^14, 2^15, ..., 2^20 values
(16,384 to 1,048,576), in that order; together they use the whole file.

The generated files are not stored in the repository. When `simulation/input/` is empty, the run
scripts generate them by running `generate.py` from `simulation/`, then check every file against
`shasum.txt`. To generate them by hand from the repo root:

    cd simulation && ../.venv/bin/python ../data/generate.py && cd ..

(`run/setup.sh` creates `.venv` with numpy.) This also writes `simulation/dataset_slice_counts.csv`,
which should be identical to `data/slice_counts.csv`.

If a file does not match `shasum.txt`, the run prints a warning and continues, and `env.txt` in the
output folder records the mismatch. Results from such files are valid runs but will not be
bit-identical to `results/gold/`.

Regenerated files can differ from the reference files in the last digit of some values. On an x86-64
Linux machine with NumPy 2.5.5, `uniform_continuous` and the two discrete datasets came out
identical, and the other nine continuous datasets differed in between 1 and 156,794 of their
2,080,768 values, each by at most a few units in the last place (largest difference 2.1e-14). This
probably comes from floating-point differences in the normal, exponential, Weibull and lognormal samplers
across NumPy versions or platforms. For bit-identical results, use the reference files: generate
them on a Mac with NumPy 2.3.5, or copy them from someone who has them, into `simulation/input/`.
If the input files change, the run notices and prepares its cached slices again.

## Audio

See `audio/README.md`. The audio is the Dharini Abhogi recording from the Carnatic Varnam Dataset
(CC BY 4.0), 8,168,256 samples.
