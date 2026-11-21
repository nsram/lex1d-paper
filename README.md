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
| `bench/` | `fit.cpp`, the single-fit driver; `refine_fit.cpp`, the Refine-ablation driver for run 4; `refine_ltr.cpp`, an exploratory left-to-right Refine variant used only by run 4; `precgroup_fit.cpp`, the precision-grouping driver for run 5; and the `CMakeLists.txt` that builds them with lex1d. |
| `run/` | Setup, run and analysis scripts (see below). |
| `data/` | The simulation generator, its checksums and slice counts, `audio/` for the real audio file, and `gpt2/` for the GPT-2 Large weight tensor (fetched by `run/gpt2.sh`; see `data/gpt2/README.md`). |
| `simulation/input/` | The 12 generated simulation files. Not in git; created on the first run. |
| `results/gold/` | Outputs of the GOLD run used in the papers: `raw/`, `sorted/`, `bindings/`, and `refine/` (run 4). |
| `results/gpt2/` | Outputs of the GPT-2 Large run (`bash run/gpt2.sh`), the second real dataset in the papers. |
| `results/figures/` | The figures in the papers. |
| `paper/` | LaTeX sources and PDFs of the technical and expository papers. |
| `talk/` | The talk, as HTML and PDF. |
| `requirements.txt`, `requirements-r.txt` | Pinned Python and R package versions (the GOLD versions). |

## The benchmark

Four scripts share one engine (`run/common.sh`, `run/run.py`):

- `run/raw.sh`: the full grid with every fit on the values in file order.
- `run/sorted.sh`: the same grid with every fit on the same values presorted, which separates the
  cost of sorting.
- `run/bindings.sh`: the same fits through lex1d's R and Python bindings, to measure binding overhead.
- `run/run4.sh`: a fourth run, lex_hybrid only, that records the coarse-DP SSE (after Collapse(M)+DP(k),
  before Refine) as well as the final SSE, so the papers can report how much Refine moves the needle.
  The grid is the 12 simulation files (10 continuous and 2 discrete) × 7 slices plus the audio file,
  at M = 4,096, 8,192 and 16,384 and k = 4 to 512. There is no weighted section and no extra M-sweep.
  In the same process it also runs an exploratory left-to-right Refine from the same coarse-DP bounds
  (`bench/refine_ltr.cpp`, a copy of frozen refine.cpp whose only change is the sweep direction;
  every tie rule is unchanged). Frozen lex1d itself is not modified. The variant is labelled exploratory
  in the outputs.
- `run/run5.sh`: a fifth, exploratory run (not GOLD) on the audio only, described under "Run 5" below.
- `run/gpt2.sh`: the second real dataset, one GPT-2 Large weight tensor (6,553,600 values), run with
  the audio protocol (all solvers, M = 1,024 to 16,384, k = 4 to 512, 3 timed rounds). It fetches the
  tensor into `data/gpt2/` if missing and writes to `out/gpt2/`; the paper's run is committed in
  `results/gpt2/`. Details in `data/gpt2/README.md`.

The main grid covers the 12 simulated datasets, each cut into 7 slices of 2^14 to 2^20 values, with
k = 4 to 512, plus an M sweep, the audio file, and a weighted subset. Each cell of the first three
runs compares LEX (`lex_hybrid`, M = 4,096, 8,192 and 16,384, and 1,024 and 2,048 in the M sweep),
plain LEX (`lex_plain`), lex1d's exact dynamic program (`ckmeans_exact`) and the R package
Ckmeans.1d.dp 4.3.6. Every fit runs in its own process under `/usr/bin/time`, so each has its own
peak memory. Each cell in the first three runs has one warm-up round and 3 timed rounds, with the
method order rotated each round. Run 4 uses one warm-up round and one timed round by default (pass
`--reps 3` for the same timing protocol): the SSE is deterministic, GOLD already showed it identical
across three rounds, and Refine timing is secondary.

Before measuring, the scripts build lex1d and the driver in Release mode with strict floating point
(`-ffp-contract=off`) and run lex1d's 6 C++ test suites. On the warm-up round the driver also calls
the public lex1d function and checks that it gives the same answer as the instrumented copy it times
(the `api_match` column).

