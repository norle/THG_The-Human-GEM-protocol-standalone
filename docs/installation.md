# Installation

THG Protocol supports Python 3.10–3.12. Install it from a repository checkout:

```bash
git clone https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git
cd THG_The-Human-GEM-protocol-standalone
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

This installs the core workflows and the `thg-gapfill`, `thg-pathway`,
`thg-compare`, and `thg-run` commands. Confirm that the command surface is
available with:

```bash
thg-gapfill --help
thg-run --help
```

## Optional capabilities

Install an extra only when your chosen workflow needs it:

| Extra | Use it for |
| --- | --- |
| `database` | Reading historical pickle checkpoints |
| `solver` | Solver-backed workflows |
| `memote` | MEMOTE and task analysis |
| `cell-specific` | Troppo-based cell-specific workflows |
| `figures` | Rendering figures |

For example:

```bash
python -m pip install -e '.[figures]'
```

The relevant [workflow](workflows/index.md) or [tool](tools/analysis.md) guide
states any additional requirements.

## Verify your installation

Check the installed entry points:

```bash
thg-run --help
thg-compare --help
thg-gapfill --help
thg-pathway --help
```

An API-level smoke test is also useful:

```bash
python -c "import thg_protocol; print(thg_protocol.__name__)"
```

The optional `memote`, solver, database, cell-specific, and figures extras are
only needed for their corresponding features. See the [CLI reference](reference/cli.md)
and [I/O and configuration reference](reference/io-and-config.md).
