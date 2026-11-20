"""Suite-wide test configuration.

``THG_TEST_SOLVER`` (for example ``hybrid`` for HiGHS, or ``glpk``) makes that
solver cobra's default for the whole session, so the solver-dependent tests
can run without a Gurobi license or be repeated on another solver.
"""

import os


def pytest_configure(config):
    solver = os.environ.get("THG_TEST_SOLVER")
    if solver:
        import cobra

        cobra.Configuration().solver = solver
