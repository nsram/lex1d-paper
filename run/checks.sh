#!/usr/bin/env bash
# Numerical checks of the technical paper's propositions (Appendix B).
# From the repo root:   bash run/checks.sh
# Needs bash run/setup.sh first (lex1d Python binding in ./.venv). Installs sympy and pandas
# into .venv if they are missing. Writes out/checks/results.json and out/checks/summary.md.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]] || ! "$PY" -c 'import lex, numpy' 2>/dev/null; then
  echo "The lex1d Python binding is not in .venv. From the repo root run: bash run/setup.sh" >&2
  exit 1
fi
if ! "$PY" -c 'import sympy, pandas' 2>/dev/null; then
  echo "Installing sympy and pandas into .venv (needed only by run/checks.py)"
  "$PY" -m pip install --disable-pip-version-check -q 'sympy==1.14.0' 'pandas==3.1.1'
fi
exec "$PY" "$ROOT/run/checks.py" "$@"
