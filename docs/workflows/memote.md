# MEMOTE and task analysis

MEMOTE and solver-backed task analysis are optional release diagnostics, not
requirements for the base package or documentation CI.

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

## Expected output and troubleshooting

Run a local diagnostic after installing the opt-in extras:

```bash
memote run --filename results/memote.html model.xml
```

Use a pinned constraint set for reproducible solver checks and keep generated
HTML outside the source tree. Solver or optimization errors are optional
environment failures; structural documentation examples remain independent of
them.
