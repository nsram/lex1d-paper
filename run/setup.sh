#!/usr/bin/env bash
# One-time setup: system tools, pinned R packages (./R-lib) and pinned Python packages plus the
# lex1d Python module (./.venv). Run it from the repo root:
#   bash run/setup.sh            (then: bash run/run3.sh)
# Options: --no-r  --no-python  -h
# Re-running is safe: anything already at its pinned version is skipped.
# Pins: requirements-r.txt and requirements.txt at the repo root.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PKG_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$PKG_DIR"
GOLD_R=4.6.2        # GOLD env.txt: Rscript (R) version 4.6.2
GOLD_PY=3.13.18     # GOLD env.txt: binding python 3.13.18
RLIB="$PKG_DIR/R-lib"
VENV="$PKG_DIR/.venv"
REQ_R="$PKG_DIR/requirements-r.txt"
REQ_PY="$PKG_DIR/requirements.txt"
DO_R=1; DO_PY=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-r) DO_R=0;;
    --no-python) DO_PY=0;;
    -h|--help) sed -n '2,7p' "$0"; exit 0;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2;;
  esac
  shift
done

say() { echo "[setup] $*"; }
have() { command -v "$1" >/dev/null 2>&1; }
OS=$(uname)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/lex_setup.XXXXXX"); trap 'rm -rf "$TMP"' EXIT
[[ "$OS" == "Darwin" ]] && export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

find_rscript() {
  local c p
  for c in Rscript /opt/homebrew/bin/Rscript /usr/local/bin/Rscript /Library/Frameworks/R.framework/Resources/bin/Rscript; do
    p=$(command -v "$c" 2>/dev/null || true); [[ -n "$p" && -x "$p" ]] && { echo "$p"; return 0; }
  done
  return 1
}
r_has_headers() {  # R.h is there, so packages can be compiled (Ubuntu: r-base-dev)
  "$1" -e 'quit(status = if (file.exists(file.path(R.home("include"), "R.h"))) 0 else 1)' >/dev/null 2>&1
}
# A python that can build the binding: 3.12+ (numpy 2.5.5), C headers (Python.h), and a venv that
# comes with pip (Ubuntu: python3-venv, python3-dev). Tried by really making a throwaway venv.
VPY=""
find_python() {
  local c p
  [[ -n "$VPY" ]] && return 0
  for c in python3.13 python3 python3.14 python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    p=$(command -v "$c" 2>/dev/null || true); [[ -n "$p" && -x "$p" ]] || continue
    "$p" -c 'import os, sys, sysconfig
sys.exit(0 if sys.version_info >= (3, 12) and os.path.exists(os.path.join(sysconfig.get_paths()["include"], "Python.h")) else 1)' \
      >/dev/null 2>&1 || continue
    rm -rf "$TMP/venvprobe"
    if "$p" -m venv "$TMP/venvprobe" >/dev/null 2>&1 && "$TMP/venvprobe/bin/python" -m pip --version >/dev/null 2>&1; then
      VPY=$p; rm -rf "$TMP/venvprobe"; return 0
    fi
  done
  return 1
}
find_cxx() { local c; for c in "${CXX:-}" c++ clang++ g++; do [[ -n "$c" ]] && have "$c" && { echo "$c"; return 0; }; done; return 1; }

