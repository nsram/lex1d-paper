# Identity and drift vs earlier Mac runs (out_v24_sorted)

v24 time is the median of the timed rounds (one fit per process). Earlier times: v15 = median of in-process repeats (presorted_s); v19/v21/v23 = single fits. Same Mac, different day.

| earlier run | method | cells | SSE identical | sizes identical | time ratio v24/earlier (median) | min | max |
|---|---|---|---|---|---|---|---|
| v15 | Ckmeans.1d.dp | 672 | 672/672 | 672/672 | 1.012 | 0.5117 | 1.451 |
| v15 | ckmeans_exact | 672 | 672/672 | 672/672 | 1.002 | 0.8053 | 1.443 |
| v15 | lex_hybrid | 672 | 672/672 | 672/672 | 1.008 | 0.8233 | 1.38 |
| v15 | lex_plain | 672 | 672/672 | 672/672 | 1.007 | 0.78 | 1.442 |
| v19_mem | Ckmeans.1d.dp | 31 | 31/31 |  |  |  |  |
| v19_mem | ckmeans_exact | 32 | 32/32 |  |  |  |  |
| v19_mem | lex_hybrid | 32 | 32/32 |  |  |  |  |
| v19_mem | lex_plain | 32 | 32/32 |  |  |  |  |
| v21 | lex_hybrid | 120 | 120/120 |  |  |  |  |
| v21_mem | Ckmeans.1d.dp | 1 | 1/1 |  |  |  |  |
| v21_mem | lex_hybrid | 1 | 1/1 |  |  |  |  |

