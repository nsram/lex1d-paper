#!/usr/bin/env bash
# Fifth run (exploratory, not GOLD): precision grouping before LEX on the audio.
# Each audio value is rounded to 5 significant digits; each run of equal rounded values in the sorted data
# becomes one atom carrying the count and the mean of its TRUE values, and lex_hybrid (M = 4096) runs on
# the atoms with weights. A bin never splits an atom, and the SSE is still exact on the real values:
# weighted SSE + within-atom sum of squares, checked against the SSE recomputed on the raw values.
# Compared with the raw variant (lex_hybrid on all 7.3M distinct values, as GOLD) at k = 64, 256, 512:
# one warm-up round (public-API and grouping checks) and 3 timed rounds, variant order alternating.
# Stops with FAIL if the raw SSE differs from GOLD lex_hybrid M=4096 or any SSE check differs by > 1e-12.
# From the repo root:   bash run/run5.sh        (about 2 minutes, most of it the raw variant)
# Results: ./out/precgroup/ (summary.md, runs.csv, env.txt, run.log)   --help lists options.
# Same setup as run/common.sh: python3 lookup, lex1d byte-identity check, cmake build (direct compiler
# fallback), the 6 C++ test suites, audio prepared by run/data.py into work/full/inputs/, env capture.
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR=$D
PKG_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMMIT=8a691ee005b657f985ffa299c57542b79570b08c
REPS=3; SKIP_TESTS=0; OUT_DIR=""

usage() {
  cat <<USAGE
Usage: bash run/run5.sh [SIM_DIR] [options]        (from the repo root)

SIM_DIR is accepted for symmetry with run4.sh and ignored: run 5 uses only the audio
(data/audio/dharini-abhogi.txt.gz).
Options:
  --reps N          timed rounds after the warm-up round (default 3)
  --skip-tests      do not run the 6 C++ test suites
  --out DIR         default ./out/precgroup
  -h, --help
USAGE
}
SIM_ARG=""
if [[ $# -gt 0 && "$1" != -* ]]; then SIM_ARG=$1; shift; fi
ORIG_ARGS=("$@"); [[ -n "$SIM_ARG" ]] && ORIG_ARGS=("$SIM_ARG" "$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reps) REPS=$2; shift;;
    --skip-tests) SKIP_TESTS=1;;
    --out) OUT_DIR=$2; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown option: $1" >&2; usage; exit 2;;
  esac
  shift
done

# Keep the machine awake (re-exec once), as run4.sh / common.sh.
if [[ "$(uname)" == "Darwin" && -z "${LEX_AWAKE:-}" ]] && command -v caffeinate >/dev/null; then
  export LEX_AWAKE="caffeinate -dims (run5.sh)"
  exec caffeinate -dims bash "$SCRIPT_DIR/run5.sh" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
fi
if [[ "$(uname)" == "Linux" && -z "${LEX_AWAKE:-}" ]]; then
  if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=probe true >/dev/null 2>&1; then
    export LEX_AWAKE="systemd-inhibit (run5.sh)"
    exec systemd-inhibit --what=sleep:idle --why="LEX precision grouping" bash "$SCRIPT_DIR/run5.sh" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
  fi
  export LEX_AWAKE="none (systemd-inhibit unavailable)"
  echo "WARNING: systemd-inhibit is not available here; nothing stops the machine from sleeping. Disable suspend for the run." >&2
fi

[[ -z "$OUT_DIR" ]] && OUT_DIR="$PKG_DIR/out/precgroup"
WORK="$PKG_DIR/work/full"
mkdir -p "$OUT_DIR" "$WORK"
OUT_DIR=$(cd "$OUT_DIR" && pwd)
LOG="$OUT_DIR/run.log"
SESSION="$(date '+%Y%m%dT%H%M%S')-$$"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" | tee -a "$LOG"; }
have() { command -v "$1" >/dev/null 2>&1; }
START_TS=$(date +%s)
log "==== run5.sh start (session $SESSION) ===="
log "args: ${ORIG_ARGS[*]:-}"
log "repo: $PKG_DIR  out: $OUT_DIR  reps: $REPS (+1 warm-up)"

# ---- python3 (standard library only) ----
PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/bin/python3; do
  p=$(command -v "$c" 2>/dev/null || true)
  [[ -n "$p" && -x "$p" ]] || continue
  "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null && { PY=$p; break; }
done
[[ -n "$PY" ]] || { log "No python3 (3.8+) found. Install it (macOS: brew install python; Ubuntu: sudo apt install python3) and re-run."; exit 1; }
log "python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"
# ---- lex1d must be byte-identical to commit 8a691ee ----
if ! LEXCHK=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1); then
  echo "$LEXCHK" | tee -a "$LOG"
  log "Stopping: lex1d/ is not byte-identical to commit $COMMIT (see above). Restore it (git checkout -- lex1d). Nothing was built or measured."; exit 1
fi
log "$LEXCHK"