`run/run3.sh` runs the first three scripts in turn, and keeps the machine awake while it does
(`caffeinate -dims` on macOS, `systemd-inhibit` on Linux). `run/run4.sh` is the same kind of one-command
entry point for the Refine ablation, and uses the same keep-awake hold. Each script writes finished
cells to disk as it goes, so running the same command again resumes where it stopped.

## Setup and run

From the repo root:

    bash run/setup.sh
    bash run/run3.sh
    bash run/run4.sh

`run/setup.sh` installs what is missing and prints a table of every component against its pinned
version. It installs the R packages into `./R-lib` and the Python packages into `./.venv`, both
inside the repo, and never touches your own R library or Python environment. Running it again skips
anything already at its pin. Pass `--no-r` to either script to leave out R.

Before the first run, put the audio file in `data/audio/` (see `data/audio/README.md`), or pass
`--skip-audio`. If `simulation/input/` is empty, the first script generates the 12 files with
`data/generate.py` and checks them against `data/shasum.txt`.

For a quick check that everything works, `bash run/run3.sh --smoke` or `bash run/run4.sh --smoke`
runs a small subset in a few minutes and writes to `out/*_smoke/`. (Smoke truncates the inputs, so
those SSE values are not compared with GOLD.)

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

## Proof checks

One command runs every check of the papers' stated results, from the repo root:

    bash run/checks.sh

It needs the lex1d Python binding in `.venv` (`bash run/setup.sh` first) and sympy and pandas,
which it installs into `.venv` if they are missing. It runs five scripts, prints a summary, and
exits nonzero if any check fails. The whole run takes about 15 seconds.

- `run/check_propositions.py`: the technical paper's propositions (Appendix A, Table 7). It
  verifies the merge-cost and transfer identities with sympy, compares the exact DP to brute force
  on tiny inputs, runs random cases through the lex1d Python binding (seed 20261116) for exactness
  when D ≤ M, LEX never worse than Collapse, Refine never raising SSE, and Collapse being
  hierarchical, and checks the DP-table memory formulas against `results/gold/raw/results.csv`.
  Results go to `out/checks/propositions/`.
- `run/check_move_rule.py`: Lemma 1, the transfer formula (7) against brute-force SSE in 20,000
  random cases, the move-sign rule (b) and its counterexample (c); and the two-copy case of
  Proposition 1, symbolically (sympy) and on 6,000 edge cases. Exact rational arithmetic.
- `run/check_no_split_duplicates.py`: Corollary 1. Over 8,591 small partitions in which no single
  transfer pays, no two neighboring bins share a value unless both hold only that value. Exact
  rational arithmetic.
- `run/check_expository_numbers.py`: numbers in the expository paper that can be recomputed from
  scratch: the Refine move counts 8, 20, 40, 70, 112 for windows of 3 to 7 bins, the Lemma 1(c)
  example, and Exercises 4, 5 and 7.
- `run/check_expository_examples.py`: every worked example and number that the expository paper
  lists in its Appendix A (Table 10), one section per row: the hand DP on six values, contiguity
  and non-nesting, the quadrangle inequality (80,000 random quadruples) and monotone splits, the
  SMAWK pseudocode against brute-force row minima, the ten-value LEX trace and the coarse DP for
  every M, the Figure 2 toy example, the atom endpoint property, the transfer examples, the memory
  budgets, and the smaller hand illustrations. Each value is compared with the value printed in the
  paper; the traces are also checked against the lex1d Python binding. Seeds 20261117, 1 and
  20261120. Results go to `out/checks/expository_examples/`.

## Run 4 numbers

`bash run/run4_numbers.sh` computes every number the papers quote from run 4, the diagnostic run that
records the coarse DP's error before Refine: Table 3 of the technical paper (coarse and final error and
the share Refine removed, by k), the regressions of the coarse error on k and M, the error ratios per
doubling of M and k, the left-to-right sweep comparison, the discrete and audio cells, and a cross-check
of the final error against `results/gold/raw/results.csv`. It reads only `results/gold/refine/results.csv`
and that file, uses no timing column, and takes a few seconds. Results go to `out/run4_numbers/results.json`
and `out/run4_numbers/summary.md`. It uses `.venv` (creating it from Python 3.12+ if needed; `run/setup.sh`
reuses it) and installs numpy, pandas and statsmodels into it if they are missing.

