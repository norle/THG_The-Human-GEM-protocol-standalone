# Tests

The maintained tests in this directory exercise the installed
`thg_protocol` package. Characterization and compatibility tests also cover
selected legacy `functions.*` entry points while those source-checkout
wrappers remain supported.

Run the central suite from the repository root after installing the package's
development extra:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

Historical suites under `test_algorithms/` are archived and are not part of
the central pytest collection. New tests should import `thg_protocol`; tests
that import `functions.*` must explicitly verify a documented compatibility
contract.