# ---- C++ build (frozen lex1d + bench/precgroup_fit.cpp) and the 6 test suites ----
CXX_BIN=${CXX:-}
if [[ -z "$CXX_BIN" ]]; then for c in c++ clang++ g++; do have $c && { CXX_BIN=$c; break; }; done; fi
[[ -n "$CXX_BIN" ]] || { log "no C++ compiler. On macOS run: xcode-select --install; on Ubuntu: sudo apt install build-essential cmake; then re-run."; exit 1; }
BUILD="$PKG_DIR/build"
FIT="$BUILD/precgroup_fit"
log "building lex1d ($COMMIT) and bench/precgroup_fit.cpp in build/"
if have cmake && cmake -S "$PKG_DIR/bench" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$(command -v "$CXX_BIN")" >>"$LOG" 2>&1; then
  BUILD_HOW="cmake Release (lex_strict_fp: -ffp-contract=off)"
  cmake --build "$BUILD" -j 8 >>"$LOG" 2>&1 || { log "build failed; see run.log"; exit 1; }
  cmake --build "$BUILD" -j 8 --target precgroup_fit >>"$LOG" 2>&1 || { log "precgroup_fit build failed; see run.log"; exit 1; }
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
  "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/bench/precgroup_fit.cpp" -o "$FIT" >>"$LOG" 2>&1 || { log "precgroup_fit build failed; see run.log"; exit 1; }
  if [[ $SKIP_TESTS == 0 ]]; then
    for t in edge exact quality coarse weighted ties; do
      "$CXX_BIN" "${FLAGS[@]}" "${SRCS[@]}" "$PKG_DIR/lex1d/cpp/tests/test_$t.cpp" -o "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test build failed: $t"; exit 1; }
      "$BUILD/test_$t" >>"$LOG" 2>&1 || { log "test FAILED: $t; stopping"; exit 1; }
    done
    log "6/6 test suites passed (direct build)"
  fi
fi
[[ -x "$FIT" ]] || { log "driver not built"; exit 1; }

# ---- data ----
if A=$("$PY" "$SCRIPT_DIR/data.py" find-audio); then log "audio: $A"
else log "Stopping: audio not found. Put dharini-abhogi.txt.gz in data/audio/ (see data/audio/README.md)."; exit 3; fi

# ---- environment ----
{
  echo "session: $SESSION"
  echo "date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "script: run5.sh  reps: $REPS (+1 warm-up)  M: 4096  k: 64,256,512  variants: raw, sig5"
  echo "uname: $(uname -a)"
  echo "sleep guard: ${LEX_AWAKE:-none}"
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
    echo "hw.ncpu: $(sysctl -n hw.ncpu 2>/dev/null)  P cores: $(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null)  E cores: $(sysctl -n hw.perflevel1.physicalcpu 2>/dev/null)"
    echo "memsize: $(sysctl -n hw.memsize 2>/dev/null)"
    echo "macOS: $(sw_vers -productVersion 2>/dev/null) ($(sw_vers -buildVersion 2>/dev/null))"
    echo "power: $(pmset -g batt 2>/dev/null | head -1)"
    echo "memory pressure at start: $(memory_pressure 2>/dev/null | tail -1)"
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
  "$PY" - "$PKG_DIR" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
files = ["lex1d/cpp/src/" + f for f in sorted(os.listdir(os.path.join(root, "lex1d/cpp/src")))]
files += ["lex1d/cpp/include/lex/lex.hpp", "bench/precgroup_fit.cpp", "bench/CMakeLists.txt",
          "run/run5.sh", "run/precgroup.py", "run/data.py", "run/check_lex1d.py", "results/gold/raw/results.csv"]
for f in files:
    print("sha256 %s  %s" % (hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest(), f))
PYEOF
  echo "audio: $A"
} > "$OUT_DIR/env_$SESSION.txt"
cp "$OUT_DIR/env_$SESSION.txt" "$OUT_DIR/env.txt"
log "environment written to env.txt (and env_$SESSION.txt)"

# ---- run + analysis (summary.md) ----
RC=0
"$PY" "$SCRIPT_DIR/precgroup.py" --fit "$FIT" --workdir "$WORK" --out "$OUT_DIR" --session "$SESSION" --reps "$REPS" 2>&1 | tee -a "$LOG" || RC=1
LEXEND=$("$PY" "$SCRIPT_DIR/check_lex1d.py" 2>&1) || RC=1
log "after the run: $LEXEND"
echo "after the run: $LEXEND" >> "$OUT_DIR/env_$SESSION.txt"
echo "end: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$OUT_DIR/env_$SESSION.txt"
cp "$OUT_DIR/env_$SESSION.txt" "$OUT_DIR/env.txt"
EL=$(( $(date +%s) - START_TS ))
if [[ $RC == 0 ]]; then log "finished run5.sh: PASS. session time: $((EL / 60))m $((EL % 60))s. Results: $OUT_DIR/summary.md"
else log "finished run5.sh: FAIL (see above and $OUT_DIR/summary.md). session time: $((EL / 60))m $((EL % 60))s"; fi
exit $RC
