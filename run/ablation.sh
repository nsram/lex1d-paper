#!/usr/bin/env bash
# Paired-move Refine ablation on current lex1d (commit 8a691ee).
# From the same start partition it compares all 8 window moves (all8) with the four single-cut
# moves only (single). Starts: Collapse to k (lex_plain) and the default coarse-DP start
# (lex_hybrid, M = 4096). Grid: uniform_continuous, gaussian_continuous and lognormal_continuous,
# N = 2^16 and 2^20 (paper slices 3 and 7), k = 8, 64, 256 and 512. Reference optimum:
# ckmeans_exact. The library is not changed; the driver is a bench-only copy of Refine.
# From the repo root:   bash run/ablation.sh
# Results: ./out/ablation/   --smoke writes out/ablation_smoke/   --help lists options.
# About 3 to 6 minutes on the GOLD Mac (exact fits are most of the time). Peak memory about 2.5 GB.
# Same setup as run/common.sh / run5.sh: python3 lookup, lex1d byte-identity check, cmake build
# (direct compiler fallback), the 6 C++ test suites, simulation data via data/generate.py when
# simulation/input/ is empty, env capture.
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR=$D
PKG_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMMIT=8a691ee005b657f985ffa299c57542b79570b08c
REPS=3; REPS_SET=0; SMOKE=0; SKIP_TESTS=0; OUT_DIR=""

usage() {
  cat <<USAGE
Usage: bash run/ablation.sh [SIM_DIR] [options]        (from the repo root)

SIM_DIR holds input/ with the 12 simulation files; the default is simulation/ in the repo. If
simulation/input/ is empty, data/generate.py writes the files there first (needs numpy:
bash run/setup.sh). --smoke does not need the simulation files.

Options:
  --smoke           tiny check: 256 synthetic values, k = 4, both starts and both variants;
                    writes out/ablation_smoke/. Those numbers are not for the paper.
  --reps N          timed Refine repetitions per cell (default 3; --smoke uses 1)
  --skip-tests      do not run the 6 C++ test suites
  --out DIR         default ./out/ablation (or ./out/ablation_smoke with --smoke)
  -h, --help
USAGE
}
SIM_ARG=""
if [[ $# -gt 0 && "$1" != -* ]]; then SIM_ARG=$1; shift; fi
ORIG_ARGS=("$@"); [[ -n "$SIM_ARG" ]] && ORIG_ARGS=("$SIM_ARG" "$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) SMOKE=1;;
    --reps) REPS=$2; REPS_SET=1; shift;;
    --skip-tests) SKIP_TESTS=1;;
    --out) OUT_DIR=$2; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown option: $1" >&2; usage; exit 2;;
  esac
  shift
done
[[ $SMOKE == 1 && $REPS_SET == 0 ]] && REPS=1

# Keep the machine awake (re-exec once), as run4.sh / run5.sh / common.sh.
if [[ "$(uname)" == "Darwin" && -z "${LEX_AWAKE:-}" ]] && command -v caffeinate >/dev/null; then
  export LEX_AWAKE="caffeinate -dims (ablation.sh)"
  exec caffeinate -dims bash "$SCRIPT_DIR/ablation.sh" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
fi
if [[ "$(uname)" == "Linux" && -z "${LEX_AWAKE:-}" ]]; then
  if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=probe true >/dev/null 2>&1; then
    export LEX_AWAKE="systemd-inhibit (ablation.sh)"
    exec systemd-inhibit --what=sleep:idle --why="LEX paired-move ablation" bash "$SCRIPT_DIR/ablation.sh" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
  fi
  export LEX_AWAKE="none (systemd-inhibit unavailable)"
  echo "WARNING: systemd-inhibit is not available here; nothing stops the machine from sleeping. Disable suspend for the run." >&2
fi

if [[ -z "$OUT_DIR" ]]; then
  if [[ $SMOKE == 1 ]]; then OUT_DIR="$PKG_DIR/out/ablation_smoke"
  else OUT_DIR="$PKG_DIR/out/ablation"; fi
