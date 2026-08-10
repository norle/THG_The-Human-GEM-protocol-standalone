# THG workflow configurations

This directory contains user-authored workflow run specifications. Configs are
reproducibility artifacts and are suitable for version control; unlike local
inputs and generated runs, they should not be globally ignored by Git.

Recommended names include:

```text
configs/beta1.json
configs/beta2.json
configs/human-database.json
configs/final-thg.json
configs/validation.json
```

A normal invocation looks like:

```bash
thg-run beta1 configs/beta1.json
```

Filesystem paths declared inside a config are resolved relative to the config
file. For example, a config in `configs/` can refer to
`../inputs/models/human1.xml` and write its generated run to
`../runs/beta1`.

The intended workspace relationship is:

```text
inputs/  → source material
configs/ → instructions describing a run
runs/    → generated execution state
```
