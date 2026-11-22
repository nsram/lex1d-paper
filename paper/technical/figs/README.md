# Technical paper figures

Figures 1-5 of the technical paper.

From the repository root:

    python3 paper/technical/figs/make_figs.py

This writes the PNGs next to this file, with the names the paper's LaTeX includes:

- `bot_v23_fig1_example.png`
- `bot_v23_fig2_accuracy.png`
- `bot_v23_fig3_time_memory.png`
- `bot_v23_fig4_msweep.png`
- `bot_v23_fig5_speedup_all.png`

Figure 1 is the ten-value worked example (no data files). Figures 2-5 read
`results/gold/raw/results.csv` (the main GOLD grid) and the coarse-DP REE
medians from `results/gold/refine/results.csv` (run 4, continuous datasets,
M = 4,096, median over cells where the coarse DP was not exact).

Needs Python 3 with matplotlib, pandas and numpy.

The PNGs in this folder were produced with Python 3.13.5, matplotlib 3.11.2, pandas 3.0.6 and numpy 2.5.5.
