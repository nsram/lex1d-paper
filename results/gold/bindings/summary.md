# bot_v24 summary (out_v24_bindings, input: bindings)

Processes: 78. Sessions: 1 (20261118T105221-32750). First row 2026-11-18T10:52:50-05:00, last 2026-11-18T11:04:45-05:00.

## Checks

- cell x method rows: 18; ok 18; skipped by the memory guard 0; failed/partial 0
- api_match (public API == instrumented copy, warm-up round): 6/6
- SSE and sizes identical across all rounds: 18/18
- D equals dataset_slice_counts.csv: 18/18
- C++ did_sort values seen: ['1'] (raw input: 1; presorted input: 0)
- lex1d Result::presorted (public API, warm-up round) values seen: ['0'] (raw: 0; presorted: 1)
- presort flag mismatches: 0

## Section bindings

| dataset | slice | k | method | fit s (median) | min | max | post-sort s | gap % | peak MiB | above baseline MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| audio | 0 | 8 | lex_hybrid M=4096 | 2.789 | 2.786 | 311 | 2.317 |  | 570.7 | 507.2 |
| audio | 0 | 8 | py_hybrid M=4096 | 2.783 | 2.775 | 2.791 |  |  | 596 | 506.8 |
| audio | 0 | 8 | rb_hybrid M=4096 | 2.895 | 2.894 | 2.899 |  |  | 686.2 | 538 |
| audio | 0 | 64 | lex_hybrid M=4096 | 2.826 | 2.797 | 2.845 | 2.349 |  | 572 | 508.4 |
| audio | 0 | 64 | py_hybrid M=4096 | 2.819 | 2.811 | 3.168 |  |  | 597.2 | 508 |
| audio | 0 | 64 | rb_hybrid M=4096 | 2.921 | 2.915 | 3.01 |  |  | 686.2 | 538.1 |
| audio | 0 | 512 | lex_hybrid M=4096 | 2.967 | 2.952 | 2.988 | 2.492 |  | 586.3 | 522.8 |
| audio | 0 | 512 | py_hybrid M=4096 | 2.968 | 2.96 | 2.981 |  |  | 610.4 | 521.2 |
| audio | 0 | 512 | rb_hybrid M=4096 | 3.125 | 3.113 | 3.137 |  |  | 686.8 | 538.7 |
| gaussian_continuous | 7 | 8 | lex_hybrid M=4096 | 0.2751 | 0.274 | 0.2812 | 0.2131 |  | 77.55 | 68.3 |
| gaussian_continuous | 7 | 8 | py_hybrid M=4096 | 0.2767 | 0.2765 | 0.2782 |  |  | 103.1 | 68.33 |
| gaussian_continuous | 7 | 8 | rb_hybrid M=4096 | 0.2916 | 0.2885 | 0.2917 |  |  | 165.4 | 71.41 |
| gaussian_continuous | 7 | 64 | lex_hybrid M=4096 | 0.2803 | 0.2785 | 0.282 | 0.2186 |  | 78.48 | 69.23 |
| gaussian_continuous | 7 | 64 | py_hybrid M=4096 | 0.2822 | 0.2797 | 0.283 |  |  | 103.9 | 69.06 |
| gaussian_continuous | 7 | 64 | rb_hybrid M=4096 | 0.2959 | 0.2953 | 0.2962 |  |  | 165.8 | 71.84 |
| gaussian_continuous | 7 | 512 | lex_hybrid M=4096 | 0.3193 | 0.3192 | 0.3208 | 0.2574 |  | 85.92 | 76.67 |
| gaussian_continuous | 7 | 512 | py_hybrid M=4096 | 0.3205 | 0.3198 | 0.3232 |  |  | 111.1 | 76.33 |
| gaussian_continuous | 7 | 512 | rb_hybrid M=4096 | 0.3397 | 0.3384 | 0.3427 |  |  | 163.3 | 69.34 |


**Binding overhead (median fit time; same SSE as C++?)**

| dataset | k | C++ s | R binding s | R/C++ | R same SSE | Python s | Py/C++ | Py same SSE |
|---|---|---|---|---|---|---|---|---|
| audio | 8 | 2.789 | 2.895 | 1.038 | yes | 2.783 | 0.9979 | yes |
| audio | 64 | 2.826 | 2.921 | 1.034 | yes | 2.819 | 0.9975 | yes |
| audio | 512 | 2.967 | 3.125 | 1.053 | yes | 2.968 | 1 | yes |
| gaussian_continuous | 8 | 0.2751 | 0.2916 | 1.06 | yes | 0.2767 | 1.006 | yes |
| gaussian_continuous | 64 | 0.2803 | 0.2959 | 1.056 | yes | 0.2822 | 1.007 | yes |
| gaussian_continuous | 512 | 0.3193 | 0.3397 | 1.064 | yes | 0.3205 | 1.004 | yes |

