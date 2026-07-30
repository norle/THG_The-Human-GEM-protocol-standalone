# MEMOTE and task analysis

MEMOTE and task-analysis runs require the optional `memote` extra and, for
some checks, a configured solver:

```bash
python -m pip install 'thg-protocol[memote,solver]'
```

These checks are opt-in CI workflows. Default tests must remain offline,
solver-independent, and independent of full-size model files.
