# Development

Run the default test set with:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

Run linting with:

```bash
ruff check src tests
```

The supported Python range is `>=3.10,<3.13`; CI covers Python 3.10, 3.11,
and 3.12. The complete release gate is documented in
[Release validation](release-validation.md).

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