fi
if [[ $SMOKE == 1 ]]; then WORK="$PKG_DIR/work/smoke"
else WORK="$PKG_DIR/work/full"; fi
mkdir -p "$OUT_DIR" "$WORK"
OUT_DIR=$(cd "$OUT_DIR" && pwd)
LOG="$OUT_DIR/run.log"
SESSION="$(date '+%Y%m%dT%H%M%S')-$$"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" | tee -a "$LOG"; }
have() { command -v "$1" >/dev/null 2>&1; }
START_TS=$(date +%s)
: > "$LOG"
log "==== ablation.sh start (session $SESSION) ===="
log "args: ${ORIG_ARGS[*]:-}"
log "repo: $PKG_DIR  out: $OUT_DIR  reps: $REPS  smoke: $SMOKE"

# ---- python3 (standard library only for the run itself) ----
PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/bin/python3; do
  p=$(command -v "$c" 2>/dev/null || true)
  [[ -n "$p" && -x "$p" ]] || continue
  "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null && { PY=$p; break; }
done
[[ -n "$PY" ]] || { log "No python3 (3.8+) found. Install it (macOS: brew install python; Ubuntu: sudo apt install python3 python3-venv python3-dev) and re-run."; exit 1; }
log "python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

# ---- lex1d must be byte-identical to commit 8a691ee ----
if ! LEXCHK=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1); then
  echo "$LEXCHK" | tee -a "$LOG"
  log "Stopping: lex1d/ is not byte-identical to commit $COMMIT (see above). Restore it (git checkout -- lex1d). Nothing was built or measured."; exit 1
fi
log "$LEXCHK"

# ---- C++ build (frozen lex1d + bench/ablation.cpp) and the 6 test suites ----
CXX_BIN=${CXX:-}
if [[ -z "$CXX_BIN" ]]; then for c in c++ clang++ g++; do have $c && { CXX_BIN=$c; break; }; done; fi
[[ -n "$CXX_BIN" ]] || { log "no C++ compiler. On macOS run: xcode-select --install; on Ubuntu: sudo apt install build-essential cmake; then re-run."; exit 1; }
BUILD="$PKG_DIR/build"
FIT="$BUILD/ablation"
log "building lex1d ($COMMIT) and bench/ablation.cpp in build/"
if have cmake && cmake -S "$PKG_DIR/bench" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$(command -v "$CXX_BIN")" >>"$LOG" 2>&1; then
  BUILD_HOW="cmake Release (lex_strict_fp: -ffp-contract=off)"
  cmake --build "$BUILD" -j 8 >>"$LOG" 2>&1 || { log "build failed; see run.log"; exit 1; }
  cmake --build "$BUILD" -j 8 --target ablation >>"$LOG" 2>&1 || { log "ablation build failed; see run.log"; exit 1; }
  if [[ $SKIP_TESTS == 0 ]]; then
    (cd "$BUILD" && ctest --output-on-failure) >>"$LOG" 2>&1 || { log "ctest FAILED; see run.log. Stopping."; exit 1; }
    log "ctest: $(grep -E 'tests passed' "$LOG" | tail -1)"
  fi
