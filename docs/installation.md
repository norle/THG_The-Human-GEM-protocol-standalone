# Installation

The package migration uses a `src/` layout and Python `>=3.10,<3.13`.

For development:

```bash
python -m pip install -e ".[dev]"
```

Optional dependency groups are defined for docs, solvers, memote, and
cell-specific workflows.

The extras can be installed independently when needed:

```bash
python -m pip install 'thg-protocol[solver]'
python -m pip install 'thg-protocol[memote]'
python -m pip install 'thg-protocol[cell-specific]'
python -m pip install 'thg-protocol[docs]'
```

The installed `thg-gapfill`, `thg-pathway`, and `thg-compare` commands expose
the stable workflows documented in [Usage](usage.md). Their `--help` output is
safe to run without model files or optional solver/network dependencies.
