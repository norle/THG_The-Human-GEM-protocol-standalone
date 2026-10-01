# Human-GEM metabolic task tables

RAVEN task tables from [Human-GEM](https://github.com/SysBioChalmers/Human-GEM),
`data/metabolicTasks/`. The tables are byte-identical copies, with no local
edits.

- Source commit: `2f1d3e33ce591b357accc08d85aebc27bdcf4244` (branch `develop`, 2026-09-29)
- Downloaded: 2026-10-01

| File | sha256 |
|---|---|
| `metabolicTasks_Essential.txt` | `d0c58503fc44d1eb49ea1b89f4cc90930a06bcd2c3972083c0986cfb126a0f18` |
| `metabolicTasks_Full.txt` | `75f338da2635bf8cd0f77d319f4880abb2a3fbbacc2217806940b79424108ad9` |
| `metabolicTasks_VerifyModel.txt` | `17409a25af172813647370557814879446feaed0236e4595a25180abe0e9faed` |
| `metabolicTasks_CellfieConsensus.txt` | `d3f746c29367e485dad2744252dc97645167fa267678a50ab8e80e244041f4a5` |
| `human_gem_names.json` | `f12d0918055f69b284236d1b462119d154cb9ed4eb8a19f9bb481d5f0737b137` |

## Why `develop` and not the release on `main`

- **`main` is broken.** Commit `a10375c4` ("chore: minor format edits",
  2026-03-20) deleted the empty first column of `metabolicTasks_Full.txt`.
  RAVEN treats a row with a non-empty first cell as a comment, so on `main`
  every task-start row of Full is dropped. Neither RAVEN nor
  `thg_protocol.raven_tasks` can use that file.
- **`develop` has the column back.** It was restored in `b42880e2`
  (2026-09-22).
- **The other three tables are identical** on `main` and `develop`.
- **Upstream curation is included:**
  - CellfieConsensus curation (PR #998). Tasks 37 and 38 are commented out
    upstream because of `NA[c]`.
  - The `GAP` → `D-glyceraldehyde 3-phosphate` rename in Essential.
  - The `heneicosanoic acid` fix in Full.

## Name mapping

`human_gem_names.json` maps every Human-GEM `name[comp]` (8,374 entries, none
ambiguous) to its `MAM…` ID, at the same commit. It lets the tables resolve
on models that keep Human-GEM's IDs but renamed metabolites, such as THG,
endoB and endoC. On models that keep Human-GEM's names (endoA), it changes
nothing. Regenerate it whenever the tables are updated:

```bash
curl -O https://raw.githubusercontent.com/SysBioChalmers/Human-GEM/<commit>/model/Human-GEM.yml
python make_name_mapping.py Human-GEM.yml <commit> > human_gem_names.json
```

## Use

THG workflow config:

```yaml
task_suite: files/metabolic_tasks/metabolicTasks_Full.txt
task_mapping: files/metabolic_tasks/human_gem_names.json
```

Pipeline:

```bash
python examples/research/test_tasks.py <model> \
  <THG>/files/metabolic_tasks/metabolicTasks_Full.txt \
  --mapping <THG>/files/metabolic_tasks/human_gem_names.json
```

The tables are imported against the model at run time, so `ALLMETS` and
`ALLMETSIN` expand to that model's metabolites. A JSON suite converted on
one model does not transfer to a smaller model.
