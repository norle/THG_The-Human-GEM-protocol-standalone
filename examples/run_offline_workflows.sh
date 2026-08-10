#!/usr/bin/env bash
set -euo pipefail

# Keep relative output paths and the documented fixture paths stable.
example_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${example_root}/scripts/run_beta1.sh"
"${example_root}/scripts/run_beta2.sh"
"${example_root}/scripts/run_human_database.sh"
"${example_root}/scripts/run_final_thg.sh"
"${example_root}/scripts/run_validation.sh"
"${example_root}/scripts/run_compare.sh"

echo "Offline workflow examples completed under examples/output/."
