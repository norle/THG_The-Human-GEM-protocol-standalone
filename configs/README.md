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

The generated templates can be run in this order:

```bash
thg-run beta1 configs/beta1.json
thg-run beta2 configs/beta2.json
thg-run start configs/human-database.json
thg-run start configs/final-thg.json
thg-run validate configs/validation.json
```

`beta1` and `human-database` consume caller-owned files from `inputs/`.
`beta2` consumes the `beta1-export` model artifact, and `final-thg` consumes
the `beta2-export` and `human-database-reconstruct` model artifacts. Those
upstream runs must exist and be complete before their downstream configs are
started. The validation template points at an exported model file in
`inputs/models/`; populate that caller-owned path with the model you want to
validate before starting the validation run.

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
