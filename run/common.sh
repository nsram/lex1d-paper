# Shared setup and run logic. Sourced by run/raw.sh (MODE=raw), run/sorted.sh (MODE=sorted),
# run/bindings.sh (MODE=bindings) and run/run4.sh (MODE=refine). Not run directly.
# Everything below is identical for the scripts except MODE.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PKG_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMMIT=8a691ee005b657f985ffa299c57542b79570b08c

case "$MODE" in
  raw) OUT_NAME=out/raw; SCRIPT_NAME=raw.sh;;
  sorted) OUT_NAME=out/sorted; SCRIPT_NAME=sorted.sh;;
  bindings) OUT_NAME=out/bindings; SCRIPT_NAME=bindings.sh;;
  refine) OUT_NAME=out/refine; SCRIPT_NAME=run4.sh;;
  *) echo "bad MODE" >&2; exit 2;;
esac

REPS=3; REPS_SET=0; MEM_GB=100; SMOKE=0; FRESH=0; NO_R=0; SKIP_INSTALL=0; SKIP_TESTS=0
SECTIONS="main,msweep,audio,weighted"; DATASETS=""; SLICES=""; KLIST=""; OUT_DIR=""

usage() {
  cat <<USAGE
Usage: bash run/$SCRIPT_NAME [SIM_DIR] [options]        (from the repo root)

SIM_DIR holds input/ with the 12 simulation files; the default is simulation/ in the repo. If
simulation/input/ is empty, data/generate.py writes the files there first (needs numpy: bash run/setup.sh).
Nothing else needs to be passed for the full run. Re-running the same command resumes:
finished cells are skipped (each row records its session id and timestamp).

Options:
  --resume          resume (this is also the default; accepted so run3.sh reruns read clearly)
  --fresh           delete this script's earlier cells and start over
  --smoke           light check: 2,048-value pieces of 4 datasets (slices 1-2), 20,000 audio values,
                    k = 4 and 64, one timed round; writes ${OUT_NAME}_smoke/
  --reps N          timed rounds per cell after the warm-up round (default 3)
  --skip-main | --skip-msweep | --skip-audio | --skip-weighted     (full-grid scripts)
  --no-r            no R (Ckmeans.1d.dp / R binding rows)
  --datasets A,B  --slices 1,2  --k 4,8   restrict the grid (full-grid scripts)
  --mem-limit-gb N  skip a fit whose predicted DP table exceeds N GB (default 100; also 85% of RAM)
  --skip-install    do not install missing R/Python packages
  --skip-tests      do not run the 6 C++ test suites
  --out DIR         default ./$OUT_NAME
  -h, --help
USAGE
}

SIM_ARG=""
if [[ $# -gt 0 && "$1" != -* ]]; then SIM_ARG=$1; shift; fi
ORIG_ARGS=("$@"); [[ -n "$SIM_ARG" ]] && ORIG_ARGS=("$SIM_ARG" "$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume) ;;
    --fresh) FRESH=1;;
    --smoke) SMOKE=1;;
    --reps) REPS=$2; REPS_SET=1; shift;;
    --skip-main) SECTIONS=${SECTIONS//main,/};;
    --skip-msweep) SECTIONS=${SECTIONS//msweep,/};;
    --skip-audio) SECTIONS=${SECTIONS//audio,/};;
    --skip-weighted) SECTIONS=${SECTIONS//,weighted/};;
    --no-r) NO_R=1;;
    --datasets) DATASETS=$2; shift;;
    --slices) SLICES=$2; shift;;
    --k) KLIST=$2; shift;;
    --mem-limit-gb) MEM_GB=$2; shift;;
    --skip-install) SKIP_INSTALL=1;;
    --skip-tests) SKIP_TESTS=1;;
    --out) OUT_DIR=$2; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown option: $1" >&2; usage; exit 2;;
  esac
  shift
