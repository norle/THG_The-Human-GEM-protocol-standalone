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
configs/reference.json
configs/validation.json
```

The generated templates can be run in this order:

```bash
thg-run reference configs/reference.json
thg-run validate configs/validation.json
```

`reference` is the canonical construction command. It consumes caller-owned
β1 inputs, runs β2, optionally reconstructs and merges Human Database records,
then gapfills and exports the final bundle. `final-thg` is retained only for
compatibility. `beta1` and `human-database` also consume caller-owned files from `inputs/`.
`beta2` consumes the `export-beta1` model artifact, and the `final-thg` workflow consumes
the `export-beta2` and `human-database-reconstruct` model artifacts. Those
upstream runs must exist and be complete before their downstream configs are
started. The `final-thg` workflow merges, validates, and exports those inputs as
a standalone compatibility route; it does not release the canonical,
post-gapfill THG reference model. The validation template points at an exported model file in
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