# ---------------------------------------------------------------- system tools
say "repo: $PKG_DIR  ($OS)"
if [[ "$OS" == "Darwin" ]]; then
  if ! xcode-select -p >/dev/null 2>&1; then
    say "Xcode command line tools are missing (they give the C++ compiler). Run:"
    echo "    xcode-select --install"
    say "then run 'bash run/setup.sh' again."; exit 1
  fi
  say "Xcode command line tools: $(xcode-select -p)"
  BREW=()
  have cmake || BREW+=(cmake)
  [[ $DO_R == 1 ]] && { find_rscript >/dev/null || BREW+=(r); }
  [[ $DO_PY == 1 ]] && { find_python >/dev/null || BREW+=(python); }
  if [[ ${#BREW[@]} -gt 0 ]]; then
    if ! have brew; then
      say "Homebrew is needed to install: ${BREW[*]}. Install it from https://brew.sh, then run 'bash run/setup.sh' again."; exit 1
    fi
    say "running: brew install ${BREW[*]}"
    brew install "${BREW[@]}"
  fi
elif [[ "$OS" == "Linux" ]]; then
  APT=()
  find_cxx >/dev/null || APT+=(build-essential)
  have cmake || APT+=(cmake)
  /usr/bin/time -v true >/dev/null 2>&1 || APT+=(time)
  if [[ $DO_R == 1 ]]; then
    if RS0=$(find_rscript); then r_has_headers "$RS0" || APT+=(r-base-dev); else APT+=(r-base r-base-dev); fi
  fi
  if [[ $DO_PY == 1 ]]; then find_python >/dev/null || APT+=(python3-venv python3-dev); fi
  if [[ ${#APT[@]} -gt 0 ]]; then
    if ! have apt-get; then
      say "missing system packages (Ubuntu names): ${APT[*]}. This is not an apt system; install the equivalents and run again."; exit 1
    fi
    SUDO=(); [[ $(id -u) -ne 0 ]] && SUDO=(sudo)
    say "running: ${SUDO[*]} apt install ${APT[*]}"
    if [[ " ${APT[*]} " == *" r-base "* ]]; then
      say "(Ubuntu's own r-base can be older than GOLD's R $GOLD_R. For a current R, add CRAN's Ubuntu"
      say " repository first: https://cran.r-project.org/bin/linux/ubuntu/ , then run this again.)"
    fi
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y "${APT[@]}"
  fi
else
  say "unsupported OS: $OS. On Windows, use WSL2 with Ubuntu (see README)."; exit 1
fi
CXXP=$(find_cxx) || { say "no C++ compiler found"; exit 1; }
say "C++ compiler: $(command -v "$CXXP")"

FAIL=0
ROWS=()
row() { ROWS+=("$(printf '%-20s %-10s %-12s %s' "$1" "$2" "$3" "$4")"); }
mm() { echo "$1" | cut -d. -f1,2; }

# ---------------------------------------------------------------- R packages -> ./R-lib
if [[ $DO_R == 1 ]]; then
  RS=$(find_rscript) || { say "R not found after install; install R and run again"; exit 1; }
  RV=$("$RS" -e 'cat(as.character(getRversion()))' 2>/dev/null | tail -1)
  say "R: $RS ($RV)"
  mkdir -p "$RLIB"
  export R_LIBS="$RLIB${R_LIBS:+:$R_LIBS}"
  say "R packages (pins in requirements-r.txt) -> R-lib"
  "$RS" "$SCRIPT_DIR/rpkgs.R" install "$RLIB" "$REQ_R" >"$TMP/rpkgs.log" 2>&1 || true
  cat "$TMP/rpkgs.log"
  RCHK=$(grep '^R package' "$TMP/rpkgs.log" || true)
  if [[ $(mm "$RV") == $(mm "$GOLD_R") ]]; then row "R" "$GOLD_R" "$RV" "ok (major.minor)"
  else row "R" "$GOLD_R" "$RV" "WARN: differs from GOLD (not pinnable; noted in env.txt)"; fi
  while read -r pkgline; do
    [[ -z "$pkgline" ]] && continue
    read -r _ _ p _ pin _ found st _ <<<"$pkgline"
    row "$p" "$pin" "$found" "$st"; [[ "$st" == ok ]] || FAIL=1
  done <<<"$RCHK"
  [[ -n "$RCHK" ]] || { row "R packages" "-" "-" "FAILED (see output above)"; FAIL=1; }
fi

# ---------------------------------------------------------------- Python venv -> ./.venv
if [[ $DO_PY == 1 ]]; then
  find_python || { say "no python 3.12+ with headers and venv found; install it and run again"; exit 1; }
  if [[ -x "$VENV/bin/python" ]] && ! "$VENV/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    say "existing .venv is broken or older than Python 3.12; recreating it"; rm -rf "$VENV"
  fi
  if [[ ! -x "$VENV/bin/python" ]]; then say "creating .venv from $VPY"; "$VPY" -m venv "$VENV"; fi
  PYV=$("$VENV/bin/python" -c 'import sys; print(sys.version.split()[0])')
  say "pip install -r requirements.txt (into .venv, Python $PYV)"
  "$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$REQ_PY" || { say "pip install failed"; FAIL=1; }
  if "$VENV/bin/python" -c 'import lex, importlib.metadata as m; assert m.version("lex1d") == "0.1.0"' 2>/dev/null; then
    say "lex1d Python module already in .venv"
  else
    say "building the lex1d Python module (from a copy of lex1d/cpp and lex1d/python) into .venv"
    cp -R "$PKG_DIR/lex1d/cpp" "$PKG_DIR/lex1d/python" "$TMP/"
    "$VENV/bin/python" -m pip install --disable-pip-version-check -q --no-build-isolation --no-deps "$TMP/python" \
      || { say "lex1d Python module build failed"; FAIL=1; }
  fi
  if [[ $(mm "$PYV") == $(mm "$GOLD_PY") ]]; then row "Python (.venv)" "$GOLD_PY" "$PYV" "ok (major.minor)"
  else row "Python (.venv)" "$GOLD_PY" "$PYV" "WARN: differs from GOLD (not pinnable; noted in env.txt)"; fi
  while read -r name pin found st; do
    row "$name" "$pin" "$found" "$st"; [[ "$st" == ok ]] || FAIL=1
  done < <("$VENV/bin/python" - "$REQ_PY" <<'PYEOF'
import sys, importlib.metadata as m
pins = [l.split("#")[0].strip() for l in open(sys.argv[1])]
pins = [p.split("==") for p in pins if p] + [["lex1d", "0.1.0"]]
for name, ver in pins:
    try:
        got = m.version(name)
    except m.PackageNotFoundError:
        got = "-"
    print(name, ver, got, "ok" if got == ver else ("MISSING" if got == "-" else "DIFFERS"))
PYEOF
  )
  "$VENV/bin/python" -c 'import lex, numpy' 2>/dev/null || { row "import lex, numpy" "-" "-" "FAILED"; FAIL=1; }
fi

# ---------------------------------------------------------------- summary
CMV=$(cmake --version 2>/dev/null | head -1 | awk '{print $3}'); CMV=${CMV:-none}
row "cmake (system)" "4.5.0" "$CMV" "info (optional; GOLD Mac had 4.5.0)"
echo
printf '%-20s %-10s %-12s %s\n' "component" "GOLD/pin" "installed" "status"
printf '%s\n' "------------------------------------------------------------------------"
printf '%s\n' "${ROWS[@]}"
echo
if [[ $FAIL == 0 ]]; then say "setup OK. Next: bash run/run3.sh"
else say "setup FAILED: see the rows above that are not ok."; fi
exit $FAIL
