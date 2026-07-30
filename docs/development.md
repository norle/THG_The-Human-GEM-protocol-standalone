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

The recorded local reproducibility baseline is
`constraints/py312-glpk.txt`. It should be used for Python 3.12 solver-gate
reproduction; maintainers must approve equivalent constraints for other
supported Python versions before release. The scheduled/manual CI solver job
uses this baseline; the Python-version matrix intentionally continues to test
the declared metadata ranges.

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
