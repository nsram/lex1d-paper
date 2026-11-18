# Identity and drift vs earlier Mac runs (out_v24_raw)

v24 time is the median of the timed rounds (one fit per process). Earlier times: v15 = median of in-process repeats (time_s, unsorted); v19/v21/v23 = single fits. Same Mac, different day.

| earlier run | method | cells | SSE identical | sizes identical | time ratio v24/earlier (median) | min | max |
|---|---|---|---|---|---|---|---|
| v15 | Ckmeans.1d.dp | 672 | 672/672 | 672/672 | 1.008 | 0.5127 | 1.217 |
| v15 | ckmeans_exact | 672 | 672/672 | 672/672 | 1.006 | 0.7006 | 1.235 |
| v15 | lex_hybrid | 672 | 672/672 | 672/672 | 1.015 | 0.8451 | 1.354 |
| v15 | lex_plain | 672 | 672/672 | 672/672 | 1.012 | 0.8588 | 1.402 |
| v19_mem | Ckmeans.1d.dp | 31 | 31/31 |  | 1.001 | 0.9724 | 1.02 |
| v19_mem | ckmeans_exact | 32 | 32/32 |  | 1.001 | 0.9536 | 1.023 |
| v19_mem | lex_hybrid | 32 | 32/32 |  | 1.005 | 0.6196 | 1.043 |
| v19_mem | lex_plain | 32 | 32/32 |  | 1.006 | 0.9523 | 1.053 |
| v21 | lex_hybrid | 120 | 120/120 |  | 1.031 | 0.8935 | 1.068 |
| v21_mem | Ckmeans.1d.dp | 1 | 1/1 |  | 1.013 | 1.013 | 1.013 |
| v21_mem | lex_hybrid | 1 | 1/1 |  | 1.028 | 1.028 | 1.028 |

