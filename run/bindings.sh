#!/usr/bin/env bash
# Binding overhead: C++ driver vs lex1d R and Python bindings (gaussian slice 7 + audio, k = 8, 64, 512, M = 4096).
# From the repo root:   bash run/bindings.sh        (run/run3.sh runs raw, sorted and bindings in turn)
# Results: ./out/bindings/   Re-running resumes.   --help lists options.
MODE=bindings
# shellcheck source=run/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
