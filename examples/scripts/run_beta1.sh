#!/usr/bin/env bash
set -euo pipefail

example_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repository_root="$(cd "${example_root}/.." && pwd)"
cd "${repository_root}"

if command -v thg-run >/dev/null 2>&1; then
    runner=(thg-run)
else
    runner=(python -m thg_protocol.workflow.cli)
fi

exec "${runner[@]}" beta1 examples/configs/beta1.json
