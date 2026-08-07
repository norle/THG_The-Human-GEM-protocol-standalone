# Development and releases

Install development and documentation dependencies with:

```bash
python -m pip install -e '.[docs,dev]'
```

Run focused tests with `pytest tests/docs` and the relevant unit/integration
groups. Build documentation with `mkdocs build --strict`; generated API pages
must remain aligned with the inventories. Keep optional solver, MEMOTE,
database, cell-specific, and figures tests isolated by their markers.

Before release, run the full test suite, build a distribution, verify the
installed wheel and console scripts, and record dependency versions. Documentation
changes should update canonical links and compatibility routes deliberately;
plans and historical evidence are excluded from the published site.
