# Tests

The maintained tests in this directory exercise the installed
`thg_protocol` package. Characterization tests use small, relocated fixtures
where package behavior needs representative historical inputs.

Run the central suite from the repository root after installing the package's
development extra:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

The former checkout-only algorithm suites have been removed. New tests should
import `thg_protocol` and keep deterministic fixtures under `tests/fixtures`.
