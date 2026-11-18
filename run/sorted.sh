#!/usr/bin/env bash
# Full grid, every fit on the same values presorted.
# From the repo root:   bash run/sorted.sh        (run/run3.sh runs raw, sorted and bindings in turn)
# Results: ./out/sorted/   Re-running resumes.   --help lists options.
MODE=sorted
# shellcheck source=run/common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
