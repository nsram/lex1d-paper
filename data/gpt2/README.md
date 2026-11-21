# GPT-2 Large weights: the second real dataset

One float32 weight tensor from GPT-2 Large, benchmarked with the same protocol as the audio recording.

## Run

From the repo root, on the Mac:

    bash run/gpt2.sh

Nothing else needs to be passed. Setup is the same as for the other runs (`bash run/setup.sh` once:
R with Ckmeans.1d.dp at the pinned version, a C++ compiler, cmake, python3). The script:

1. checks `lex1d/` against commit 8a691ee and builds `bench/fit.cpp` (runs the 6 C++ test suites);
2. fetches the tensor into this folder if it is missing (`run/gpt2_fetch.py`: HTTPS range reads of
   `model.safetensors`, about 26 MB; pass nothing). It checks dtype F32, shape 1280 x 5120, and the
   SHA-256 of the tensor bytes, and stops if D <= 4,096;
3. runs the audio protocol on the 6,553,600 values in stored (row-major) order: Ckmeans.1d.dp 4.3.6 in R,
   ckmeans_exact, lex_plain, and lex_hybrid at M = 1,024, 2,048, 4,096 (default), 8,192 and 16,384, for
   k = 4, 8, 16, 32, 64, 128, 256, 512; raw input order; per cell one warm-up round and 3 timed rounds,
   methods interleaved, one process per fit under `/usr/bin/time -l` for peak memory; plus the load-only
   baselines. This is the `audio` section of the GOLD raw run with the data swapped.

`bash run/gpt2.sh --smoke` is a one-minute check on the first 65,536 values (k = 4 and 64, one timed round).
Re-running resumes; `--fresh` starts over.

## Memory

Ckmeans.1d.dp keeps two k x N matrices, about 16kN bytes: 54 GB at k = 512 (the audio run peaked at
67.9 GB for N = 8.2 million). The run assumes a Mac with 128 GB of RAM, as for GOLD. The log prints total
and available memory at the start. Before each cell, any fit whose predicted table plus a 2 GB margin
exceeds the memory available at that moment is skipped and recorded as `skipped_mem` (with the numbers)
rather than run into swap. Quit other large apps before starting. To retry a skipped cell, delete its
CSV under `out/gpt2/cells/gpt2/` and run the command again.

## Runtime

About 45 to 60 minutes on the M3 Max, plus a few minutes for the build and tests: the audio section
took 56 minutes for N = 8,168,256, and every solver here scales about linearly in N (6,553,600 / 8,168,256
= 0.80). Most of it is Ckmeans.1d.dp and ckmeans_exact at k = 256 and 512.

## Outputs

`out/gpt2/`: `results.csv` (one row per k and method: median, min and max fit time, SSE, gap to the
exact SSE, peak memory, stage times), `summary.md` (section "gpt2"), `cells/`, `reps.csv`,
`inputs_manifest.csv`, `env.txt`, `run.log`. The tensor's hashes and statistics are in
`data/gpt2/gpt2_stats.json`.

The results used in the technical paper are committed in `results/gpt2/` (see below); a new run writes to
`out/gpt2/` and never touches them.

## Committed results

`results/gpt2/` holds the paper's run (21 November 2026, M3 Max, 47 min, rc 0, all 9 cells and 64 cell × method
rows ok, 3 timed rounds each): `results.csv`, `reps.csv`, `summary.md`, `env.txt`, `env_<session>.txt`,
`run.log` and `inputs_manifest.csv`, unchanged from `out/gpt2/`. As in `results/gold/`, `cells/` is left out;
its rows are all in `reps.csv`.
`data/gpt2/gpt2_stats.json` is the fetch record of the same run.

## Source and license

GPT-2 Large, https://huggingface.co/openai-community/gpt2-large, MIT license (Copyright OpenAI).
File `model.safetensors` at commit `32b71b12589c2f8d625668d2335a01cac3249519`: 3,247,159,078 bytes,
SHA-256 `5f47f3e12f91cd33b662ce7e433b6150ad5512b5884a2cee961b50e9c3bbebce` (Hugging Face LFS hash;
`python3 run/gpt2_fetch.py --full` downloads the whole file and checks it). Tensor `h.0.mlp.c_fc.weight`
(`transformer.h.0.mlp.c_fc.weight` in the PyTorch module), F32, shape [1280, 5120], header 43,806 bytes,
data offsets 30,470,144 to 56,684,544.

- `gpt2-large_h0_mlp_c_fc_weight.f32le`: the tensor's 26,214,400 bytes as stored (little-endian float32,
  row-major), SHA-256 `3b5cac6f1a695c6d6493aa65cdabec45b3a6dd541fee24604e03d208a5d28557`.
  It is not committed (ignored in `.gitignore`); if it is absent the run fetches it and checks this hash.
- As float64 (exact conversion, row-major, little-endian), SHA-256
  `140e15241b545ad369fd92fad6154b4785024f468fe61afb4e0eaf4c2dc6731e`.
- N = 6,553,600; D = 6,275,774 distinct values; min -0.50753, max 0.48709, mean 9.06e-05, sd 0.047466,
  excess kurtosis 0.240.
