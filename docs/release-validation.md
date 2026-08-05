# Release validation

This is the repeatable release gate for the package surface. It is designed to
run from a clean checkout and keeps the default validation offline.

## Local gate

```bash
python -m pip install -c constraints/py312-glpk.txt -e ".[dev,solver]"
ruff check src tests
pytest -m "not slow and not online and not solver and not gurobi and not memote"
python -m build

# Installed commands should parse help without repository data.
thg-gapfill --help
thg-pathway --help
thg-compare --help
thg-run --help
```

The built wheel must also be installed without dependencies into a temporary
virtual environment outside the checkout. From that environment, verify the
package imports and all installed command help surfaces:

```bash
python -m venv /tmp/thg-wheel-check/venv
/tmp/thg-wheel-check/venv/bin/python -m pip install --no-deps dist/*.whl
cd /tmp
/tmp/thg-wheel-check/venv/bin/python -c \
  "import thg_protocol; import thg_protocol.services"
/tmp/thg-wheel-check/venv/bin/python -c \
  "from thg_protocol.database import reconstruct_model_from_pickle, reconstruct_model_with_services; from thg_protocol.model_build import build_model, build_model_batch"
/tmp/thg-wheel-check/venv/bin/python -c \
  "from thg_protocol.merge import merge_models, merge_models_from_paths"
/tmp/thg-wheel-check/venv/bin/python -c \
  "from thg_protocol.cell_specific import reduce_model_by_activity"
/tmp/thg-wheel-check/venv/bin/thg-gapfill --help
/tmp/thg-wheel-check/venv/bin/thg-pathway --help
/tmp/thg-wheel-check/venv/bin/thg-compare --help
/tmp/thg-wheel-check/venv/bin/thg-run --help
```

The CI package job runs the same gate on Python 3.10, 3.11, and 3.12. Solver,
slow, and online jobs are opt-in scheduled or manually dispatched jobs; they
must not change the default offline contract.

Before publishing a release, approve the versions and optional extras in the
[dependency compatibility matrix](dependency-compatibility.md), and verify
the artifact inventory and Git LFS checks described in
[data and model files](data-and-model-files.md).