else
  BUILD_HOW="direct $CXX_BIN -O3 -DNDEBUG -std=c++17 -ffp-contract=off (cmake missing or < 3.21)"
  log "cmake unavailable: $BUILD_HOW"
  mkdir -p "$BUILD"
  FLAGS=(-O3 -DNDEBUG -std=c++17 -ffp-contract=off -I"$PKG_DIR/lex1d/cpp/include" -I"$PKG_DIR/lex1d/cpp/src")
  SRCS=("$PKG_DIR"/lex1d/cpp/src/*.cpp)
  "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/bench/ablation.cpp" -o "$FIT" >>"$LOG" 2>&1 || { log "ablation build failed; see run.log"; exit 1; }
  if [[ $SKIP_TESTS == 0 ]]; then
    for t in edge exact quality coarse weighted ties; do
      "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/lex1d/cpp/tests/test_$t.cpp" -o "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test build failed: $t"; exit 1; }
      "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test FAILED: $t; stopping"; exit 1; }
    done
    log "6/6 test suites passed (direct build)"
  fi
fi
[[ -x "$FIT" ]] || { log "driver not built"; exit 1; }

# ---- data (full run only) ----
INPUT=""
INPUT_CHECK="not used (smoke)"
SLICE_ARGS=()
if [[ $SMOKE == 0 ]]; then
  SIM=${SIM_ARG:-$PKG_DIR/simulation}
  [[ -d "$SIM" ]] || SIM="$PKG_DIR/$SIM"
  if ! INPUT=$("$PY" "$SCRIPT_DIR/data.py" find-input "$SIM"); then
    if [[ -n "$SIM_ARG" ]]; then
      log "Data not found in $SIM_ARG: expected $SIM_ARG/input/gaussian_continuous.txt (and the other 11 files)."; exit 3
    fi
    GPY=""
    for c in "$PKG_DIR/.venv/bin/python" "$PY"; do
      [[ -x "$c" ]] && "$c" -c 'import numpy' 2>/dev/null && { GPY=$c; break; }
    done
    [[ -n "$GPY" ]] || { log "simulation/input/ is empty and no python with numpy was found to generate it. Run: bash run/setup.sh"; exit 3; }
    log "simulation/input/ is empty: generating the 12 files with data/generate.py ($GPY, numpy $("$GPY" -c 'import numpy; print(numpy.__version__)'))"
    mkdir -p "$PKG_DIR/simulation"
    (cd "$PKG_DIR/simulation" && "$GPY" "$PKG_DIR/data/generate.py") >>"$LOG" 2>&1 || { log "data/generate.py failed; see run.log"; exit 1; }
    if cmp -s "$PKG_DIR/simulation/dataset_slice_counts.csv" "$PKG_DIR/data/slice_counts.csv"; then
      log "generated D counts match data/slice_counts.csv"
    else
      log "WARNING: generated D counts (simulation/dataset_slice_counts.csv) differ from data/slice_counts.csv"
    fi
    INPUT=$("$PY" "$SCRIPT_DIR/data.py" find-input "$PKG_DIR/simulation") || { log "generation wrote no usable files"; exit 1; }
  fi
  log "input folder: $INPUT"
  INPUT_CHECK="all checked files match data/shasum.txt"
  VDS="uniform_continuous,gaussian_continuous,lognormal_continuous"
  if ! LEX_PREPARED_DIR="$WORK/inputs" "$PY" "$SCRIPT_DIR/data.py" verify "$INPUT" "$VDS" 2>&1 | tee -a "$LOG"; then
    INPUT_CHECK="MISMATCH against data/shasum.txt: results will not be bit-identical to a Mac reference run"
    log "WARNING: a data file does not match data/shasum.txt (see above). Continuing, but the results will not be"
    log "bit-identical to the Mac reference slices. Files generated with another NumPy version or on another platform can differ in the last digit."
  fi
  mkdir -p "$WORK/inputs"
  "$PY" "$SCRIPT_DIR/ablation_prep.py" \
    --input "$INPUT" --prepared "$WORK/inputs" --manifest "$OUT_DIR/inputs_manifest.csv" \
    > "$WORK/slices.txt"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    SLICE_ARGS+=(--slice "$line")
    log "slice $line"
  done < "$WORK/slices.txt"
  log "wrote $OUT_DIR/inputs_manifest.csv"
fi

# ---- environment ----
{
  echo "session: $SESSION"
  echo "date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "script: ablation.sh  reps: $REPS  smoke: $SMOKE  grid: uniform,gaussian,lognormal x N=2^16,2^20 x k=8,64,256,512 x starts collapse,coarse4096 x variants all8,single"
  echo "uname: $(uname -a)"
  echo "sleep guard: ${LEX_AWAKE:-none}"
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
    echo "hw.ncpu: $(sysctl -n hw.ncpu 2>/dev/null)  P cores: $(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null)  E cores: $(sysctl -n hw.perflevel1.physicalcpu 2>/dev/null)"
    echo "memsize: $(sysctl -n hw.memsize 2>/dev/null)"
    echo "macOS: $(sw_vers -productVersion 2>/dev/null) ($(sw_vers -buildVersion 2>/dev/null))"
    echo "power: $(pmset -g batt 2>/dev/null | head -1)"
  else
    echo "os: $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}")"
    echo "cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"
    echo "nproc: $(nproc)"
    echo "mem: $(grep -E 'MemTotal|MemAvailable' /proc/meminfo | tr -s ' ' | tr '\n' ' ')"
  fi
  echo "cxx: $(command -v "$CXX_BIN"): $("$CXX_BIN" --version 2>&1 | head -1)"
  echo "cmake: $(cmake --version 2>/dev/null | head -1 || echo none)"
  echo "build: $BUILD_HOW"
  echo "python: $PY $("$PY" -c 'import sys; print(sys.version.split()[0])')"
  echo "lex1d commit: $COMMIT (lex1d/ is the commit's zip, verbatim)"
  echo "$LEXCHK (manifest run/lex1d_8a691ee.sha256)"
  echo "input_check: $INPUT_CHECK"
  "$PY" - "$PKG_DIR" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
files = ["lex1d/cpp/src/" + f for f in sorted(os.listdir(os.path.join(root, "lex1d/cpp/src")))]
files += ["lex1d/cpp/include/lex/lex.hpp", "bench/ablation.cpp", "bench/CMakeLists.txt",
          "run/ablation.sh", "run/ablation_analyze.py", "run/ablation_prep.py",
          "run/data.py", "run/check_lex1d.py"]
for f in files:
    print("sha256 %s  %s" % (hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest(), f))
PYEOF
} > "$OUT_DIR/env_$SESSION.txt"
cp "$OUT_DIR/env_$SESSION.txt" "$OUT_DIR/env.txt"
log "environment written to env.txt (and env_$SESSION.txt)"

# ---- run + analysis ----
RC=0
set +e
set -o pipefail
if [[ $SMOKE == 1 ]]; then
  "$FIT" --out "$OUT_DIR/results.csv" --smoke --reps "$REPS" 2>&1 | tee -a "$LOG"
  RC=${PIPESTATUS[0]}
else
  "$FIT" --out "$OUT_DIR/results.csv" --reps "$REPS" "${SLICE_ARGS[@]}" 2>&1 | tee -a "$LOG"
  RC=${PIPESTATUS[0]}
fi
set -e
if [[ ! -s "$OUT_DIR/results.csv" ]]; then
  log "no results.csv was written. See $OUT_DIR/run.log"
  exit 1
fi
"$PY" "$SCRIPT_DIR/ablation_analyze.py" "$OUT_DIR/results.csv" | tee "$OUT_DIR/summary.txt"
cat "$OUT_DIR/summary.txt" >> "$LOG"

LEXEND=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1) || RC=1
log "after the run: $LEXEND"
echo "after the run: $LEXEND" >> "$OUT_DIR/env_$SESSION.txt"
echo "end: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$OUT_DIR/env_$SESSION.txt"
cp "$OUT_DIR/env_$SESSION.txt" "$OUT_DIR/env.txt"
EL=$(( $(date +%s) - START_TS ))
if [[ $RC == 0 ]]; then
  log "finished ablation.sh: PASS. session time: $((EL / 60))m $((EL % 60))s. Results: $OUT_DIR"
  log "To commit them: copy results.csv, moves_8way.csv, moves_3way.csv, summary.txt and env.txt into results/ablation/ (see results/ablation/README.md)."
else
  log "finished ablation.sh: FAIL (see above and $OUT_DIR/summary.txt). session time: $((EL / 60))m $((EL % 60))s"
fi
exit $RC