## Runtime and memory

GOLD ran on a MacBook Pro with an Apple M3 Max (12 performance and 4 efficiency cores) and 128 GB of
RAM, macOS 15.8.1, on 17 and 18 November 2026. The raw and sorted runs each took under 4 hours
of compute, and the bindings calibration less than 10 minutes. Run 4 is much smaller (lex_hybrid only,
2,040 cells, one warm-up and one timed round): summing GOLD's own lex_hybrid fit times gives about 8
minutes of compute, plus process overhead, so about 15–25 minutes on that machine. The exploratory
left-to-right Refine runs in the same process from a copy of the coarse bounds, so it does not add a
process; GOLD's Refine times summed to about 1 second, and doubling that is a few extra seconds, not a
change to the 15–25 minute estimate. When M is at least the number of atoms the coarse DP is already
the exact DP and the gap is 0.

The largest memory use is Ckmeans.1d.dp on the audio at k = 512, with a peak of 67.9 GB. lex1d's
exact dynamic program peaks at 15.7 GB on the same cell, and LEX at 0.61 GB. Before each fit the
scripts predict the size of its dynamic-programming table and skip the fit if it would exceed
100 GB or 85% of the machine's RAM, whichever is smaller (`--mem-limit-gb` changes the first). A
machine with less than about 80 GB of RAM therefore skips the largest R and exact cells instead of
swapping; skipped cells are marked in `results.csv`.

## Run 5: precision grouping (exploratory)

`bash run/run5.sh` takes about 2 minutes. It rounds each audio value to 5 significant digits and turns
each run of equal rounded values in the sorted data into one atom (552,603 atoms instead of 7,295,677
distinct values). Each atom carries the count and the mean of its true values, and lex_hybrid (M = 4,096)
runs on the atoms with weights, so a bin never splits an atom. The SSE stays exact on the real values:
the weighted SSE plus the within-atom sum of squares. That sum is checked against the SSE recomputed on
the raw values from the mapped cuts, and must agree to 1e-12. Run 5 compares this with plain lex_hybrid
at k = 64, 256 and 512, with one warm-up round and 3 timed rounds, and the variant order alternates.
The plain variant's SSE must equal GOLD's bit for bit. Results go to `out/precgroup/`: `summary.md`
(medians, speed-ups, gaps to the exact SSE, and the checks), `runs.csv`, `env.txt` and `run.log`.

## Measurement details

These details were in the paper's experimental-setup section and now live here.

- **Machine.** MacBook Pro, Apple M3 Max (12 performance and 4 efficiency cores), 128 GB of RAM,
  macOS 15.8.1, on AC power.
- **Compiler.** Apple clang 17.0.0, with floating-point contraction off (`-ffp-contract=off`), so a
  multiply and an add are never fused into one instruction with a single rounding. Bit-identity
  with the Scala reference and across the bindings depends on this.
- **Threads.** LEX, lex1d's exact DP and Ckmeans.1d.dp are single-threaded; Ckmeans.1d.dp's own
  README describes it as running on a single core.
- **Timing.** Every fit runs on unsorted input with the sort included: one warm-up run and three
  timed runs per cell and solver, each in its own process; the reported time is the median of the
  three. Ckmeans.1d.dp is timed inside R around the call. LEX and the exact DP are timed in a C++
  driver that uses a stage-instrumented copy of lex1d and records each stage's time; on the warm-up
  run the driver also calls the public lex1d function and checks that it returns the same result
  (3,860 of 3,860 checks passed in GOLD). Every fit is repeated on presorted copies of the same
  inputs to measure the cost of the sort.
- **Memory.** Peak resident set size of every fit, read from `/usr/bin/time -l` (macOS) or
  `/usr/bin/time -v` (Linux) in each of its four processes; the paper reports the median over the
  four. Process baselines (the C++ driver, R or Python, plus the loaded data) are measured separately
  with load-only processes. The paper reports memory in MB (10^6 bytes) and GB (10^9 bytes).
- **Data precision.** The synthetic datasets are written with 18 decimals; the decoded audio is
  stored with 8 decimals.

## Outputs

The first three scripts write to `out/raw/`, `out/sorted/` or `out/bindings/`; run 4 writes to
`out/refine/`:

