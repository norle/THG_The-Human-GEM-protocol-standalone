"""Start the β1 workflow using the Python runner API."""

import os
from pathlib import Path

from thg_protocol.workflow.runner import start


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    os.chdir(repository_root)
    run_dir = start(repository_root / "examples/configs/beta1.json")
    print(f"β1 run started: {run_dir}")


if __name__ == "__main__":
    main()
