#!/usr/bin/env bash
# All numerical checks of the papers' results, in one command. From the repo root:
#   bash run/checks.sh
# Runs, in order:
#   run/check_propositions.py          technical paper, Appendix A, Table 7 (lex1d binding, sympy)
#   run/check_move_rule.py             Lemma 1 and the two-copy case of Proposition 1 (sympy)
#   run/check_no_split_duplicates.py   Corollary 1
#   run/check_expository_numbers.py    move counts and exercises in the expository paper
#   run/check_expository_examples.py   expository paper, Appendix A, Table 10 (lex1d binding)
# Needs bash run/setup.sh first (lex1d Python binding in ./.venv). Installs sympy and pandas
# into .venv if they are missing. Writes out/checks/propositions/ and out/checks/expository_examples/.
# Exits nonzero if any script fails.
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]] || ! "$PY" -c 'import lex, numpy' 2>/dev/null; then
  echo "The lex1d Python binding is not in .venv. From the repo root run: bash run/setup.sh" >&2
  exit 1
fi
if ! "$PY" -c 'import sympy, pandas' 2>/dev/null; then
  echo "Installing sympy and pandas into .venv (needed by the check scripts)"
  "$PY" -m pip install --disable-pip-version-check -q 'sympy==1.14.0' 'pandas==3.1.1' || exit 1
fi
SCRIPTS=(check_propositions check_move_rule check_no_split_duplicates check_expository_numbers check_expository_examples)
declare -a RESULT
FAILED=0
for s in "${SCRIPTS[@]}"; do
  echo "=== run/$s.py"
  t0=$SECONDS
  if "$PY" "$ROOT/run/$s.py"; then st=PASS; else st=FAIL; FAILED=$((FAILED + 1)); fi
  RESULT+=("$(printf '%-34s %s  (%ds)' "run/$s.py" "$st" $((SECONDS - t0)))")
done
echo
echo "=== Summary"
printf '%s\n' "${RESULT[@]}"
if [[ $FAILED -gt 0 ]]; then
  echo "$FAILED of ${#SCRIPTS[@]} check scripts FAILED"
  exit 1
fi
echo "all ${#SCRIPTS[@]} check scripts passed"