done
# Run 4 (Refine ablation): lex_hybrid only, no R. One timed round by default (SSE is deterministic;
# pass --reps N to measure timing more carefully). Smoke still uses one timed round.
if [[ "$MODE" == refine ]]; then
  NO_R=1
  [[ $REPS_SET == 0 ]] && REPS=1
  # main + audio; no weighted section and no extra M-sweep values (M is 4096, 8192, 16384)
  # Keep an explicit --skip-* / remaining default: drop msweep and weighted, which run 4 does not run.
  SECTIONS=${SECTIONS//msweep,/}
  SECTIONS=${SECTIONS//,weighted/}
  SECTIONS=${SECTIONS//weighted/}
  SECTIONS=${SECTIONS//,,/,}
  SECTIONS=${SECTIONS#,}
  SECTIONS=${SECTIONS%,}
  [[ -z "$SECTIONS" ]] && SECTIONS="main,audio"
fi
if [[ "$MODE" == refine ]]; then
  [[ $SMOKE == 1 && $REPS_SET == 0 ]] && REPS=1
else
  [[ $SMOKE == 1 && $REPS == 3 ]] && REPS=1
fi
[[ -z "$OUT_DIR" ]] && OUT_DIR="$PKG_DIR/$OUT_NAME$([[ $SMOKE == 1 ]] && echo _smoke || true)"
WORK="$PKG_DIR/work/$([[ $SMOKE == 1 ]] && echo smoke || echo full)"

# Keep the machine awake (re-exec once; skipped when run3.sh already holds it).
if [[ "$(uname)" == "Darwin" && -z "${LEX_AWAKE:-}" ]] && command -v caffeinate >/dev/null; then
  export LEX_AWAKE="caffeinate -i"
  exec caffeinate -i bash "$SCRIPT_DIR/$SCRIPT_NAME" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
fi
if [[ "$(uname)" == "Linux" && -z "${LEX_AWAKE:-}" ]]; then
  if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=probe true >/dev/null 2>&1; then
    export LEX_AWAKE="systemd-inhibit"
    exec systemd-inhibit --what=sleep:idle --why="LEX benchmark" bash "$SCRIPT_DIR/$SCRIPT_NAME" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
  fi
  export LEX_AWAKE="none (systemd-inhibit unavailable)"
  echo "WARNING: systemd-inhibit is not available here; nothing stops the machine from sleeping. Disable suspend for the run." >&2
fi

[[ $FRESH == 1 ]] && rm -rf "$OUT_DIR/cells"
mkdir -p "$OUT_DIR/cells" "$WORK"
OUT_DIR=$(cd "$OUT_DIR" && pwd)
LOG="$OUT_DIR/run.log"
SESSION="$(date '+%Y%m%dT%H%M%S')-$$"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" | tee -a "$LOG"; }
have() { command -v "$1" >/dev/null 2>&1; }
START_TS=$(date +%s)
log "==== $SCRIPT_NAME start (session $SESSION) ===="
log "args: ${ORIG_ARGS[*]:-}"
log "repo: $PKG_DIR  out: $OUT_DIR  mode: $MODE  reps: $REPS (+1 warm-up)  smoke: $SMOKE"
NDONE=$(find "$OUT_DIR/cells" -name '*.csv' 2>/dev/null | wc -l | tr -d ' ')
[[ $NDONE -gt 0 ]] && log "resuming: $NDONE cells already finished in $OUT_DIR/cells (they are kept)"

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
# ---- lex1d must be byte-identical to commit 8a691ee (manifest from the commit's zip) ----
if ! LEXCHK=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1); then
  echo "$LEXCHK" | tee -a "$LOG"
  log "Stopping: lex1d/ is not byte-identical to commit $COMMIT (see above). Restore it (git checkout -- lex1d). Nothing was built or measured."; exit 1
fi
log "$LEXCHK"
if [[ "$(uname)" == "Darwin" ]]; then
  [[ -x /usr/bin/time ]] || { log "/usr/bin/time not found"; exit 1; }
else
  /usr/bin/time -v true >/dev/null 2>&1 || { log "GNU time (/usr/bin/time -v) not found; it gives each fit's peak RSS. Install it: sudo apt install time"; exit 1; }
fi

# ---- R ----
RS=""; RB=""
RLIB="$PKG_DIR/R-lib"; mkdir -p "$RLIB"
export R_LIBS="$RLIB${R_LIBS:+:$R_LIBS}"
if [[ $NO_R == 0 ]]; then
  for c in Rscript /opt/homebrew/bin/Rscript /usr/local/bin/Rscript /Library/Frameworks/R.framework/Resources/bin/Rscript; do
    p=$(command -v "$c" 2>/dev/null || true); [[ -n "$p" && -x "$p" ]] && { RS=$p; break; }
  done
  [[ -n "$RS" ]] || { log "R not found. Install R (macOS: https://cran.r-project.org or brew install r; Ubuntu: sudo apt install r-base r-base-dev) and re-run, or pass --no-r."; exit 1; }
  for c in "$(dirname "$RS")/R" R /opt/homebrew/bin/R /usr/local/bin/R; do
    p=$(command -v "$c" 2>/dev/null || true); [[ -n "$p" && -x "$p" ]] && { RB=$p; break; }
  done
  need_pkg() { "$RS" -e "suppressPackageStartupMessages(library($1))" >/dev/null 2>&1; }
  # Missing packages are installed at the GOLD pins (requirements-r.txt), the same way run/setup.sh does.
  inst_pkg() {
    need_pkg "$1" && return 0
    [[ $SKIP_INSTALL == 1 ]] && return 1
    log "R package $1 missing; installing the pinned R packages (requirements-r.txt) into R-lib (as run/setup.sh does)"
    "$RS" "$SCRIPT_DIR/rpkgs.R" install "$RLIB" "$PKG_DIR/requirements-r.txt" >>"$LOG" 2>&1 || true
    need_pkg "$1"
  }
  if [[ $MODE != bindings ]]; then
    inst_pkg Ckmeans.1d.dp || { log "Ckmeans.1d.dp is missing and could not be installed. Run: bash run/setup.sh. Or pass --no-r."; exit 1; }
    log "R: $RS; Ckmeans.1d.dp $("$RS" -e 'cat(as.character(packageVersion("Ckmeans.1d.dp")))' 2>/dev/null | tail -1)"
  else
    inst_pkg Rcpp || true
  fi
  # Warn (do not stop) if the R packages R will load differ from the pins, or R's major.minor from GOLD's 4.6.
  RPIN=$("$RS" "$SCRIPT_DIR/rpkgs.R" check "$RLIB" "$PKG_DIR/requirements-r.txt" 2>&1 | grep '^R package' || true)
  if echo "$RPIN" | grep -qE ' (DIFFERS|MISSING) '; then
    log "WARNING: R packages differ from the GOLD pins (bash run/setup.sh installs them):"; echo "$RPIN" | tee -a "$LOG"
  else log "R packages at the GOLD pins (requirements-r.txt)"; fi
  RVER=$("$RS" -e 'cat(as.character(getRversion()))' 2>/dev/null | tail -1)
  [[ "${RVER%.*}" == "4.6" ]] || log "WARNING: R $RVER; GOLD used R 4.6.2"
fi

# ---- C++ build (frozen lex1d + driver) and the 6 test suites ----
CXX_BIN=${CXX:-}
if [[ -z "$CXX_BIN" ]]; then for c in c++ clang++ g++; do have $c && { CXX_BIN=$c; break; }; done; fi
[[ -n "$CXX_BIN" ]] || { log "no C++ compiler. On macOS run: xcode-select --install; on Ubuntu: sudo apt install build-essential cmake; then re-run."; exit 1; }
if ! have cmake && [[ $SKIP_INSTALL == 0 ]] && have brew; then
  log "cmake not found; trying: brew install cmake"; brew install cmake >>"$LOG" 2>&1 || true
fi
BUILD="$PKG_DIR/build"
FIT="$BUILD/fit"
log "building lex1d ($COMMIT) and bench/fit.cpp in build/"
if have cmake && cmake -S "$PKG_DIR/bench" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$(command -v "$CXX_BIN")" >>"$LOG" 2>&1; then
  BUILD_HOW="cmake Release (lex_strict_fp: -ffp-contract=off)"
  cmake --build "$BUILD" -j 8 >>"$LOG" 2>&1 || { log "build failed; see run.log"; exit 1; }
  if [[ "$MODE" == refine ]]; then
    cmake --build "$BUILD" -j 8 --target refine_fit >>"$LOG" 2>&1 || { log "refine_fit build failed; see run.log"; exit 1; }
  fi
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
  "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/bench/fit.cpp" -o "$FIT" >>"$LOG" 2>&1 || { log "build failed"; exit 1; }
  if [[ $SKIP_TESTS == 0 ]]; then
    for t in edge exact quality coarse weighted ties; do
      "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/lex1d/cpp/tests/test_$t.cpp" -o "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test build failed: $t"; exit 1; }
      "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test FAILED: $t; stopping"; exit 1; }
    done
    log "6/6 test suites passed (direct build)"
  fi
fi
if [[ "$MODE" == refine ]]; then
  if [[ ! -x "$BUILD/refine_fit" ]]; then
    log "building bench/refine_fit.cpp directly"
    FLAGS=(-O3 -DNDEBUG -std=c++17 -ffp-contract=off -I"$PKG_DIR/lex1d/cpp/include" -I"$PKG_DIR/lex1d/cpp/src" -I"$PKG_DIR/bench")
    SRCS=("$PKG_DIR"/lex1d/cpp/src/*.cpp)
    "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/bench/refine_fit.cpp" "$PKG_DIR/bench/refine_ltr.cpp" -o "$BUILD/refine_fit" >>"$LOG" 2>&1 \
      || { log "refine_fit build failed; see run.log"; exit 1; }

  fi
  FIT="$BUILD/refine_fit"
fi
[[ -x "$FIT" ]] || { log "driver not built"; exit 1; }

# ---- bindings (bindings script only): lex1d R package into R-lib, lex1d Python module into .venv ----
RBIND=0; PYB=""
if [[ $MODE == bindings ]]; then
  if [[ -n "$RS" && -n "$RB" ]]; then
    if need_pkg Rcpp; then
      RSRC="$WORK/rpkg"; rm -rf "$RSRC"; mkdir -p "$RSRC"
      cp -R "$PKG_DIR/lex1d/cpp" "$PKG_DIR/lex1d/r" "$RSRC/"   # configure copies ../cpp into r/src (copy, so lex1d/ stays verbatim)
      if (cd "$RSRC" && "$RB" CMD INSTALL -l "$RLIB" r) >>"$LOG" 2>&1 && need_pkg lex1d; then
        RBIND=1; log "lex1d R binding installed in R-lib ($("$RS" -e 'cat(as.character(packageVersion("lex1d")))' 2>/dev/null | tail -1))"
      else log "WARNING: lex1d R binding install failed (see run.log); R binding rows skipped"; fi
    else log "WARNING: Rcpp missing; R binding rows skipped"; fi
  else log "WARNING: R not available; R binding rows skipped"; fi
  VENV="$PKG_DIR/.venv"
  if [[ ! -x "$VENV/bin/python" ]] || ! "$VENV/bin/python" -c 'import lex, numpy' 2>/dev/null; then
    if [[ $SKIP_INSTALL == 0 ]]; then
      log "building the lex1d Python module into .venv (pinned pip packages from requirements.txt; needs internet). bash run/setup.sh does this up front."
      PSRC="$WORK/pypkg"; rm -rf "$PSRC"; mkdir -p "$PSRC"
      cp -R "$PKG_DIR/lex1d/cpp" "$PKG_DIR/lex1d/python" "$PSRC/"
      # base python for the venv: needs the C headers (Python.h) to build the extension, and 3.12+ (numpy 2.5.5)
      VPY=""
      for c in "$PY" python3 python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
               /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
        p=$(command -v "$c" 2>/dev/null || true); [[ -n "$p" && -x "$p" ]] || continue
        "$p" -c 'import os, sys, sysconfig; sys.exit(0 if sys.version_info >= (3, 12) and os.path.exists(os.path.join(sysconfig.get_paths()["include"], "Python.h")) else 1)' 2>/dev/null && { VPY=$p; break; }
      done
      [[ -n "$VPY" ]] || { log "no python 3.12+ with development headers (Python.h) found; cannot build the Python binding"; VPY="$PY"; }
      log "venv base python: $VPY"
      { { [[ -x "$VENV/bin/python" ]] || "$VPY" -m venv "$VENV"; } \
        && "$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$PKG_DIR/requirements.txt" \
        && "$VENV/bin/python" -m pip install --disable-pip-version-check -q --no-build-isolation --no-deps "$PSRC/python"; } >>"$LOG" 2>&1 || true
    fi
  fi
  if [[ -x "$VENV/bin/python" ]] && "$VENV/bin/python" -c 'import lex, numpy' 2>/dev/null; then
    PYB="$VENV/bin/python"; log "lex1d Python binding: $("$PYB" -c 'import importlib.metadata as m, numpy; print(m.version("lex1d"), "numpy", numpy.__version__)')"
    PYPIN=$("$PYB" - "$PKG_DIR/requirements.txt" <<'PYEOF'
import sys, importlib.metadata as m
pins = [l.split("#")[0].strip() for l in open(sys.argv[1])]
for name, ver in (p.split("==") for p in pins if p):
    try:
        got = m.version(name)
    except m.PackageNotFoundError:
        got = "missing"
    if got != ver:
        print("%s pinned %s, found %s" % (name, ver, got))
v = sys.version_info
if (v.major, v.minor) != (3, 13):
    print("Python %d.%d.%d; GOLD used 3.13.18" % (v.major, v.minor, v.micro))
PYEOF
)
    if [[ -n "$PYPIN" ]]; then log "WARNING: .venv differs from GOLD (pinned packages: bash run/setup.sh): $(echo "$PYPIN" | paste -sd ';' -)"
    else log ".venv packages at the GOLD pins (requirements.txt)"; fi
  else log "WARNING: lex1d Python module not available; Python binding rows skipped"; fi
fi

# ---- data ----
# simulation/input/ (or SIM_DIR) must hold the 12 files. If the default folder is empty, data/generate.py
# writes them (run from simulation/, since it writes to input/ in its working directory), then every file
# is checked against data/shasum.txt. A mismatch is a warning, not a stop: the run goes on, but its
# results will not be bit-identical to results/gold/.
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
if [[ $SMOKE == 1 ]]; then VDS="gaussian_continuous,lognormal_continuous,triangular_discrete,spike_uniform_discrete"
elif [[ $MODE == bindings ]]; then VDS="gaussian_continuous"
else VDS="${DATASETS:-}"; fi
INPUT_CHECK="all checked files match data/shasum.txt"
if ! LEX_PREPARED_DIR="$WORK/inputs" "$PY" "$SCRIPT_DIR/data.py" verify "$INPUT" ${VDS:+"$VDS"} 2>&1 | tee -a "$LOG"; then
  INPUT_CHECK="MISMATCH against data/shasum.txt: results will not be bit-identical to results/gold/"
  log "WARNING: a data file does not match data/shasum.txt (see above). Continuing, but the results will not be"
  log "bit-identical to results/gold/. Files generated with another NumPy version or on another platform can differ in the last digit."
fi
NEED_AUDIO=0
[[ $MODE == bindings || ",$SECTIONS," == *",audio,"* ]] && NEED_AUDIO=1
if [[ $NEED_AUDIO == 1 ]]; then
  if A=$("$PY" "$SCRIPT_DIR/data.py" find-audio); then log "audio: $A"
  else log "Stopping: audio not found. Put dharini-abhogi.txt.gz in data/audio/ (see data/audio/README.md), or pass --skip-audio."; exit 3; fi
fi

# ---- environment ----
{
  echo "session: $SESSION"
  echo "date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "script: $SCRIPT_NAME  mode: $MODE  reps: $REPS (+1 warm-up)  smoke: $SMOKE  sections: $SECTIONS  mem_limit_gb: $MEM_GB"
  echo "uname: $(uname -a)"
  echo "sleep guard: ${LEX_AWAKE:-none}"
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
    echo "hw.ncpu: $(sysctl -n hw.ncpu 2>/dev/null)  P cores: $(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null)  E cores: $(sysctl -n hw.perflevel1.physicalcpu 2>/dev/null)"
    echo "memsize: $(sysctl -n hw.memsize 2>/dev/null)"
    echo "macOS: $(sw_vers -productVersion 2>/dev/null) ($(sw_vers -buildVersion 2>/dev/null))"
    echo "power: $(pmset -g batt 2>/dev/null | head -1)"
    echo "memory pressure at start: $(memory_pressure 2>/dev/null | tail -1)"
    echo "time: /usr/bin/time -l"
  else
    echo "os: $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}")"
    echo "cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"
    echo "nproc: $(nproc)"
    echo "mem: $(grep -E 'MemTotal|MemAvailable' /proc/meminfo | tr -s ' ' | tr '\n' ' ')"
    echo "time: /usr/bin/time -v"
  fi
  echo "cxx: $(command -v "$CXX_BIN"): $("$CXX_BIN" --version 2>&1 | head -1)"
  echo "cmake: $(cmake --version 2>/dev/null | head -1 || echo none)"
  echo "build: $BUILD_HOW"
  echo "python: $PY $("$PY" -c 'import sys; print(sys.version.split()[0])')"
  if [[ -n "$RS" ]]; then
    echo "R: $RS $("$RS" --version 2>&1 | head -1)"
    echo "Ckmeans.1d.dp: $("$RS" -e 'cat(tryCatch(as.character(packageVersion("Ckmeans.1d.dp")), error=function(e) "not installed"))' 2>/dev/null | tail -1)"
    echo "Rcpp: $("$RS" -e 'cat(tryCatch(as.character(packageVersion("Rcpp")), error=function(e) "not installed"))' 2>/dev/null | tail -1)"
    echo "R pins (requirements-r.txt): $(echo "${RPIN:-}" | awk '{print $3"="$7"("$8")"}' | paste -sd ' ' -)"
  else echo "R: not used"; fi
  if [[ -n "$PYB" ]]; then echo "binding python: $PYB $("$PYB" -c 'import sys, numpy; print(sys.version.split()[0], "numpy", numpy.__version__)')"
    echo "binding pip packages: $("$PYB" - <<'PYEOF'
import importlib.metadata as m
out = []
for n in ["nanobind", "scikit-build-core", "cmake", "packaging", "pathspec", "lex1d"]:
    try:
        out.append("%s=%s" % (n, m.version(n)))
    except m.PackageNotFoundError:
        out.append("%s=missing" % n)
print(" ".join(out))
PYEOF
)"; fi
  echo "lex1d commit: $COMMIT (lex1d/ is the commit's zip, verbatim)"
  echo "$LEXCHK (manifest run/lex1d_8a691ee.sha256)"
  "$PY" - "$PKG_DIR" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
files = ["lex1d/cpp/src/" + f for f in sorted(os.listdir(os.path.join(root, "lex1d/cpp/src")))]
files += ["lex1d/cpp/include/lex/lex.hpp", "lex1d/r/src/lex1d_r.cpp", "lex1d/r/R/ckmeans.R",
          "lex1d/python/src/_core.cpp", "lex1d/python/src/lex/__init__.py", "bench/fit.cpp",
          "run/run.py", "run/check_lex1d.py", "run/fit_r.R", "run/fit_py.py", "run/data.py", "run/common.sh"]
for f in files:
    print("sha256 %s  %s" % (hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest(), f))
PYEOF
  if [[ "$MODE" == refine ]]; then
  "$PY" - "$PKG_DIR" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
for f in ["bench/refine_fit.cpp", "bench/refine_ltr.cpp", "bench/refine_ltr.hpp", "run/run4.sh"]:
    print("sha256 %s  %s" % (hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest(), f))
PYEOF
  fi
  echo "input: $INPUT"
  echo "input check: $INPUT_CHECK"
} > "$OUT_DIR/env_$SESSION.txt"
cp "$OUT_DIR/env_$SESSION.txt" "$OUT_DIR/env.txt"
log "environment written to env.txt (and env_$SESSION.txt)"

# ---- run ----
ARGS=(--mode "$MODE" --input-dir "$INPUT" --out "$OUT_DIR" --workdir "$WORK" --fit "$FIT" --session "$SESSION"
      --reps "$REPS" --mem-limit-gb "$MEM_GB" --sections "$SECTIONS")
[[ -n "$RS" ]] && ARGS+=(--rscript "$RS")
[[ $RBIND == 1 ]] && ARGS+=(--rb 1)
[[ -n "$PYB" ]] && ARGS+=(--pyb "$PYB")
[[ $SMOKE == 1 ]] && ARGS+=(--smoke)
[[ -n "$DATASETS" ]] && ARGS+=(--datasets "$DATASETS")
[[ -n "$SLICES" ]] && ARGS+=(--slices "$SLICES")
[[ -n "$KLIST" ]] && ARGS+=(--k "$KLIST")
RC=0
"$PY" "$SCRIPT_DIR/run.py" "${ARGS[@]}" 2>&1 | tee -a "$LOG" || RC=1

# ---- merge and analysis (also compares raw vs sorted if both folders exist) ----
"$PY" "$SCRIPT_DIR/analyze.py" --out "$OUT_DIR" 2>&1 | tee -a "$LOG" || log "WARNING: analysis failed (results are in cells/)"
LEXEND=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1) || RC=1
log "after the run: $LEXEND"
echo "after the run: $LEXEND" >> "$OUT_DIR/env_$SESSION.txt"
echo "end: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$OUT_DIR/env_$SESSION.txt"
EL=$(( $(date +%s) - START_TS ))
log "finished $SCRIPT_NAME (rc $RC). session time: $((EL / 3600))h $((EL % 3600 / 60))m $((EL % 60))s. Results: $OUT_DIR"
exit $RC
