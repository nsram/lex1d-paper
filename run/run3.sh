#!/usr/bin/env bash
# Runs raw.sh, sorted.sh and bindings.sh in sequence under ONE keep-awake hold. Re-running resumes.
# From the repo root:   bash run/run3.sh            (options such as --smoke or --no-r are passed on)
# raw.sh generates simulation/input/ first if it is empty (data/generate.py, checked against data/shasum.txt).
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname)" == "Darwin" && -z "${LEX_RUN3_AWAKE:-}" ]]; then
  export LEX_RUN3_AWAKE=1 LEX_AWAKE="caffeinate -dims (run3.sh)"
  exec caffeinate -dims bash "$D/run3.sh" "$@"
fi
if [[ "$(uname)" == "Linux" && -z "${LEX_RUN3_AWAKE:-}" ]]; then
  export LEX_RUN3_AWAKE=1
  if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=probe true >/dev/null 2>&1; then
    export LEX_AWAKE="systemd-inhibit (run3.sh)"
    exec systemd-inhibit --what=sleep:idle --why="LEX benchmark" bash "$D/run3.sh" "$@"
  fi
  echo "WARNING: systemd-inhibit is not available here; nothing stops the machine from sleeping. Disable suspend for the run." >&2
fi
bash "$D/raw.sh" "$@" --resume
bash "$D/sorted.sh" "$@" --resume
bash "$D/bindings.sh" "$@" --resume
