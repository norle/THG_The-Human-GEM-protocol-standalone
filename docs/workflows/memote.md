# MEMOTE and task analysis

MEMOTE and task-analysis runs require the optional `memote` extra and, for
some checks, a configured solver:

```bash
python -m pip install 'thg-protocol[memote,solver]'
```

These checks are opt-in CI workflows. Default tests must remain offline,
solver-independent, and independent of full-size model files.

The small task input files formerly held under the checkout-only MEMOTE
directory now live in `tests/fixtures/memote/`. They are fixtures only; the
removed task implementation is not part of the package or release gate.
