#!/usr/bin/env bash
set -euo pipefail

# Keep relative output paths and the documented fixture paths stable.
example_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${example_root}/.." && pwd)"
cd "${repository_root}"

if command -v thg-run >/dev/null 2>&1; then
    runner=(thg-run)
else
    runner=(python -m thg_protocol.workflow.cli)
fi

"${runner[@]}" beta1 examples/configs/beta1.json
"${runner[@]}" beta2 examples/configs/beta2.json
"${runner[@]}" start examples/configs/human-database.json
"${runner[@]}" start examples/configs/final-thg.json
"${runner[@]}" validate examples/configs/validation.json
"${runner[@]}" compare examples/configs/compare.json

echo "Offline workflow examples completed under examples/output/."
