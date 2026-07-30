# Dependency Compatibility Matrix

This is the initial compatibility inventory requested by the refactoring plan.
The Python 3.12 GLPK baseline is recorded in
[`constraints/py312-glpk.txt`](../constraints/py312-glpk.txt); it is a
reproducibility baseline, not maintainer-approved release policy.

| Area | Supported/current value | Source | Verification status |
| --- | --- | --- | --- |
| Python | `>=3.10,<3.13` | `pyproject.toml` | CI matrix configured for 3.10, 3.11, and 3.12 |
| Base model stack | COBRA `>=0.26`, NumPy, pandas, SciPy, NetworkX, libSBML, Requests, tqdm | `pyproject.toml`, `constraints/py312-glpk.txt` | Offline tests run on Python 3.12 |
| Development | Black, build, pytest, pytest-cov, Ruff | `.[dev]` | CI installs; local baseline pins pytest |
| Solver workflows | PuLP `>=2.7`, swiglpk | `.[solver]` | Opt-in; not part of default test selection |
| Memote workflows | Memote | `.[memote]` | Opt-in; not part of default test selection |
| Cell-specific workflows | pathos, troppo | `.[cell-specific]` | Opt-in; compatibility not yet characterized |
| Documentation | MkDocs, MkDocs Material | `.[docs]` | Opt-in; `mkdocs.yml` is configured |

The default CI/test contract is offline, non-slow, non-solver, non-Gurobi, and
non-memote tests. Add an approved constraints file for each supported Python
and solver combination before publishing a release; the current file records
only the Python 3.12 GLPK validation baseline.
