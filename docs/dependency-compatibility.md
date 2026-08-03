# Dependency Compatibility Matrix

This is the initial compatibility inventory requested by the refactoring plan.
The GLPK baselines are recorded in
[`constraints/`](../constraints/). They are the release-validation policy for
the declared Python 3.10–3.12 range; update the matching file and CI matrix
together when a dependency changes.

| Area | Supported/current value | Source | Verification status |
| --- | --- | --- | --- |
| Python | `>=3.10,<3.13` | `pyproject.toml` | CI matrix and per-version GLPK constraints configured for 3.10, 3.11, and 3.12 |
| Base model stack | COBRA `>=0.26`, NumPy, pandas, SciPy, NetworkX, libSBML, Requests, tqdm | `pyproject.toml`, `constraints/py310-glpk.txt`, `constraints/py311-glpk.txt`, `constraints/py312-glpk.txt` | Python 3.12 offline gate recorded; 3.10/3.11 are CI release gates |
| Development | Black, build, pytest, pytest-cov, Ruff | `.[dev]` | CI installs; local baseline pins pytest |
| Solver workflows | PuLP `>=2.7`, swiglpk | `.[solver]` | Opt-in; not part of default test selection |
| Memote workflows | Memote | `.[memote]` | Opt-in; not part of default test selection |
| Cell-specific workflows | pathos, troppo | `.[cell-specific]` | Opt-in; package boundary covered, solver-heavy runs remain optional |
| Documentation | MkDocs, MkDocs Material | `.[docs]` | Opt-in; `mkdocs.yml` is configured |

The default CI/test contract is offline, non-slow, non-solver, non-Gurobi, and
non-memote tests. Solver jobs use the matching Python 3.12 GLPK baseline; the
Python-version files pin the direct workflow stack while allowing the dev extra
to resolve its own tooling dependencies.

## Closed checkout workflows

The former checkout-specific requirements files were retired with their
source directories. Supported dependency choices are represented by the
extras above and by the installed commands.
