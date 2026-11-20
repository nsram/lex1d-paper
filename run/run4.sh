#!/usr/bin/env bash
# Fourth GOLD run: Refine ablation on lex_hybrid only.
# For each cell, records the coarse-DP SSE (after Collapse(M)+DP(k), before Refine) and the final SSE,
# plus Refine sweeps, moves and stage times. It also runs an exploratory left-to-right Refine from the
# same coarse-DP bounds (bench/refine_ltr.cpp; frozen lex1d is untouched) and records its SSE, sweeps,
# moves, time, and whether the partition equals the standard right-to-left one.
# The grid is the 12 simulation files x 7 slices plus audio, lex_hybrid at M = 4096, 8192 and 16384,
# k = 4..512 (same k set as GOLD). Discrete datasets are included.
# One warm-up (public-API check) and one timed round by default: SSE is deterministic (GOLD already
# showed identical SSE across 3 rounds) and Refine timing is secondary. Pass --reps 3 for GOLD-like timing.
# From the repo root:   bash run/run4.sh            (or: bash run/run4.sh simulation)
# Results: ./out/refine/   Re-running resumes.   --help lists options.
# Keeps the machine awake for the whole run (caffeinate -dims on macOS, systemd-inhibit on Linux).
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname)" == "Darwin" && -z "${LEX_RUN4_AWAKE:-}" ]]; then
  export LEX_RUN4_AWAKE=1 LEX_AWAKE="caffeinate -dims (run4.sh)"
  exec caffeinate -dims bash "$D/run4.sh" "$@"
fi
if [[ "$(uname)" == "Linux" && -z "${LEX_RUN4_AWAKE:-}" ]]; then
  export LEX_RUN4_AWAKE=1
  if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=probe true >/dev/null 2>&1; then
    export LEX_AWAKE="systemd-inhibit (run4.sh)"
    exec systemd-inhibit --what=sleep:idle --why="LEX Refine ablation" bash "$D/run4.sh" "$@"
  fi
  echo "WARNING: systemd-inhibit is not available here; nothing stops the machine from sleeping. Disable suspend for the run." >&2
fi
MODE=refine
# shellcheck source=run/common.sh
source "$D/common.sh"
