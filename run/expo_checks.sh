#!/usr/bin/env bash
# Checks of the worked examples and numbers in the expository paper (Appendix A, Table 10).
# From the repo root:   bash run/expo_checks.sh
# Needs bash run/setup.sh first (lex1d Python binding and numpy in ./.venv); installs nothing.
# Writes out/expo_checks/results.json and out/expo_checks/summary.md.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]] || ! "$PY" -c 'import lex, numpy' 2>/dev/null; then
  echo "The lex1d Python binding is not in .venv. From the repo root run: bash run/setup.sh" >&2
  exit 1
fi
exec "$PY" "$ROOT/run/expo_checks.py" "$@"
