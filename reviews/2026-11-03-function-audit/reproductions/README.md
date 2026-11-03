These scripts demonstrate the **current defects**. Their assertions expect the wrong behavior and should be replaced by assertions for correct behavior when implementing fixes. They change only in-memory models or temporary files, and do not run entire notebooks or live services.

Run from the repository root with the package's dependencies and an available solver:

```bash
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-audit-core-repro.py
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-gapfill-negative-e2e.py
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-audit-annotations-repro.py
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-audit-workflow-repro.py
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-audit-notebook-repro.py
PYTHONPATH=src python reviews/2026-11-03-function-audit/reproductions/thg-audit-additional-repro.py
```

The core script checks findings 1, 7–9, 15 and 19. The separate gap-fill script exercises finding 9 through the public API. Annotation checks cover 2–6, 10, 11 and 13; workflow checks cover 12 and 14; notebook checks cover 16 and 17; additional checks cover 18 and 20. Numbering in individual scripts and slice reports may predate the consolidated report.

`reproduction-results.log` records execution of these exact copied scripts. `../javascript-syntax-check.log` records syntax checks of five extracted scripts; those checks do not exercise a browser or validate runtime dependencies.
