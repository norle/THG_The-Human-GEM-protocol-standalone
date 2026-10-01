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

This installs the core workflows, including the β1 → β2 → gapfill reference
construction path, and the four THG commands.

## Optional capabilities

The base install is enough for the reference workflow and offline examples.
Install extras only when you need these capabilities:

| Extra | Use it for |
| --- | --- |
| `database` | Reading historical pickle checkpoints |
| `solver` | Solver-backed workflows |
| `memote` | MEMOTE and task analysis |
| `figures` | Rendering figures |

For example, add figure rendering with:

```bash
python -m pip install -e .
python -m pip install -e '.[figures]'
```

The relevant [workflow](workflows/index.md) or [tool](tools/analysis.md) guide
states any external services, credentials, or configuration still required.

## Optional service credentials

Service-backed workflows may require credentials such as `BIOCYC_EMAIL` and
`BIOCYC_PASSWORD`. THG reads simple, trusted dotenv files without adding a
dotenv dependency.
It checks them in this order:

1. `THG_ENV_FILE`, when set;
2. `.env` in the current working directory;
3. `.env` in the THG project/package directory.

Existing environment variables always win. Files earlier in the list also win
when the same variable appears more than once. A dotenv file supports simple
`KEY=VALUE` and `export KEY=VALUE` lines; it is not executed as shell code.
Keep it private and never commit it:

```dotenv
BIOCYC_EMAIL=you@example.com
BIOCYC_PASSWORD=your-password
```

## Verify your installation

Check the installed CLI entry points:

```bash
thg-run --help
thg-compare --help
thg-gapfill --help
thg-pathway --help
```

The `full` extra remains available as a convenience bundle for all optional
capabilities. Optional extras do not run MEMOTE, contact external services, or
enable a workflow stage automatically. See the
[CLI reference](reference/cli.md), [I/O and configuration reference](reference/io-and-config.md),
and [Python API reference](api/core.md).
