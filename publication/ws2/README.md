# WS2: correctness fixes and engineering comparison (partial)

Status: inventory only. `fixes.csv` lists every fix (refactoring doc, audit findings 1-20, β1 consolidation)
with its status; most are marked fixture-only or pending. No real-data impact measurement is done yet.
`engineering.csv` has only numbers verified on 2026-11-04 plus the 2026-11-03 audit test run; the
`pytest -m "not online"` count, legacy-checkout numbers and runtime are pending. Memory was
exhausted on the machine, so no pytest or model-loading job was run.

Next: measure R1-R5, B1 on the full Human 2.1.1 model and run legacy vs standalone functions on the same
input (separate legacy env, adjacent checkout `../THG_The-Human-GEM-protocol`).
