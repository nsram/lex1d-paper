# Paired-move Refine ablation

Outputs of `bash run/ablation.sh`, run on an Apple M3 Max (macOS) on 2026-11-22
with lex1d commit 8a691ee. `env.txt` has the full environment.

The run compares Refine with all 8 window moves against Refine with the 4 single-cut
moves only. Datasets: uniform, Gaussian and lognormal (continuous) slices at
N = 2^16 and 2^20. k = 8, 64, 256, 512. Starts: Collapse (`lex_plain`) and the
default coarse start with M = 4096 (`lex_hybrid`). 96 rows, all checks passed.

Files:

- `results.csv`: one row per cell and variant, with SSE, exact SSE, per-move
  accepted counts `m0..m7` and computed SSE drops `g0..g7`.
- `moves_8way.csv`: pooled counts and SSE drop for each of the 8 moves.
- `moves_3way.csv`: the same grouped into single (moves 1-4), paired
  shrink/grow (0, 7) and paired translate (5, 6).
- `summary.txt`: REE comparison and move shares, as reported in Section 6.2
  of the paper.
- `env.txt`, `run.log`: environment and run log.

A rerun on Linux (Debian, x86-64) gave identical SSE values and move counts in
all 96 rows.

To rerun from the repository root: `bash run/ablation.sh` (outputs in
`out/ablation/`, about 3 to 6 minutes on the Mac).
