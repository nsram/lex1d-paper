#!/usr/bin/env bash
# Second real dataset: the audio protocol on one GPT-2 Large weight tensor (h.0.mlp.c_fc.weight,
# 1280 x 5120 = 6,553,600 float32 values, raw input order). Same solvers as the audio section
# (Ckmeans.1d.dp in R, ckmeans_exact, lex_plain, lex_hybrid at M = 1,024 ... 16,384 with 4,096 the
# default), k = 4 ... 512, one warm-up and 3 timed rounds per cell, peak RSS per fit.
# From the repo root:   bash run/gpt2.sh          (--smoke for a 65,536-value check; --help for options)
# Fetches the tensor into data/gpt2/ first if it is missing (run/gpt2_fetch.py, about 26 MB over HTTPS).
# Results: ./out/gpt2/   Re-running resumes. The results used in the paper are committed in results/gpt2/.
MODE=gpt2
# shellcheck source=run/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
