# Raw vs presorted input (same cells, two runs)

Cells compared: 4624. SSE identical: 4624/4624; sizes identical: 4624/4624.

Sort cost = median fit time on raw input minus median fit time on presorted input (C++ also times its sort stage directly: t_sort_raw). Ckmeans.1d.dp 4.3.6 also checks for sorted input (one O(n) scan) and skips its std::sort, but still copies x and builds an index vector.

Medians over continuous datasets (and all k) per N:

| section | N | method | raw s | sorted s | raw - sorted s | C++ t_sort (raw) s |
|---|---|---|---|---|---|---|
| audio | 8168256 | Ckmeans.1d.dp | 17.92 | 17.02 | 0.9237 |  |
| audio | 8168256 | ckmeans_exact | 11.95 | 11.51 | 0.5071 | 0.4988 |
| audio | 8168256 | lex_hybrid M=1024 | 2.926 | 2.449 | 0.5059 | 0.4989 |
| audio | 8168256 | lex_hybrid M=16384 | 2.913 | 2.431 | 0.5009 | 0.4986 |
| audio | 8168256 | lex_hybrid M=2048 | 2.917 | 2.432 | 0.5002 | 0.4988 |
| audio | 8168256 | lex_hybrid M=4096 | 2.908 | 2.429 | 0.5047 | 0.4989 |
| audio | 8168256 | lex_hybrid M=8192 | 2.915 | 2.425 | 0.5082 | 0.499 |
| audio | 8168256 | lex_plain | 3.595 | 3.098 | 0.4961 | 0.4989 |
| main | 16384 | Ckmeans.1d.dp | 0.03194 | 0.03079 | 0.00135 |  |
| main | 16384 | ckmeans_exact | 0.01717 | 0.01628 | 8.76e-04 | 6.22e-04 |
| main | 16384 | lex_hybrid M=16384 | 0.01736 | 0.0163 | 8.88e-04 | 6.24e-04 |
| main | 16384 | lex_hybrid M=4096 | 0.005689 | 0.005261 | 7.00e-04 | 6.25e-04 |
| main | 16384 | lex_hybrid M=8192 | 0.009632 | 0.008991 | 7.67e-04 | 6.26e-04 |
| main | 16384 | lex_plain | 0.002852 | 0.00223 | 6.46e-04 | 6.28e-04 |
| main | 32768 | Ckmeans.1d.dp | 0.06348 | 0.05761 | 0.005063 |  |
| main | 32768 | ckmeans_exact | 0.0374 | 0.03383 | 0.003053 | 0.001356 |
| main | 32768 | lex_hybrid M=16384 | 0.02097 | 0.01833 | 0.002315 | 0.001352 |
| main | 32768 | lex_hybrid M=4096 | 0.00875 | 0.00694 | 0.001784 | 0.001356 |
| main | 32768 | lex_hybrid M=8192 | 0.01269 | 0.01061 | 0.001995 | 0.001354 |
| main | 32768 | lex_plain | 0.006294 | 0.004678 | 0.00163 | 0.001355 |
| main | 65536 | Ckmeans.1d.dp | 0.1293 | 0.1281 | 0.003098 |  |
| main | 65536 | ckmeans_exact | 0.07866 | 0.07669 | 0.002545 | 0.002897 |
| main | 65536 | lex_hybrid M=16384 | 0.02686 | 0.02435 | 0.003025 | 0.002885 |
| main | 65536 | lex_hybrid M=4096 | 0.01478 | 0.01199 | 0.003051 | 0.002885 |
| main | 65536 | lex_hybrid M=8192 | 0.01871 | 0.01597 | 0.003092 | 0.002887 |
| main | 65536 | lex_plain | 0.01352 | 0.01071 | 0.003105 | 0.00291 |
| main | 131072 | Ckmeans.1d.dp | 0.2575 | 0.248 | 0.008316 |  |
| main | 131072 | ckmeans_exact | 0.1652 | 0.1584 | 0.006437 | 0.00649 |
| main | 131072 | lex_hybrid M=16384 | 0.03985 | 0.03311 | 0.006533 | 0.006498 |
| main | 131072 | lex_hybrid M=4096 | 0.02782 | 0.02127 | 0.006538 | 0.006487 |
| main | 131072 | lex_hybrid M=8192 | 0.03158 | 0.0251 | 0.00653 | 0.00649 |
| main | 131072 | lex_plain | 0.02922 | 0.02277 | 0.006564 | 0.006494 |
| main | 262144 | Ckmeans.1d.dp | 0.515 | 0.5074 | 0.01736 |  |
| main | 262144 | ckmeans_exact | 0.3471 | 0.3385 | 0.01219 | 0.01381 |
| main | 262144 | lex_hybrid M=16384 | 0.0671 | 0.05519 | 0.01366 | 0.01382 |
| main | 262144 | lex_hybrid M=4096 | 0.05528 | 0.04227 | 0.01375 | 0.01381 |
| main | 262144 | lex_hybrid M=8192 | 0.05901 | 0.04605 | 0.01372 | 0.01381 |
| main | 262144 | lex_plain | 0.06195 | 0.04882 | 0.01368 | 0.01383 |
| main | 524288 | Ckmeans.1d.dp | 1.036 | 1.029 | 0.009995 |  |
| main | 524288 | ckmeans_exact | 0.7253 | 0.7056 | 0.007591 | 0.02897 |
| main | 524288 | lex_hybrid M=16384 | 0.1314 | 0.1088 | 0.02677 | 0.02894 |
| main | 524288 | lex_hybrid M=4096 | 0.1194 | 0.09619 | 0.02749 | 0.02899 |
| main | 524288 | lex_hybrid M=8192 | 0.1232 | 0.1008 | 0.02723 | 0.02896 |
| main | 524288 | lex_plain | 0.1383 | 0.1149 | 0.02591 | 0.02897 |
| main | 1048576 | Ckmeans.1d.dp | 2.117 | 2.055 | 0.0899 |  |
| main | 1048576 | ckmeans_exact | 1.505 | 1.431 | 0.06236 | 0.06114 |
| main | 1048576 | lex_hybrid M=1024 | 0.2843 | 0.2274 | 0.05858 | 0.06124 |
| main | 1048576 | lex_hybrid M=16384 | 0.296 | 0.2456 | 0.05982 | 0.06124 |
| main | 1048576 | lex_hybrid M=2048 | 0.2847 | 0.2262 | 0.05888 | 0.06128 |
| main | 1048576 | lex_hybrid M=4096 | 0.2847 | 0.2254 | 0.05919 | 0.06116 |
| main | 1048576 | lex_hybrid M=8192 | 0.2877 | 0.2323 | 0.05973 | 0.06127 |
| main | 1048576 | lex_plain | 0.3287 | 0.274 | 0.05995 | 0.06124 |
| weighted | 16384 | Ckmeans.1d.dp | 0.1558 | 0.1558 | 9.46e-04 |  |
| weighted | 16384 | ckmeans_exact | 0.07949 | 0.07888 | 7.32e-04 | 7.16e-04 |
| weighted | 16384 | lex_hybrid M=4096 | 0.01934 | 0.01857 | 7.27e-04 | 7.09e-04 |
| weighted | 16384 | lex_plain | 0.003298 | 0.002598 | 7.06e-04 | 7.15e-04 |
| weighted | 32768 | Ckmeans.1d.dp | 0.3104 | 0.3083 | 0.001833 |  |
| weighted | 32768 | ckmeans_exact | 0.1717 | 0.1706 | 0.00152 | 0.001498 |
| weighted | 32768 | lex_hybrid M=4096 | 0.02247 | 0.02091 | 0.001519 | 0.001491 |
| weighted | 32768 | lex_plain | 0.007095 | 0.005667 | 0.00144 | 0.001523 |
| weighted | 65536 | Ckmeans.1d.dp | 0.6161 | 0.6137 | 0.006405 |  |
| weighted | 65536 | ckmeans_exact | 0.3732 | 0.3671 | 0.004132 | 0.003155 |
| weighted | 65536 | lex_hybrid M=4096 | 0.02905 | 0.02589 | 0.003171 | 0.003171 |
| weighted | 65536 | lex_plain | 0.01471 | 0.0116 | 0.003107 | 0.003166 |
| weighted | 131072 | Ckmeans.1d.dp | 1.232 | 1.221 | 0.01027 |  |
| weighted | 131072 | ckmeans_exact | 0.7964 | 0.7874 | 0.008057 | 0.006734 |
| weighted | 131072 | lex_hybrid M=4096 | 0.04303 | 0.03614 | 0.007075 | 0.006735 |
| weighted | 131072 | lex_plain | 0.0313 | 0.02436 | 0.00687 | 0.006824 |
| weighted | 262144 | Ckmeans.1d.dp | 2.463 | 2.433 | 0.02555 |  |
| weighted | 262144 | ckmeans_exact | 1.706 | 1.691 | 0.01508 | 0.0144 |
| weighted | 262144 | lex_hybrid M=4096 | 0.07368 | 0.05865 | 0.015 | 0.01439 |
| weighted | 262144 | lex_plain | 0.06882 | 0.05443 | 0.0146 | 0.01445 |
| weighted | 524288 | Ckmeans.1d.dp | 5.018 | 4.904 | 0.05024 |  |
| weighted | 524288 | ckmeans_exact | 3.629 | 3.596 | 0.03137 | 0.0309 |
| weighted | 524288 | lex_hybrid M=4096 | 0.1499 | 0.1174 | 0.03273 | 0.03086 |
| weighted | 524288 | lex_plain | 0.1595 | 0.1275 | 0.0313 | 0.03086 |
| weighted | 1048576 | Ckmeans.1d.dp | 10.34 | 10.23 | 0.0871 |  |
| weighted | 1048576 | ckmeans_exact | 7.817 | 7.684 | 0.07772 | 0.06453 |
| weighted | 1048576 | lex_hybrid M=4096 | 0.3587 | 0.2977 | 0.06233 | 0.06448 |
| weighted | 1048576 | lex_plain | 0.426 | 0.3657 | 0.06198 | 0.0646 |

