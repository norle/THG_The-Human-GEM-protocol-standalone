# Installed commands

The package installs four commands. All have import-safe `--help` output and
require explicit input and output paths for actual work.

| Command | Python entry point | Purpose |
| --- | --- | --- |
| `thg-gapfill` | `thg_protocol.gapfill.cli:main` | Standalone COBRA JSON/SBML gap filling |
| `thg-pathway` | `thg_protocol.pathway.cli:main` | Apply a pathway configuration to a JSON model |
| `thg-compare` | `thg_protocol.analysis.compare_cli:main` | Compare model reactions and write CSV reports |
| `thg-run` | `thg_protocol.workflow.cli:main` | Start and resume a checksum-verified workflow DAG |

Run these commands from any directory after installation:

```bash
thg-gapfill --help
thg-pathway --help
thg-compare --help
thg-run --help
```

The [workflow pages](../workflows/index.md) contain CLI examples and the generated
reference pages contain the parser and error contracts.

## Recommended entry points

Use the installed commands in the workflow guides. The generated parser
references below document the exact options for each command.

## Parser APIs

::: thg_protocol.gapfill.cli
    options:
      members:
        - build_parser
        - main

::: thg_protocol.pathway.cli
    options:
      members:
        - build_parser
        - main

::: thg_protocol.analysis.compare_cli
    options:
      members:
        - build_parser
        - main

::: thg_protocol.workflow.cli
    options:
      members:
        - build_parser
        - main
