#!/usr/bin/env bash
# Numbers from run 4 (the diagnostic Refine run) quoted in the papers.
# From the repo root:   bash run/run4_numbers.sh
# Reads results/gold/refine/ (and results/gold/raw/results.csv for one cross-check). Uses ./.venv; if it
# does not exist yet, creates it from a Python 3.12+ (run/setup.sh reuses it later). Installs pandas and
# statsmodels into .venv if they are missing. Writes out/run4_numbers/results.json and summary.md.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  for p in python3.13 python3.12 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      echo "Creating .venv from $p"; "$p" -m venv "$ROOT/.venv"; break
    fi
  done
fi
if [[ ! -x "$PY" ]]; then echo "Needs Python 3.12+ with venv; or run: bash run/setup.sh" >&2; exit 1; fi
if [[ ! -f "$ROOT/results/gold/refine/results.csv" ]]; then echo "results/gold/refine/results.csv is missing" >&2; exit 1; fi
if ! "$PY" -c 'import numpy, pandas, statsmodels' 2>/dev/null; then
  echo "Installing numpy, pandas and statsmodels into .venv (needed only by run/run4_numbers.py)"
  "$PY" -m pip install --disable-pip-version-check -q 'numpy==2.5.5' 'pandas==3.1.1' 'statsmodels==0.15.0'
fi
exec "$PY" "$ROOT/run/run4_numbers.py" "$@"