| File | Contents |
|---|---|
| `results.csv` | One row per cell and method: median, minimum and maximum fit time over the timed rounds, SSE, gap to the exact SSE, peak memory, stage times, and checks. Run 4 also has `coarse_sse`, `coarse_gap_pct`, the reduction factor and the percent of the coarse gap that Refine removed. |
| `reps.csv` | One row per process (every round of every fit). |
| `summary.md` | Tables of gaps, speed-ups, memory and checks. |
| `gold_check.csv`, `gold_check.md` | SSE identity and time ratios against the GOLD run in `results/gold/`. Run 4 compares final SSE and bin sizes to GOLD `raw` lex_hybrid rows, bit for bit. |
| `refine_ablation.md` | Run 4 only: per-k/M summary of the coarse gap, the final gap, the reduction factor and the percent of the gap Refine removed, with continuous, discrete and audio shown separately, plus an exploratory comparison of left-to-right vs standard right-to-left Refine. |
| `raw_vs_sorted.csv`, `raw_vs_sorted.md` | Sort cost per cell and method (written once both raw and sorted exist). |
| `inputs_manifest.csv` | SHA-256 of every prepared input file and the check that each sorted copy is a permutation of its raw slice. |
| `env.txt`, `env_<session>.txt` | Machine, compiler, R and Python versions, and SHA-256 of the lex1d and benchmark sources. |
| `run.log` | The full log. |
| `cells/` | Per-cell CSVs that `results.csv` and `reps.csv` are merged from. |
| `figures/` | Quick-look plots, if matplotlib is installed. |

## What results/gold contains

`results/gold/raw/`, `sorted/` and `bindings/` hold the files above from the first three GOLD runs,
unchanged, except `cells/` and `figures/`, which are left out because `run/analyze.py` regenerates
them from `reps.csv`. GOLD's results show 4,624 cell and method rows per grid script, all ok, with
`api_match` 3,860/3,860 and SSE identical across all rounds in every row. Run 4 is a later addition;
its outputs are in `results/gold/refine/`: `results.csv`, `gold_check.csv` and `gold_check.md` (final SSE
and bin sizes identical to GOLD's raw lex_hybrid rows in 2,040 of 2,040 cells), `refine_ablation.md`,
`summary.md`, `env*.txt` and `inputs_manifest.csv`, unchanged. `reps.csv`, `run.log`, `cells/` and
`figures/` are left out to keep the repository small; the papers use only `results.csv`, and none of
run 4's timing columns.

GOLD was run with an earlier copy of these scripts that carried version prefixes in their file names
(for example `bot_v24_lex_full.sh` for `run/raw.sh`), so those names appear in GOLD's `run.log` and
`env.txt`. The scripts were renamed for this repository; the method, the CSV columns and the lex1d
sources are the same.

`results/figures/` holds the four figures in the papers, drawn from GOLD.


## What results/gpt2 contains

`results/gpt2/` holds the GPT-2 Large run used in the papers (`bash run/gpt2.sh`, 21 November 2026, same
machine as GOLD): `results.csv`, `reps.csv`, `summary.md`, `env*.txt`, `run.log` and `inputs_manifest.csv`,
unchanged from `out/gpt2/`. As in `results/gold/`, `cells/` is left out; its rows are all in `reps.csv`. All 64 cell and method rows are ok with 3 timed rounds, and SSE is identical across rounds.
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

**GPT-2 Large weights.** 6,553,600 float32 values (1,280 × 5,120) of tensor `h.0.mlp.c_fc.weight` from
GPT-2 Large (openai-community/gpt2-large on Hugging Face, commit 32b71b12, MIT license, Copyright OpenAI).
The tensor is not committed: `run/gpt2.sh` fetches its 26 MB by HTTPS range reads of `model.safetensors`
and checks its SHA-256. See `data/gpt2/README.md`.

## License

The code (`run/`, `bench/`, `lex1d/`, `data/generate.py`) is under the MIT License (see `LICENSE`).

The papers, talk, figures and results data are under Creative Commons Attribution 4.0 International
(see `LICENSE-CC-BY-4.0`), © 2026 Sriram Natarajan.

The audio in `data/audio/` is under CC BY 4.0 by its original authors, as stated in
`data/audio/README.md`.
