# Dependency Compatibility Matrix

This is the initial compatibility inventory requested by the refactoring plan.
It describes the package metadata currently in the working tree; it is not a
lock file and still requires maintainer approval before becoming a release
constraint set.

| Area | Supported/current value | Source | Verification status |
| --- | --- | --- | --- |
| Python | `>=3.10,<3.13` | `pyproject.toml` | CI matrix configured for 3.10, 3.11, and 3.12 |
| Base model stack | COBRA `>=0.26`, NumPy, pandas, SciPy, NetworkX, libSBML, Requests, tqdm | `pyproject.toml` | Offline tests run on Python 3.12.9 |
| Development | Black, build, pytest, pytest-cov, Ruff | `.[dev]` | Installed and used locally |
| Solver workflows | PuLP `>=2.7`, swiglpk | `.[solver]` | Opt-in; not part of default test selection |
| Memote workflows | Memote | `.[memote]` | Opt-in; not part of default test selection |
| Cell-specific workflows | pathos, troppo | `.[cell-specific]` | Opt-in; compatibility not yet characterized |
| Documentation | MkDocs, MkDocs Material | `.[docs]` | Opt-in; `mkdocs.yml` is configured |

The default CI/test contract is offline, non-slow, non-solver, non-Gurobi, and
non-memote tests. Exact transitive versions should be captured in a supported
constraints or lock file before a release.
