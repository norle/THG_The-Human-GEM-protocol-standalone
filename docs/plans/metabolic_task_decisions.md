# Metabolic task decisions: storage and CellfieConsensus curation

Choices for the two open section-4 items in
`metabolic_task_alignment_plan.md`, for the goal "run the Human-GEM task
tables on the models used in the pipeline". Measured 2026-10-01 with GLPK,
closed medium, on the Human-GEM tables in `tests/fixtures/memote/data/`.

## Outcome (2026-10-01)

- **Decision 1: option 1A.** The tables are stored in
  `files/metabolic_tasks/` with a generated `human_gem_names.json`. They are
  taken from Human-GEM `develop` at `2f1d3e33`, because `main`'s Full table
  has lost its first column. See that folder's README.
- **Decision 2: no local curation.** Upstream curated CellfieConsensus in
  PR #998 and commented out tasks 37 and 38. Essential and Full are the main
  set; CellfieConsensus is optional.
- **Results with the stored tables and mapping**, biomass LB relaxed:

  | Model | Essential | Full | CellfieConsensus |
  |---|---|---|---|
  | endoA baseline | 55 pass, 2 invalid | 244 pass, 9 fail, 4 invalid | 149 pass, 44 invalid |
  | endoC_final_7 | 51 pass, 6 invalid | 250 pass, 4 fail, 3 invalid | 148 pass, 2 fail, 43 invalid |

- **Open: VerifyModel fails on both endo models** (19 of 21; it passes 21 of
  21 on Human-GEM). These tasks must be infeasible: making something from
  nothing must fail. On endoC, "oxygen from water" is feasible through
  added reactions, for example the unbalanced `R08758_c`
  (`…cholestane --> …cholestan-26-al + 2 H+`) together with
  `MAR07938`/`MAR01987`. Until these leaks are fixed, Essential/Full passes
  on these models overstate what they can really do. The work plan is in
  `metabolic_task_leaks_plan.md`.

## Open decisions

Nothing below is decided yet. Nothing from this work is committed.

1. **Leaking reactions in the endo models (most important).** Find and fix
   the reactions that let VerifyModel tasks pass, or accept the leaks and
   treat Essential/Full results on these models as upper bounds. Plan:
   `metabolic_task_leaks_plan.md`.
