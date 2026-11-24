"""Compare two reference builds from the same frozen inputs.

Usage: compare_replay.py RUN_X RUN_Y OUT.json

Reports, per stage, whether the recorded model checksums are identical, then
the byte checksum of the final SBML and JSON files and a semantic comparison
of the final models. Different bytes with an equal semantic comparison mean
serialization or provenance differs, not chemistry.
"""

import hashlib
import json
import sys
from pathlib import Path

from thg_protocol.analysis.compare import compare_model_files_semantically


def final_dir(run: Path) -> Path:
    attempts = sorted((run / "artifacts" / "export-reference").glob("attempt-*"))
    if not attempts:
        raise FileNotFoundError(f"{run} has no export-reference attempt")
    return attempts[-1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    run_x, run_y, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    dir_x, dir_y = final_dir(run_x), final_dir(run_y)
    sums_x = json.loads((dir_x / "reference-checksums.json").read_text())
    sums_y = json.loads((dir_y / "reference-checksums.json").read_text())
    stages = {
        stage: {
            "equal": sums_x.get(stage) == sums_y.get(stage),
            "x": sums_x.get(stage),
            "y": sums_y.get(stage),
        }
        for stage in sorted(set(sums_x) | set(sums_y))
    }
    files = {}
    for name in ("thg-reference.xml", "thg-reference.json"):
        x, y = sha256(dir_x / name), sha256(dir_y / name)
        files[name] = {"equal": x == y, "x": x, "y": y}
    semantic = compare_model_files_semantically(
        dir_x / "thg-reference.json", dir_y / "thg-reference.json"
    )
    result = {
        "run_x": str(run_x),
        "run_y": str(run_y),
        "stages_equal": sum(item["equal"] for item in stages.values()),
        "stages_total": len(stages),
        "first_differing_stage": next(
            (name for name, item in stages.items() if not item["equal"]), None
        ),
        "stages": stages,
        "files": files,
        "semantic_equal": bool(semantic.get("equal")),
        "semantic": semantic,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(
        f"stages equal {result['stages_equal']}/{result['stages_total']}; "
        f"files {[k for k, v in files.items() if v['equal']]} equal; "
        f"semantic_equal={result['semantic_equal']}"
    )


if __name__ == "__main__":
    main()
