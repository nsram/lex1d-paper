# lex1d-paper

Replication material for two papers by N. Sriram on LEX, a method for least-squares scalar
quantization (1-D k-means with contiguous bins):

- the technical paper, *Fast, memory-efficient, deterministic least-squares scalar quantization via
  coarsening, dynamic programming, and local exchanges* (working title), and
- the expository paper, *LEX explained: least-squares scalar quantization from exact dynamic
  programming to coarsen–solve–refine* (working title).

LEX itself is the C++ library [lex1d](https://github.com/nsram/lex1d), with Python and R bindings.
This repository holds a frozen copy of lex1d (commit `8a691ee`), the benchmark that produced every
simulation number in the papers, the outputs of that benchmark run (called GOLD below), the paper
figures, and the data or the means to regenerate it.

## Layout

| Path | What it holds |
|---|---|
| `lex1d/` | lex1d at commit `8a691ee005b657f985ffa299c57542b79570b08c`, byte for byte. Every run checks it against `run/lex1d_8a691ee.sha256` and stops if any file differs. |
| `bench/` | `fit.cpp`, the single-fit driver, and the `CMakeLists.txt` that builds it with lex1d. |
| `run/` | Setup, run and analysis scripts (see below). |
| `data/` | The simulation generator, its checksums and slice counts, and `audio/` for the real audio file. |
| `simulation/input/` | The 12 generated simulation files. Not in git; created on the first run. |
| `results/gold/` | Outputs of the GOLD run used in the papers: `raw/`, `sorted/`, `bindings/`. |
| `results/figures/` | The figures in the papers. |
| `results/prior/` | SSEs and times from earlier runs on the same Mac, used for an identity check. |
| `paper/` | LaTeX sources and PDFs of the technical and expository papers. |
| `talk/` | The talk, as HTML and PDF. |
| `requirements.txt`, `requirements-r.txt` | Pinned Python and R package versions (the GOLD versions). |

## The benchmark

Three scripts share one engine (`run/common.sh`, `run/run.py`):

- `run/raw.sh`: the full grid with every fit on the values in file order.
- `run/sorted.sh`: the same grid with every fit on the same values presorted, which separates the
  cost of sorting.
- `run/bindings.sh`: the same fits through lex1d's R and Python bindings, to measure binding overhead.

The grid covers the 12 simulated datasets, each cut into 7 slices of 2^14 to 2^20 values, with
k = 4 to 512, plus an M sweep, the audio file, and a weighted subset. Each cell compares LEX
(`lex_hybrid`, M = 4,096, 8,192 and 16,384, and 1,024 and 2,048 in the M sweep), plain LEX
(`lex_plain`), lex1d's exact dynamic program (`ckmeans_exact`) and the R package Ckmeans.1d.dp
4.3.6. Every fit runs in its own process under `/usr/bin/time`, so each has its own peak memory; each
cell has one warm-up round and 3 timed rounds, with the method order rotated each round.

Before measuring, the scripts build lex1d and the driver in Release mode with strict floating point
(`-ffp-contract=off`) and run lex1d's 6 C++ test suites. On the warm-up round the driver also calls
the public lex1d function and checks that it gives the same answer as the instrumented copy it times
(the `api_match` column).

`run/run3.sh` runs the three scripts in turn, and keeps the machine awake while it does
(`caffeinate` on macOS, `systemd-inhibit` on Linux). Each script writes finished cells to disk as it
goes, so running the same command again resumes where it stopped.

## Setup and run

From the repo root:

    bash run/setup.sh
    bash run/run3.sh

`run/setup.sh` installs what is missing and prints a table of every component against its pinned
version. It installs the R packages into `./R-lib` and the Python packages into `./.venv`, both
inside the repo, and never touches your own R library or Python environment. Running it again skips
anything already at its pin. Pass `--no-r` to either script to leave out R.

Before the first run, put the audio file in `data/audio/` (see `data/audio/README.md`), or pass
`--skip-audio`. If `simulation/input/` is empty, the first script generates the 12 files with
`data/generate.py` and checks them against `data/shasum.txt`.

For a quick check that everything works, `bash run/run3.sh --smoke` runs a small subset in a few
minutes and writes to `out/*_smoke/`.

Each script takes `--help`. Useful options: `--no-r`, `--skip-audio`, `--datasets A,B`,
`--slices 1,2`, `--k 4,8`, `--reps N`, `--fresh` (start over), `--mem-limit-gb N`.

### macOS

Needs the Xcode command line tools (`xcode-select --install`) and Homebrew (https://brew.sh).
`run/setup.sh` runs `brew install` for whatever of `cmake`, `r` and `python` is missing.

### Ubuntu 24.04 or newer

`run/setup.sh` runs `sudo apt-get install` for whatever is missing of `build-essential`, `cmake`,
`time`, `r-base`, `r-base-dev`, `python3-venv` and `python3-dev`. Ubuntu 24.04 or newer is needed
because numpy 2.5.5 requires Python 3.12. Ubuntu's own `r-base` can be older than the R 4.6.2 used
for GOLD; CRAN's Ubuntu repository (https://cran.r-project.org/bin/linux/ubuntu/) has a current R.
The R packages compile from source on first install, which takes a few minutes once.

### Windows

Use WSL2 with Ubuntu 24.04 (`wsl --install -d Ubuntu-24.04`), clone the repo inside the Linux file
system (for example under `~`, not `/mnt/c`), and follow the Ubuntu steps.

### Versions

R and Python themselves cannot be pinned through Homebrew or apt, so setup and the run scripts warn
when their versions differ from GOLD's (R 4.6.2, Python 3.13). The R packages (Rcpp 1.1.2,
Ckmeans.1d.dp 4.3.6, and Rdpack and rbibutils, which Ckmeans.1d.dp needs) and the Python packages
(numpy 2.5.5, nanobind 3.1.0, scikit-build-core 1.1.2, cmake 4.4.5, packaging 26.3, pathspec 1.1.1)
are installed at exact versions. The Python versions are the ones on the GOLD machine. Rcpp and
Ckmeans.1d.dp are recorded in GOLD's `env.txt`; the Rdpack and rbibutils pins are the CRAN releases
current on 18 November 2026, since GOLD did not record them.

The run scripts themselves need only Python 3.8+ with its standard library. numpy is used only by
the Python binding and by `data/generate.py`.

## Runtime and memory

GOLD ran on a MacBook Pro with an Apple M3 Max (12 performance and 4 efficiency cores) and 128 GB of
RAM, macOS 15.8.1, on 17 and 18 November 2026. The raw and sorted runs each took under 4 hours
of compute, and the bindings calibration less than 10 minutes. The sorted and bindings logs show
longer wall-clock spans because the Mac slept during part of those runs; the medians are unaffected.

The largest memory use is Ckmeans.1d.dp on the audio at k = 512, with a peak of 67.9 GB. lex1d's
exact dynamic program peaks at 15.7 GB on the same cell, and LEX at 0.61 GB. Before each fit the
scripts predict the size of its dynamic-programming table and skip the fit if it would exceed
100 GB or 85% of the machine's RAM, whichever is smaller (`--mem-limit-gb` changes the first). A
machine with less than about 80 GB of RAM therefore skips the largest R and exact cells instead of
swapping; skipped cells are marked in `results.csv`.

## Outputs

Each script writes to `out/raw/`, `out/sorted/` or `out/bindings/`:

| File | Contents |
|---|---|
| `results.csv` | One row per cell and method: median, minimum and maximum fit time over the timed rounds, SSE, gap to the exact SSE, peak memory, stage times, and checks. |
| `reps.csv` | One row per process (every round of every fit). |
| `summary.md` | Tables of gaps, speed-ups, memory and checks. |
| `prior_check.csv`, `prior_check.md` | SSE identity and time ratios against `results/prior/`. |
| `raw_vs_sorted.csv`, `raw_vs_sorted.md` | Sort cost per cell and method (written once both raw and sorted exist). |
| `inputs_manifest.csv` | SHA-256 of every prepared input file and the check that each sorted copy is a permutation of its raw slice. |
| `env.txt`, `env_<session>.txt` | Machine, compiler, R and Python versions, and SHA-256 of the lex1d and benchmark sources. |
| `run.log` | The full log. |
| `cells/` | Per-cell CSVs that `results.csv` and `reps.csv` are merged from. |
| `figures/` | Quick-look plots, if matplotlib is installed. |

## What results/gold contains

`results/gold/raw/`, `sorted/` and `bindings/` hold the files above from the GOLD run, unchanged,
except `cells/` and `figures/`, which are left out because `run/analyze.py` regenerates them from
`reps.csv`. GOLD's results show 4,624 cell and method rows per grid script, all ok, with
`api_match` 3,860/3,860 and SSE identical across all rounds in every row.

GOLD was run with an earlier copy of these scripts that carried version prefixes in their file names
(for example `bot_v24_lex_full.sh` for `run/raw.sh`), so those names appear in GOLD's `run.log` and
`env.txt`. The scripts were renamed for this repository; the method, the CSV columns and the lex1d
sources are the same.

`results/figures/` holds the four figures in the papers, drawn from GOLD.

## Data

**Simulation.** `data/generate.py` (seed 2048) writes 12 datasets of 2,080,768 values each: ten
continuous and two discrete. The reference files were generated on the GOLD Mac with NumPy 2.3.5;
`data/shasum.txt` holds their SHA-256. Files regenerated with another NumPy version or on another
platform can differ in the last digit of some values; the run then warns and continues, and its
results will not be bit-identical to GOLD. See `data/README.md`.

**Audio.** 8,168,256 samples of a recording of the varnam "Dharini" in raga Abhogi, from the
Carnatic Varnam Dataset by Xavier Serra, Gopala Krishna Koduri, Vignesh Ishwar and Joan Serrà
(doi:10.34810/DATA2311), licensed CC BY 4.0. The file is `data/audio/dharini-abhogi.txt.gz`; its
SHA-256 is checked before use. See `data/audio/README.md`.

## License

The code (`run/`, `bench/`, `lex1d/`, `data/generate.py`) is under the MIT License (see `LICENSE`).

The papers, talk, figures and results data are under Creative Commons Attribution 4.0 International
(see `LICENSE-CC-BY-4.0`), © 2026 Sriram Natarajan.

The audio in `data/audio/` is under CC BY 4.0 by its original authors, as stated in
`data/audio/README.md`.
