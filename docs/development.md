# Development

Run the default test set with:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

Run linting with:

```bash
ruff check src tests
```

Before a packaging checkpoint, build and test the wheel from outside the
checkout. The CI job performs the same import and installed-CLI help smoke
tests:

```bash
python -m build
python -m pip install --no-deps dist/*.whl
thg-gapfill --help
thg-compare --help
thg-pathway --help
```
