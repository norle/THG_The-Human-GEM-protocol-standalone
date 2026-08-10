# Runnable examples

The repository includes an offline-first examples directory with configuration
templates and scripts for the maintained workflow entry points. The inputs are
deliberately small documentation fixtures; they demonstrate interfaces and
artifact flow, not research-quality human GEM reconstruction.

## Run the workflow examples

Install the core package from the repository root:

```bash
python -m pip install -e .
```

Then run the complete registered-workflow set:

```bash
./examples/run_offline_workflows.sh
```

This executes β1, β2, Human Database, Final THG, validation, and the
registered comparison workflow. Generated run directories are written under
`examples/output/`, which is ignored by Git.

Each workflow also has its own directly runnable script:

```text
examples/scripts/
├── run_beta1.sh
├── run_beta1.py
├── run_beta2.sh
├── run_beta2.py
├── run_human_database.sh
├── run_human_database.py
├── run_final_thg.sh
├── run_final_thg.py
├── run_validation.sh
├── run_validation.py
├── run_compare.sh
├── run_compare.py
└── run_api_examples.py
```

For example:

```bash
./examples/scripts/run_beta1.sh
./examples/scripts/run_validation.sh
```

The equivalent Python entry points use the workflow runner directly:

```bash
python examples/scripts/run_beta1.py
python examples/scripts/run_validation.py
```

The individual JSON templates are in `examples/configs/`:

```text
examples/configs/
├── beta1.json
├── beta2.json
├── human-database.json
├── final-thg.json
├── validation.json
└── compare.json
```

For example, to run only validation:

```bash
thg-run validate examples/configs/validation.json
thg-run status examples/output/validation --json
```

The templates resolve their input paths relative to the configuration files,
but run them from the repository root so their output paths remain predictable.

## Run the Python API recipe

The lower-level reconstruction, pathway, annotation, connectivity, balance,
and comparison APIs are demonstrated by:

```bash
python examples/scripts/run_api_examples.py
```

This writes its results under `examples/output/api/`. The [practical
quickstart](quickstart.md) explains the same operations step by step, while the
[workflow overview](workflows/index.md) explains when to use each registered
workflow.

These examples do not enable network services, credentials, MEMOTE, or
solver-backed checks. Enable those capabilities only in a configuration suited
to the model and evidence being processed.
