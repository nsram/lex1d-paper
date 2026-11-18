#!/usr/bin/env bash
# Full grid, every fit on the values in file order (raw input).
# From the repo root:   bash run/raw.sh        (run/run3.sh runs raw, sorted and bindings in turn)
# Results: ./out/raw/   Re-running resumes.   --help lists options.
MODE=raw
# shellcheck source=run/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
