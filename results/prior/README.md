# Earlier Mac runs (identity and drift check)

`prior_mac.csv` holds SSEs and fit times from earlier benchmark runs on the same Mac (Apple M3 Max)
that used the same frozen lex1d C++ sources. `run/analyze.py` compares every new run against it and
writes `prior_check.csv` and `prior_check.md` into the output folder: whether each SSE is bit-identical,
and the ratio of the new fit time to the earlier one. On another machine the SSEs should still match;
the time ratios will not.

The `source` column names the earlier run:

- `v15`: the main 84-slice grid (ckmeans_exact, lex_plain, lex_hybrid M=4096, Ckmeans.1d.dp).
  `time_raw_s` = median time on unsorted input, `time_presorted_s` = median on presorted input.
- `v21`: the M sweep (slice 7, 10 continuous datasets, M = 1024 ... 8192, k = 64/256/512; single fit,
  timer included the sort) and the audio k = 512 memory run.
- `v19_mem`: memory runs (Gaussian slices and audio, k = 8/64/256/512, one process per fit).
- `v23_rbind`: the lex1d R binding and the k = 16 Ckmeans.1d.dp drift cells.

In `v15`, lex_hybrid on the two discrete datasets recorded the effective M (= D); here those 80 rows
carry the requested M = 4096, which is what the current scripts record.

The CSV columns `sse_v24`, `time_v24` and `time_ratio_v24_over_prior` in `prior_check.csv` hold the new
run's values; the names are kept so the files match `results/gold/`.
