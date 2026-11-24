"""Run a reference build with pinned native Gurobi settings.

Usage: python publication/ws1/run_build.py CONFIG   (never uses solver 'auto')

The entry point is guarded: coverage workers re-import this module.
"""
import sys

import cobra
import gurobipy

from thg_protocol.workflow.cli import main


def pin_solver() -> None:
    cobra.Configuration().solver = "gurobi"
    cobra.Configuration().processes = 1
    cobra.Configuration().tolerance = 1e-7
    for key, value in {"Threads": 2, "FeasibilityTol": 1e-7,
                       "OptimalityTol": 1e-7, "IntFeasTol": 1e-7}.items():
        gurobipy.setParam(key, value)


if __name__ == "__main__":
    pin_solver()
    sys.argv = ["thg-run", "reference", sys.argv[1], "-v"]
    raise SystemExit(main())
