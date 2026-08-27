# Installation

THG Protocol supports Python 3.10–3.12. Install it from a repository checkout:

```bash
git clone https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git
cd THG_The-Human-GEM-protocol-standalone
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[full]'
```

This installs the core workflows, all optional runtime capabilities, and the
four THG commands.

## Installation profiles

The `full` profile above is the simplest choice for a general-purpose
installation. It includes:

| Extra | Use it for |
| --- | --- |
| `database` | Reading historical pickle checkpoints |
| `solver` | Solver-backed workflows |
| `memote` | MEMOTE and task analysis |
| `figures` | Rendering figures |

For a smaller environment, install only the core package and add capabilities
as needed:

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

Installing `full` makes the optional tools available; it does not run MEMOTE,
contact external services, or enable a workflow stage automatically. See the
[CLI reference](reference/cli.md) and [I/O and configuration reference](reference/io-and-config.md).
