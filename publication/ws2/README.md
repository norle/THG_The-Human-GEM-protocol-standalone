# WS2: correctness fixes and engineering comparison (partial)

Status: inventory only. `fixes.csv` lists every fix (refactoring doc, audit findings 1-20, β1 consolidation)
with its status; most are marked fixture-only or pending. No real-data impact measurement is done yet.
`engineering.csv` has only numbers verified on 2026-11-04 plus the 2026-11-03 audit test run; the
`pytest -m "not online"` count, legacy-checkout numbers and runtime are pending. Memory was
exhausted on the machine, so no pytest or model-loading job was run.

Next: measure R1-R5, B1 on the full Human 2.1.1 model and run legacy vs standalone functions on the same
input (separate legacy env, adjacent checkout `../THG_The-Human-GEM-protocol`).

## Numerical prerequisite verification (2026-11-09)

`pytest-offline.log`: 2,513 passed, 1,254 warnings, 350.38 s. Command:
```sh
python - <<'PYTEST' > publication/ws2/pytest-offline.log 2>&1
import cobra, pytest
cobra.Configuration().solver = "glpk"
raise SystemExit(pytest.main(["-m", "not online", "--ignore=tests/docs", "-q"]))
PYTEST
```

GLPK is the default for this offline check; solver-specific tests may select
Gurobi and require its license service. The docs tests are excluded because
MkDocs lives in the base environment. This is test evidence, not full-model
benchmark evidence. Additional focused runner/importer/publication tests after
checksum validation: 69 passed. Three measured correctness examples remain
pending; the historical inventory above is not upgraded by these tests.
