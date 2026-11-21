# Refine vs coarse-DP gap (GOLD run 4)

For each lex_hybrid cell: the coarse-DP SSE is the instrumented partition after Collapse(M)+DP(k) and before Refine; the final SSE is after Refine. Gaps are 100 × (SSE − exact) / exact, using GOLD raw `ckmeans_exact` SSEs (this run does not re-run the exact DP). Reduction factor is coarse_gap / final_gap; percent of gap removed is 100 × (coarse_gap − final_gap) / coarse_gap. When M is at least the number of atoms the coarse DP is already exact (gap 0); those cells are counted separately and left out of the reduction statistics.

Cells: 2040 ok; already exact (M ≥ atoms, gap 0): 504; cells with a coarse gap: 1536.

## continuous (10 datasets)

**M = 4096** (549 cells with a coarse gap, 11 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 1.47e-05 (0–9.47e-05) | 0 (0–1.64e-05) | ∞ (1–∞) | 100 (0–100) | 11 (1–223) | 13 (0–370) | 9/70 |
| 8 | 8.49e-05 (0–3.03e-04) | 3.37e-07 (0–8.00e-05) | 371 (1.148–∞) | 99.73 (12.89–100) | 11 (1–250) | 3e+01 (0–695) | 2/70 |
| 16 | 3.44e-04 (9.84e-06–6.68e-04) | 2.55e-06 (0–1.99e-04) | 113.3 (1–∞) | 99.1 (0–100) | 1e+01 (1–543) | 61 (0–1351) | 0/70 |
| 32 | 0.00134 (1.19e-04–0.002588) | 4.52e-05 (0–4.49e-04) | 32.76 (2.453–∞) | 96.94 (59.24–100) | 18 (2–350) | 1e+02 (2–2427) | 0/70 |
| 64 | 0.005688 (1.31e-04–0.009797) | 3.81e-04 (0–0.001791) | 12.38 (3.6–∞) | 91.92 (72.22–100) | 23 (2–436) | 283 (5–5556) | 0/70 |
| 128 | 0.024 (0.002461–0.03501) | 0.001306 (0–0.004262) | 14.45 (5.303–∞) | 93.08 (81.14–100) | 19 (2–400) | 525 (14–8463) | 0/70 |
| 256 | 0.09771 (0.01112–0.1346) | 0.007897 (1.47e-04–0.01747) | 12.08 (4.797–264.3) | 91.72 (79.16–99.62) | 25 (3–363) | 1108 (35–15704) | 0/70 |
| 512 | 0.4023 (0.06848–0.5685) | 0.03852 (0.007345–0.07865) | 9.698 (5.492–26.98) | 89.69 (81.79–96.29) | 27 (3–354) | 2e+03 (98–28900) | 0/70 |


**M = 8192** (522 cells with a coarse gap, 38 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 2.68e-06 (0–2.36e-05) | 0 (0–4.40e-06) | inf (1–∞) | 100 (0–100) | 4 (1–112) | 4 (0–163) | 18/70 |
| 8 | 1.58e-05 (0–5.03e-05) | 4.18e-08 (0–2.72e-05) | 138.7 (1–∞) | 99.23 (0–100) | 6 (1–189) | 1e+01 (0–289) | 8/70 |
| 16 | 6.31e-05 (0–1.71e-04) | 1.06e-07 (0–1.07e-04) | 195.9 (1.376–∞) | 99.49 (27.32–100) | 6 (1–163) | 26 (0–655) | 5/70 |
| 32 | 2.61e-04 (0–7.48e-04) | 9.35e-06 (0–1.92e-04) | 18.54 (1–∞) | 94.6 (0–100) | 6 (1–191) | 6e+01 (0–1280) | 4/70 |
| 64 | 0.001175 (0–0.002376) | 6.48e-05 (0–4.84e-04) | 14.14 (1–∞) | 92.93 (0–100) | 8 (1–122) | 1e+02 (0–1765) | 3/70 |
| 128 | 0.004785 (8.52e-06–0.009214) | 2.72e-04 (0–0.001577) | 15.15 (1–∞) | 93.4 (0–100) | 10 (1–229) | 213 (0–3751) | 0/70 |
| 256 | 0.02049 (2.38e-04–0.03402) | 0.001623 (0–0.005983) | 11.71 (4.642–∞) | 91.46 (78.46–100) | 11 (2–236) | 445 (2–6523) | 0/70 |
| 512 | 0.07444 (0.001505–0.1325) | 0.006951 (0–0.01717) | 11.91 (5.82–∞) | 91.6 (82.82–100) | 14 (2–216) | 9e+02 (9–13158) | 0/70 |


**M = 16384** (441 cells with a coarse gap, 119 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 2.11e-07 (0–3.80e-06) | 0 (0–6.71e-07) | ∞ (1–∞) | 100 (0–100) | 2 (1–60) | 1 (0–86) | 27/70 |
| 8 | 1.89e-06 (0–1.21e-05) | 0 (0–4.72e-06) | inf (1–∞) | 99.98 (0–100) | 3 (1–51) | 4 (0–117) | 20/70 |
| 16 | 1.38e-05 (0–5.44e-05) | 0 (0–8.73e-06) | 93.92 (2.446–∞) | 98.94 (59.11–100) | 4 (1–124) | 1e+01 (0–280) | 15/70 |
| 32 | 4.17e-05 (0–1.44e-04) | 7.63e-07 (0–4.92e-05) | 19.91 (1–∞) | 94.98 (0–100) | 4 (1–121) | 18 (0–546) | 14/70 |
| 64 | 2.02e-04 (0–5.14e-04) | 5.90e-06 (0–1.46e-04) | 18.14 (1–∞) | 94.49 (0–100) | 4 (1–79) | 4e+01 (0–735) | 13/70 |
| 128 | 7.57e-04 (0–0.002312) | 3.94e-05 (0–2.69e-04) | 15.54 (1.012–∞) | 93.56 (1.18–100) | 5 (1–80) | 8e+01 (0–1713) | 10/70 |
| 256 | 0.003524 (0–0.008466) | 2.71e-04 (0–0.001351) | 12.64 (4.25–∞) | 92.09 (76.47–100) | 5 (1–83) | 2e+02 (0–3006) | 10/70 |
| 512 | 0.01454 (0–0.03362) | 0.001171 (0–0.004472) | 11.24 (4.84–∞) | 91.1 (79.34–100) | 7 (1–112) | 3e+02 (0–5658) | 10/70 |


## discrete (2 datasets)

**M = 4096** (0 cells with a coarse gap, 112 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 8 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 16 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 32 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 64 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 128 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 256 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 512 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |


**M = 8192** (0 cells with a coarse gap, 112 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 8 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 16 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 32 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 64 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 128 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 256 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 512 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |


**M = 16384** (0 cells with a coarse gap, 112 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 8 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 16 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 32 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 64 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 128 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 256 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |
| 512 | 0 (0–0) | 0 (0–0) | already exact |  | 1 (1–1) | 0 (0–0) | 14/14 |


## audio

**M = 4096** (8 cells with a coarse gap, 0 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 2.25e-05 (2.25e-05–2.25e-05) | 4.56e-09 (4.56e-09–4.56e-09) | 4926 (4926–4926) | 99.98 (99.98–99.98) | 587 (587–587) | 1168 (1168–1168) | 0/1 |
| 8 | 1.13e-04 (1.13e-04–1.13e-04) | 9.36e-06 (9.36e-06–9.36e-06) | 12.03 (12.03–12.03) | 91.69 (91.69–91.69) | 1149 (1149–1149) | 4148 (4148–4148) | 0/1 |
| 16 | 5.35e-04 (5.35e-04–5.35e-04) | 9.82e-06 (9.82e-06–9.82e-06) | 54.46 (54.46–54.46) | 98.16 (98.16–98.16) | 909 (909–909) | 7059 (7059–7059) | 0/1 |
| 32 | 0.001556 (0.001556–0.001556) | 8.47e-07 (8.47e-07–8.47e-07) | 1837 (1837–1837) | 99.95 (99.95–99.95) | 907 (907–907) | 13098 (13098–13098) | 0/1 |
| 64 | 0.007833 (0.007833–0.007833) | 1.13e-04 (1.13e-04–1.13e-04) | 69.55 (69.55–69.55) | 98.56 (98.56–98.56) | 976 (976–976) | 27159 (27159–27159) | 0/1 |
| 128 | 0.02573 (0.02573–0.02573) | 0.001609 (0.001609–0.001609) | 15.99 (15.99–15.99) | 93.75 (93.75–93.75) | 1368 (1368–1368) | 50809 (50809–50809) | 0/1 |
| 256 | 0.1091 (0.1091–0.1091) | 0.003855 (0.003855–0.003855) | 28.31 (28.31–28.31) | 96.47 (96.47–96.47) | 6490 (6490–6490) | 213409 (213409–213409) | 0/1 |
| 512 | 0.4332 (0.4332–0.4332) | 0.02774 (0.02774–0.02774) | 15.61 (15.61–15.61) | 93.6 (93.6–93.6) | 3089 (3089–3089) | 288571 (288571–288571) | 0/1 |


**M = 8192** (8 cells with a coarse gap, 0 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 1.66e-06 (1.66e-06–1.66e-06) | 4.56e-09 (4.56e-09–4.56e-09) | 363.7 (363.7–363.7) | 99.73 (99.73–99.73) | 232 (232–232) | 447 (447–447) | 0/1 |
| 8 | 1.83e-05 (1.83e-05–1.83e-05) | 1.36e-07 (1.36e-07–1.36e-07) | 134.9 (134.9–134.9) | 99.26 (99.26–99.26) | 110 (110–110) | 628 (628–628) | 0/1 |
| 16 | 1.12e-04 (1.12e-04–1.12e-04) | 7.54e-06 (7.54e-06–7.54e-06) | 14.89 (14.89–14.89) | 93.29 (93.29–93.29) | 399 (399–399) | 2934 (2934–2934) | 0/1 |
| 32 | 5.59e-04 (5.59e-04–5.59e-04) | 3.77e-07 (3.77e-07–3.77e-07) | 1483 (1483–1483) | 99.93 (99.93–99.93) | 678 (678–678) | 7815 (7815–7815) | 0/1 |
| 64 | 0.001776 (0.001776–0.001776) | 8.56e-05 (8.56e-05–8.56e-05) | 20.74 (20.74–20.74) | 95.18 (95.18–95.18) | 1242 (1242–1242) | 20019 (20019–20019) | 0/1 |
| 128 | 0.007423 (0.007423–0.007423) | 4.31e-04 (4.31e-04–4.31e-04) | 17.21 (17.21–17.21) | 94.19 (94.19–94.19) | 1417 (1417–1417) | 33537 (33537–33537) | 0/1 |
| 256 | 0.02914 (0.02914–0.02914) | 0.001362 (0.001362–0.001362) | 21.4 (21.4–21.4) | 95.33 (95.33–95.33) | 775 (775–775) | 60835 (60835–60835) | 0/1 |
| 512 | 0.1163 (0.1163–0.1163) | 0.006139 (0.006139–0.006139) | 18.94 (18.94–18.94) | 94.72 (94.72–94.72) | 1617 (1617–1617) | 133717 (133717–133717) | 0/1 |


**M = 16384** (8 cells with a coarse gap, 0 already exact). Each cell is median (min–max) over datasets; sweeps and moves are medians of those values.

| k | coarse gap % | final gap % | reduction factor | % of gap removed | median sweeps | median moves | already exact |
|---|---|---|---|---|---|---|---|
| 4 | 1.66e-06 (1.66e-06–1.66e-06) | 4.56e-09 (4.56e-09–4.56e-09) | 363.7 (363.7–363.7) | 99.73 (99.73–99.73) | 232 (232–232) | 447 (447–447) | 0/1 |
| 8 | 3.64e-06 (3.64e-06–3.64e-06) | 4.10e-11 (4.10e-11–4.10e-11) | 8.87e+04 (8.87e+04–8.87e+04) | 100 (100–100) | 168 (168–168) | 617 (617–617) | 0/1 |
| 16 | 2.35e-05 (2.35e-05–2.35e-05) | 9.50e-06 (9.50e-06–9.50e-06) | 2.476 (2.476–2.476) | 59.62 (59.62–59.62) | 137 (137–137) | 996 (996–996) | 0/1 |
| 32 | 1.45e-04 (1.45e-04–1.45e-04) | 1.20e-06 (1.20e-06–1.20e-06) | 120.8 (120.8–120.8) | 99.17 (99.17–99.17) | 398 (398–398) | 4691 (4691–4691) | 0/1 |
| 64 | 5.32e-04 (5.32e-04–5.32e-04) | 1.38e-05 (1.38e-05–1.38e-05) | 38.45 (38.45–38.45) | 97.4 (97.4–97.4) | 284 (284–284) | 5935 (5935–5935) | 0/1 |
| 128 | 0.001806 (0.001806–0.001806) | 1.05e-04 (1.05e-04–1.05e-04) | 17.19 (17.19–17.19) | 94.18 (94.18–94.18) | 486 (486–486) | 13608 (13608–13608) | 0/1 |
| 256 | 0.007957 (0.007957–0.007957) | 8.47e-04 (8.47e-04–8.47e-04) | 9.392 (9.392–9.392) | 89.35 (89.35–89.35) | 428 (428–428) | 27581 (27581–27581) | 0/1 |
| 512 | 0.02879 (0.02879–0.02879) | 0.002472 (0.002472–0.002472) | 11.64 (11.64–11.64) | 91.41 (91.41–91.41) | 807 (807–807) | 56578 (56578–56578) | 0/1 |


## Exploratory variant: left-to-right Refine vs standard right-to-left

Each cell starts both Refine directions from the same coarse-DP bounds. Tie rules are unchanged (larger bounds win; tie sweeps still push right). This is an exploratory variant in the paper-repo harness (`bench/refine_ltr.cpp`); frozen lex1d is the RTL code.

- cells with both directions: 2040
- partitions equal (LTR == RTL): 1449/2040
- partitions differ: 591/2040
- gap difference (LTR − RTL), percentage points: median 0, min -0.002918, max 0.002714; median |diff| 0, max |diff| 0.002918

By k (all datasets and M):

| k | cells | partitions differ | median LTR−RTL gap pp | signed max |diff| (signed) | median |diff| |
|---|---|---|---|---|---|
| 4 | 255 | 1/255 | 0 | 4.27e-06 | 0 |
| 8 | 255 | 6/255 | 0 | -1.27e-06 | 0 |
| 16 | 255 | 12/255 | 0 | -1.58e-04 | 0 |
| 32 | 255 | 42/255 | 0 | -7.70e-05 | 0 |
| 64 | 255 | 84/255 | 0 | -5.31e-04 | 0 |
| 128 | 255 | 114/255 | 0 | 8.27e-04 | 0 |
| 256 | 255 | 161/255 | 0 | -0.002217 | 7.52e-06 |
| 512 | 255 | 171/255 | 0 | -0.002918 | 3.58e-05 |


By dataset (all k and M; lognormal, exponential and weibull are the skewed continuous families):

| dataset | cells | partitions differ | median LTR−RTL gap pp | signed max |diff| (signed) | median |diff| |
|---|---|---|---|---|---|
| audio | 24 | 6/24 | 0 | -2.07e-04 | 0 |
| bimodal_gaussian_continuous | 168 | 61/168 | 0 | 0.002714 | 0 |
| exponential_continuous (skewed) | 168 | 52/168 | 0 | 0.001603 | 0 |
| gaussian_continuous | 168 | 59/168 | 0 | -0.002918 | 0 |
| gmm_continuous | 168 | 53/168 | 0 | -0.002642 | 0 |
| lognormal_continuous (skewed) | 168 | 51/168 | 0 | 0.001333 | 0 |
| mixed_continuous | 168 | 67/168 | 0 | -0.002871 | 0 |
| spike_uniform_discrete | 168 | 0/168 | 0 | 0 | 0 |
| triangular_discrete | 168 | 0/168 | 0 | 0 | 0 |
| truncated_continuous | 168 | 63/168 | 0 | 0.001536 | 0 |
| uniform_continuous | 168 | 64/168 | 0 | -0.002837 | 0 |
| weibull_continuous (skewed) | 168 | 55/168 | 0 | 0.002481 | 0 |
| wg_mixture_continuous | 168 | 60/168 | 0 | 0.002472 | 0 |


By family:

| family | cells | partitions differ | median LTR−RTL gap pp | signed max |diff| (signed) |
|---|---|---|---|---|
| skewed continuous (lognormal, exponential, weibull) | 504 | 158/504 | 0 | 0.002481 |
| other continuous | 1176 | 427/1176 | 0 | -0.002918 |
| discrete | 336 | 0/336 | 0 | 0 |
| audio | 24 | 6/24 | 0 | -2.07e-04 |


## GOLD identity (final SSE vs results/gold/raw lex_hybrid)

- cells compared: 2040
- final SSE identical: 2040/2040
- sizes identical: 2040/2040
