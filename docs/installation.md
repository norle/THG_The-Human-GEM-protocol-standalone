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

This installs the core workflows and the `thg-gapfill`, `thg-pathway`, and
`thg-compare` commands. Confirm that a command is available with:

```bash
thg-gapfill --help
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

The relevant [task guide](usage.md) states any additional requirements. Users
building the package, documentation, or test environment should see
[development](development.md).