2. **Where forced biomass is released.** Data-constrained models force
   `MAR13082` (LB > 0), so every task is infeasible under a closed medium.
   Options:
   - the caller (the pipeline's `test_tasks.py`) relaxes LB > 0 / UB < 0 on
     non-boundary reactions before running, or
   - a runner option in `run_task_suite` (for example
     `release_forced_fluxes=True`), recorded in the report.
3. **Metabolites missing from a context model: `invalid` or `failed`.**
   Today the importer reports `invalid`; RAVEN reports `failed`
   ("Could not find all inputs", `ok=false`). Most of the ~40 invalid
   CellfieConsensus tasks on endoA/endoC are this case. Switching would be an
   importer policy option.
4. **Pipeline default task table.** `examples/research/test_tasks.py`
   (pipeline) still defaults to `data/metabolicTasks_Full_thg.txt`, a stale
   local edit. Options: point the default at
   `<THG>/files/metabolic_tasks/metabolicTasks_Full.txt` with the mapping, or
   copy the folder into the pipeline.
5. **Committing.** `files/metabolic_tasks/`, the `.gitignore` whitelist and
   these plan docs are untracked in THG.
6. **Upstream issue (optional).** Report to Human-GEM that `main`'s
   `metabolicTasks_Full.txt` lost its first column in `a10375c4` and cannot
   be parsed; `develop` has the fix (`b42880e2`) but it is not released.

The analysis below is what the decisions were based on.

## What the pipeline models look like

| Model (pipeline `models/`) | IDs | Names | Notes |
|---|---|---|---|
| `endoA_251219_preprocessed_*` | `MAM…` | Human-GEM names | Biomass `MAR13082` has LB 37.5, which makes every task infeasible under a closed medium |
| `endoC_final_7`, `THG-beta2_endoB` | `MAM…` (plus `C…` IDs) | THG renamed (`L-glutamine`, …) | Matching by name fails |
| `EC_3006_1` | BiGG | BiGG | Human-GEM tables cannot work without a full BiGG mapping; out of scope here |

Results of importing the tables against each model, with the biomass LB
relaxed to 0. The name mapping is described under 1A.

| Model | Essential (57) | Full (257) | CellfieConsensus (195) |
|---|---|---|---|
| Human-GEM 2022-06-21 | 57 pass | 257 pass | 169 pass, 17 fail, 9 invalid |
| endoA baseline (no mapping) | 55 pass, 2 invalid | 242 pass, 9 fail, 6 invalid | 148 pass, 47 invalid |
| endoC_final_7 (no mapping) | 0 pass, 38 invalid | 2 pass, 161 invalid | 0 pass, 174 invalid |
| endoC_final_7 (with name mapping) | 51 pass, 6 invalid | 250 pass, 4 fail, 3 invalid | 142 pass, 10 fail, 43 invalid |

Almost every remaining invalid task on endoA/endoC references a metabolite
that was removed when the context-specific model was built, for example
`glycogenin[c]`, `ethanol[e]` or `alpha-tocopherol[e]`. These are facts about
the model, not errors in the table.

The JSON suites I converted on Human-GEM do **not** transfer to the reduced
models. The `ALLMETSIN[e]` output of Essential task GR (growth on Ham's
medium) is expanded at conversion time to 1,665 Human-GEM metabolites. On
endoA, 865 of them are missing, so GR becomes invalid even though it passes
when the table is imported against endoA directly.

## Decision 1: what to store, and where

**1A. Store the original tables plus one generated name mapping (recommended).**

```
files/metabolic_tasks/
  README.md                          source commit, sha256 of each table, how the mapping was generated
  metabolicTasks_Essential.txt       unmodified Human-GEM tables
  metabolicTasks_Full.txt
  metabolicTasks_VerifyModel.txt
  metabolicTasks_CellfieConsensus.txt
  human_gem_names.json               "name[comp]" -> MAM ID for all 8,369 Human-GEM metabolites (380 KB, no ambiguous names)
```

- Each run imports the table against the actual model with
  `--mapping human_gem_names.json`. Wildcards then expand against that model,
  and the report records the table and mapping hashes.
- One mapping covers every `MAM…` model (endoA, endoB, endoC, THG-beta2),
  whether or not the metabolites were renamed.
- The pipeline's edited `data/metabolicTasks_Full_thg.txt` is no longer
  needed. It differs from the original only in a renamed metabolite
  (`glucose 1-phosphate`), which the mapping covers.
- Cost: name resolution on every run takes a few seconds per table.
  `human_gem_names.json` must be regenerated if a newer Human-GEM release is
  adopted.

**1B. Store JSON suites converted on Human-GEM.**
- Fully pinned IDs that can be reviewed in a diff, with no name resolution at
  run time.
- Wildcard tasks break on every reduced model (see above), and the files are
  large (Essential 414 KB, Full 945 KB, Cellfie 1.9 MB).
- Only reasonable if wildcard tasks are dropped or the JSON contract gains
  unexpanded wildcards, which would be a code change.

**1C. Store a converted JSON suite per target model**
(`files/metabolic_tasks/<model>/…json`).
- Correct wildcards, fully pinned.
- One set per model version, so it goes stale with every new endoA/endoC
  build. Best kept as a run output rather than a stored input.

Where the files live:

- **THG `files/metabolic_tasks/` (recommended):** `files/` is tracked
  (27 MB, HTML via LFS) and already holds curated inputs. This becomes the
  single source of truth.
- **Pipeline `data/`:** gitignored, so it is not versioned. Fine for a local
  copy, but not as the source.
- **Both repos:** the pipeline's `test_tasks.py` takes the THG path as
  arguments (`--tasks …/files/metabolic_tasks/… --mapping …`). Nothing is
  duplicated.

## Decision 2: CellfieConsensus curation

These 16 references fail on Human-GEM itself, so the problem is in the table:

| Ref | Tasks (rows) | What it most likely is |
|---|---|---|
| `NA[c]` | 37, 38 (223, 227) | Glycogen synthesis/degradation primer: `glycogenin[c]` (MAM01996c). It is **not** Na+ |
| `NA[c]` | 181 (1140) | Optional by-product of bilirubin synthesis (bounds 0–1): unknown, can be dropped |
| `NA[r]` | 184 (1152), 187 (1166) | Released from dolichyl-phosphate-D-mannose: `dolichyl-phosphate[r]` (MAM01733r) |
| `NA[r]` | 187 (1168) | Released when the oligosaccharide moves from G00006 to asparagine: `dolichyl-diphosphate[r]` (MAM01732r) |
| `propanoyl-CoA[e]` | 167–170 | Bile acid side-chain cleavage, which is peroxisomal: `propanoyl-CoA[x]` |
| `FADH2[e]`, `NADPH[e]` | 168–170 | Cofactors put in `[e]` by mistake. The same tasks also use `ATP[e]`, `CoA[e]`, `AMP[e]`, `PPi[e]`, which resolve but are biologically wrong |

`NA` stands for "not available": the same text means different metabolites
in different tasks, even twice within task 187. The mapping file is keyed by
text, not by row, so it **cannot** fix these. Any curation needs an edited
copy of the table.

**2A. Use Essential + Full, and set CellfieConsensus aside (recommended to
start).**
- Both resolve 100% on Human-GEM and nearly 100% on endoA/endoC with the
  mapping.
- Full already covers most of Cellfie's pathways.

**2B. Curate a copy.**
- Add `metabolicTasks_CellfieConsensus_curated.txt` next to the unmodified
  original, with a changelog in the README.
- Edits to the rows above:
  - `NA[c]` → `glycogenin[c]` in 37/38,
  - drop row 1140,
  - `NA[r]` → `dolichyl-phosphate[r]` / `dolichyl-diphosphate[r]`,
  - move the `[e]` cofactors in 167–170 to their real compartments.
- Tasks 167–170 need a bile-acid compartment review rather than a rename.
  That is the only part requiring judgement.

**2C. Use CellfieConsensus with `resolved_only`.**
- Run the 186 resolvable tasks and list the 9 invalid ones as omitted in the
  suite metadata.
- No curation, but tasks 37/38 (glycogen) and 167–170 (bile acids) are lost.

## Two related findings that affect fit

1. **Forced biomass.** Data-constrained models (endoA baseline, in-vitro
   bounds) force biomass, so all tasks fail under a closed medium. Tasks
   should run on the model with forced internal fluxes released. This can be
   done either:
   - by the caller (the pipeline script relaxes LB > 0 on non-boundary
     reactions before running), or
   - by a runner option.
2. **Metabolites removed from context models.** These tasks are reported
   `invalid`, while RAVEN reports them as failed ("Could not find all
   inputs", `ok=false`). For context-specific models, `failed` is arguably
   the right reading. This would be an importer policy switch.
